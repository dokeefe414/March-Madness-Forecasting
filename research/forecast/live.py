"""Build independently sourced 2026–27 men's basketball ratings from real final scores.

Source: SportsDataverse NCAA stats-derived schedule CSV release.
https://github.com/sportsdataverse/sportsdataverse-data/releases/tag/ncaa_mbb_schedule

All dates, scores and teams come from the feed. This pipeline explicitly does
not invent an NCAA tournament field, seed, pace, possession count, or forecast.
No crosswalk to the historical Kaggle team ID space is assumed.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from .core import EloEngine, Game

SOURCE_URL = (
    "https://github.com/sportsdataverse/sportsdataverse-data/releases/download/"
    "ncaa_mbb_schedule/ncaa_mbb_schedule_2027.csv.gz"
)
SEASON = 2027
# Freeze at the expected Selection Sunday boundary; the actual tournament
# bracket cannot be simulated with *pre-tournament* features after postseason.
REGULAR_SEASON_CUTOFF = date(2027, 3, 14)
FIRST_DATE = date(2026, 11, 1)
MAX_DOWNLOAD_BYTES = 12_000_000
NEEDED = {"contest_id", "game_date", "home", "away", "home_score", "away_score", "season"}


def final_games(csv_text: str, as_of: date | None = None) -> list[dict]:
    """Strict parse: only completed scores, chronological, unique contest IDs.

    Schedules with no scores are intentionally skipped; duplicate final-score
    rows are de-duplicated, but conflicting values abort the ingestion.
    """
    as_of = as_of or datetime.now(timezone.utc).date()
    reader = csv.DictReader(io.StringIO(csv_text))
    missing = NEEDED - set(reader.fieldnames or ())
    if missing:
        raise ValueError(f"NCAA schedule missing required columns: {sorted(missing)}")
    seen: dict[str, dict] = {}
    for row in reader:
        if str(row["season"]).strip() != str(SEASON):
            continue
        game_date = date.fromisoformat(row["game_date"].strip()[:10])
        if game_date < FIRST_DATE or game_date > min(as_of, REGULAR_SEASON_CUTOFF):
            continue
        home, away = str(row["home"] or "").strip(), str(row["away"] or "").strip()
        if not home or not away or home.casefold() == away.casefold():
            raise ValueError("schedule contains missing or duplicate opponents")
        try:
            home_score, away_score = int(row["home_score"]), int(row["away_score"])
        except (TypeError, ValueError):
            continue  # future/scheduled games are not results
        if home_score == away_score == 0:
            continue
        if home_score < 1 or away_score < 1 or home_score == away_score:
            raise ValueError(f"invalid final score in contest {row['contest_id']}")
        game_id = str(row["contest_id"] or "").strip()
        if not game_id:
            raise ValueError("missing NCAA contest_id")
        game = {
            "id": game_id,
            "date": game_date.isoformat(),
            "home": home, "away": away,
            "homeScore": home_score, "awayScore": away_score,
        }
        if game_id in seen and seen[game_id] != game:
            raise ValueError(f"conflicting duplicate contest {game_id}")
        seen[game_id] = game
    return sorted(seen.values(), key=lambda g: (g["date"], g["id"]))


def build_current(games: list[dict], retrieved_at: datetime | None = None,
                  url: str = SOURCE_URL) -> dict:
    """Fit transparent, reset-at-season-start Elo; derive descriptive margins."""
    if not games:
        raise ValueError("no completed 2026–27 games; refusing to publish false live rankings")
    now = retrieved_at or datetime.now(timezone.utc)
    names = sorted({g["home"] for g in games} | {g["away"] for g in games}, key=str.casefold)
    name_to_id = {name: i + 1 for i, name in enumerate(names)}
    id_to_name = {i: name for name, i in name_to_id.items()}
    model_games = []
    points = defaultdict(lambda: [0, 0])
    opponents: dict[int, list[int]] = defaultdict(list)
    for index, g in enumerate(games):
        home_id, away_id = name_to_id[g["home"]], name_to_id[g["away"]]
        home_win = g["homeScore"] > g["awayScore"]
        winner, loser = (home_id, away_id) if home_win else (away_id, home_id)
        model_games.append(Game(
            season=SEASON,
            day_num=(date.fromisoformat(g["date"]) - FIRST_DATE).days,
            winner=winner, loser=loser,
            winner_score=max(g["homeScore"], g["awayScore"]),
            loser_score=min(g["homeScore"], g["awayScore"]),
            winner_location="H" if home_win else "A",
        ))
        points[home_id][0] += g["homeScore"]
        points[home_id][1] += g["awayScore"]
        points[away_id][0] += g["awayScore"]
        points[away_id][1] += g["homeScore"]
        opponents[home_id].append(away_id)
        opponents[away_id].append(home_id)
    # EloEngine sorts on (date, winner id, loser id), not actual tip-off;
    # same-day order is an approximation, disclosed prominently below.
    engine = EloEngine().fit(model_games, id_to_name)
    public_ids = {
        team_id: "ncaa-" + hashlib.sha256(name.encode("utf-8")).hexdigest()[:12]
        for team_id, name in id_to_name.items()
    }
    rating_by_id = {i: state.rating for i, state in engine.states.items()}
    rows = engine.rankings()
    for row in rows:
        internal_id = int(row["teamId"])
        row["teamId"] = public_ids[internal_id]
        played = len(opponents[internal_id])
        row["pointsForPerGame"] = round(points[internal_id][0] / played, 2)
        row["pointsAgainstPerGame"] = round(points[internal_id][1] / played, 2)
        row["marginPerGame"] = round(
            (points[internal_id][0] - points[internal_id][1]) / played, 2
        )
        row["opponentAverageElo"] = round(
            sum(rating_by_id[i] for i in opponents[internal_id]) / played, 1
        )
    return {
        "mode": "current", "season": SEASON, "throughDay": engine.last_day,
        "label": f"{SEASON} men's season / through {games[-1]['date']}",
        "isComplete": False, "regularSeasonGames": len(games),
        "source": "SportsDataverse NCAA men's basketball schedule (stats.ncaa.org derived)",
        "sourceUrl": url,
        "retrievedAtUtc": now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "lastGameDate": games[-1]["date"],
        "cutoffDate": REGULAR_SEASON_CUTOFF.isoformat(),
        "method": "Independent 2027 Elo (K=24, home=65) with bounded recent trend; uncalibrated for 2027",
        "sourceIdSpace": "NCAA team names (hashed IDs; NOT historical Kaggle IDs)",
        "isOfficialBracket": False,
        "teams": rows,
        "recentGames": list(reversed(games[-16:])),
        "limitations": [
            "NCAA-source schedule is a third-party published snapshot, not an instantaneous live feed.",
            "This models available scored games, including possible non-Division-I opponents; no field selection.",
            "Margin and opponent Elo are descriptive, not pace-adjusted or tournament-trained features.",
            "Team identity uses NCAA names; no unverified joins to historic Kaggle IDs.",
            "Same-day ordering is approximate; last game date and retrieval UTC do not certify real-time updates.",
        ],
    }


def fetch_csv(url: str = SOURCE_URL) -> str:
    request = Request(url, headers={"User-Agent": "MarchForecastResearch/0.5"})
    with urlopen(request, timeout=45) as response:
        raw = response.read(MAX_DOWNLOAD_BYTES + 1)
    if len(raw) > MAX_DOWNLOAD_BYTES:
        raise ValueError("source exceeded bounded download size")
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    if len(raw) > 90_000_000:
        raise ValueError("decompressed source exceeded size limit")
    return raw.decode("utf-8-sig")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="Offline CSV/CSV.gz fixture (no network)")
    parser.add_argument("--out", type=Path, default=Path("web/public/current/2027.json"))
    args = parser.parse_args()
    if args.input:
        raw = args.input.read_bytes()
        content = (gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw).decode("utf-8-sig")
        origin = f"local fixture {args.input.name}"
    else:
        content = fetch_csv()
        origin = SOURCE_URL
    games = final_games(content)
    output = build_current(games, url=origin)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"Published {len(games)} confirmed NCAA-source games, "
          f"{len(output['teams'])} teams, through {output['lastGameDate']}")
    print(f"Current-season snapshot: {args.out}")


if __name__ == "__main__":
    main()
