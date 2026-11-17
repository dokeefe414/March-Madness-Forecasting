"""Boosted-matchup classifier validation with leakage-resistant feature pairs."""
import math
import unittest
from forecast.advanced import Features
from forecast.boosted import train_boosted
from forecast.benchmark import Outcome, Year, evaluate


class BoostingTests(unittest.TestCase):
    def test_symmetry_and_determinism(self):
        past = [Features(d, d + 12, 0.15) for d in (150, -90, 20, 70, -20)] * 12
        a = train_boosted(past, rounds=10)
        b = train_boosted(past, rounds=10)
        self.assertEqual(a, b)
        item = Features(96, 106, .12)
        inverse = Features(-96, -106, -.12)
        self.assertAlmostEqual(a.probability(item), 1-a.probability(inverse), places=12)
        self.assertTrue(0 < a.probability(item) < 1)

    def test_invalid_data(self):
        with self.assertRaises(ValueError):
            train_boosted([])
        with self.assertRaises(ValueError):
            train_boosted([Features(1, 1)], rounds=0)
        with self.assertRaises(ValueError):
            train_boosted([Features(float("nan"), 1)])

    def test_future_outcomes_do_not_change_trained_model(self):
        years = [Year(2000+i, (Outcome(180, 170, .2), Outcome(-50, -80, -.12)), 0)
                 for i in range(7)]
        a = evaluate(years, "source", min_training_seasons=3)
        b = evaluate(years[:-1] + [Year(2006, (Outcome(-300, -270, -.4),), 0)], "source", min_training_seasons=3)
        self.assertEqual(a["yearByYear"][-1]["boostedStumps"], b["yearByYear"][-1]["boostedStumps"])
        self.assertNotEqual(a["yearByYear"][-1]["models"]["boosted"]["brier"],
                            b["yearByYear"][-1]["models"]["boosted"]["brier"])


if __name__ == "__main__":
    unittest.main()
