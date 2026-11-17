"""Date-frozen opponent-adjusted margin model, independent benchmark, NO promotion.

Only completed NCAA-source games with dates strictly earlier than the game
being predicted can influence that prediction. Score data alone cannot infer
possessions: the website uses verified possession box scores separately.

The method fits an interpretable, regularized additive team scoring model:
  E[home points] = league avg + offense[home] + defenseAllowed[away]
  E[away points] = league avg + offense[away] + defenseAllowed[home]
Offense and defense effects are regularized against zero and iterated. Separate
older-game residuals provide a *rough* Gaussian margin uncertainty. The normal
approximation is an explicit research assumption, not a calibrated sportsbook
spread or a replacement of the public Elo probability.
"""
from __future__ import annotations
import argparse
import json
import math
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

from .core import matchup_probability

REGULARIZATION_GAMES = 9.
ITERATIONS = 12
MIN_TEAM_GAMES = 3
MIN_LEAGUE_GAMES = 50
HOME_ELO_POINTS = 65.
ELO_K = 24.
MIN_SIGMA = 9.
PRIOR_SIGMA = 15.
SIGMA_PRIOR_GAMES = 40.

def _safe_score(g:dict)->bool:
    try:
        h,a=int(g["homeScore"]),int(g["awayScore"])
    except (TypeError,KeyError,ValueError):
        return False
    return (0<h<201 and 0<a<201 and h!=a and
            g.get("home") and g.get("away") and g["home"]!=g["away"])

def _fitted(history:list[dict])->dict:
    if not history:
        return {"league":72.,"offense":{},"defense":{},"counts":{}}
    scores=[v for g in history for v in (g["homeScore"],g["awayScore"])]
    league=sum(scores)/len(scores)
    rows=defaultdict(list)
    for g in history:
        rows[g["home"]].append((float(g["homeScore"]),g["away"]))
        rows[g["away"]].append((float(g["awayScore"]),g["home"]))
    off={t:0. for t in rows}
    defense={t:0. for t in rows}
    for _ in range(ITERATIONS):
        new_off={
            team:sum(p-league-defense[opponent] for p,opponent in rec)/(len(rec)+REGULARIZATION_GAMES)
            for team,rec in rows.items()
        }
        new_def={
            team:sum(p-league-new_off.get(opponent,0.) for p,opponent in rec)/(len(rec)+REGULARIZATION_GAMES)
            for team,rec in defaultdict(list,{
              t:[(points,opponent) for g in history
                   for points,opponent in (
                     [(float(g["awayScore"]),g["away"])] if g["home"]==t else
                     [(float(g["homeScore"]),g["home"])] if g["away"]==t else [])]
              for t in rows
            }).items()
        }
        off=new_off
        defense=new_def
    return {"league":league,"offense":off,"defense":defense,
            "counts":{t:len(rec) for t,rec in rows.items()}}

def _probability(margin:float,sigma:float)->float:
    return max(.001,min(.999,.5*(1.+math.erf(margin/(sigma*math.sqrt(2.))))))

def _prior_sigma(history:list[dict],fit:dict)->float:
    # Old games only, using last fitted strengths. This is a descriptive
    # upper/lower-bounded residual spread, not a forward-calibrated interval.
    residuals=[]
    for g in history:
        predicted=(fit["offense"].get(g["home"],0.)+fit["defense"].get(g["away"],0.)
            -fit["offense"].get(g["away"],0.)-fit["defense"].get(g["home"],0.))
        residuals.append(((g["homeScore"]-g["awayScore"])-predicted)**2)
    variance=(sum(residuals)+SIGMA_PRIOR_GAMES*PRIOR_SIGMA**2)/(len(residuals)+SIGMA_PRIOR_GAMES)
    return max(MIN_SIGMA,min(30.,math.sqrt(variance)))

