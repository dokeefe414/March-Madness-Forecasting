"""March Forecast research engine: transparent, chronological Elo-based baselines."""

from .core import Game, EloEngine, matchup_probability, simulate_bracket

__all__ = ["Game", "EloEngine", "matchup_probability", "simulate_bracket"]
