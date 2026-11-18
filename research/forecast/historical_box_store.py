"""Auditable optional historical NCAA game-box feature store.

Source file is *optional*. If missing, return explicit unavailable coverage;
the model championship uses only pinned day-132 rating inputs. Do not claim
that the pinned historical archive supplies possessions, rebounds or shooting.

A valid supplied CSV has one contest per row, with an official NCAA source
URL/event ID, day <= 132, the full two-sided box score, and NCAA team IDs
that match the committed historical season ratings. No winner-derived
features and no postseason game can enter the feature table.

Raw stats -> team four factors, possession-normalized points and prior
opponent quality, with a SHA-256 digest. These reconstructions are restricted
to the pre-tournament cutoff; they are NOT original dated pregame snapshots
for individual regular-season games.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

NUMERIC_FIELDS=("homePoints","awayPoints","homePossessions","awayPossessions",
"homeFga","awayFga","homeFgm","awayFgm","homeFg3m","awayFg3m",
"homeFta","awayFta","homeTov","awayTov","homeOrb","awayOrb",
"homeDrb","awayDrb")
MIN_GAMES=5
MAX_DAY=132

def _number(row:dict,key:str)->float:
    try:x=float(row[key])
    except (ValueError,TypeError,KeyError) as exc:
        raise ValueError(f"Missing numerical {key}") from exc
    if not math.isfinite(x) or x<0:raise ValueError(f"Negative or non-finite {key}")
    return x

def _side(row:dict,prefix:str)->dict:
    return {name:_number(row,prefix+name) for name in
        ("Points","Possessions","Fga","Fgm","Fg3m","Fta","Tov","Orb","Drb")}

def _check_box(s:dict,opp:dict)->None:
    if not 45<=s["Possessions"]<=120:raise ValueError("Implausible recorded possession count")
    if not 30<=s["Fga"]<=130 or s["Fgm"]>s["Fga"] or s["Fg3m"]>s["Fgm"]:
        raise ValueError("Implausible source shooting totals")
    if s["Points"]<30 or s["Points"]>200 or s["Points"]<2*s["Fgm"]+s["Fg3m"]-4:
        raise ValueError("Implausible NCAA box points")
    if s["Tov"]>s["Possessions"] or s["Orb"]>s["Fga"]-s["Fgm"]+3:
        raise ValueError("Implausible source turnover/rebound totals")
    if opp["Drb"]+s["Orb"]<=0:raise ValueError("Missing rebounding opportunities")

def load(web:Path,source:Path|None=None)->dict:
    index=json.loads((web/"data/history-index.json").read_text(encoding="utf-8"))
    seasons={int(e["season"]):e for e in index["seasons"] if e.get("isComplete") and e.get("throughDay")==MAX_DAY}
    base={"schemaVersion":1,"mode":"optional-pre-tournament-box-store",
          "sourceCommit":index["sourceCommit"],"sourceFile":str(source) if source else None,
          "available":False,"sourceSha256":None,"sourceGames":0,"teamSeasons":0,
          "missingBoxSeasons":sorted(seasons),
          "teamFeatures":[],"featureDefinitions":{
            "efgPct":"(FGM + 0.5*3PM) / FGA",
            "turnoverRate":"TOV / source possessions",
            "offensiveReboundPct":"ORB / (ORB + opponent DRB)",
            "freeThrowRate":"FTA / FGA",
            "offensePer100":"points / possessions * 100",
            "defensePer100":"opponent points / opponent possessions * 100",
            "pacePossessions":"mean independently verified source possessions",
            "opponentRatingMean":"mean opponent committed day-132 Elo rating; descriptive SOS proxy"},
          "limitations":["No fabricated historical Four Factors when NCAA event box rows are unavailable.",
             "Constructed features are as of the 132-day pre-tournament cutoff, not frozen before each prior regular-season contest.",
             "External supplied source citations and team IDs must be checked; a URL alone cannot establish authenticity."]}
    if source is None or not source.exists():return base
    raw=source.read_bytes()
    rows=list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
    if not rows:raise ValueError("Box-score source cannot be empty")
    if not {"season","day","eventId","homeTeamId","awayTeamId","sourceUri",*NUMERIC_FIELDS}.issubset(set(rows[0])):
        raise ValueError("Missing required official box-score columns")
    team_map={}
    for season in {int(r["season"]) for r in rows}:
        if season not in seasons:raise ValueError(f"Unusable source season {season}")
        d=json.loads((web/f"public/seasons/{season}.json").read_text(encoding="utf-8"))
        if d.get("sourceCommit")!=index["sourceCommit"] or d.get("throughDay")!=MAX_DAY:
            raise ValueError("Source season rating pin/cutoff differs")
        team_map[season]={str(t["teamId"]):t for t in d["teams"]}
    seen=set()
    per=defaultdict(list)
    by_season=set()
    for row in rows:
        season=int(row["season"])
        day=int(row["day"])
        home,away=str(row["homeTeamId"]),str(row["awayTeamId"])
        event=str(row["eventId"]).strip()
        if not 1<=day<=MAX_DAY:raise ValueError("Post-tournament or unbounded source box day")
        if home==away or home not in team_map[season] or away not in team_map[season]:
            raise ValueError("Missing or repeated verified source team identity")
        uri=row["sourceUri"].strip()
        if not (uri.startswith("https://stats.ncaa.org/") or uri.startswith("https://www.ncaa.com/")):
            raise ValueError("Only claimed official NCAA event sources are accepted")
        if not event or (season,event) in seen:raise ValueError("Duplicate or missing source event ID")
        seen.add((season,event))
        h,a=_side(row,"home"),_side(row,"away")
        _check_box(h,a);_check_box(a,h)
        if h["Points"]==a["Points"]:raise ValueError("Basketball final tie is unsupported")
        for ident,own,opp,other in ((home,h,a,away),(away,a,h,home)):
            per[(season,ident)].append((own,opp,team_map[season][other]["rating"]))
        by_season.add(season)
    features=[]
    for (season,ident),events in sorted(per.items()):
        if len(events)<MIN_GAMES:continue
        own=sum((e[0]["Points"] for e in events))
        poss=sum(e[0]["Possessions"] for e in events)
        opp_pts=sum(e[1]["Points"] for e in events)
        opp_poss=sum(e[1]["Possessions"] for e in events)
        attempts=sum(e[0]["Fga"] for e in events)
        efg=sum(e[0]["Fgm"]+.5*e[0]["Fg3m"] for e in events)/attempts
        tov=sum(e[0]["Tov"] for e in events)/poss
        orb=sum(e[0]["Orb"] for e in events)
        defensive=sum(e[1]["Drb"] for e in events)
        ftr=sum(e[0]["Fta"] for e in events)/attempts
        features.append({"season":season,"teamId":ident,"sourceGames":len(events),
          "efgPct":round(efg,6),"turnoverRate":round(tov,6),
          "offensiveReboundPct":round(orb/(orb+defensive),6),
          "freeThrowRate":round(ftr,6),
          "offensePer100":round(own/poss*100,5),
          "defensePer100":round(opp_pts/opp_poss*100,5),
          "pacePossessions":round(poss/len(events),4),
          "opponentRatingMean":round(sum(float(e[2]) for e in events)/len(events),3)})
    return {**base,"available":True,"sourceSha256":hashlib.sha256(raw).hexdigest(),
            "sourceGames":len(rows),"teamSeasons":len(features),
            "missingBoxSeasons":sorted(set(seasons)-by_season),
            "teamFeatures":features,
            "limitations":base["limitations"]+[
                "At least five official event rows are required for each team; entries with fewer are omitted.",
                "This optional dataset cannot replace the original 1985–2025 training features until enough audited source records exist."]}
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--web-dir",type=Path,default=Path("web"))
    p.add_argument("--source",type=Path)
    p.add_argument("--out",type=Path,default=Path("web/public/research/historical-box-coverage.json"))
    args=p.parse_args()
    result=load(args.web_dir,args.source)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({k:result[k] for k in ("available","sourceGames","teamSeasons","missingBoxSeasons")}))
if __name__=="__main__":main()
