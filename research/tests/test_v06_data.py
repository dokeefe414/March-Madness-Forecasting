"""Untrusted multi-source metadata, pace metrics and hypothetical field tests."""
import unittest
from datetime import datetime, timezone
from forecast.reference import canonical, parse_directory, annotate_teams
from forecast.efficiency import attach_efficiency
from forecast.selection import build_watchlist
from forecast.live import build_current, validate_supplements

DIRECTORY = """team,conference,id,season
College A,Big South,101,2027
College B,Big South,102,2027
College C,Metro,103,2027
Other team,Old conf,104,2026
"""

BOX = """contest_id,team,o_poss,d_poss,ortg,drtg,season
100,College A,75,74,104,93,2027
100,College B,74,75,93,104,2027
101,College B,72,73,105,99,2027
101,College C,73,72,99,105,2027
998,College A,80,80,240,20,2027
"""

GAMES = [
    {"id": "100", "date": "2026-11-04", "home": "College A", "away": "College B",
     "homeScore": 78, "awayScore": 69},
    {"id": "101", "date": "2026-11-06", "home": "College B", "away": "College C",
     "homeScore": 70, "awayScore": 66},
]


class VerifiedSourceTests(unittest.TestCase):
    def test_directory_normalization_and_conflicts(self):
        self.assertEqual(canonical("St. John's"), "st john s")
        catalog = parse_directory(DIRECTORY)
        self.assertEqual(len(catalog), 3)
        rows = [{"name": "College A"}, {"name": "Unknown D-II"}]
        report = annotate_teams(rows, catalog)
        self.assertTrue(rows[0]["conferenceVerified"])
        self.assertEqual(rows[0]["conference"], "Big South")
        self.assertFalse(rows[1]["conferenceVerified"])
        self.assertEqual(report["unmatchedRatedTeams"], 1)
        conflict = DIRECTORY + "College A,Other conference,999,2027\n"
        self.assertNotIn("college a", parse_directory(conflict))

    def test_possession_efficiency_matches_only_confirmed_ids(self):
        rows = [{"name": name} for name in ("College A", "College B", "College C")]
        report = attach_efficiency(rows, GAMES, BOX)
        self.assertEqual(report["matchedTeamGames"], 4)
        self.assertEqual(report["teamsWithMetrics"], 3)
        self.assertEqual(rows[0]["offRating100"], 104)
        self.assertEqual(rows[0]["possessionGames"], 1)
        self.assertTrue(all("adjNet100" in r for r in rows))

    def test_live_integration_and_missing_supplements(self):
        t = datetime(2026, 11, 8, tzinfo=timezone.utc)
        output = build_current(GAMES, t, directory_csv=DIRECTORY, box_csv=BOX)
        self.assertEqual(output["identityCoverage"]["matchedRatedTeams"], 3)
        self.assertEqual(output["efficiencyCoverage"]["matchedTeamGames"], 4)
        self.assertEqual(output["selectionWatchlist"]["status"], "insufficient-coverage")
        # Only conference labels, not verified season-2027 D-I membership,
        # are supplied in this fixture. The provisional field remains gated.
        self.assertEqual(output["selectionWatchlist"]["matchedConferences"], 0)
        self.assertEqual(output["divisionCoverage"]["status"], "unavailable")
        plain = build_current(GAMES, t)
        self.assertEqual(plain["efficiencyCoverage"]["status"], "unavailable")
        self.assertEqual(plain["identityCoverage"]["status"], "unavailable")

    def test_optional_source_failure_is_isolated(self):
        sources, warnings = validate_supplements(
            "not,a,valid,header\\n", BOX, None, None)
        self.assertIsNone(sources["directory_csv"])
        self.assertEqual(sources["box_csv"], BOX)
        self.assertEqual(len(warnings), 1)
        output = build_current(GAMES, box_csv=sources["box_csv"])
        self.assertEqual(output["efficiencyCoverage"]["matchedTeamGames"], 4)
        self.assertEqual(output["identityCoverage"]["status"], "unavailable")

    def test_power_watchlist_does_not_create_missing_leagues(self):
        rows = []
        for ci in range(32):
            for j in range(3):
                rank = ci * 3 + j
                rows.append({
                    "teamId": f"t{rank}", "name": f"Team {rank}",
                    "conference": f"League {ci}", "conferenceVerified": True, "divisionIConfirmed": True,
                    "projectedRating": 1800 - rank, "wins": 10, "losses": j,
                })
        result = build_watchlist(rows, "2026-11-15")
        self.assertEqual(result["status"], "ready")
        self.assertEqual(len(result["teams"]), 76)
        self.assertEqual(sum(x["category"] == "conference-proxy" for x in result["teams"]), 32)
        self.assertEqual(sum(x["category"] == "power-only-at-large" for x in result["teams"]), 44)
        self.assertEqual(len({t["teamId"] for t in result["teams"]}), 76)
        self.assertFalse(result["official"])
        no_league = rows[:-3]
        broken = build_watchlist(no_league, "2026-11-15")
        self.assertEqual(broken["status"], "insufficient-coverage")
        self.assertEqual(broken["teams"], [])


if __name__ == "__main__":
    unittest.main()
