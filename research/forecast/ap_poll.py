"""Immutable weekly AP Top 25 versus source-aware 2027 Elo research.

ESPN relays the men's AP poll. Compare poll ranks with a *game-date-frozen*
Elo replay (only results dated before that poll's source week). AP is not the
ground truth for winning games and never trains, promotes or grades any model.

First successful capture of a new source poll week is frozen in Git. A later
source correction or newly backfilled NCAA game may NOT rewrite earlier
comparisons. Importantly, 'game-date frozen' is not identical to knowing
precisely which statistics were published at the poll's release instant.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from .live import FIRST_DATE, REGULAR_SEASON_CUTOFF, build_current

SEASON = 2027
SCHEMA = 1
SOURCE = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/rankings?groups=50"
POLL_WEB = "https://www.espn.com/mens-college-basketball/rankings"
MAX_SOURCE_BYTES = 1_500_000
MIN_MATCHES = 20
MIN_RATED_D1 = 25


def fetch_poll() -> dict:
    request = Request(SOURCE, headers={
        "User-Agent": "MarchForecastResearch/1.0 (public rankings comparison)",
        "Accept": "application/json",
    })
    with urlopen(request, timeout=25) as response:
        raw = response.read(MAX_SOURCE_BYTES + 1)
    if len(raw) > MAX_SOURCE_BYTES:
        raise ValueError("AP rankings payload exceeds maximum source size")
    return json.loads(raw.decode("utf-8"))


def _week_date(raw: object) -> date:
    if not isinstance(raw, str) or len(raw) < 10:
        raise ValueError("Poll edition is missing an explicit source week date")
    day = date.fromisoformat(raw[:10])
    if not date(2026, 10, 1) <= day <= date(2027, 4, 12):
        raise ValueError("Poll edition outside 2026-27 season")
    return day


def extract_ap_poll(payload: dict, captured_at: datetime) -> dict:
    """Require exactly one actual men's AP poll and 25 unique provider IDs."""
    if captured_at.tzinfo is None:
        raise ValueError("AP capture clock must be timezone aware")
    if not isinstance(payload, dict):
        raise ValueError("AP response must be an object")
    season = payload.get("season")
    if isinstance(season, dict):
        season = season.get("year")
    if season is not None and int(season) != SEASON:
        raise ValueError("Poll source season does not match the 2027 season")
    polls = payload.get("rankings")
    if not isinstance(polls, list):
        raise ValueError("ESPN men's basketball rankings list is unavailable")
    ap = [p for p in polls if isinstance(p, dict) and (
        str(p.get("type", "")).lower() == "ap" or
        "ap top 25" in str(p.get("name", "")).lower() or
        str(p.get("shortName", "")).lower() == "ap poll"
    )]
    if len(ap) != 1:
        raise ValueError("Source must expose exactly one men's AP Top 25 poll")
    poll = ap[0]
    week = payload.get("latestWeek") or {}
    if not isinstance(week, dict):
        week = {}
    # ESPN's latestWeek.startDate is the source edition anchor, not a date
    # invented by this script. Poll-specific explicit date is a fallback.
    source_date = week.get("startDate") or poll.get("date")
    week_start = _week_date(source_date)
    if week_start > captured_at.date() + timedelta(days=1):
        raise ValueError("Source poll edition appears to be in the future")
    if (captured_at.date() - week_start).days > 16:
        raise ValueError("AP source poll edition is stale; refusing new snapshot")
    entries = poll.get("ranks")
    if not isinstance(entries, list) or len(entries) != 25:
        raise ValueError("AP Top 25 poll does not contain exactly 25 ranked schools")
    out = []
    seen = set()
    for row in entries:
        if not isinstance(row, dict):
            raise ValueError("Malformed AP poll row")
        rank = row.get("current")
        team = row.get("team")
        if isinstance(rank, bool) or not isinstance(rank, int) or not 1 <= rank <= 25:
            raise ValueError("AP Top 25 poll rank is invalid")
        if not isinstance(team, dict):
            raise ValueError("Missing ESPN poll team identity")
        team_id = str(team.get("id") or "").strip()
        name = str(team.get("displayName") or team.get("name") or "").strip()
        if not team_id.isdecimal() or not name:
            raise ValueError("AP team missing its source-authored ESPN ID")
        if team_id in seen:
            raise ValueError("Duplicate AP source ESPN school identity")
        seen.add(team_id)
        out.append({"apRank": rank, "espnTeamId": team_id,
                    "apName": name, "pollPoints": row.get("points")})
    out.sort(key=lambda t: t["apRank"])
    # A real AP Top 25 may contain ties (e.g. the November 16, 2026
    # poll tied Michigan and USC at #18, skipping #19). Preserve the
    # official competition-style ranks, rather than inventing rank 19.
    # For a tied group of k, the following rank must skip k-1 slots.
    i=0
    while i<len(out):
        rank=out[i]["apRank"]
        if rank!=i+1:
            raise ValueError("AP poll ranks violate competition ranking after a tie")
        j=i+1
        while j<len(out) and out[j]["apRank"]==rank:
            j+=1
        if j-i>1:
            points=[x["pollPoints"] for x in out[i:j]]
            if all(p is not None for p in points) and len({str(p) for p in points})!=1:
                raise ValueError("AP tied ranks have inconsistent vote point totals")
        i=j
    return {"sourceWeekStart": week_start.isoformat(),
            "sourceWeekNumber": (week.get("number") or
                                 (poll.get("occurrence") or {}).get("number")),
            "sourcePollName": poll.get("name") or "AP Top 25",
            "ranks": out}


