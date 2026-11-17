"""Deterministic gradient-boosted probability corrections over Elo.

Weak learners are regularized decision stumps fit by Newton log-loss gain.
Every historical training sample is presented both as winner (x,1) and as
loser (-x,0), preventing a winner-oriented training target from becoming
trivially all-positive. Final prediction is anti-symmetrized so
P(A beats B) = 1 - P(B beats A) exactly.

This small explainable prototype competes with Elo on *later* years; there
is no claim it is stronger unless the held-out benchmark demonstrates it.
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Sequence
from .advanced import Features, sigmoid

BASE = math.log(10.0)
THRESHOLDS = (
    (-1.5, -0.75, 0.0, 0.75, 1.5),
    (-1.5, -0.5, 0.0, 0.5, 1.5),
    (-0.35, -0.15, 0.0, 0.15, 0.35),
)


@dataclass(frozen=True)
class Stump:
    feature: int
    threshold: float
    left: float
    right: float


@dataclass(frozen=True)
class BoostedModel:
    stumps: tuple[Stump, ...]
    learning_rate: float = 0.12

    def raw_logit(self, x: tuple[float, float, float]) -> float:
        score = BASE * x[0]
        for s in self.stumps:
            score += self.learning_rate * (s.left if x[s.feature] < s.threshold else s.right)
        return score

    def probability(self, feat: Features) -> float:
        x = feat.vector()
        inverse = tuple(-v for v in x)
        logit = (self.raw_logit(x) - self.raw_logit(inverse)) / 2.0
        return sigmoid(logit)


def train_boosted(examples: Sequence[Features], rounds: int = 14,
                  learning_rate: float = 0.12, ridge: float = 4.0,
                  min_leaf: int = 20) -> BoostedModel:
    if not examples:
        raise ValueError("Boosting requires earlier-season games")
    if not (1 <= rounds <= 200) or not (0 < learning_rate <= 1) or ridge <= 0 or min_leaf < 1:
        raise ValueError("Invalid boosting hyperparameters")
    inputs = [f.vector() for f in examples]
    rows = inputs + [tuple(-v for v in x) for x in inputs]
    labels = [1.0] * len(inputs) + [0.0] * len(inputs)
    logits = [BASE * x[0] for x in rows]
    stumps: list[Stump] = []
    for _ in range(rounds):
        grads = []
        hess = []
        for score, y in zip(logits, labels):
            p = sigmoid(score)
            grads.append(y - p)
            hess.append(max(1e-7, p * (1 - p)))
        gtotal, htotal = sum(grads), sum(hess)
        best = None
        best_gain = 0.0
        for dim in range(3):
            for threshold in THRESHOLDS[dim]:
                count = 0
                gl = hl = 0.0
                for x, g, h in zip(rows, grads, hess):
                    if x[dim] < threshold:
                        count += 1
                        gl += g
                        hl += h
                if count < min_leaf or len(rows) - count < min_leaf:
                    continue
                gr, hr = gtotal - gl, htotal - hl
                gain = gl * gl / (hl + ridge) + gr * gr / (hr + ridge)
                if gain > best_gain + 1e-12:
                    best_gain = gain
                    best = Stump(dim, threshold,
                                 max(-2.0, min(2.0, gl / (hl + ridge))),
                                 max(-2.0, min(2.0, gr / (hr + ridge))))
        if best is None:
            break
        stumps.append(best)
        for i, x in enumerate(rows):
            logits[i] += learning_rate * (best.left if x[best.feature] < best.threshold else best.right)
    return BoostedModel(tuple(stumps), learning_rate)
