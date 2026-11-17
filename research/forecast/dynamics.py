"""Online time-series regime signals derived only from already completed games.

This explicitly targets changing dynamics rather than a fixed full-season
average. The projection is bounded, deterministic, and never looks at future
games. It is a transparent signal baseline, not a hidden Kalman or deep model.
"""
from __future__ import annotations
import math
from typing import Sequence


def regime_features(history: Sequence[float], current: float | None = None) -> dict:
    values = [float(v) for v in history]
    if not values or any(not math.isfinite(v) for v in values):
        raise ValueError("Elo history must contain finite values")
    rating = float(values[-1] if current is None else current)
    if not math.isfinite(rating):
        raise ValueError("current rating must be finite")
    increments = [values[i]-values[i-1] for i in range(1,len(values))]
    if len(increments) < 3:
        return {"adaptiveRating": round(rating,4), "regimeShift":0.0,
                "volatility":0.0, "ewmaSlope":0.0, "gamesObserved":len(increments),
                "sampleStatus":"insufficient"}
    recent = increments[-6:]
    mean = sum(recent)/len(recent)
    variance = sum((v-mean)**2 for v in recent)/len(recent)
    volatility = math.sqrt(variance)
    ema = increments[0]
    for value in increments[1:]:
        ema = .4*value + .6*ema
    latest = sum(increments[-3:])/3
    earlier = sum(increments[-6:-3])/max(len(increments[-6:-3]),1) if len(increments)>=6 else mean
    shift = latest-earlier
    # Shrink early form signals and high-variance regimes. This is a
    # sensitivity baseline, not an optimized win-probability estimator.
    shrink = min(1.0,len(increments)/10.0)
    adjustment = (2.5*ema+.8*shift)*shrink/(1+volatility/20)
    adjustment = max(-24.0,min(24.0,adjustment))
    return {
        "adaptiveRating":round(rating+adjustment,4),
        "regimeShift":round(shift,4),
        "volatility":round(volatility,4),
        "ewmaSlope":round(ema,4),
        "gamesObserved":len(increments),
        "sampleStatus":"higher" if len(increments)>=10 else "limited",
    }
