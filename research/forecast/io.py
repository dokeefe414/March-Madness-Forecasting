"""Load Kaggle March Machine Learning Mania compact men's CSV data."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .core import Game


def read_team_names(data_dir: Path) -> dict[int, str]:
    path = Path(data_dir) / "MTeams.csv"
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        require_columns(reader.fieldnames, {"TeamID", "TeamName"}, path)
        return {int(row["TeamID"]): row["TeamName"].strip() for row in reader}


def require_columns(actual: list[str] | None, required: set[str], path: Path) -> None:
    missing = required - set(actual or [])
    if missing:
        raise ValueError(f"{path} is missing columns: {', '.join(sorted(missing))}")


def read_regular_season(
    data_dir: Path, season: int, through_day: int | None = None
) -> list[Game]:
    path = Path(data_dir) / "MRegularSeasonCompactResults.csv"
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        require_columns(
            reader.fieldnames,
            {"Season", "DayNum", "WTeamID", "LTeamID", "WScore", "LScore", "WLoc"},
            path,
        )
        games = []
        for row in reader:
            if int(row["Season"]) != season:
                continue
            day = int(row["DayNum"])
            if through_day is not None and day > through_day:
                continue
            games.append(Game(
                season=season,
                day_num=day,
                winner=int(row["WTeamID"]),
                loser=int(row["LTeamID"]),
                winner_score=int(row["WScore"]),
                loser_score=int(row["LScore"]),
                winner_location=row["WLoc"].strip(),
            ))
        return sorted(games, key=lambda g: (g.day_num, g.winner, g.loser))


def write_json(destination: Path, data: dict) -> None:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
