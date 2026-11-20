"""Recent ESPN-confirmed men's NCAA basketball finals for the daily website.

This is a separate *display* stream, not the rating training source and not a
substitute for a dual-verified forecast settlement. It exposes final games
while the NCAA-derived SportsDataverse CSV may lag behind.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .live import FIRST_DATE, REGULAR_SEASON_CUTOFF
from .reference import canonical
from .snapshot import (_one_team, independently_verified_finals, parse_time,
                       retrieve_fixture, ESPN_BASE)

EASTERN = ZoneInfo("America/New_York")
LOOKBACK_DAYS = 4
MAX_PUBLIC_RESULTS = 150


def _source_label(side: dict) -> str | None:
    info = side.get("team")
    if not isinstance(info, dict):
        return None
    for key in ("location", "shortDisplayName", "displayName"):
        label = str(info.get(key) or "").strip()
        if label:
            return label[:110]
    return None


def build_finals(scoreboards: list[dict], ratings: dict, ncaa_games: list[dict],
                 captured_at: datetime, unavailable_dates: list[str] | None = None,
                 requested_days: int = LOOKBACK_DAYS,
                 result_limit: int | None = MAX_PUBLIC_RESULTS) -> dict:
    """Return source-confirmed finals without inferring NCAA-score coverage.

    Only ESPN STATUS_FINAL with completed=true and positive unequal integer
    scores is accepted. NCAA inclusion requires a unique independently
    verified school identity, same scheduled Eastern date, home/away
    designation AND identical scores. Unknown ESPN team IDs are not guessed.
    """
    if captured_at.tzinfo is None:
        raise ValueError("Capture time must be timezone-aware")
    if ratings.get("mode") != "current" or ratings.get("season") != 2027:
        raise ValueError("Finals report requires a sourced 2027 season")
    if not isinstance(ncaa_games, list) or not isinstance(scoreboards, list):
        raise ValueError("Finals inputs must be lists")
    now = captured_at.astimezone(timezone.utc)
    today = now.astimezone(EASTERN).date()
    if not isinstance(requested_days,int) or requested_days < 1 or requested_days > 14:
        raise ValueError("A bounded recent-finals lookback is required")
    earliest = today - timedelta(days=requested_days-1)
    if result_limit is not None and (not isinstance(result_limit,int) or result_limit < 1):
        raise ValueError("Invalid ESPN final display/result limit")

    name_index: dict[str, list[dict]] = defaultdict(list)
    id_index: dict[str, list[dict]] = defaultdict(list)
    for team in ratings["teams"]:
        name_index[canonical(team["name"])].append(team)
        if team.get("espnSourceTeamId"):
            id_index[str(team["espnSourceTeamId"])].append(team)

    accepted: dict[tuple[str, str, str, int, int], int] = defaultdict(int)
    rating_inputs: dict[tuple[str, str, str, int, int], int] = defaultdict(int)
    for game in ncaa_games:
        key = (game["date"], game["home"], game["away"],
               game["homeScore"], game["awayScore"])
        rating_inputs[key] += 1
        if game.get("source", "NCAA-derived schedule") == "NCAA-derived schedule":
            accepted[key] += 1

    found: dict[str, dict] = {}
    for board in scoreboards:
        if not isinstance(board, dict) or not isinstance(board.get("events"), list):
            raise ValueError("ESPN scoreboard response missing events list")
        verified = independently_verified_finals([board])
        for event in board["events"]:
            eid = str(event.get("id") or "").strip()
            source = verified.get(eid)
            if source is None:
                continue
            day = date.fromisoformat(source["date"])
            if not max(FIRST_DATE,earliest) <= day <= min(today,REGULAR_SEASON_CUTOFF):
                continue
            competitions = event.get("competitions") or []
            if len(competitions) != 1:
                continue
            sides = competitions[0].get("competitors") or []
            h = [x for x in sides if x.get("homeAway") == "home"]
            a = [x for x in sides if x.get("homeAway") == "away"]
            if len(h) != 1 or len(a) != 1:
                continue
            home, away = h[0], a[0]
            home_record = _one_team(home, name_index, id_index)
            away_record = _one_team(away, name_index, id_index)
            name_h = home_record["name"] if home_record else _source_label(home)
            name_a = away_record["name"] if away_record else _source_label(away)
            if not name_h or not name_a or canonical(name_h) == canonical(name_a):
                continue
            scores = (source["homeScore"], source["awayScore"])
            # An exact NCAA tie-in is evidence of a rating input, whereas a
            # missing crosswalk or differing home designation is inconclusive.
            eligible = bool(home_record and away_record and
                            home_record["teamId"] != away_record["teamId"])
            home_espn_id = str((home.get("team") or {}).get("id") or "")
            away_espn_id = str((away.get("team") or {}).get("id") or "")
            # Stricter than fallback name matching: only an actual
            # provider-authored same-season ESPN ID can feed new Elo games.
            id_linked = bool(eligible and home_espn_id and away_espn_id and
                str(home_record.get("espnSourceTeamId") or "") == home_espn_id and
                str(away_record.get("espnSourceTeamId") or "") == away_espn_id)
            key = (source["date"], name_h, name_a, *scores)
            included = eligible and accepted.get(key, 0) == 1
            # NCAA may still lag even after the Elo pipeline has used a
            # strictly ESPN-final+ID-verified result. Keep these separate.
            rating_included = eligible and rating_inputs.get(key, 0) == 1
            public = {
                "eventId": eid, "date":source["date"],
                "scheduledStartUtc":parse_time(event["date"]).isoformat().replace("+00:00", "Z"),
                "home":name_h, "away":name_a,
                "homeScore":scores[0], "awayScore":scores[1],
                "winner":name_h if scores[0] > scores[1] else name_a,
                "status":"ESPN-final",
                "ncaaRatingInputConfirmed":included,
                "eloRatingInputConfirmed":rating_included,
                "ncaaIdentityMatchConfirmed":eligible,
                "espnIdentityIdsMatch":id_linked,
                "homeEspnTeamId":home_espn_id,
                "awayEspnTeamId":away_espn_id,
                "proof":"ESPN STATUS_FINAL and completed=true with final scores",
            }
            previous = found.get(eid)
            if previous is not None and previous != public:
                raise ValueError("Conflicting ESPN final records for event " + eid)
            found[eid] = public

    all_rows = sorted(found.values(), key=lambda x:(x["date"],x["scheduledStartUtc"],x["eventId"]),
                      reverse=True)
    warnings = list(unavailable_dates or [])
    status = ("source-unavailable" if not scoreboards else
              "source-partial" if warnings else "source-ready")
    return {
        "schemaVersion":1,"season":2027,"type":"ESPN-recent-final-scoreboard",
        "status":status,
        "generatedAtUtc":now.isoformat().replace("+00:00","Z"),
        "ratingRetrievedAtUtc":ratings["retrievedAtUtc"],
        "ncaaResultsThroughDate":ratings["lastGameDate"],
        "source":ESPN_BASE,
        "lookbackDays":requested_days,
        "boardDaysRetrieved":len(scoreboards),
        "sourceWarnings":warnings,
        "confirmedFinalCount":len(found),
        "ncaaRatingInputMatched":sum(bool(g["ncaaRatingInputConfirmed"]) for g in found.values()),
        "eloRatingInputMatched":sum(bool(g["eloRatingInputConfirmed"]) for g in found.values()),
        "mostRecentEspnFinalDate":all_rows[0]["date"] if all_rows else None,
        "games":all_rows if result_limit is None else all_rows[:result_limit],
        "limitations":[
            "Only ESPN-confirmed completed finals are displayed. Some dates may be missing when ESPN is unavailable.",
            "Elo, team records and research train from the accepted NCAA score stream plus strictly ESPN-final+same-season-ID-verified supplemental games, deduplicated by team pair/date/score.",
            "A game without an exact NCAA pair/date/score match is marked not confirmed in rating source, not treated as an erroneous result.",
            "Independent forecast settlement still requires both ESPN final status and the exact NCAA score matching the earliest archived before-tipoff pick.",
            "The listed game time originates from ESPN; it is not a guaranteed independently verified actual tipoff.",
            "All data is refreshed by scheduled GitHub Pages builds; this is not live streaming.",
        ]
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ratings",type=Path,default=Path("web/public/current/2027.json"))
    parser.add_argument("--games",type=Path,default=Path("web/public/current/2027-games.json"))
    parser.add_argument("--scoreboards-json",type=Path,
                        help="Offline JSON array of scoreboard fixtures; no network")
    parser.add_argument("--out",type=Path,default=Path("web/public/current/recent-finals.json"))
    args = parser.parse_args()
    ratings = json.loads(args.ratings.read_text(encoding="utf-8"))
    ncaa = json.loads(args.games.read_text(encoding="utf-8"))
    if (ncaa.get("season") != 2027 or
        ncaa.get("retrievedAtUtc") != ratings.get("retrievedAtUtc")):
        raise ValueError("NCAA accepted game and rating timestamps differ")

    now=datetime.now(timezone.utc)
    warnings=[]
    if args.scoreboards_json:
        boards=json.loads(args.scoreboards_json.read_text(encoding="utf-8"))
    else:
        boards=[]
        eastern_today=now.astimezone(EASTERN).date()
        for day in [eastern_today-timedelta(days=i) for i in range(LOOKBACK_DAYS)]:
            try:
                boards.append(retrieve_fixture(day))
            except (OSError,TimeoutError,ValueError) as exc:
                warnings.append(f"{day.isoformat()}: {exc}")
        if warnings:
            print("WARNING: Recent ESPN finals feed partially unavailable; omitted dates will not be fabricated: "+"; ".join(warnings))
    try:
        report=build_finals(boards,ratings,ncaa["games"],now,warnings)
    except ValueError as exc:
        if args.scoreboards_json:
            # Offline tests and fixtures fail closed on inconsistent inputs.
            raise
        # A malformed *optional* ESPN scoreboard must not stop the primary
        # validated NCAA/Elo site from publishing. Withhold only this panel
        # and report the problem; never publish a guessed score.
        print(f"WARNING: ESPN recent-finals integrity check failed: {exc}")
        report=build_finals([],ratings,ncaa["games"],now,
                            [*warnings,f"ESPN final-source integrity error: {exc}"])
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(f"ESPN daily scoreboard: {report['confirmedFinalCount']} final games "
          f"across {report['boardDaysRetrieved']}/{LOOKBACK_DAYS} requested days; "
          f"NCAA-Elo source pair confirmed for {report['ncaaRatingInputMatched']}")

if __name__=="__main__":
    main()
