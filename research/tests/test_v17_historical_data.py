"""Historical source and nested out-of-time evaluation regression tests."""
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from forecast.historical_dataset import load_dataset,evaluate,build


def synthetic(web:Path):
    (web/"data").mkdir()
    (web/"public/seasons").mkdir(parents=True)
    (web/"public/tournaments").mkdir(parents=True)
    entries=[]
    for season in range(2015,2025):
        rated={"season":season,"sourceCommit":"immutable-test-source",
            "isComplete":True,"throughDay":132,
            "teams":[{"teamId":str(i),"rating":1500+i*25+season%3*3,
                       "projectedRating":1510+i*20,"wins":10+i,"losses":8}
                     for i in range(1,7)]}
        games=[{"day":134+i,"winnerId":str(w),"loserId":str(l),
                "winnerScore":75+i,"loserScore":60+i}
               for i,(w,l) in enumerate([(1,2),(3,4),(5,6)])]
        tournament={"season":season,"sourceCommit":"immutable-test-source",
                    "mainDrawOnly":False,"games":games}
        entries.append({"season":season,"isComplete":True,"throughDay":132,
                        "teams":6,"tournamentGames":3})
        (web/f"public/seasons/{season}.json").write_text(json.dumps(rated))
        (web/f"public/tournaments/{season}.json").write_text(json.dumps(tournament))
    (web/"data/history-index.json").write_text(json.dumps({
        "sourceCommit":"immutable-test-source","seasons":entries}))


class HistoricalInfrastructureTests(unittest.TestCase):
    def test_source_manifest_and_reproducible_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            web=Path(folder);synthetic(web)
            rows,manifest,report=build(web)
            self.assertEqual(len(rows),30)
            self.assertEqual(manifest["includedSeasons"],10)
            self.assertEqual(report["testedGames"],15)
            self.assertEqual(report["firstTestSeason"],2020)
            self.assertFalse(report["activePublicModelChanged"])
            self.assertEqual((rows[0].side_a_id,rows[0].side_b_id,rows[0].side_a_won),("1","2",1))
            self.assertEqual((rows,manifest,report),build(web))
            self.assertEqual(len(manifest["perSeason"][0]["seasonSha256"]),64)

    def test_test_year_results_never_select_that_year_model(self):
        with tempfile.TemporaryDirectory() as folder:
            web=Path(folder);synthetic(web)
            rows,manifest=load_dataset(web)
            baseline=evaluate(rows,manifest)
            altered=deepcopy(rows)
            # Winner label reversal on the last season is intentionally
            # hypothetical; only the 2024 label changes.
            from dataclasses import replace
            altered=[replace(x,side_a_won=1-x.side_a_won) if x.season==2024 else x
                     for x in altered]
            changed=evaluate(altered,manifest)
            self.assertEqual(baseline["yearByYear"][-1]["selectedByEarlierOos"],
                             changed["yearByYear"][-1]["selectedByEarlierOos"])
            self.assertEqual(baseline["yearByYear"][-1]["temperatureFromPriorYears"],
                             changed["yearByYear"][-1]["temperatureFromPriorYears"])
            self.assertNotEqual(baseline["yearByYear"][-1]["elo"]["brier"],
                                changed["yearByYear"][-1]["elo"]["brier"])

    def test_corrupt_source_and_duplicate_games_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            web=Path(folder);synthetic(web)
            path=web/"public/tournaments/2024.json"
            data=json.loads(path.read_text())
            data["games"].append(dict(data["games"][0]))
            path.write_text(json.dumps(data))
            index=web/"data/history-index.json"
            idx=json.loads(index.read_text())
            idx["seasons"][-1]["tournamentGames"]+=1
            index.write_text(json.dumps(idx))
            with self.assertRaisesRegex(ValueError,"Duplicate tournament"):
                load_dataset(web)
            data["games"].pop()
            data["sourceCommit"]="changed"
            path.write_text(json.dumps(data))
            idx["seasons"][-1]["tournamentGames"]-=1
            index.write_text(json.dumps(idx))
            with self.assertRaisesRegex(ValueError,"source pin"):
                load_dataset(web)

    def test_partial_seasons_and_missing_team_are_reported_not_imputed(self):
        with tempfile.TemporaryDirectory() as folder:
            web=Path(folder);synthetic(web)
            idx_path=web/"data/history-index.json"
            idx=json.loads(idx_path.read_text())
            idx["seasons"][2]["isComplete"]=False
            idx_path.write_text(json.dumps(idx))
            path=web/"public/tournaments/2024.json"
            data=json.loads(path.read_text())
            data["games"][0]["loserId"]="not-a-team"
            path.write_text(json.dumps(data))
            rows,manifest=load_dataset(web)
            self.assertIn(2017,manifest["excludedSeasons"])
            self.assertEqual(manifest["omittedMissingRatedTeams"],1)
            self.assertEqual(len(rows),26)
            self.assertTrue(all(r.side_a_id!="not-a-team" and r.side_b_id!="not-a-team" for r in rows))

    def test_orientation_independence_of_winner_label(self):
        with tempfile.TemporaryDirectory() as folder:
            web=Path(folder);synthetic(web)
            path=web/"public/tournaments/2024.json"
            games=json.loads(path.read_text())
            games["games"][0]["winnerId"],games["games"][0]["loserId"]=games["games"][0]["loserId"],games["games"][0]["winnerId"]
            path.write_text(json.dumps(games))
            rows,_=load_dataset(web)
            r=next(x for x in rows if x.season==2024 and x.day==134)
            self.assertEqual((r.side_a_id,r.side_b_id),("1","2"))
            self.assertEqual(r.side_a_won,0)

    def test_real_committed_historical_archives(self):
        repository=Path(__file__).resolve().parents[2]
        rows,manifest,report=build(repository/"web")
        self.assertGreater(manifest["includedSeasons"],30)
        self.assertGreater(report["testedGames"],1000)
        self.assertIn(2020,manifest["excludedSeasons"])
        self.assertIn(2026,manifest["excludedSeasons"])
        self.assertEqual(report["firstTestSeason"],1990)
        self.assertEqual(report["lastTestSeason"],2025)
        self.assertEqual(report["metrics"]["elo"]["games"],report["metrics"]["nestedSelected"]["games"])


if __name__=="__main__":
    unittest.main()