def _average_ranks(values: list[int]) -> list[float]:
    """Standard Spearman tie handling: assign the mean occupied rank."""
    n=len(values)
    ordered=sorted(range(n),key=lambda i:(values[i],i))
    output=[0.0]*n
    start=0
    while start<n:
        stop=start+1
        while stop<n and values[ordered[stop]]==values[ordered[start]]:
            stop+=1
        average=(start+1+stop)/2
        for k in range(start,stop):
            output[ordered[k]]=average
        start=stop
    return output


def _spearman(pairs: list[tuple[int, int]]) -> float | None:
    """Pearson of matched-cohort average ranks, valid for actual AP ties."""
    n=len(pairs)
    if n<3:
        return None
    a=_average_ranks([p[0] for p in pairs])
    b=_average_ranks([p[1] for p in pairs])
    mean=(n+1)/2
    cov=sum((x-mean)*(y-mean) for x,y in zip(a,b))
    va=sum((x-mean)**2 for x in a)
    vb=sum((y-mean)**2 for y in b)
    if va<=0 or vb<=0:
        return None
    return round(cov/math.sqrt(va*vb),5)


def snapshot(poll: dict, current: dict, games: list[dict],
             captured_at: datetime) -> dict:
    """Replay the same Elo method through Sunday before AP's source week."""
    if (current.get("mode") != "current" or
        current.get("season") != SEASON or
        not current.get("eloMethodology", {}).get("version")):
        raise ValueError("Cannot compare AP to unverified current-season Elo")
    cutoff = date.fromisoformat(poll["sourceWeekStart"]) - timedelta(days=1)
    if cutoff > captured_at.date():
        raise ValueError("Cannot compare poll against future scores")
    earlier = [g for g in games if date.fromisoformat(g["date"]) <= cutoff]
    if not earlier:
        return _no_comparison(poll, current, captured_at, cutoff,
                              "No observed games before this poll's week")
    # Only use the same accepted scored games as the active 2027 model,
    # filtered by game date BEFORE the source poll edition began.
    replay = build_current(earlier, retrieved_at=captured_at)
    current_by_name = {t["name"]: t for t in current["teams"]}
    team_pool = []
    for team in replay["teams"]:
        source = current_by_name.get(team["name"])
        if (source and source.get("divisionIConfirmed") is True and
            str(source.get("espnSourceTeamId") or "").strip()):
            team_pool.append({
                "name": team["name"], "teamId": team["teamId"],
                "espnTeamId": str(source["espnSourceTeamId"]),
                "elo": float(team["rating"]),
                "games": int(team["wins"]) + int(team["losses"]),
            })
    team_pool.sort(key=lambda t: (-t["elo"], t["name"]))
    known_ids = set()
    ranks = {}
    ambiguous = set()
    for i, team in enumerate(team_pool):
        eid = team["espnTeamId"]
        if eid in known_ids:
            ambiguous.add(eid)
        known_ids.add(eid)
        ranks[eid] = {**team, "eloRank": i+1}
    for eid in ambiguous:
        ranks.pop(eid, None)
    elo_top25 = {t["espnTeamId"] for t in team_pool[:25]}
    records=[]
    for row in poll["ranks"]:
        team = ranks.get(row["espnTeamId"])
        records.append({
            "apRank": row["apRank"], "apName": row["apName"],
            "espnTeamId": row["espnTeamId"],
            "eloRank": team["eloRank"] if team else None,
            "elo": round(team["elo"],1) if team else None,
            "eloTeamName": team["name"] if team else None,
            "eloGames": team["games"] if team else None,
            "rankGap": (team["eloRank"]-row["apRank"]) if team else None,
            "eloTop25": bool(team and row["espnTeamId"] in elo_top25),
        })
    eligible = [r for r in records if r["eloRank"] is not None]
    n=len(eligible)
    sufficient = n >= MIN_MATCHES and len(team_pool) >= MIN_RATED_D1
    common25 = sum(r["eloTop25"] for r in eligible)
    ap10={r["espnTeamId"] for r in records[:10]}
    elo10={x["espnTeamId"] for x in team_pool[:10]}
    rho = _spearman([(r["apRank"],r["eloRank"]) for r in eligible])
    base={
        "pollKey":"AP-2027-"+poll["sourceWeekStart"],
        "sourceWeekStart":poll["sourceWeekStart"],
        "sourceWeekNumber":poll["sourceWeekNumber"],
        "capturedAtUtc":captured_at.astimezone(timezone.utc).isoformat().replace("+00:00","Z"),
        "eloGameCutoffDate":cutoff.isoformat(),
        "eloModelVersion":current["eloMethodology"]["version"],
        "sourcePollName":poll["sourcePollName"],
        "ncaaPlusEspnRatedGamesThroughCutoff":len(earlier),
        "divisionIRatedProgramsAtCutoff":len(team_pool),
        "matchedApTeams":n,
        "missingApTeams":25-n,
        "status":"ready" if sufficient else "incomplete-source-coverage",
        "top25Overlap":common25 if sufficient else None,
        "top10Overlap":len(ap10&elo10) if sufficient else None,
        "meanAbsoluteRankGap":(round(sum(abs(r["rankGap"]) for r in eligible)/n,2)
                               if sufficient else None),
        "spearmanWithinMatched":rho if sufficient else None,
        "teams":records,
        "eloTop25":[{"eloRank":i+1,"team":t["name"],"espnTeamId":t["espnTeamId"],
                     "elo":round(t["elo"],1)} for i,t in enumerate(team_pool[:25])],
        "limitations":[
            "AP is a voted ranking, not the truth for game prediction accuracy.",
            "Elo replay uses only games with dates before the AP edition week. Backfilled game results may have been published after the poll; this is not a time-stamped prospective prediction.",
            "Unmatched schools are not assigned a fictitious Elo rank; incomplete coverage suppresses agreement metrics.",
            "Rank comparisons are among source-linked rated 2027 Division I programs, not all rated opponents.",
            "Existing immutable historical poll comparisons never change after the first successful capture.",
        ],
    }
    return base


