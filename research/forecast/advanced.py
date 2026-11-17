"""Interpretable outcome-supervised basketball matchup model.

No opponent-seed or post-tournament features. Chronological caller controls the
training years; historical tournament outcomes supervise only *earlier* seasons.
Our three features represent base Elo strength, short-term form (difference
between projected and base Elo) and in-season win percentage. This is NOT a
possession-based efficiency model and does not use proprietary betting lines.
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Sequence

FEATURE_NAMES = ("elo_strength", "recent_form", "win_percentage")


@dataclass(frozen=True)
class Features:
    elo_diff: float
    trend_diff: float
    win_pct_diff: float = 0.0

    def vector(self) -> tuple[float, float, float]:
        if not all(math.isfinite(value) for value in
                   (self.elo_diff, self.trend_diff, self.win_pct_diff)):
            raise ValueError("features must be finite")
        return (self.elo_diff / 400.0,
                (self.trend_diff - self.elo_diff) / 40.0,
                self.win_pct_diff)


def sigmoid(value: float) -> float:
    if value >= 0.0:
        return 1.0 / (1.0 + math.exp(-value))
    e = math.exp(value)
    return e / (1.0 + e)


def train_logistic(
    past: Sequence[Features],
    iterations: int = 240,
    learning_rate: float = 0.3,
    ridge: float = 0.025,
) -> tuple[float, float, float]:
    """Fit a no-intercept logistic regression with L2 regularization.

    Features are oriented toward the observed winner. A symmetric training
    pair (x,1) and (-x,0) has the same average gradient as (x,1), so there is
    no target-class imbalance despite that storage convention. No intercept
    enforces P(A beats B) = 1 - P(B beats A). Entirely deterministic.
    """
    if not past:
        raise ValueError("at least one previous-season game is required")
    if iterations < 1 or not (0 < learning_rate <= 1) or not (0 <= ridge < 1):
        raise ValueError("invalid training configuration")
    rows = [example.vector() for example in past]
    weights = [math.log(10.0), 0.0, 0.0]  # regular Elo as sensible initialization
    n = len(rows)
    for _ in range(iterations):
        gradient = [0.0, 0.0, 0.0]
        for row in rows:
            residual = sigmoid(sum(a * b for a, b in zip(row, weights))) - 1.0
            for col in range(3):
                gradient[col] += residual * row[col]
        for col in range(3):
            weights[col] -= learning_rate * (gradient[col] / n + ridge * weights[col])
    if not all(math.isfinite(v) for v in weights):
        raise ArithmeticError("nonfinite fitted logistic weights")
    return (weights[0], weights[1], weights[2])


def predict(features: Features, weights: tuple[float, float, float]) -> float:
    if len(weights) != 3 or not all(math.isfinite(w) for w in weights):
        raise ValueError("expected exactly three finite model coefficients")
    return sigmoid(sum(a * b for a, b in zip(features.vector(), weights)))
