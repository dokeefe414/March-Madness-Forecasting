"""Regression tests for historical-only probabilistic score and calibration models."""
import math
import unittest
from dataclasses import replace
from pathlib import Path
from forecast.historical_dataset import load_dataset
from forecast.historical_probabilistic import (
    _ridge,_estimate,_calibration,_score_intervals,evaluate,BLEND_WEIGHTS,PROBABILITY_SCALES
)

class HistoricalProbabilisticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows,cls.manifest=load_dataset(Path(__file__).resolve().parents[2]/"web")

    def test_historical_heldout_score_and_probability_are_finite(self):
        report=evaluate(self.rows,self.manifest)
        self.assertEqual(report["mode"],"historical-research-only")
        self.assertFalse(report["policy"]["liveForecastsChanged"])
        self.assertTrue(report["policy"]["noAutomaticPromotion"])
        self.assertGreater(report["heldOutGames"],1500)
        self.assertEqual(report["metrics"]["elo"]["games"],report["metrics"]["nestedEnsemble"]["games"])
        for model in ("elo","calibratedElo","scoringProbability","nestedEnsemble"):
            metrics=report["metrics"][model]
            self.assertTrue(0<=metrics["brier"]<=1)
            self.assertTrue(0<=metrics["accuracy"]<=1)
            self.assertTrue(math.isfinite(metrics["logLoss"]))
        interval=report["metrics"]["projectedScores"]
        self.assertGreater(interval["marginMAE"],0)
        self.assertGreater(interval["totalMAE"],0)
        self.assertTrue(0<=interval["margin80Coverage"]<=1)
        self.assertTrue(0<=interval["total80Coverage"]<=1)
        self.assertEqual(sum(v["games"] for v in report["calibration"]["ensemble"]["bins"]),
                         report["heldOutGames"])
        self.assertEqual(report["yearByYear"][0]["modelWeight"],0.)
        self.assertEqual(report["yearByYear"][0]["scoreProbabilityScale"],1.)
        self.assertTrue(all(y["modelWeight"] in BLEND_WEIGHTS for y in report["yearByYear"]))
        self.assertTrue(all(y["scoreProbabilityScale"] in PROBABILITY_SCALES for y in report["yearByYear"]))

    def test_future_outcomes_cannot_change_prior_season_model_or_predictions(self):
        truncated=[r for r in self.rows if r.season<=1998]
        base=evaluate(truncated,self.manifest)
        altered=[replace(r,side_a_won=1-r.side_a_won,
             winner_score=r.winner_score+5) if r.season==1998 else r for r in truncated]
        new=evaluate(altered,self.manifest)
        self.assertEqual(base["yearByYear"][:-1],new["yearByYear"][:-1])
        self.assertEqual(base["yearByYear"][-1]["modelWeight"],
                         new["yearByYear"][-1]["modelWeight"])
        self.assertEqual(base["yearByYear"][-1]["scoreProbabilityScale"],
                         new["yearByYear"][-1]["scoreProbabilityScale"])
        self.assertNotEqual(base["yearByYear"][-1]["scoreIntervals"]["totalMAE"],
                            new["yearByYear"][-1]["scoreIntervals"]["totalMAE"])

    def test_future_years_cannot_change_earlier_heldout_report(self):
        small=[r for r in self.rows if r.season<=1996]
        larger=[r for r in self.rows if r.season<=1998]
        a=evaluate(small,self.manifest)
        b=evaluate(larger,self.manifest)
        self.assertEqual(a["yearByYear"],b["yearByYear"][:len(a["yearByYear"])])

    def test_regularization_and_probability_calibration_input_guards(self):
        sample=self.rows[:220]
        margin=_ridge(sample,"margin")
        total=_ridge(sample,"total")
        self.assertEqual(len(margin),4)
        self.assertEqual(len(total),4)
        self.assertTrue(math.isfinite(_estimate(sample[0],margin,"margin")))
        self.assertTrue(math.isfinite(_estimate(sample[0],total,"total")))
        with self.assertRaisesRegex(ValueError,"Cannot train"):
            _ridge([],"margin")
        with self.assertRaisesRegex(ValueError,"Nonfinite"):
            _calibration([{"ensemble":math.nan,"y":1}],"ensemble")
        self.assertEqual(_score_intervals([])["margin80Coverage"],None)

if __name__=="__main__":
    unittest.main()
