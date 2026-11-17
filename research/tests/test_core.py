"""Tests for chronological updates, forecasts, probabilities and simulations."""

import unittest

from forecast.core import EloEngine, Game, TeamState, forecast_rating, matchup_probability, simulate_bracket


class CoreTests(unittest.TestCase):
    def test_neutral_probabilities_are_symmetric(self):
        p = matchup_probability(1640, 1510)
        self.assertAlmostEqual(p + matchup_probability(1510, 1640), 1.0)
        self.assertGreater(p, 0.5)

    def test_pregame_brier_no_target_leakage(self):
        game = Game(2025, 10, 1, 2, 75, 69, "N")
        model = EloEngine().fit([game], {1: "One", 2: "Two"})
        self.assertAlmostEqual(model.brier_score(), 0.25)
        self.assertAlmostEqual(model.states[1].rating, 1512.0)
        self.assertAlmostEqual(model.states[2].rating, 1488.0)

    def test_sorted_chronologically_and_no_cross_season(self):
        earlier = Game(2025, 1, 1, 2, 90, 80)
        later = Game(2025, 10, 2, 1, 76, 70)
        a = EloEngine().fit([later, earlier], {})
        b = EloEngine().fit([earlier, later], {})
        self.assertEqual(a.rankings(), b.rankings())
        with self.assertRaises(ValueError):
            EloEngine().fit([earlier, Game(2026, 11, 1, 2, 80, 60)], {})

    def test_projection_only_after_sufficient_games_and_bounded(self):
        state = TeamState(1, "Test")
        self.assertEqual(forecast_rating(state), 1500.0)
        state.history = [1500, 1512, 1524, 1536, 1548]
        state.rating, state.wins = 1548, 4
        self.assertAlmostEqual(forecast_rating(state), 1563.0)

    def test_reject_invalid_values(self):
        with self.assertRaises(ValueError):
            matchup_probability(float("nan"), 1500)
        with self.assertRaises(ValueError):
            EloEngine().fit([Game(2025, 1, 1, 1, 65, 70)], {})
        with self.assertRaises(ValueError):
            simulate_bracket([("x", 1500)] * 3, 1)

    def test_seeded_bracket_and_probabilities(self):
        entrants = [("favorite", 2000), ("underdog", 1200), ("a", 1400), ("b", 1400)]
        result = simulate_bracket(entrants, runs=1000, seed=7)
        self.assertEqual(result, simulate_bracket(entrants, runs=1000, seed=7))
        self.assertAlmostEqual(sum(row["titleProbability"] for row in result), 1)
        self.assertEqual(len(result[0]["advanceProbabilityByRound"]), 2)
        self.assertEqual(result[0]["teamId"], "favorite")

    def test_empty_fit(self):
        model = EloEngine().fit([], {})
        self.assertEqual(model.rankings(), [])
        self.assertIsNone(model.brier_score())


if __name__ == "__main__":
    unittest.main()
