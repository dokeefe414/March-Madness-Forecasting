"""CLI: generate historical snapshots, evaluate pregame accuracy, simulate brackets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .core import EloEngine, simulate_bracket
from .io import read_regular_season, read_team_names, write_json


def main() -> None:
    parser = argparse.ArgumentParser(description="March Forecast chronological baseline")
    sub = parser.add_subparsers(dest="command", required=True)

    rank = sub.add_parser("rank", help="Export a historical ratings snapshot")
    rank.add_argument("--data-dir", type=Path, required=True)
    rank.add_argument("--season", type=int, required=True)
    rank.add_argument("--through-day", type=int)
    rank.add_argument("--out", type=Path, required=True)

    backtest = sub.add_parser("backtest", help="Score pre-game regular-season predictions")
    backtest.add_argument("--data-dir", type=Path, required=True)
    backtest.add_argument("--seasons", type=int, nargs="+", required=True)

    sim = sub.add_parser("simulate", help="Simulate supplied bracket order")
    sim.add_argument("--bracket", type=Path, required=True, help="JSON with entrants [{teamId, rating}]")
    sim.add_argument("--runs", type=int, default=10000)
    sim.add_argument("--seed", type=int, default=42)
    sim.add_argument("--out", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "rank":
        names = read_team_names(args.data_dir)
        games = read_regular_season(args.data_dir, args.season, args.through_day)
        if not games:
            parser.error("no games found for season / day filter")
        model = EloEngine().fit(games, names)
        output = {
            "mode": "historical",
            "season": args.season,
            "throughDay": model.last_day,
            "label": f"Historical {args.season} regular-season snapshot",
            "source": "Kaggle March Machine Learning Mania: MTeams + MRegularSeasonCompactResults",
            "method": "Elo + bounded recent-rating trend v0.1; neutral-site matchup odds",
            "teams": model.rankings(),
        }
        write_json(args.out, output)
        print(f"Wrote {len(output['teams'])} teams from {len(games)} games to {args.out}")
        print(f"Pre-game regular-season Brier: {model.brier_score():.4f}")
    elif args.command == "backtest":
        names = read_team_names(args.data_dir)
        for season in args.seasons:
            games = read_regular_season(args.data_dir, season)
            if not games:
                print(f"{season}: no games (skipped)")
                continue
            model = EloEngine().fit(games, names)
            print(f"{season}: games={len(games)}, pregame Brier={model.brier_score():.4f}")
        print("These are regular-season pre-game scores, NOT tournament validation.")
    else:
        payload = json.loads(args.bracket.read_text(encoding="utf-8"))
        entrants = [(str(row["teamId"]), float(row["rating"])) for row in payload["entrants"]]
        results = simulate_bracket(entrants, runs=args.runs, seed=args.seed)
        write_json(args.out, {"runs": args.runs, "seed": args.seed, "results": results})
        print(f"Wrote bracket simulation to {args.out}")


if __name__ == "__main__":
    main()
