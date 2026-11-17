"""Hermetic proof: predictions precede sourced start; results settle later."""
import json
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from forecast.snapshot import forecast_scheduled, settle_snapshots, write_ledger, parse_time

NOW = datetime(2026, 11, 16, 14, tzinfo=timezone.utc)
RATINGS = {
    "mode": "current", "season": 2027,
    "retrievedAtUtc": "2026-11-16T13:00:00Z",
    "lastGameDate": "2026-11-15", "sourceUrl": "https://example.invalid/ncaa",
    "teams": [
        {"name": "Duke", "teamId": "duke", "rating": 1550},
        {"name": "North Carolina", "teamId": "unc", "rating": 1520},
    ],
}


def game(identifier: str, start: str, state="STATUS_SCHEDULED", away="North Carolina",
         home="Duke", neutral=False):
    return {
        "id": identifier, "date": start,
        "status": {"type": {"name": state, "completed": state == "STATUS_FINAL"}},
        "competitions": [{
            "neutralSite": neutral,
            "competitors": [
                {"homeAway": "home", "team": {"location": home, "displayName": home + " Blue Devils"}},
                {"homeAway": "away", "team": {"location": away, "displayName": away + " Tar Heels"}},
            ],
        }],
    }


class PregameAuditTests(unittest.TestCase):
    def test_future_time_and_exact_match_only(self):
        scoreboard = {"events": [
            game("ESPN-1", "2026-11-17T01:00:00Z"),
            game("ESPN-2", "2026-11-16T13:50:00Z"),
            game("ESPN-3", "2026-11-17T02:00:00Z", state="STATUS_FINAL"),
            game("ESPN-4", "2026-11-17T02:00:00Z", away="Other University"),
            game("ESPN-1", "2026-11-17T01:00:00Z"),
        ]}
        report = forecast_scheduled([scoreboard], RATINGS, NOW)
        self.assertEqual(len(report["predictions"]), 1)
        self.assertEqual(report["predictions"][0]["eventId"], "ESPN-1")
        self.assertEqual(report["predictions"][0]["scheduledEasternDate"], "2026-11-16")
        self.assertGreater(report["predictions"][0]["homeWinProbability"], .5)
        self.assertEqual(report["coverage"]["unmatchedOrAmbiguous"], 1)
        self.assertEqual(report["coverage"]["duplicateIds"], 1)
        self.assertEqual(report["coverage"]["startedOrTooClose"], 1)
        self.assertEqual(report["coverage"]["notScheduled"], 1)
        self.assertEqual(report["timeBufferMinutes"], 15)

    def test_future_ratings_rejected_and_invalid_time(self):
        wrong = {**RATINGS, "retrievedAtUtc": "2026-11-17T00:00:00Z"}
        with self.assertRaisesRegex(ValueError, "future"):
            forecast_scheduled([{"events": []}], wrong, NOW)
        with self.assertRaisesRegex(ValueError, "timezone"):
            parse_time("2026-11-16T23:00:00")

    def test_separate_settlements_are_append_only(self):
        forecast = forecast_scheduled([{"events": [game("ESPN-1", "2026-11-17T01:00:00Z")]}], RATINGS, NOW)
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            first = write_ledger(directory, forecast, [], NOW)
            self.assertEqual(first["scores"]["settledPredictions"], 0)
            snap = list((directory / "snapshots").glob("*.json"))[0]
            before = snap.read_bytes()
            final = [{
                "id": "NCAA-100", "date": "2026-11-16",
                "home": "Duke", "away": "North Carolina",
                "homeScore": 84, "awayScore": 80,
            }]
            later = NOW + timedelta(days=2)
            result = write_ledger(directory, {"predictions": []}, final, later)
            self.assertEqual(result["scores"]["settledPredictions"], 1)
            self.assertEqual(snap.read_bytes(), before)
            self.assertEqual(result["settlements"][0]["observedHome"], 1)
            self.assertGreaterEqual(result["scores"]["brier"], 0)
            # Re-running must not settle the same pregame record twice.
            again = write_ledger(directory, {"predictions": []}, final, later + timedelta(days=1))
            self.assertEqual(again["scores"]["settledPredictions"], 1)

    def test_wrong_sides_never_settle(self):
        report = forecast_scheduled([{"events": [game("ESPN-1", "2026-11-17T01:00:00Z")]}], RATINGS, NOW)
        report["snapshotId"] = "immutable"
        source = [{"id":"NCAA-1","date":"2026-11-16","home":"North Carolina",
                   "away":"Duke","homeScore":100,"awayScore":70}]
        self.assertEqual(settle_snapshots([report], source, set(), NOW + timedelta(days=2)), [])

    def test_tampering_and_time_travel_are_rejected(self):
        from forecast.audit import audit_ledger
        forecast = forecast_scheduled([{"events": [
            game("ESPN-1", "2026-11-17T01:00:00Z")]}], RATINGS, NOW)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            write_ledger(path, forecast, [], NOW)
            self.assertEqual(audit_ledger(path)["predictions"], 1)
            snap_file = next((path / "snapshots").glob("*.json"))
            saved = json.loads(snap_file.read_text())
            altered = {**saved, "generatedAtUtc": "2026-11-17T00:55:00Z"}
            snap_file.write_text(json.dumps(altered))
            with self.assertRaisesRegex(ValueError, "tip-off buffer"):
                audit_ledger(path)
            snap_file.write_text(json.dumps(saved))
            with self.assertRaisesRegex(ValueError, "tip-off buffer|newer"):
                settle_snapshots([{**saved, "generatedAtUtc": "2026-11-17T00:55:00Z"}],
                    [{"id":"100","date":"2026-11-16","home":"Duke","away":"North Carolina",
                      "homeScore":80,"awayScore":70}], set(), NOW + timedelta(days=2))
            final = [{"id":"100","date":"2026-11-16","home":"Duke","away":"North Carolina",
                      "homeScore":80,"awayScore":70}]
            write_ledger(path, {"predictions": []}, final, NOW + timedelta(days=2))
            self.assertEqual(audit_ledger(path)["settledPredictions"], 1)
            settlement_file = next((path / "settlements").glob("*.json"))
            settled = json.loads(settlement_file.read_text())
            settled["results"][0]["brier"] = 0.999999
            settlement_file.write_text(json.dumps(settled))
            with self.assertRaisesRegex(ValueError, "scoring mismatch"):
                audit_ledger(path)

    def test_empty_public_ledger_is_explicit(self):
        from forecast.audit import audit_ledger
        with tempfile.TemporaryDirectory() as folder:
            result = audit_ledger(Path(folder))
            self.assertEqual(result["status"], "verified")
            self.assertEqual(result["predictions"], 0)
            self.assertEqual(result["settledPredictions"], 0)


if __name__ == "__main__":
    unittest.main()
