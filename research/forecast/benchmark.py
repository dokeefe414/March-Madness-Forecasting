"""Leakage-aware rolling-year tournament benchmarks from committed historical archives.

A year Y is evaluated only with season-Y pre-tournament team ratings. The
calibration temperature is chosen using tournament outcomes from seasons < Y.
Retrospective *actual matchups* are scored; this is NOT bracket prediction.
No third-party dependencies and no network access are required.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from .advanced import Features, train_logistic, predict as logistic_predict
from .boosted import train_boosted
from .dynamics import regime_features
from dataclasses import dataclass
from pathlib import Path

TEMPERATURES = (0.5, 0.65, 0.8, 1.0, 1.25, 1.5, 2.0, 3.0, 4.0)
METHODS = ("coin_flip", "elo", "trend_elo", "adaptive_form", "calibrated_trend_elo", "logistic", "boosted")


@dataclass(frozen=True)
class Outcome:
    """Rating difference is from the *eventual winner's* perspective."""

    base_difference: float
    trend_difference: float
    win_pct_difference: float = 0.0
    adaptive_difference: float | None = None


@dataclass(frozen=True)
class Year:
    season: int
    games: tuple[Outcome, ...]
    omitted_games: int


def probability_of_winner(difference: float, temperature: float = 1.0) -> float:
    """Numerically stable logistic Elo probability for an observed winner."""
    if not (math.isfinite(difference) and math.isfinite(temperature) and temperature > 0):
        raise ValueError("difference must be finite and temperature positive and finite")
    z = difference * math.log(10.0) / (400.0 * temperature)
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    exp_z = math.exp(z)
    return exp_z / (1.0 + exp_z)


def load_years(web_dir: Path) -> tuple[list[Year], str]:
    """Load and validate pre-tournament snapshots and *held-out* outcome files.

    Full regular-season source coverage and a nonempty, non-play-in-only NCAA
    tournament are required. Teams missing ratings are counted, never invented.
    """
    web_dir = Path(web_dir)
    index = json.loads((web_dir / "data/history-index.json").read_text(encoding="utf-8"))
    source_commit = index["sourceCommit"]
    years: list[Year] = []
    seen: set[int] = set()
    for entry in sorted(index["seasons"], key=lambda e: e["season"]):
        season = entry["season"]
        if season in seen:
            raise ValueError(f"duplicate season {season}")
        seen.add(season)
        if not entry["isComplete"] or entry["throughDay"] != 132 or not entry["tournamentGames"]:
            continue
        snapshot = json.loads((web_dir / f"public/seasons/{season}.json").read_text(encoding="utf-8"))
        tournament = json.loads((web_dir / f"public/tournaments/{season}.json").read_text(encoding="utf-8"))
        if snapshot["season"] != season or tournament["season"] != season:
            raise ValueError(f"season mismatch for {season}")
        if not snapshot.get("isComplete") or snapshot.get("throughDay") != 132:
            raise ValueError(f"season {season} is not a complete pre-tournament snapshot")
        if snapshot.get("sourceCommit") != source_commit or tournament.get("sourceCommit") != source_commit:
            raise ValueError(f"source pin mismatch in {season} archive")
        if tournament.get("mainDrawOnly"):
            continue
        games = tournament["games"]
        if len(games) != entry["tournamentGames"]:
            raise ValueError(f"tournament game-count mismatch for {season}")
        teams = {str(t["teamId"]): t for t in snapshot["teams"]}
        year_games: list[Outcome] = []
        omitted = 0
        for game in games:
            winner, loser = teams.get(str(game["winnerId"])), teams.get(str(game["loserId"]))
            if winner is None or loser is None:
                omitted += 1
                continue
            if int(game["winnerScore"]) <= int(game["loserScore"]):
                raise ValueError(f"invalid winner/loser score in season {season}")
            base = float(winner["rating"]) - float(loser["rating"])
            trend = float(winner["projectedRating"]) - float(loser["projectedRating"])
            if not (math.isfinite(base) and math.isfinite(trend)):
                raise ValueError(f"non-finite rating in season {season}")
            def win_pct(team: dict) -> float:
                played = int(team.get("wins", 0)) + int(team.get("losses", 0))
                return float(team.get("wins", 0)) / played if played else 0.5
            adaptive = (regime_features(winner.get("history", [winner["rating"]]),
                                        winner["rating"])["adaptiveRating"]
                        - regime_features(loser.get("history", [loser["rating"]]),
                                          loser["rating"])["adaptiveRating"])
            year_games.append(Outcome(base, trend, win_pct(winner) - win_pct(loser), adaptive))
        if year_games:
            years.append(Year(season, tuple(year_games), omitted))
    if not years:
        raise ValueError("no complete historical tournament seasons found")
    return years, source_commit