def _no_comparison(poll:dict,current:dict,captured_at:datetime,cutoff:date,
                   reason:str)->dict:
    return {"pollKey":"AP-2027-"+poll["sourceWeekStart"],
            "sourceWeekStart":poll["sourceWeekStart"],
            "sourceWeekNumber":poll["sourceWeekNumber"],
            "capturedAtUtc":captured_at.isoformat().replace("+00:00","Z"),
            "eloGameCutoffDate":cutoff.isoformat(),
            "eloModelVersion":current["eloMethodology"]["version"],
            "sourcePollName":poll["sourcePollName"],
            "status":"incomplete-source-coverage",
            "reason":reason,"matchedApTeams":0,"missingApTeams":25,
            "top25Overlap":None,"top10Overlap":None,
            "spearmanWithinMatched":None,"meanAbsoluteRankGap":None,
            "divisionIRatedProgramsAtCutoff":0,"ncaaPlusEspnRatedGamesThroughCutoff":0,
            "teams":[{"apRank":x["apRank"],"apName":x["apName"],
                      "espnTeamId":x["espnTeamId"],"eloRank":None,
                      "elo":None,"eloTop25":False,"rankGap":None} for x in poll["ranks"]],
            "eloTop25":[],"limitations":[reason]}


def baseline()->dict:
    return {"schemaVersion":SCHEMA,"season":SEASON,
            "mode":"weekly-AP-vs-Elo-independent-research",
            "pollSourceUrl":SOURCE,"sourceLandingUrl":POLL_WEB,
            "weeks":[],
            "policy":"First valid ESPN-transmitted AP edition is frozen by source week. Compare to before-week Elo replays; source-aligned ESPN IDs only. NOT model training, promotion or independently graded forecast accuracy."}


