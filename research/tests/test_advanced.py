"""Tests for the additional model and interval/reliability machinery."""
import math
import unittest

from forecast.advanced import Features, predict, train_logistic
from forecast.benchmark import Outcome, Year, evaluate, reliability, block_bootstrap


class AdvancedModelTests(unittest.TestCase):
    def test_symmetric_odds_and_sane_weights(self):
        examples = [Features(220, 215, .2)] * 30 + [Features(-35, -25, -.1)] * 15
        weights = train_logistic(examples, iterations=80)
        self.assertTrue(all(math.isfinite(w) for w in weights))
        x = Features(130, 150, .1)
        neg = Features(-130, -150, -.1)
        self.assertAlmostEqual(predict(x, weights), 1 - predict(neg, weights), places=12)
        self.assertGreater(predict(x, weights), .5)

    def test_invalid_training(self):
        with self.assertRaises(ValueError):
            train_logistic([])
        with self.assertRaises(ValueError):
            train_logistic([Features(float("nan"), 10)])
        with self.assertRaises(ValueError):
            train_logistic([Features(5, 5)], iterations=0)

    def test_reliability_correctly_counts_upsets(self):
        bins = reliability([.9, .1, .7, .3, .5])
        self.assertEqual(sum(b["count"] for b in bins), 5)
        bucket = next(b for b in bins if b["lower"] == .9)
        self.assertEqual(bucket["count"], 2)
        self.assertEqual(bucket["accuracy"], .5)
        self.assertAlmostEqual(bucket["confidence"], .9)

    def test_past_only_fitted_logistic(self):
        years = [Year(2000 + i, (Outcome(100, 130, .1), Outcome(-25, -30, -.1)), 0)
                 for i in range(7)]
        orig = evaluate(years, "pinned", 3)
        self.assertEqual(orig["evaluatedYears"], 4)
        self.assertIn("logistic", orig["aggregate"])
        self.assertIn("seasonBlockUncertainty", orig)
        other = years[:-1] + [Year(2006, (Outcome(-150, -180, -.6),), 0)]
        changed = evaluate(other, "pinned", 3)
        self.assertEqual(orig["yearByYear"][-1]["logisticWeights"],
                         changed["yearByYear"][-1]["logisticWeights"])
        self.assertNotEqual(orig["yearByYear"][-1]["models"]["logistic"]["brier"],
                            changed["yearByYear"][-1]["models"]["logistic"]["brier"])


if __name__ == "__main__":
    unittest.main()
