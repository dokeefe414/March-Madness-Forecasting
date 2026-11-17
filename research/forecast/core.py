"""Chronological team-strength estimation and neutral-site bracket simulation.

This is a baseline, NOT a fitted ARIMA / Kalman filter. Rating forecasts use a
small, bounded recent Elo slope. All updates use games that already occurred.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Mapping, Sequence


@dataclass(frozen=True)
class Game:
    season: int
    day_num: int
    winner: int
    loser: int
    winner_score: int
    loser_score: int
    winner_location: str = "N"  # Kaggle WLoc: H, A, N


@dataclass
class TeamState:
    team_id: int
    name: str
    rating: float = 1500.0
    wins: int = 0
    losses: int = 0
    history: list[float] = field(default_factory=lambda: [1500.0])

    @property
    def games(self) -> int:
        return self.wins + self.losses


def matchup_probability(rating_a: float, rating_b: float, home_advantage_a: float = 0.0) -> float:
    """Probability A wins; home_advantage_a is in Elo points."""
    if not all(math.isfinite(x) for x in (rating_a, rating_b, home_advantage_a)):
        raise ValueError("ratings and home advantage must be finite")
    diff = (rating_a + home_advantage_a - rating_b) / 400.0
    return 1.0 / (1.0 + 10.0 ** (-diff))


def forecast_rating(state: TeamState, horizon_games: int = 3, lookback: int = 5) -> float:
    """Conservative projected Elo rating from recent changes, clipped per game.

    This is intentionally a transparent heuristic to beat with proper time-series
    methods later. It is NOT a multi-season statistical estimate.
    """
    if horizon_games < 0 or lookback < 1:
        raise ValueError("horizon_games must be >=0 and lookback >=1")
    if state.games < 4 or horizon_games == 0:
        return state.rating
    n = min(lookback, len(state.history) - 1)
    slope = (state.history[-1] - state.history[-n - 1]) / n
    bounded = max(-10.0, min(10.0, slope))
    return state.rating + 0.5 * min(horizon_games, 6) * bounded


class EloEngine:
    """Independent per-season Elo estimator with chronological pre-game evaluation."""

    def __init__(self, k_factor: float = 24.0, home_advantage: float = 65.0):
        if k_factor <= 0 or not math.isfinite(k_factor):
            raise ValueError("k_factor must be positive and finite")
        if home_advantage < 0 or not math.isfinite(home_advantage):
            raise ValueError("home_advantage must be nonnegative and finite")
        self.k_factor = k_factor
        self.home_advantage = home_advantage
        self.states: dict[int, TeamState] = {}
        self.pregame_brier: list[float] = []
        self.pregame_accuracy: list[float] = []
        self.season: int | None = None
        self.last_day: int | None = None

    def fit(self, games: Sequence[Game], team_names: Mapping[int, str]) -> "EloEngine":
        """Fit one season; never leak a game's result into its pre-game prediction."""
        self.states = {}
        self.pregame_brier = []
        self.pregame_accuracy = []
        self.last_day = None
        self.season = None
        ordered = sorted(games, key=lambda g: (g.day_num, g.winner, g.loser))
        for game in ordered:
            if self.season is None:
                self.season = game.season
            if game.season != self.season:
                raise ValueError("fit accepts one season at a time")
            if game.winner == game.loser or game.winner_score <= game.loser_score:
                raise ValueError("invalid winning game record")
            if game.winner_location not in {"H", "A", "N"}:
                raise ValueError("winner_location must be H, A or N")
            winner = self.states.setdefault(
                game.winner, TeamState(game.winner, team_names.get(game.winner, str(game.winner)))
            )
            loser = self.states.setdefault(
                game.loser, TeamState(game.loser, team_names.get(game.loser, str(game.loser)))
            )
            home = {"H": self.home_advantage, "A": -self.home_advantage, "N": 0.0}[game.winner_location]
            expected_winner = matchup_probability(winner.rating, loser.rating, home)
            # Evaluate fixed ID orientation: using only the winner side would bias
            # interpretation of the Brier metric.
            first_id_won = game.winner < game.loser
            p_first = expected_winner if first_id_won else 1.0 - expected_winner
            outcome_first = 1.0 if first_id_won else 0.0
            self.pregame_brier.append((p_first - outcome_first) ** 2)
            self.pregame_accuracy.append(1.0 if expected_winner > .5 else .5 if expected_winner == .5 else 0.0)
            delta = self.k_factor * (1.0 - expected_winner)
            winner.rating += delta
            loser.rating -= delta
            winner.wins += 1
            loser.losses += 1
            winner.history.append(winner.rating)
            loser.history.append(loser.rating)
            self.last_day = game.day_num
        return self

    def brier_score(self) -> float | None:
        return sum(self.pregame_brier) / len(self.pregame_brier) if self.pregame_brier else None

    def pregame_accuracy_score(self) -> float | None:
        return sum(self.pregame_accuracy) / len(self.pregame_accuracy) if self.pregame_accuracy else None

    def rankings(self) -> list[dict]:
        """Return compact dashboard data. Ratings are not title probabilities."""
        ranked = sorted(
            self.states.values(),
            key=lambda state: (-forecast_rating(state), state.name, state.team_id),
        )
        rows = []
        for i, state in enumerate(ranked, start=1):
            projected = forecast_rating(state)
            rows.append({
                "rank": i,
                "teamId": str(state.team_id),
                "name": state.name,
                "rating": round(state.rating, 1),
                "projectedRating": round(projected, 1),
                "trend": round(projected - state.rating, 1),
                "wins": state.wins,
                "losses": state.losses,
                "history": [round(v, 1) for v in state.history[-12:]],
            })
        return rows


def simulate_bracket(
    entrants: Sequence[tuple[str, float]],
    runs: int = 10000,
    seed: int = 42,
) -> list[dict]:
    """Simulate ordered single-elimination bracket; first two entrants play.

    Entrants must already be in bracket order. Play-in rounds are not modeled.
    """
    size = len(entrants)
    if size < 2 or size & (size - 1):
        raise ValueError("entrants must have a power-of-two count >= 2")
    if len({team_id for team_id, _ in entrants}) != size:
        raise ValueError("entrant IDs must be unique")
    if runs < 1:
        raise ValueError("runs must be >=1")
    for _, rating in entrants:
        if not math.isfinite(rating):
            raise ValueError("ratings must be finite")
    rng = random.Random(seed)
    titles = {team_id: 0 for team_id, _ in entrants}
    round_counts = {team_id: [0] * int(math.log2(size)) for team_id, _ in entrants}
    for _ in range(runs):
        current = list(entrants)
        round_num = 0
        while len(current) > 1:
            next_round = []
            for j in range(0, len(current), 2):
                a, b = current[j], current[j + 1]
                victor = a if rng.random() < matchup_probability(a[1], b[1]) else b
                round_counts[victor[0]][round_num] += 1
                next_round.append(victor)
            current = next_round
            round_num += 1
        titles[current[0][0]] += 1
    result = [
        {"teamId": team_id, "titleProbability": count / runs,
         "advanceProbabilityByRound": [v / runs for v in round_counts[team_id]]}
        for team_id, count in titles.items()
    ]
    return sorted(result, key=lambda item: (-item["titleProbability"], item["teamId"]))
