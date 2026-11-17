"""CSV fixture tests: season and chronological cutoff must hold."""

import tempfile
import unittest
from pathlib import Path

from forecast.io import read_regular_season, read_team_names


class InputTests(unittest.TestCase):
    def test_parse_season_filter_and_day_cutoff(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "MTeams.csv").write_text(
                "TeamID,TeamName\n10,North A\n20,South B\n", encoding="utf-8"
            )
            (root / "MRegularSeasonCompactResults.csv").write_text(
                "Season,DayNum,WTeamID,LTeamID,WScore,LScore,WLoc,NumOT\n"
                "2025,10,10,20,70,62,H,0\n"
                "2025,20,20,10,80,76,A,0\n"
                "2026,1,10,20,72,60,N,0\n", encoding="utf-8"
            )
            self.assertEqual(read_team_names(root)[10], "North A")
            games = read_regular_season(root, 2025, through_day=10)
            self.assertEqual(len(games), 1)
            self.assertEqual(games[0].winner_location, "H")

    def test_invalid_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "MTeams.csv").write_text("Nope\n1\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing columns"):
                read_team_names(root)


if __name__ == "__main__":
    unittest.main()
