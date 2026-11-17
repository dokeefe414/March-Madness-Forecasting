"""Rebuild every available men's historical season from pinned Kaggle CSV files.

Usage:
  PYTHONPATH=research python -m forecast.history --data-dir research/data/raw

Outputs readable, provenance-labeled snapshots, a compact year index, and
tournament results. No generated JSON claims to be a 2027 forecast.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from .core import EloEngine, Game, forecast_rating, matchup_probability
from .io import read_team_names, write_json

SOURCE_COMMIT = "f8c521735ec41580711ce2d3e27dfd40f24e9e29"
SOURCE_URL = (
    "https://github.com/Andreachurchwell/march-madness-bracket-simulator/"
    f"tree/{SOURCE_COMMIT}/data/raw"
)

# 2026 supplemental source uses public-facing labels instead of Kaggle IDs.
# This is the 64-team main draw only (63 games); the four First Four games
# are NOT in this file. It is not suitable as a complete tourney backtest.
ALIASES_2026 = {
    "Iowa State": "Iowa St",
    "Kennesaw State": "Kennesaw",
    "Long Island": "LIU Brooklyn",
    "St. John's": "St John's",
    "Michigan St.": "Michigan St",
    "North Dakota St.": "N Dakota St",
    "PVAMU": "Prairie View",
    "Utah St.": "Utah St",
    "Kennesaw St.": "Kennesaw",
    "Queens (N.C.)": "Queens NC",
    "Wright St.": "Wright St",
    "Iowa St.": "Iowa St",
    "Tennessee St.": "Tennessee St",
    "McNeese": "McNeese St",
    "Miami (FL)": "Miami FL",
    "Miami (OH)": "Miami OH",
    "Michigan State": "Michigan St",
    "North Dakota State": "N Dakota St",
    "Ohio State": "Ohio St",
    "Prairie View A&M": "Prairie View",
    "Queens (NC)": "Queens NC",
    "Saint Louis": "St Louis",
    "Saint Mary's": "St Mary's CA",
    "Tennessee State": "Tennessee St",
    "UConn": "Connecticut",
    "Utah State": "Utah St",
    "Wright State": "Wright St",
}


def read_csv(path: Path, mandatory: set[str]) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        missing = mandatory - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"{path.name} missing columns: {sorted(missing)}")
        return list(reader)


def load_games(path: Path) -> dict[int, list[Game]]:
    fields = {"Season", "DayNum", "WTeamID", "WScore", "LTeamID", "LScore", "WLoc"}
    grouped: dict[int, list[Game]] = defaultdict(list)
    for row in read_csv(path, fields):
        year = int(row["Season"])
        grouped[year].append(Game(
            season=year,
            day_num=int(row["DayNum"]),
            winner=int(row["WTeamID"]),
            loser=int(row["LTeamID"]),
            winner_score=int(row["WScore"]),
            loser_score=int(row["LScore"]),
            winner_location=row["WLoc"],
        ))
    return dict(grouped)


def load_seeds(path: Path) -> dict[int, dict[int, str]]:
    grouped: dict[int, dict[int, str]] = defaultdict(dict)
    for row in read_csv(path, {"Season", "Seed", "TeamID"}):
        grouped[int(row["Season"])][int(row["TeamID"])] = row["Seed"]
    return dict(grouped)


def map_2026_name(name: str, id_by_name: dict[str, int]) -> int:
    canonical = ALIASES_2026.get(name.strip(), name.strip())
    try:
        return id_by_name[canonical.casefold()]
    except KeyError as exc:
        raise ValueError(f"Unrecognized 2026 tournament team {name!r}; update aliases") from exc


def load_2026_supplement(data_dir: Path, id_by_name: dict[str, int]) -> tuple[list[dict], dict[int, str]]:
    results_path = data_dir / "2026_bracket_results.csv"
    bracket_path = data_dir / "bracket_2026.csv"
    if not (results_path.exists() and bracket_path.exists()):
        return [], {}
    results = read_csv(
        results_path, {"round", "region", "team1", "team2", "team1_score", "team2_score", "winner"}
    )
    games = []
    for row in results:
        a = map_2026_name(row["team1"], id_by_name)
        b = map_2026_name(row["team2"], id_by_name)
        winner = map_2026_name(row["winner"], id_by_name)
        score_a, score_b = int(row["team1_score"]), int(row["team2_score"])
        if winner not in (a, b) or a == b or score_a == score_b:
            raise ValueError(f"Invalid 2026 game {row}")
        if (score_a > score_b) != (winner == a):
            raise ValueError(f"2026 winner-score mismatch: {row}")
        games.append({
            "round": row["round"],
            "region": row["region"],
            "winnerId": str(winner),
            "loserId": str(b if winner == a else a),
            "winnerScore": max(score_a, score_b),
            "loserScore": min(score_a, score_b),
        })
    seed_rows = read_csv(bracket_path, {"region", "seed", "team"})
    seeds = {
        map_2026_name(row["team"], id_by_name): f"{row['region']} {int(row['seed']):02}"
        for row in seed_rows
    }
    if len(games) != 63 or len(seeds) != 64 or games[-1]["round"] != "Championship":
        raise ValueError("Unexpected 2026 main-draw coverage; cannot publish it as complete")
    return games, seeds


def build_history(
    data_dir: Path,
    output_dir: Path,
    default_season: int = 2025,
) -> dict:
    data_dir, output_dir = Path(data_dir), Path(output_dir)
    names = read_team_names(data_dir)
    id_by_name = {name.casefold(): team_id for team_id, name in names.items()}
    regular = load_games(data_dir / "MRegularSeasonCompactResults.csv")
    tournament = load_games(data_dir / "MNCAATourneyCompactResults.csv")
    seeds = load_seeds(data_dir / "MNCAATourneySeeds.csv")
    supplement_2026, supplement_seeds = load_2026_supplement(data_dir, id_by_name)
    if supplement_seeds:
        seeds[2026] = supplement_seeds

    entries = []
    for year in sorted(regular):
        year_games = regular[year]
        if not year_games:
            continue
        model = EloEngine().fit(year_games, names)
        cutoff = model.last_day
        complete = cutoff == 132
        if cutoff is None:
            continue
        rows = model.rankings()
        for row in rows:
            seed = seeds.get(year, {}).get(int(row["teamId"]))
            if seed:
                row["seed"] = seed

        historical = sorted(
            tournament.get(year, []),
            key=lambda g: (g.day_num, g.winner, g.loser)
        )
        scored, squared_error, correct, missing = 0, 0.0, 0.0, 0
        public_games = []
        for game in historical:
            w = model.states.get(game.winner)
            l = model.states.get(game.loser)
            if w is None or l is None:
                missing += 1
            else:
                probability = matchup_probability(forecast_rating(w), forecast_rating(l))
                squared_error += (1.0 - probability) ** 2
                correct += 1.0 if probability > 0.5 else 0.5 if probability == 0.5 else 0
                scored += 1
            public_games.append({
                "day": game.day_num,
                "winnerId": str(game.winner),
                "loserId": str(game.loser),
                "winnerScore": game.winner_score,
                "loserScore": game.loser_score,
            })
        if year == 2026 and supplement_2026:
            public_games = supplement_2026
            champion_id = int(supplement_2026[-1]["winnerId"])
        else:
            champion_id = historical[-1].winner if historical else None

        champion = names.get(champion_id) if champion_id is not None else None
        if year == 2026 and supplement_2026:
            champion = "Michigan"  # independently confirmed by NCAA, April 6, 2026
        tournament_meta = {
            "champion": champion,
            "championId": str(champion_id) if champion_id is not None else None,
            "games": len(public_games) if year == 2026 else len(historical),
            "evaluatedGames": scored,
            "missingTeams": missing,
            "brier": round(squared_error / scored, 4) if scored else None,
            "accuracy": round(correct / scored, 4) if scored else None,
            "source": (
                "Community 2026 64-team main-draw results; four First Four games excluded"
                if year == 2026 and supplement_2026 else
                "No NCAA tournament held" if year == 2020 else
                "Kaggle historical NCAA tournament compact results"
            ),
            "mainDrawOnly": year == 2026 and bool(supplement_2026),
        }
        snapshot = {
            "mode": "historical",
            "season": year,
            "throughDay": cutoff,
            "isComplete": complete,
            "regularSeasonGames": len(year_games),
            "label": (
                f"{year} men's NCAA basketball — through Selection Sunday"
                if complete else f"{year} men's NCAA basketball — through Kaggle day {cutoff} (incomplete source)"
            ),
            "source": "Kaggle March Machine Learning Mania men's CSVs (public mirror, pinned commit)",
            "sourceUrl": SOURCE_URL,
            "sourceCommit": SOURCE_COMMIT,
            "method": "Elo k=24, home adjustment=65, bounded recent Elo trend (v0.1); not a trained time-series model",
            "tournament": tournament_meta,
            "teams": rows,
        }
        write_json(output_dir / "public" / "seasons" / f"{year}.json", snapshot)
        public_tournament = {
            "season": year,
            "champion": champion,
            "mainDrawOnly": year == 2026 and bool(supplement_2026),
            "teams": {str(id_): names[id_] for id_ in
                      sorted({int(game["winnerId"]) for game in public_games} |
                             {int(game["loserId"]) for game in public_games})},
            "games": public_games,
        }
        write_json(output_dir / "public" / "tournaments" / f"{year}.json", public_tournament)
        if year == default_season:
            write_json(output_dir / "data" / "rankings.json", snapshot)
        entries.append({
            "season": year, "throughDay": cutoff,
            "isComplete": complete, "regularSeasonGames": len(year_games),
            "teams": len(rows), "champion": champion,
            "tournamentGames": len(public_games),
            "tournamentBrier": tournament_meta["brier"],
        })
    if not any(e["season"] == default_season for e in entries):
        raise ValueError(f"default season {default_season} not available")
    index = {
        "source": "Kaggle March Machine Learning Mania men's data (pinned community mirror)",
        "sourceCommit": SOURCE_COMMIT,
        "firstSeason": entries[0]["season"],
        "lastSeason": entries[-1]["season"],
        "seasons": entries,
    }
    write_json(output_dir / "data" / "history-index.json", index)
    return index


def main() -> None:
    parser = argparse.ArgumentParser(description="Export all available historical seasons")
    parser.add_argument("--data-dir", type=Path, default=Path("research/data/raw"))
    parser.add_argument("--out-dir", type=Path, default=Path("web"))
    parser.add_argument("--default-season", type=int, default=2025)
    args = parser.parse_args()
    summary = build_history(args.data_dir, args.out_dir, args.default_season)
    print(f"Wrote {len(summary['seasons'])} seasons ({summary['firstSeason']}–{summary['lastSeason']}); "
          f"default season: {args.default_season}")


if __name__ == "__main__":
    main()
