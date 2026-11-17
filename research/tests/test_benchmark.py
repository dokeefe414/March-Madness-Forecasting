"""Regression tests for leak-free, deterministic historical tournament evaluation."""
import json
import tempfile
import unittest
from pathlib import Path

from forecast.benchmark import (
    Outcome, Year, choose_temperature, evaluate, load_years,
    probability_of_winner, scores,
)


class RollingBenchmarkTests(unittest.TestCase):
    def test_probabilities_and_loss(self):
        self.assertAlmostEqual(probability_of_winner(0), 0.5)
        self.assertAlmostEqual(probability_of_winner(100, 1), 1 - probability_of_winner(-100, 1))
        self.assertEqual(probability_of_winner(-1e8), 0.0)
        self.assertEqual(probability_of_winner(1e8), 1.0)
        with self.assertRaises(ValueError):
            probability_of_winner(3, 0)
        self.assertEqual(scores([0.5, 0.5])["brier"], 0.25)

    def test_temperature_trains_on_past_only(self):
        # Highly accurate large rating gaps should prefer sharpening.
        past = [Outcome(250, 250)] * 20
        self.assertLess(choose_temperature(past), 1)
        years = [Year(y, (Outcome(200, 200),), 0) for y in range(2000, 2006)]
        original = evaluate(years, "frozen", min_training_seasons=2)
        altered = years[:-1] + [Year(2005, (Outcome(-200, -200),), 0)]
        changed = evaluate(altered, "frozen", min_training_seasons=2)
        self.assertEqual(original["yearByYear"][-1]["calibrationTemperature"],
                         changed["yearByYear"][-1]["calibrationTemperature"])
        self.assertNotEqual(original["yearByYear"][-1]["models"]["trend_elo"]["brier"],
                            changed["yearByYear"][-1]["models"]["trend_elo"]["brier"])
        self.assertEqual(original, evaluate(years, "frozen", min_training_seasons=2))
        self.assertEqual(original["firstTestSeason"], 2002)
        self.assertEqual(original["lastTestSeason"], 2005)
        self.assertEqual(original["aggregate"]["coin_flip"]["brier"], .25)

    def test_duplicate_year_and_insufficient_history_rejected(self):
        y = Year(2025, (Outcome(20, 30),), 0)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            evaluate([y, y], "x", 1)
        with self.assertRaisesRegex(ValueError, "not enough"):
            evaluate([y], "x", 1)
        with self.assertRaises(ValueError):
            evaluate([y], "x", 0)

    def test_loads_complete_seasons_and_excludes_2020_and_partial_2026(self):
        with tempfile.TemporaryDirectory() as temp:
            web = Path(temp)
            (web / "data").mkdir()
            (web / "public/seasons").mkdir(parents=True)
            (web / "public/tournaments").mkdir(parents=True)
            entries = []
            for season in (2019, 2020, 2021, 2022, 2026):
                full = season not in (2020, 2026)
                entries.append({
                    "season": season, "throughDay": 132 if full else 118,
                    "isComplete": full, "tournamentGames": 1 if full else 0,
                })
                if not full:
                    continue
                ratings = {
                    "season": season, "throughDay": 132, "isComplete": True,
                    "sourceCommit": "pinned", "teams": [
                        {"teamId": "1", "rating": 1700, "projectedRating": 1710},
                        {"teamId": "2", "rating": 1500, "projectedRating": 1490},
                    ],
                }
                tourney = {
                    "season": season, "sourceCommit": "pinned", "mainDrawOnly": False,
                    "games": [{"winnerId": "1", "loserId": "2",
                               "winnerScore": 80, "loserScore": 70}],
                }
                (web / f"public/seasons/{season}.json").write_text(json.dumps(ratings))
                (web / f"public/tournaments/{season}.json").write_text(json.dumps(tourney))
            (web / "data/history-index.json").write_text(
                json.dumps({"sourceCommit": "pinned", "seasons": entries}))
            years, source = load_years(web)
            self.assertEqual(source, "pinned")
            self.assertEqual([y.season for y in years], [2019, 2021, 2022])
            self.assertEqual(evaluate(years, source, 1)["evaluatedYears"], 2)

            # Missing rated teams are reported as omissions; no default odds invented.
            path = web / "public/tournaments/2022.json"
            tourney = json.loads(path.read_text())
            tourney["games"].append({"winnerId": "3", "loserId": "2",
                                      "winnerScore": 80, "loserScore": 75})
            path.write_text(json.dumps(tourney))
            entries[-2]["tournamentGames"] = 2
            (web / "data/history-index.json").write_text(
                json.dumps({"sourceCommit": "pinned", "seasons": entries}))
            year_list, _ = load_years(web)
            self.assertEqual(year_list[-1].omitted_games, 1)
            self.assertEqual(len(year_list[-1].games), 1)

            # Historical data corruption must fail explicitly rather than bias metrics.
            tourney["sourceCommit"] = "other"
            path.write_text(json.dumps(tourney))
            with self.assertRaisesRegex(ValueError, "source pin"):
                load_years(web)


if __name__ == "__main__":
    unittest.main()
