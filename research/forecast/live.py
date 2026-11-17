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
from .reference import TEAM_URL, parse_directory, annotate_teams
from .efficiency import BOX_URL, attach_efficiency
from .selection import build_watchlist

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


def parse_source_date(raw: str) -> date:
    """Parse the provider's ISO or U.S. month/day/year published date.

    SportsDataverse's 2027 CSV currently publishes dates like 11/07/2026,
    while some producer versions use ISO 2026-11-07. Both map to the same
    date; ambiguous day/month guessing is deliberately prohibited.
    """
    token = str(raw or "").strip()[:10]
    try:
        return date.fromisoformat(token)
    except ValueError:
        try:
            return datetime.strptime(token, "%m/%d/%Y").date()
        except ValueError as exc:
            raise ValueError(f"Unrecognized NCAA game_date {raw!r}") from exc


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
        game_date = parse_source_date(row["game_date"])
        if game_date < FIRST_DATE or game_date > min(as_of, REGULAR_SEASON_CUTOFF):
            continue
        home, away = str(row["home"] or "").strip(), str(row["away"] or "").strip()
        if not home or not away or home.casefold() == away.casefold():
            raise ValueError("schedule contains missing or duplicate opponents")
        try:
            home_score, away_score = int(row["home_score"]), int(row["away_score"])
        except (TypeError, ValueError):
            continue  # future/scheduled games are not results
        # The upstream NCAA schedule includes partially populated scoreboards
        # (including 0-x and tied scores) for games that are not confirmed
        # finals. An NCAA basketball game has no tied final. Skip these rather
        # than manufacturing a completed result; malformed negative scores
        # still fail rather than being treated as missing data.
        if home_score < 0 or away_score < 0:
            raise ValueError(f"negative score in contest {row['contest_id']}")
        if home_score == 0 or away_score == 0 or home_score == away_score:
            continue
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
                  url: str = SOURCE_URL, directory_csv: str | None = None,
                  box_csv: str | None = None) -> dict:
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
    directory_report = {
        "source": TEAM_URL, "status": "unavailable", "matchedRatedTeams": 0,
        "ratedTeams": len(rows), "policy": "No conference match without source crosswalk.",
    }
    for row in rows:
        row["conference"] = None
        row["conferenceVerified"] = False
    if directory_csv is not None:
        directory_report = annotate_teams(rows, parse_directory(directory_csv))
        directory_report["status"] = "ready"

    efficiency_report = {
        "source": BOX_URL, "status": "unavailable",
        "matchedTeamGames": 0, "teamsWithMetrics": 0,
        "policy": "No possession metrics without verified team box rows.",
    }
    if box_csv is not None:
        efficiency_report = attach_efficiency(rows, games, box_csv)
        efficiency_report["status"] = "ready" if efficiency_report["matchedTeamGames"] else "empty"

    watchlist = build_watchlist(rows, games[-1]["date"])
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
        "pregameDiagnostics": {
            "evaluatedGames": len(engine.pregame_brier),
            "brier": round(engine.brier_score(), 6),
            "accuracy": round(engine.pregame_accuracy_score(), 6),
            "coinFlipBrier": 0.25,
            "method": "Retrospective sequential Elo pregame evaluation before each game's update",
            "caveat": "Not timestamped published pregame picks; same-day tip-off order is approximate.",
        },
        "teams": rows,
        "identityCoverage": directory_report,
        "efficiencyCoverage": efficiency_report,
        "selectionWatchlist": watchlist,
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
    parser.add_argument("--input", type=Path, help="Offline schedule CSV/CSV.gz fixture (no network)")
    parser.add_argument("--directory-input", type=Path, help="Offline NCAA team crosswalk CSV/CSV.gz")
    parser.add_argument("--box-input", type=Path, help="Offline team box CSV/CSV.gz")
    parser.add_argument("--skip-supplemental", action="store_true", help="For offline baselines only")
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
    def read_fixture(path: Path) -> str:
        raw = path.read_bytes()
        return (gzip.decompress(raw) if raw[:2] == b"\x5cx1f\x5cx8b" else raw).decode("utf-8-sig")

    def supplemental(path: Path | None, source_url: str, label: str) -> str | None:
        if args.skip_supplemental:
            return None
        if path is not None:
            return read_fixture(path)
        if args.input is not None:
            # An offline run never implicitly downloads unrelated sources.
            return None
        try:
            return fetch_csv(source_url)
        except (OSError, ValueError) as exc:
            print(f"Supplemental {label} unavailable: {exc}. Publishing a disclosed missing-data state.")
            return None

    directory_csv = supplemental(args.directory_input, TEAM_URL, "identity")
    box_csv = supplemental(args.box_input, BOX_URL, "team box")
    try:
        output = build_current(games, url=origin,
                               directory_csv=directory_csv, box_csv=box_csv)
    except ValueError as exc:
        # Refuse to label uncertain source identity as verified. Keep real
        # score-derived Elo available, but expose empty supplemental coverage.
        print(f"Supplemental crosswalk/box validation failed: {exc}. No inferred identity or efficiency data.")
        output = build_current(games, url=origin)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"Published {len(games)} confirmed NCAA-source games, "
          f"{len(output['teams'])} teams, through {output['lastGameDate']}")
    print(f"Conference-matched programs: {output['identityCoverage'].get('matchedRatedTeams', 0)}; "
          f"possession rows: {output['efficiencyCoverage'].get('matchedTeamGames', 0)}; "
          f"watchlist: {output['selectionWatchlist']['status']}")
    print(f"Current-season snapshot: {args.out}")


if __name__ == "__main__":
    main()
