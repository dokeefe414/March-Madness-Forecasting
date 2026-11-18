"""v2.0: real historical season championship and strict no-hindsight controls."""
from __future__ import annotations
import math
import unittest
from dataclasses import replace
from pathlib import Path
from forecast.historical_dataset import load_dataset
from forecast.model_championship import evaluate,features,MODEL_NAMES

WEB=Path(__file__).resolve().parents[2]/"web"
class ModelChampionshipTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
    cls.games,cls.manifest=load_dataset(WEB)

 def test_actual_pinned_history_contains_nontrivial_matched_out_of_time_games(self):
    r=evaluate(self.games,self.manifest)
    self.assertEqual(r["mode"],"historical-only")
    self.assertEqual(r["sourceCommit"],self.manifest["sourceCommit"])
    self.assertGreaterEqual(r["evaluatedSeasons"],30)
    self.assertGreater(r["heldOutGames"],2000)
    self.assertFalse(r["safety"]["livePredictionsModified"])
    self.assertTrue(r["modelSelection"]["noAutomaticProductionPromotion"])
    self.assertEqual(len(r["models"]),6)
    self.assertTrue(all(r["models"][k]["games"]==r["heldOutGames"] for k in MODEL_NAMES))
    self.assertEqual(r["nestedChampion"]["games"],r["heldOutGames"])
    self.assertEqual(r["nestedGainYearBlock95"],evaluate(self.games,self.manifest)["nestedGainYearBlock95"])
    self.assertEqual(r["yearByYear"][0]["championSelectedBeforeResults"],"elo")
    self.assertEqual(r["yearByYear"][1]["championSelectedBeforeResults"],"elo")
    self.assertEqual(r["yearByYear"][2]["championSelectedBeforeResults"],"elo")
    for k,m in r["models"].items():
        self.assertTrue(0<=m["brier"]<=1,k)
        self.assertTrue(0<=m["accuracy"]<=1,k)
        self.assertTrue(math.isfinite(m["logLoss"]),k)

 def test_test_year_answers_do_not_change_selection_or_preceding_results(self):
    sample=[r for r in self.games if r.season<=1993]
    old=evaluate(sample,self.manifest)
    latest=max(r.season for r in sample)
    changed=[replace(r,side_a_won=1-r.side_a_won,
       winner_score=r.winner_score+10) if r.season==latest else r for r in sample]
    new=evaluate(changed,self.manifest)
    self.assertEqual(old["yearByYear"][:-1],new["yearByYear"][:-1])
    self.assertEqual(old["yearByYear"][-1]["championSelectedBeforeResults"],
                     new["yearByYear"][-1]["championSelectedBeforeResults"])
    self.assertNotEqual(old["yearByYear"][-1]["modelScores"]["elo"]["brier"],
                        new["yearByYear"][-1]["modelScores"]["elo"]["brier"])

 def test_train_label_orientation_not_test_year_leakage(self):
    row=self.games[0]
    original=features(row,False)
    swapped=features(replace(row,side_a_won=1-row.side_a_won),False)
    self.assertEqual(original.vector(),swapped.vector())
    self.assertEqual(tuple(-x for x in features(row,True).vector()),
                     features(replace(row,side_a_won=1-row.side_a_won),True).vector())

 def test_not_enough_earlier_seasons_fails_closed(self):
    few=[r for r in self.games if r.season<=1990]
    with self.assertRaisesRegex(ValueError,"Insufficient"):
        evaluate(few,self.manifest)
if __name__=="__main__":unittest.main()
