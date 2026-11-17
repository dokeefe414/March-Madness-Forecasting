"""Offline checks of nightly static site source invariants."""
from __future__ import annotations
import unittest
from datetime import datetime, timezone
from forecast.freshness import check_snapshot

CLOCK = datetime(2026, 11, 17, 6, 9, tzinfo=timezone.utc)
SAMPLE = {
    "mode": "current",
    "season": 2027,
    "sourceUrl": "https://github.com/sportsdataverse/sportsdataverse-data/releases/tag/ncaa_mbb_schedule",
    "retrievedAtUtc": "2026-11-17T06:05:00Z",
    "lastGameDate": "2026-11-16",
    "regularSeasonGames": 2,
    "teams": [
        {"teamId": "ncaa-one", "rating": 1512, "projectedRating": 1515, "wins": 2, "losses": 0, "divisionIConfirmed": True},
        {"teamId": "ncaa-two", "rating": 1488, "projectedRating": 1484, "wins": 0, "losses": 2, "divisionIConfirmed": False},
    ],
    "recentGames": [{"id": "two", "date": "2026-11-16"}, {"id": "one", "date": "2026-11-15"}],
    "pregameDiagnostics": {"evaluatedGames": 2, "brier": .2, "accuracy": .5},
}

class NightlyStatusTests(unittest.TestCase):
    def test_valid_snapshot_and_schedule(self):
        result = check_snapshot(SAMPLE, CLOCK)
        self.assertEqual(result["status"], "source-recent")
        self.assertEqual(result["acceptedGameCount"], 2)
        self.assertEqual(result["confirmedDivisionIPrograms"], 1)
        self.assertIn("1:00 a.m.", result["primaryRefresh"])

    def test_outdated_or_impossible_source_rejected(self):
        for changes in (
            {"retrievedAtUtc": "2026-11-15T06:05:00Z"},
            {"retrievedAtUtc": "2026-11-19T06:05:00Z"},
            {"lastGameDate": "2026-11-19"},
            {"regularSeasonGames": 3},
            {"recentGames": [{"date": "2026-11-14"}]},
            {"teams": [{**SAMPLE["teams"][0], "teamId": "ncaa-one"}] * 2},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                check_snapshot({**SAMPLE, **changes}, CLOCK)

    def test_source_gap_disclosed_not_falsified(self):
        status = check_snapshot({
            **SAMPLE, "lastGameDate": "2026-11-08",
            "recentGames": [{"date": "2026-11-08"}],
        }, CLOCK)
        self.assertEqual(status["status"], "source-may-be-delayed")
        self.assertGreater(status["sourceLagCalendarDaysUtc"], 2)
