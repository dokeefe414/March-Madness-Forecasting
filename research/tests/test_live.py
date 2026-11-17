"""Hermetic current-season feed tests. Never depend on a live API in CI."""
import io
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from forecast.live import final_games, build_current

CSV = """contest_id,game_date,home,away,home_score,away_score,season
100,2026-11-02,College A,College B,78,69,2027
101,2026-11-03,College B,College C,65,70,2027
102,2026-11-10,College A,College C,,,2027
100,2026-11-02,College A,College B,78,69,2027
103,2027-04-05,College A,College C,84,70,2027
104,2026-11-05,College C,College A,2,1,2026
"""


class LiveSeasonTests(unittest.TestCase):
    def test_ingest_dedupes_future_and_unplayed(self):
        rows = final_games(CSV, date(2026, 11, 16))
        self.assertEqual([r["id"] for r in rows], ["100", "101"])
        output = build_current(rows, datetime(2026, 11, 16, tzinfo=timezone.utc))
        self.assertEqual(output["season"], 2027)
        self.assertEqual(output["mode"], "current")
        self.assertEqual(output["regularSeasonGames"], 2)
        self.assertEqual(len(output["teams"]), 3)
        self.assertEqual(sum(row["wins"] for row in output["teams"]), 2)
        self.assertEqual(sum(row["losses"] for row in output["teams"]), 2)
        self.assertEqual(output["isOfficialBracket"], False)
        self.assertEqual(output["pregameDiagnostics"]["evaluatedGames"], 2)
        self.assertTrue(0 <= output["pregameDiagnostics"]["brier"] <= 1)
        self.assertTrue(0 <= output["pregameDiagnostics"]["accuracy"] <= 1)
        self.assertEqual(output["pregameDiagnostics"]["coinFlipBrier"], .25)
        self.assertIn("2026-11-16", output["retrievedAtUtc"])
        self.assertTrue(all(t["teamId"].startswith("ncaa-") for t in output["teams"]))
        self.assertTrue(all("marginPerGame" in t for t in output["teams"]))

    def test_deterministic_identity_and_missing_data(self):
        rows = final_games(CSV, date(2026, 11, 16))
        a, b = build_current(rows), build_current(rows)
        self.assertEqual([x["teamId"] for x in a["teams"]],
                         [x["teamId"] for x in b["teams"]])
        self.assertEqual([x["projectedRating"] for x in a["teams"]],
                         [x["projectedRating"] for x in b["teams"]])
        with self.assertRaisesRegex(ValueError, "no completed"):
            build_current([])

    def test_reject_malformed_source(self):
        with self.assertRaisesRegex(ValueError, "missing required"):
            final_games("home,away\nA,B")
        with self.assertRaisesRegex(ValueError, "conflicting duplicate"):
            final_games(CSV + "100,2026-11-02,College A,College B,84,69,2027\n",
                        date(2026, 11, 16))
        with self.assertRaisesRegex(ValueError, "invalid final"):
            final_games(CSV + "105,2026-11-09,College A,College B,90,90,2027\n",
                        date(2026, 11, 16))


if __name__ == "__main__":
    unittest.main()
