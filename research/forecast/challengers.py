"""Two independently evaluated causal challenger models for current men's basketball.

Bayesian shrinkage applies an explicit Normal-like early-sample shrinkage of
team Elo to its 1500 prior with predictive uncertainty attenuation. Online
residual stumps provide a small gradient-correction ensemble. Neither is a
trained historical tournament model, a public pretipoff pick, or a permission
to replace the deployed Elo forecast. Date-grouped predictions are frozen
before any results from that day update either challenger.
"""
from __future__ import annotations
import argparse
import json
import math
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from .core import matchup_probability

EASTERN=ZoneInfo("America/New_York")
def probability_from_logit(x:float)->float:
    x=max(-16.,min(16.,x))
    return 1/(1+math.exp(-x))
def _stats(rows:list[dict],key:str)->dict:
    if not rows:return {"games":0,"brier":None,"accuracy":None,"logLoss":None}
    return {"games":len(rows),
            "brier":round(sum((r[key]-r["observed"])**2 for r in rows)/len(rows),6),
            "accuracy":round(sum((.5 if r[key]==.5 else float((r[key]>.5)==bool(r["observed"]))) for r in rows)/len(rows),6),
            "logLoss":round(-sum(math.log(max(1e-8,r[key] if r["observed"] else 1-r[key])) for r in rows)/len(rows),6)}
def build_challengers(games:list[dict],ratings:dict,now:datetime|None=None)->dict:
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:raise ValueError("Expected timezone-aware current date")
    if ratings.get("mode")!="current" or ratings.get("season")!=2027:
        raise ValueError("Only sourced 2027 current ratings supported")
    if len(games)!=ratings.get("regularSeasonGames"):
        raise ValueError("Source game count mismatch")
    if not ratings.get("retrievedAtUtc"):raise ValueError("Missing source retrieval timestamp")
    cutoff=now.astimezone(EASTERN).date().isoformat()
    groups=defaultdict(list)
    seen=set()
    for g in games:
        if g["id"] in seen:raise ValueError("Duplicate source game")
        seen.add(g["id"])
        if g["date"]>=cutoff:continue
        if not ratings.get("lastGameDate") or g["date"]>ratings["lastGameDate"]:
            raise ValueError("Unverifiable game newer than ratings")
        if g["home"]==g["away"] or min(g["homeScore"],g["awayScore"])<=0 or g["homeScore"]==g["awayScore"]:
            raise ValueError("Only completed non-tie games allowed")
        groups[g["date"]].append(g)
    elo:dict[str,float]={}
    played:dict[str,int]={}
    wins:dict[str,int]={}
    # Three fixed two-leaf residual stumps, updated only after each date.
    count=[[0.,0.] for _ in range(3)]
    gradient=[[0.,0.] for _ in range(3)]
    records=[]
    def features(h:str,a:str)->tuple[int,int,int]:
        gap=elo[h]-elo[a]
        form=(wins[h]/max(1,played[h]))-(wins[a]/max(1,played[a]))
        return (int(gap>125),int(form>0),int(played[h]-played[a]>4))
    for day in sorted(groups):
        batch=sorted(groups[day],key=lambda g:str(g["id"]))
        frozen=[]
        for g in batch:
            h,a=g["home"],g["away"]
            for name in (h,a):
                elo.setdefault(name,1500.)
                played.setdefault(name,0)
                wins.setdefault(name,0)
            observed=int(g["homeScore"]>g["awayScore"])
            baseline=matchup_probability(elo[h],elo[a],65.)
            home_shrink=played[h]/(played[h]+8)
            away_shrink=played[a]/(played[a]+8)
            bh=1500+(elo[h]-1500)*home_shrink
            ba=1500+(elo[a]-1500)*away_shrink
            # Bounded probability uncertainty from small-sample exposure.
            temp=1+0.25*(8/(8+played[h])+8/(8+played[a]))
            bayes=matchup_probability(bh/temp,ba/temp,65/temp)
            leaves=features(h,a)
            correction=sum(.32*gradient[i][leaf]/(20+count[i][leaf]) for i,leaf in enumerate(leaves))
            boosted=probability_from_logit(math.log(baseline/(1-baseline))+max(-.7,min(.7,correction)))
            frozen.append({"id":g["id"],"date":day,"home":h,"away":a,
                           "observed":observed,"baseline":baseline,"bayes":bayes,
                           "boosted":boosted,"leaves":leaves})
        records.extend(frozen)
        # Update all state only AFTER the day's complete forecast vector.
        for row in frozen:
            h,a=row["home"],row["away"]
            d=24*(row["observed"]-row["baseline"])
            elo[h]+=d
            elo[a]-=d
            played[h]+=1
            played[a]+=1
            wins[h]+=row["observed"]
            wins[a]+=1-row["observed"]
            for i,leaf in enumerate(row["leaves"]):
                count[i][leaf]+=1.
                gradient[i][leaf]+=row["observed"]-row["boosted"]
    per_date=[]
    for day in sorted(groups):
        rows=[r for r in records if r["date"]==day]
        per_date.append({"date":day,"games":len(rows),
                         "baselineBrier":_stats(rows,"baseline")["brier"],
                         "bayesianBrier":_stats(rows,"bayes")["brier"],
                         "residualStumpBrier":_stats(rows,"boosted")["brier"]})
    return {"schemaVersion":1,"mode":"research-only","season":2027,
            "ratingRetrievedAtUtc":ratings["retrievedAtUtc"],
            "trainedThroughDate":max(groups) if groups else None,
            "asOfExclusive":cutoff,"evaluatedGames":len(records),"evaluatedDates":len(groups),
            "methods":{
                "elo":_stats(records,"baseline"),
                "bayesianShrinkage":_stats(records,"bayes"),
                "onlineResidualStumps":_stats(records,"boosted")},
            "perDate":per_date[-50:],
            "policy":"Date-frozen retrospective evaluation. No genuine publicly archived first-pick performance is claimed. No model promotion.",
            "methodNotes":[
                "Shrink Elo skill to prior 1500 by n/(n+8) and soften probabilities under small exposure; prior constants are research assumptions.",
                "Three binary residual gradient stumps use only previous-day observations and regularization n+20; not a fitted production gradient-boosted tree model.",
                "Same-day batches have immutable forecasts before day-level result updates. Parameter choices were not hyperparameter-optimized on held-out seasons."
            ]}
def main()->None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games",type=Path,default=Path("web/public/current/2027-games.json"))
    parser.add_argument("--ratings",type=Path,default=Path("web/public/current/2027.json"))
    parser.add_argument("--out",type=Path,default=Path("web/public/current/challengers.json"))
    args=parser.parse_args()
    games=json.loads(args.games.read_text(encoding="utf-8"))
    ratings=json.loads(args.ratings.read_text(encoding="utf-8"))
    if games.get("retrievedAtUtc")!=ratings.get("retrievedAtUtc"):
        raise ValueError("Sourced games and ratings snapshots do not match")
    result=build_challengers(games["games"],ratings)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result))
if __name__=="__main__":
    main()