def _metrics(rows:list[dict],kind:str)->dict:
    if not rows:return {"games":0,"marginMAE":None,"totalMAE":None,"winnerAccuracy":None,"brier":None,"logLoss":None}
    n=len(rows)
    def l(r):return max(1e-8,r[kind+"Probability"] if r["homeWon"] else 1-r[kind+"Probability"])
    return {
        "games":n,
        "marginMAE":round(sum(abs(r[kind+"Margin"]-r["actualMargin"]) for r in rows)/n,5),
        "totalMAE":round(sum(abs(r[kind+"Total"]-r["actualTotal"]) for r in rows)/n,5),
        "winnerAccuracy":round(sum(float((r[kind+"Probability"]>.5)==r["homeWon"]) if r[kind+"Probability"]!=.5 else .5 for r in rows)/n,6),
        "brier":round(sum((r[kind+"Probability"]-int(r["homeWon"]))**2 for r in rows)/n,6),
        "logLoss":round(-sum(math.log(l(r)) for r in rows)/n,6),
    }

def evaluate(games:list[dict],ratings:dict,now:datetime|None=None)->dict:
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:raise ValueError("Evaluation time must be timezone-aware")
    if not isinstance(ratings,dict) or ratings.get("season")!=2027 or ratings.get("mode")!="current":
        raise ValueError("Source data must be current NCAA 2027")
    if len(games)!=ratings.get("regularSeasonGames"):
        raise ValueError("Game source count differs from rating source")
    if ratings.get("retrievedAtUtc") is None or not ratings.get("lastGameDate"):
        raise ValueError("Missing source provenance")
    observed=set()
    daily=defaultdict(list)
    cutoff=now.date().isoformat()
    for g in games:
        if not _safe_score(g):raise ValueError("Invalid finalized game")
        if g["id"] in observed:raise ValueError("Duplicate event ID")
        observed.add(g["id"])
        if g["date"]>ratings["lastGameDate"]:raise ValueError("Game newer than source ratings")
        if g["date"]>=cutoff:continue
        daily[g["date"]].append(g)
    previous=[]
    elo=defaultdict(lambda:1500.)
    predictions=[]
    days=[]
    skipped=defaultdict(int)
    for d in sorted(daily):
        group=sorted(daily[d],key=lambda g:str(g["id"]))
        # Fit, predict and freeze every matchup before considering same-date finals.
        fit=_fitted(previous)
        sigma=_prior_sigma(previous,fit)
        earlier_mean=fit["league"]
        frozen=[]
        for g in group:
            h,a=g["home"],g["away"]
            if len(previous)<MIN_LEAGUE_GAMES:
                skipped["notEnoughLeagueGames"]+=1;continue
            if min(fit["counts"].get(h,0),fit["counts"].get(a,0))<MIN_TEAM_GAMES:
                skipped["notEnoughPriorTeamGames"]+=1;continue
            hp=earlier_mean+fit["offense"].get(h,0.)+fit["defense"].get(a,0.)
            ap=earlier_mean+fit["offense"].get(a,0.)+fit["defense"].get(h,0.)
            # No implied venue bump. The mean-only control is the previously
            # published neutral baseline, trained on the identical earlier games.
            hrows=[p for p in previous if h in (p["home"],p["away"])]
            arows=[p for p in previous if a in (p["home"],p["away"])]
            def means(t,rows):
                f=sum(p["homeScore"] if t==p["home"] else p["awayScore"] for p in rows)/len(rows)
                against=sum(p["awayScore"] if t==p["home"] else p["homeScore"] for p in rows)/len(rows)
                return f,against
            hfor,hallow=means(h,hrows);afor,aallow=means(a,arows)
            naiveh=(hfor+aallow)/2
            naivea=(afor+hallow)/2
            elo_probability=matchup_probability(elo[h],elo[a]+(-HOME_ELO_POINTS))
            # Probability maps margin to a Gaussian *research* assumption.
            p=_probability(hp-ap,sigma)
            np=_probability(naiveh-naivea,sigma)
            actualh,actuala=int(g["homeScore"]),int(g["awayScore"])
            frozen.append({
                "eventId":str(g["id"]),"date":d,"home":h,"away":a,
                "actualMargin":actualh-actuala,"actualTotal":actualh+actuala,
                "homeWon":actualh>actuala,
                "adjustedMargin":hp-ap,"adjustedTotal":hp+ap,"adjustedProbability":p,
                "rawMargin":naiveh-naivea,"rawTotal":naiveh+naivea,"rawProbability":np,
                "eloMargin":0.,"eloTotal":0.,"eloProbability":elo_probability,
                "priorLeagueGames":len(previous),"priorHomeGames":len(hrows),
                "priorAwayGames":len(arows),"priorMarginSigma":round(sigma,3)
            })
        predictions.extend(frozen)
        if frozen:
            days.append({"date":d,"games":len(frozen),
                "adjustedMarginMAE":_metrics(frozen,"adjusted")["marginMAE"],
                "rawMarginMAE":_metrics(frozen,"raw")["marginMAE"],
                "adjustedBrier":_metrics(frozen,"adjusted")["brier"],
                "rawBrier":_metrics(frozen,"raw")["brier"],
                "eloBrier":round(sum((r["eloProbability"]-int(r["homeWon"]))**2 for r in frozen)/len(frozen),6)})
        # Current-day outcomes update Elo only AFTER all day predictions.
        for g in group:
            h,a=g["home"],g["away"]
            p=matchup_probability(elo[h],elo[a]-HOME_ELO_POINTS)
            diff=ELO_K*(int(g["homeScore"]>g["awayScore"])-p)
            elo[h]+=diff;elo[a]-=diff
        previous.extend(group)
    elo_brier=round(sum((r["eloProbability"]-int(r["homeWon"]))**2 for r in predictions)/len(predictions),6) if predictions else None
    return {
        "schemaVersion":1,"season":2027,"mode":"research-only","retrievedAtUtc":ratings["retrievedAtUtc"],
        "trainedThroughDate":max(daily) if daily else None,
        "sourceGames":len(games),"evaluatedGames":len(predictions),"evaluatedDays":len(days),
        "excluded":dict(skipped),"minimumTrainingGames":MIN_LEAGUE_GAMES,
        "methods":{"opponentAdjusted":_metrics(predictions,"adjusted"),
                   "rawScoringMeans":_metrics(predictions,"raw"),
                   "elo":{"games":len(predictions),"brier":elo_brier}},
        "perDate":days[-100:],
        "auditFirst40":[{k:(round(v,5) if isinstance(v,float) else v) for k,v in row.items()}
                        for row in predictions[:40]],
        "modelVersion":"regularized-additive-margin-v1",
        "assumptions":{"regularizationGames":REGULARIZATION_GAMES,"iterations":ITERATIONS,
                        "minPriorTeamGames":MIN_TEAM_GAMES,"marginPriorSigma":PRIOR_SIGMA,
                        "noHomeVenueBonus":True},
        "policy":"Date-frozen historical replay, NOT a source-verified prospectively archived score forecast. No challenger is promoted; public winner probabilities remain the established selection.",
        "limitations":["Score-only NCAA finals do not reveal possessions. Only verified NCAA box possession rates enable the separate current match-up pace projection.",
            "The fixed Gaussian margin approximation has not been independently calibrated on future games.",
            "Same-day games are all evaluated against identical pre-date state; last game date is not a real-tipoff timestamp.",
            "Scores are from the same season and prior dates; no injury, travel or actual sportsbook line data is assumed."]
    }

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ratings",type=Path,default=Path("web/public/current/2027.json"))
    p.add_argument("--games",type=Path,default=Path("web/public/current/2027-games.json"))
    p.add_argument("--out",type=Path,default=Path("web/public/current/score-research.json"))
    a=p.parse_args()
    ratings=json.loads(a.ratings.read_text(encoding="utf-8"))
    g=json.loads(a.games.read_text(encoding="utf-8"))
    if g.get("retrievedAtUtc")!=ratings.get("retrievedAtUtc"):raise ValueError("Source capture timestamps do not match")
    result=evaluate(g["games"],ratings)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"games":result["evaluatedGames"],"methods":result["methods"]}))
if __name__=="__main__":main()
