"""Source-traceable ESPN STATUS_FINAL game receipts for daily Elo updates.

This module does not grade the immutable original pregame forecast ledger.
It conservatively extends NCAA-derived ratings when the independent provider's
NCAA schedule release lags behind a *confirmed final* ESPN scoreboard. The
ESPN ID must match the same-season published school crosswalk exactly.

Receipts survive future rebuilds through a committed Git file; when NCAA
later reports that result we replay it only ONCE under the NCAA contest ID.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .reference import canonical

EASTERN=ZoneInfo("America/New_York")
SCHEMA=1
FIRST="2026-11-01"
LAST="2027-03-14"
SOURCE="ESPN college basketball STATUS_FINAL and season-2027 provider-authorized team IDs"
RECEIPT_KEYS=("eventId","date","home","away","homeScore","awayScore",
              "homeEspnTeamId","awayEspnTeamId","scheduledStartUtc")


def _parse_time(raw:str)->datetime:
    value=datetime.fromisoformat(str(raw).replace("Z","+00:00"))
    if value.tzinfo is None:
        raise ValueError("Final receipt has timezone-naive timestamp")
    return value.astimezone(timezone.utc)


def _identity(game:dict)->tuple[str,str,str]:
    date_str=str(game["date"])
    names=sorted((canonical(game["home"]),canonical(game["away"])))
    if not names[0] or names[0]==names[1]:
        raise ValueError("Final must have two distinct nonempty teams")
    return date_str,names[0],names[1]


def _scores_by_team(game:dict)->dict[str,int]:
    return {canonical(game["home"]):int(game["homeScore"]),
            canonical(game["away"]):int(game["awayScore"])}


def _receipt(row:dict,observed:datetime)->dict:
    if not row.get("espnIdentityIdsMatch"):
        raise ValueError("No two-sided same-season ESPN identity proof")
    item={key:row[key] for key in RECEIPT_KEYS}
    event_id=str(item["eventId"]).strip()
    if not event_id or not item["homeEspnTeamId"] or not item["awayEspnTeamId"]:
        raise ValueError("Missing ESPN event/team IDs")
    d=date.fromisoformat(str(item["date"]))
    if d<date.fromisoformat(FIRST) or d>date.fromisoformat(LAST):
        raise ValueError("ESPN final outside 2026-27 regular season")
    if d>observed.astimezone(EASTERN).date():
        raise ValueError("Future ESPN result date cannot update Elo")
    tip=_parse_time(str(item["scheduledStartUtc"]))
    if tip>observed:
        raise ValueError("ESPN result is ahead of observed clock")
    if not isinstance(item["homeScore"],int) or not isinstance(item["awayScore"],int):
        raise ValueError("ESPN final score must be integral")
    if min(item["homeScore"],item["awayScore"])<=0 or item["homeScore"]==item["awayScore"]:
        raise ValueError("Invalid purported completed basketball final")
    _identity(item)
    item["eventId"]=event_id
    item["firstObservedAtUtc"]=observed.isoformat().replace("+00:00","Z")
    item["source"]=SOURCE
    return item


def _read_saved(saved:dict|None)->dict[str,dict]:
    if saved is None:
        return {}
    if (saved.get("schemaVersion")!=SCHEMA or saved.get("season")!=2027
        or not isinstance(saved.get("receipts"),list)):
        raise ValueError("Unknown or corrupt durable ESPN final receipt file")
    quarantined=saved.get("quarantinedEventIds",[])
    if (not isinstance(quarantined,list) or
        any(not isinstance(x,str) or not x for x in quarantined) or
        len(set(quarantined))!=len(quarantined)):
        raise ValueError("Invalid quarantined ESPN event IDs in durable receipt file")
    found={}
    for item in saved["receipts"]:
        if not isinstance(item,dict):
            raise ValueError("Non-object ESPN receipt")
        if not all(k in item for k in (*RECEIPT_KEYS,"firstObservedAtUtc","source")):
            raise ValueError("Incomplete saved ESPN receipt")
        if item["source"]!=SOURCE:
            raise ValueError("Unsupported ESPN receipt provenance")
        stamp=_parse_time(item["firstObservedAtUtc"])
        # A stored receipt should never have a future/invalid event time.
        validated=_receipt({**item,"espnIdentityIdsMatch":True},stamp)
        if validated!=item:
            raise ValueError("Saved ESPN receipt differs from strict canonical form")
        event_id=item["eventId"]
        if event_id in found:
            raise ValueError("Duplicate saved ESPN event ID")
        found[event_id]=item
    return found


def merge_games(ncaa_games:list[dict],espn_finals:list[dict],
                ratings:dict,saved:dict|None=None,
                observed:datetime|None=None,
                warnings:list[str]|None=None)->tuple[list[dict],dict,dict]:
    """Reconcile ESPN and NCAA games and return (replay, report, durable file).

    Fail closed on saved tampering. A newly conflicting ESPN score or a
    questionable same-team/date NCAA duplicate is quarantined from the rating
    increment; it cannot erase an already accepted NCAA source game.
    """
    now=observed or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Source observation clock must be timezone-aware")
    now=now.astimezone(timezone.utc)
    if ratings.get("season")!=2027 or ratings.get("mode")!="current":
        raise ValueError("Expected provisional current-season NCAA ratings")
    if not isinstance(ncaa_games,list) or not isinstance(espn_finals,list):
        raise ValueError("Expected two game arrays")
    trusted_by_id:dict[str,dict]={}
    ambiguous_linked:set[str]=set()
    for team in ratings["teams"]:
        linked=str(team.get("espnSourceTeamId") or "").strip()
        if linked and linked not in ambiguous_linked:
            if linked in trusted_by_id and trusted_by_id[linked]["teamId"]!=team["teamId"]:
                # A bad optional identity crosswalk must not kill all Elo.
                # Exclude this ESPN ID rather than accepting a guessed school.
                ambiguous_linked.add(linked)
                trusted_by_id.pop(linked,None)
            else:
                trusted_by_id[linked]=team
    saved_by_id=_read_saved(saved)
    prior_quarantined=set(saved.get("quarantinedEventIds",[])) if saved else set()
    current_by_id:dict[str,dict]={}
    rejected=Counter()
    if ambiguous_linked:
        rejected["ambiguousProviderTeamIds"]=len(ambiguous_linked)
    for row in espn_finals:
        if not row.get("espnIdentityIdsMatch"):
            rejected["noAuthoritativeTeamIdPair"]+=1
            continue
        try:
            item=_receipt(row,now)
        except (ValueError,KeyError,TypeError,OverflowError):
            rejected["malformedEspnFinal"]+=1
            continue
        event_id=item["eventId"]
        if event_id in current_by_id and current_by_id[event_id]!=item:
            rejected["duplicateConflictingEspnFinal"]+=1
            # The duplicate remains excluded even if encountered again.
            current_by_id[event_id]=None
        elif event_id not in current_by_id:
            current_by_id[event_id]=item

    conflicts=set(prior_quarantined)
    for eid,new in current_by_id.items():
        if new is None:
            conflicts.add(eid)
            continue
        old=saved_by_id.get(eid)
        if old:
            # firstObservedAtUtc is intentionally frozen in the ledger.
            if any(old[key]!=new[key] for key in RECEIPT_KEYS):
                rejected["changedVerifiedEspnScore"]+=1
                conflicts.add(eid)
        else:
            saved_by_id[eid]=new

    candidates={}
    pair_to_ids:dict[tuple[str,str,str],list[str]]=defaultdict(list)
    for eid,item in saved_by_id.items():
        if eid in conflicts:
            continue
        h=trusted_by_id.get(str(item["homeEspnTeamId"]))
        a=trusted_by_id.get(str(item["awayEspnTeamId"]))
        if not h or not a or h["teamId"]==a["teamId"] or (
            h["name"]!=item["home"] or a["name"]!=item["away"]):
            rejected["identityCrosswalkUnavailableOrChanged"]+=1
            continue
        if _parse_time(item["firstObservedAtUtc"])>now:
            rejected["futureObservedReceipt"]+=1
            continue
        key=_identity(item)
        pair_to_ids[key].append(eid)
        candidates[eid]=item

    ncaa_by_pair:dict[tuple[str,str],list[dict]]=defaultdict(list)
    for game in ncaa_games:
        day,h,a=_identity(game)
        ncaa_by_pair[(h,a)].append(game)
    merged=[{**g,"source":"NCAA-derived schedule"} for g in ncaa_games]
    selected=0
    for eid in sorted(candidates,key=lambda x:(candidates[x]["date"],x)):
        item=candidates[eid]
        key=_identity(item)
        if len(pair_to_ids[key])!=1:
            rejected["ambiguousEspnSameDayPair"]+=1
            continue
        # A NCAA producer may use UTC vs Eastern calendar dates, or reverse
        # home/away at a neutral event. Search +/- one day and require an
        # identical per-team score before declaring the ESPN game a duplicate.
        date_s,h,a=key
        d=date.fromisoformat(date_s)
        near=[g for g in ncaa_by_pair.get((h,a),[])
              if abs((date.fromisoformat(g["date"])-d).days)<=1]
        if near:
            identical=[g for g in near if _scores_by_team(g)==_scores_by_team(item)]
            if len(near)==1 and len(identical)==1:
                rejected["alreadyInNcaa"]+=1
            else:
                rejected["ncaaScoreOrDateConflict"]+=1
            continue
        merged.append({
            "id":"espn:"+eid,"date":item["date"],"home":item["home"],
            "away":item["away"],"homeScore":item["homeScore"],
            "awayScore":item["awayScore"],"source":"ESPN-confirmed STATUS_FINAL",
            "espnEventId":eid,"firstObservedAtUtc":item["firstObservedAtUtc"],
        })
        selected+=1
    merged.sort(key=lambda g:(g["date"],str(g["id"])))
    counts={key:int(value) for key,value in sorted(rejected.items())}
    persisted={"schemaVersion":SCHEMA,"season":2027,"source":SOURCE,
               "quarantinedEventIds":sorted(conflicts),
               "receipts":[saved_by_id[eid] for eid in sorted(saved_by_id)]}
    report={"schemaVersion":SCHEMA,"mode":"daily-multi-source-Elo",
            "ncaaAcceptedGames":len(ncaa_games),
            "ratedEspnOnlyFinals":selected,
            "totalRatedGames":len(merged),
            "espnFinalsObservedThisRun":len(espn_finals),
            "persistedEspnFinalReceipts":len(saved_by_id),
            "quarantinedEspnEvents":len(conflicts),
            "espnOnlyLastGameDate":max((g["date"] for g in merged
                                       if g["source"]=="ESPN-confirmed STATUS_FINAL"),default=None),
            "ncaaLastGameDate":max((g["date"] for g in ncaa_games),default=None),
            "rejectedOrReconciled":counts,
            "sourceWarnings":list(warnings or []),
            "policy":"Only ESPN completed STATUS_FINAL with both provider-authorized same-season team IDs. Score/date/pair overlap with NCAA is counted ONCE; disagreement is quarantined. Original dual-verified first picks and settlements stay immutable. Rebuild Elo and research using all source-accepted results every publish.",
            "caveat":"ESPN-only accepted finals are not independently NCAA score-confirmed yet. Retroactive prior-date model research does not prove these scores were available at the time of old predictions.",
        }
    return merged,report,persisted


def load_receipts(path:Path|None)->dict|None:
    if path is None or not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_receipts(path:Path,value:dict)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,sort_keys=True)+"\n",encoding="utf-8")