def choose_temperature(training_games: list[Outcome]) -> float:
    """Fit *only* a scalar temperature by minimizing earlier-year log loss."""
    if not training_games:
        raise ValueError("calibration requires earlier-season games")
    def loss(temp: float) -> float:
        return sum(-math.log(max(probability_of_winner(g.trend_difference, temp), 1e-15))
                   for g in training_games) / len(training_games)
    # Prefer unchanged Elo when losses tie, to avoid artificial complexity.
    return min(TEMPERATURES, key=lambda t: (loss(t), abs(math.log(t))))


def scores(probabilities: list[float]) -> dict[str, float | int]:
    """Every probability is P(actual winner); Brier and log loss are symmetric."""
    if not probabilities:
        raise ValueError("cannot score an empty tournament")
    n = len(probabilities)
    return {
        "games": n,
        "brier": round(sum((1.0 - p) ** 2 for p in probabilities) / n, 6),
        "logLoss": round(sum(-math.log(max(p, 1e-15)) for p in probabilities) / n, 6),
        "accuracy": round(sum(1.0 if p > .5 else .5 if p == .5 else 0.0
                              for p in probabilities) / n, 6),
    }


def reliability(probabilities: list[float]) -> list[dict]:
    """Estimate calibration conditional on the predicted favorite, in 10 bins.

    With stored winner-oriented probabilities, the expected favorite outcome is
    1 when the recorded winner was favored, 0 when an upset occurred, and 0.5
    for ties in model strength. This avoids the all-winner-label artifact.
    """
    bins: list[list[tuple[float, float]]] = [[] for _ in range(10)]
    for p in probabilities:
        confidence = max(p, 1.0 - p)
        observed = 1.0 if p > .5 else 0.0 if p < .5 else 0.5
        index = min(9, max(0, int((confidence - .5) * 20)))
        bins[index].append((confidence, observed))
    return [{
        "lower": round(0.5 + i * .05, 2),
        "upper": round(0.5 + (i + 1) * .05, 2),
        "count": len(rows),
        "confidence": round(sum(p for p, _ in rows) / len(rows), 6) if rows else None,
        "accuracy": round(sum(y for _, y in rows) / len(rows), 6) if rows else None,
    } for i, rows in enumerate(bins)]


def block_bootstrap(years: list[dict], samples: int = 2000, seed: int = 2027) -> dict:
    """Paired 95% interval for Brier difference to Elo, resampling whole years.

    This is a descriptive uncertainty interval, NOT a formal guarantee of
    superiority. A season is the resampling unit, not a single correlated game.
    """
    rng = random.Random(seed)
    methods = [method for method in METHODS if method != "elo"]
    result = {}
    for method in methods:
        draws = []
        for _ in range(samples):
            selected = [years[rng.randrange(len(years))] for _ in years]
            n = sum(y["evaluatedGames"] for y in selected)
            delta = sum(y["evaluatedGames"] *
                        (y["models"][method]["brier"] - y["models"]["elo"]["brier"])
                        for y in selected) / n
            draws.append(delta)
        draws.sort()
        result[method] = {
            "deltaBrierVsElo": round(sum(y["evaluatedGames"] *
                (y["models"][method]["brier"] - y["models"]["elo"]["brier"])
                for y in years) / sum(y["evaluatedGames"] for y in years), 6),
            "interval95": [round(draws[int(.025 * samples)], 6),
                           round(draws[min(samples - 1, int(.975 * samples))], 6)],
            "samples": samples,
            "unit": "tournament season",
        }
    return result