def update_history(existing:dict,edition:dict)->tuple[dict,bool]:
    if (existing.get("schemaVersion")!=SCHEMA or
        existing.get("season")!=SEASON or
        existing.get("mode")!=baseline()["mode"] or
        not isinstance(existing.get("weeks"),list)):
        raise ValueError("Unknown/invalid AP poll comparison archive")
    current = existing["weeks"]
    keys=[w.get("pollKey") for w in current]
    if len(keys)!=len(set(keys)):
        raise ValueError("AP comparison archive has duplicate week keys")
    if edition["pollKey"] in keys:
        return existing,False
    merged={**existing,"weeks":sorted([*current,edition],
                                      key=lambda r:r["sourceWeekStart"])}
    return merged,True


def main()->None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--poll-json",type=Path,help="Offline ESPN poll fixture (no network)")
    p.add_argument("--ratings",type=Path,default=Path("web/public/current/2027.json"))
    p.add_argument("--games",type=Path,default=Path("web/public/current/2027-games.json"))
    p.add_argument("--history",type=Path,default=Path("web/public/research/ap-poll-history.json"))
    args=p.parse_args()
    history=json.loads(args.history.read_text(encoding="utf-8")) if args.history.exists() else baseline()
    if (history.get("schemaVersion")!=SCHEMA or history.get("season")!=SEASON
        or not isinstance(history.get("weeks"),list)):
        raise ValueError("Invalid saved AP poll history")
    now=datetime.now(timezone.utc)
    try:
        data=json.loads(args.poll_json.read_text(encoding="utf-8")) if args.poll_json else fetch_poll()
        poll=extract_ap_poll(data,now)
    except (OSError,TimeoutError,ValueError,KeyError,TypeError) as exc:
        if args.poll_json:
            raise
        print("AP poll unavailable or incomplete; frozen past weeks preserved: "+str(exc)[:280])
        args.history.parent.mkdir(parents=True,exist_ok=True)
        if not args.history.exists():
            args.history.write_text(json.dumps(history,indent=2)+"\n",encoding="utf-8")
        return
    key="AP-2027-"+poll["sourceWeekStart"]
    if any(row.get("pollKey")==key for row in history["weeks"]):
        print(f"Previously captured AP edition {key}; immutable comparison preserved.")
        return
    ratings=json.loads(args.ratings.read_text(encoding="utf-8"))
    games=json.loads(args.games.read_text(encoding="utf-8"))
    if (ratings.get("retrievedAtUtc")!=games.get("retrievedAtUtc") or
        games.get("season")!=SEASON):
        raise ValueError("AP comparison Elo and game files are not source aligned")
    report=snapshot(poll,ratings,games["games"],now)
    merged,changed=update_history(history,report)
    if changed:
        args.history.parent.mkdir(parents=True,exist_ok=True)
        args.history.write_text(json.dumps(merged,indent=2)+"\n",encoding="utf-8")
        print(f"Saved {key}: AP/Elo matched {report['matchedApTeams']}/25, "
              f"Top 25 overlap {report['top25Overlap']}; "
              f"state={report['status']}; {report['eloGameCutoffDate']} Elo cutoff")


if __name__=="__main__":
    main()
