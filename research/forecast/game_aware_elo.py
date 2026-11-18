"""Source-aware, game-by-game regular-season Elo.

Keep the historical core Elo model unchanged. This independent 2027 estimator
uses game-time opponent strength and designated home court in the expected win
probability, then uses the observed score margin to *bound* the magnitude of
each update. It makes no claims about injuries, possessions or neutral venue
when those fields are absent from the verified schedule feed.

All games on the same source calendar date are evaluated against the SAME
start-of-day ratings. The source supplies no trustworthy tipoff ordering; this
avoids using an earlier-processed same-day final to predict another game
that may actually have started first. Updates apply after date-level scoring.
"""
from __future__ import annotations

import math
from collections import defaultdict
from itertools import groupby
from typing import Mapping, Sequence

from .core import EloEngine, Game, TeamState, matchup_probability

MARGIN_CAP = 25
MARGIN_FLOOR = .85
MARGIN_GAIN = .65


def margin_multiplier(points: int) -> float:
    """Bounded log margin weighting: 1-point wins ~1x, 25+ points max 1.50x."""
    if type(points) is not int or points < 1:
        raise ValueError("Winning score margin must be a positive integer")
    return MARGIN_FLOOR + MARGIN_GAIN * min(
        1.0, math.log1p(points) / math.log1p(MARGIN_CAP)
    )


class GameAwareEloEngine(EloEngine):
    """Date-frozen, score-aware Elo with explainable per-contest movements.

    When margin_sensitive=False, it is a strictly paired classic K=24 control,
    with the same home-court and date embargo as the enhanced estimator.
    """

    def __init__(self, k_factor: float = 24.0, home_advantage: float = 65.0,
                 margin_sensitive: bool = True):
        super().__init__(k_factor=k_factor, home_advantage=home_advantage)
        self.margin_sensitive = margin_sensitive
        self.game_receipts: list[dict] = []
        self.team_receipts: dict[int, list[dict]] = {}

    def fit(self, games: Sequence[Game],
            team_names: Mapping[int, str]) -> "GameAwareEloEngine":
        self.states = {}
        self.pregame_brier = []
        self.pregame_accuracy = []
        self.game_receipts = []
        self.team_receipts = {}
        self.season = None
        self.last_day = None
        ordered = sorted(games, key=lambda g: (
            g.day_num, min(g.winner, g.loser), max(g.winner, g.loser),
            g.contest_id, g.winner_score, g.loser_score,
        ))
        seen_contests: set[str] = set()
        for day, group in groupby(ordered, key=lambda g: g.day_num):
            pending = []
            for game in group:
                if self.season is None:
                    self.season = game.season
                if game.season != self.season:
                    raise ValueError("fit accepts one season at a time")
                if (game.day_num < 0 or game.winner == game.loser or
                    game.winner_score <= game.loser_score or game.loser_score <= 0):
                    raise ValueError("invalid winning game record")
                if game.winner_location not in {"H", "A", "N"}:
                    raise ValueError("winner_location must be H, A or N")
                if game.contest_id:
                    if game.contest_id in seen_contests:
                        raise ValueError("duplicate contest in Elo updates")
                    seen_contests.add(game.contest_id)
                winner = self.states.setdefault(
                    game.winner, TeamState(game.winner, team_names.get(game.winner, str(game.winner)))
                )
                loser = self.states.setdefault(
                    game.loser, TeamState(game.loser, team_names.get(game.loser, str(game.loser)))
                )
                venue = {"H":self.home_advantage,"A":-self.home_advantage,"N":0.0}[game.winner_location]
                p_winner = matchup_probability(winner.rating, loser.rating, venue)
                first_id_won = game.winner < game.loser
                p_first = p_winner if first_id_won else 1.0 - p_winner
                outcome_first = 1.0 if first_id_won else 0.0
                self.pregame_brier.append((p_first - outcome_first) ** 2)
                self.pregame_accuracy.append(
                    1.0 if p_winner > .5 else .5 if p_winner == .5 else 0.0
                )
                margin = game.winner_score - game.loser_score
                multiplier = margin_multiplier(margin) if self.margin_sensitive else 1.0
                effective_k = self.k_factor * multiplier
                delta = effective_k * (1.0 - p_winner)
                receipt = {
                    "contestId":game.contest_id,
                    "dayNum":day,
                    "winnerId":game.winner,"loserId":game.loser,
                    "preWinnerElo":round(winner.rating,6),
                    "preLoserElo":round(loser.rating,6),
                    "winnerProbability":round(p_winner,7),
                    "scoreMargin":margin,
                    "venue":game.winner_location,
                    "homeAdvantageElo":venue,
                    "effectiveK":round(effective_k,5),
                    "winnerDelta":round(delta,5),
                    "loserDelta":round(-delta,5),
                }
                pending.append((winner, loser, delta, receipt))
            # All predictions and movements have been calculated using the
            # start-of-date ratings, including games involving the same team.
            for winner, loser, delta, receipt in pending:
                winner.rating += delta
                loser.rating -= delta
                winner.wins += 1
                loser.losses += 1
                winner.history.append(winner.rating)
                loser.history.append(loser.rating)
                self.game_receipts.append(receipt)
                self.team_receipts.setdefault(winner.team_id, []).append(receipt)
                self.team_receipts.setdefault(loser.team_id, []).append(receipt)
            self.last_day = day
        if self.game_receipts:
            movement = sum(x.rating - 1500 for x in self.states.values())
            if not math.isclose(movement, 0.0, abs_tol=1e-7):
                raise ValueError("Elo zero-sum rating conservation failed")
        return self

    def paired_summary(self, classic: "GameAwareEloEngine") -> dict:
        """Descriptive date-frozen comparison, not a prospective promotion gate."""
        if len(self.pregame_brier) != len(classic.pregame_brier):
            raise ValueError("Elo cohorts differ")
        enhanced = self.brier_score()
        control = classic.brier_score()
        return {
            "schemaVersion":1, "method":"Paired previous-date-only Elo replay",
            "evaluatedGames":len(self.pregame_brier),
            "enhancedBrier":round(enhanced,6) if enhanced is not None else None,
            "classicBrier":round(control,6) if control is not None else None,
            "enhancedAccuracy":round(self.pregame_accuracy_score(),6)
                if self.pregame_accuracy else None,
            "classicAccuracy":round(classic.pregame_accuracy_score(),6)
                if classic.pregame_accuracy else None,
            "enhancedBrierGain":round(control-enhanced,6)
                if control is not None and enhanced is not None else None,
            "caveat":"Retrospective date-frozen results, NOT actual timestamped pre-tipoff forecasts; score-margin weighting is not proven to improve future accuracy.",
        }