def evaluate(years: list[Year], source_commit: str, min_training_seasons: int = 5) -> dict:
    """Chronological walk-forward test: no outcome from test year tunes test year."""
    if min_training_seasons < 1:
        raise ValueError("min_training_seasons must be >= 1")
    ordered = sorted(years, key=lambda y: y.season)
    if len({y.season for y in ordered}) != len(ordered):
        raise ValueError("duplicate evaluation years")
    if len(ordered) <= min_training_seasons:
        raise ValueError("not enough seasons to train and evaluate")
    predictions: dict[str, list[float]] = {method: [] for method in METHODS}
    test_years = []
    for i in range(min_training_seasons, len(ordered)):
        current = ordered[i]
        past = [game for previous in ordered[:i] for game in previous.games]
        temperature = choose_temperature(past)
        weights = train_logistic([
            Features(g.base_difference, g.trend_difference, g.win_pct_difference)
            for g in past
        ])
        boosted = train_boosted([
            Features(g.base_difference, g.trend_difference, g.win_pct_difference)
            for g in past
        ])
        row: dict[str, list[float]] = {
            "coin_flip": [0.5 for _ in current.games],
            "elo": [probability_of_winner(game.base_difference) for game in current.games],
            "trend_elo": [probability_of_winner(game.trend_difference) for game in current.games],
            "adaptive_form": [
                probability_of_winner(g.adaptive_difference if g.adaptive_difference is not None
                                      else g.base_difference) for g in current.games
            ],
            "calibrated_trend_elo": [
                probability_of_winner(game.trend_difference, temperature) for game in current.games
            ],
            "logistic": [
                logistic_predict(Features(g.base_difference, g.trend_difference,
                                          g.win_pct_difference), weights)
                for g in current.games
            ],
            "boosted": [
                boosted.probability(Features(g.base_difference, g.trend_difference,
                                             g.win_pct_difference))
                for g in current.games
            ],
        }
        for method in METHODS:
            predictions[method].extend(row[method])
        test_years.append({
            "season": current.season,
            "trainingSeasons": i,
            "trainingThrough": ordered[i - 1].season,
            "evaluatedGames": len(current.games),
            "omittedGames": current.omitted_games,
            "calibrationTemperature": temperature,
            "logisticWeights": [round(w, 6) for w in weights],
            "boostedStumps": [{
                "feature": s.feature, "threshold": s.threshold,
                "left": round(s.left, 6), "right": round(s.right, 6),
            } for s in boosted.stumps],
            "models": {method: scores(row[method]) for method in METHODS},
        })
    return {
        "schemaVersion": 2,
        "type": "historical-actual-matchup-walk-forward",
        "sourceCommit": source_commit,
        "minTrainingSeasons": min_training_seasons,
        "evaluatedYears": len(test_years),
        "firstTestSeason": test_years[0]["season"],
        "lastTestSeason": test_years[-1]["season"],
        "aggregate": {method: scores(predictions[method]) for method in METHODS},
        "reliability": {method: reliability(predictions[method]) for method in METHODS},
        "seasonBlockUncertainty": block_bootstrap(test_years),
        "yearByYear": test_years,
        "limitations": [
            "Matchups are historical observed pairs, not predicted field selection or bracket paths.",
            "All test-season features are frozen regular-season Elo snapshots, never tournament outcomes or seeds.",
            "Temperature is chosen from previous seasons' tournament outcomes only.",
            "Incomplete seasons and canceled tournaments are excluded; missing team ratings are counted and skipped.",
            "The baseline Elo parameters were fixed before this evaluation, not independently optimized by year.",
            "Logistic coefficients are fit on historical *earlier-year* tournament outcomes and regular-season-only features.",
            "Gradient-boosted residual stumps are fit on earlier tournament years only; each paired sample has a symmetric winner/loser orientation.",
            "Adaptive regime feature uses only same-season prior regular-season Elo history; the model is heuristic and not trained on held-out outcomes.",
            "A 95% season-block bootstrap is descriptive uncertainty, not a future guarantee.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--web-dir", type=Path, default=Path("web"))
    parser.add_argument("--out", type=Path, default=Path("research/outputs/rolling-benchmark.json"))
    parser.add_argument("--min-training-seasons", type=int, default=5)
    args = parser.parse_args()
    years, source_commit = load_years(args.web_dir)
    report = evaluate(years, source_commit, args.min_training_seasons)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Walk-forward: {report['evaluatedYears']} seasons "
          f"({report['firstTestSeason']}–{report['lastTestSeason']})")
    for method, values in report["aggregate"].items():
        print(f"{method:22s} Brier={values['brier']:.4f} "
              f"LogLoss={values['logLoss']:.4f} Accuracy={values['accuracy']:.1%} "
              f"N={values['games']}")
    print(f"Reproducible JSON report: {args.out}")


if __name__ == "__main__":
    main()
