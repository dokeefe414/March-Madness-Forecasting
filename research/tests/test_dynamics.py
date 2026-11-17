"""Causal adaptivity and finite signal tests."""
import unittest
from forecast.dynamics import regime_features


class RegimeTests(unittest.TestCase):
    def test_future_elos_do_not_change_historical_prefix(self):
        past = [1500,1512,1503,1520,1523,1535,1544,1540,1556,1560]
        a = regime_features(past)
        b = regime_features(past + [1900,2000])
        self.assertNotEqual(a["adaptiveRating"], b["adaptiveRating"])
        self.assertEqual(a, regime_features(past))
        self.assertLessEqual(abs(a["adaptiveRating"]-past[-1]),24)
        self.assertGreaterEqual(a["volatility"],0)

    def test_cold_start_and_invalid_values(self):
        f = regime_features([1500,1510])
        self.assertEqual(f["sampleStatus"],"insufficient")
        self.assertEqual(f["adaptiveRating"],1510)
        with self.assertRaises(ValueError):
            regime_features([])
        with self.assertRaises(ValueError):
            regime_features([1500,float("nan")])


if __name__ == "__main__":
    unittest.main()
