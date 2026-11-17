"""Historical import and 2026 supplemental mapping tests."""
import tempfile
import unittest
from pathlib import Path

from forecast.history import build_history, map_2026_name
from forecast.download import git_blob_sha


class HistoricalPipelineTests(unittest.TestCase):
    def test_git_blob_sha_known(self):
        self.assertEqual(git_blob_sha(b"hello\n"), "ce013625030ba8dba906f756967f9e9ca394464a")

    def test_2026_alias(self):
        self.assertEqual(map_2026_name("UConn", {"connecticut": 1163}), 1163)
        with self.assertRaisesRegex(ValueError, "Unrecognized"):
            map_2026_name("Made Up", {"connecticut": 1163})

    def test_output_tournament_held_out_of_training(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw, out = root / "raw", root / "web"
            raw.mkdir()
            (raw / "MTeams.csv").write_text("TeamID,TeamName\n1,North\n2,South\n", encoding="utf8")
            (raw / "MRegularSeasonCompactResults.csv").write_text(
                "Season,DayNum,WTeamID,WScore,LTeamID,LScore,WLoc,NumOT\n"
                "2025,1,1,77,2,60,N,0\n"
                "2025,132,1,80,2,70,H,0\n", encoding="utf8"
            )
            (raw / "MNCAATourneyCompactResults.csv").write_text(
                "Season,DayNum,WTeamID,WScore,LTeamID,LScore,WLoc,NumOT\n"
                "2025,136,2,70,1,65,N,0\n", encoding="utf8"
            )
            (raw / "MNCAATourneySeeds.csv").write_text(
                "Season,Seed,TeamID\n2025,W01,1\n2025,W16,2\n", encoding="utf8"
            )
            index = build_history(raw, out)
            import json
            snapshot = json.loads((out / "data" / "rankings.json").read_text(encoding="utf8"))
            self.assertEqual(index["seasons"][0]["tournamentGames"], 1)
            self.assertEqual(snapshot["tournament"]["champion"], "South")
            self.assertEqual(snapshot["teams"][0]["name"], "North")
            self.assertTrue(snapshot["isComplete"])
            self.assertEqual(snapshot["tournament"]["evaluatedGames"], 1)
            self.assertGreater(snapshot["tournament"]["brier"], .25)
            result = json.loads((out / "public" / "tournaments" / "2025.json").read_text())
            self.assertEqual(result["games"][0]["winnerScore"], 70)


if __name__ == "__main__":
    unittest.main()
