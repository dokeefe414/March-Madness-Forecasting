"""Causal, uncertainty-aware 2027 team latent-strength experimental benchmark.

Each team maintains a Gaussian skill mean and variance. A game's score margin
provides a noisy observation of the two skills' difference. All observations
for game day D are predicted using only days < D; updating happens AFTER that
date's probabilities have been recorded. The present Eastern game day is
entirely excluded to protect against partially populated scoreboards.

This is a *fixed-assumption* Kalman-style linear filter, not an officially
validated NCAA win-probability model; its logistic matchup mapping is a
research scenario only until proven on real archived before-tipoff games.
"""
from __future__ import annotations
import argparse
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict
from zoneinfo import ZoneInfo
from .core import TeamState, matchup_probability

EASTERN = ZoneInfo("America/New_York")
INITIAL_VARIANCE = 150.0**2
OBSERVATION_VARIANCE = 250.0**2
PROCESS_VARIANCE = 18.0**2
MARGIN_TO_ELO = 18.0
HOME_ADVANTAGE = 65.0

@dataclass
class Latent:
    mean:float=1500.
    variance:float=INITIAL_VARIANCE
    changes:list[float]=field(default_factory=list)
    shock_count:int=0
    history:list[float]=field(default_factory=lambda:[1500.])

def _posterior(h:Latent,a:Latent,margin:int) -> None:
    # z estimates *neutral* skill gap. The fixed 65-point home court is
    # removed from the observation before measuring forecast innovation.
    z=max(-400.,min(400.,MARGIN_TO_ELO*margin))-HOME_ADVANTAGE
    residual=z-(h.mean-a.mean)
    hvar=h.variance+PROCESS_VARIANCE
    avar=a.variance+PROCESS_VARIANCE
    s=hvar+avar+OBSERVATION_VARIANCE
    if abs(residual)>2.5*math.sqrt(s):
        h.shock_count+=1
        a.shock_count+=1
    step_h=hvar/s*residual
    step_a=avar/s*residual
    h.mean+=step_h
    a.mean-=step_a
    h.variance=max(250.,hvar*(1-hvar/s))
    a.variance=max(250.,avar*(1-avar/s))
    h.changes.append(step_h)
    a.changes.append(-step_a)
    h.history.append(h.mean)
    a.history.append(a.mean)

def build_state_space(games:list[dict],ratings:dict,now:datetime|None=None) -> dict:
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Causal state space needs an aware as-of timestamp")
    cutoff=now.astimezone(EASTERN).date().isoformat()
    if ratings.get("mode")!="current" or ratings.get("season")!=2027:
        raise ValueError("Wrong sourced season")
    if len(games)!=ratings.get("regularSeasonGames"):
        raise ValueError("Underlying scored-game count does not match current ratings")
    grouped=defaultdict(list)
    for game in games:
        day=game["date"]
        if day>=cutoff:
            continue
        if day>ratings["lastGameDate"]:
            raise ValueError("Cannot learn from a game later than the source snapshot")
        grouped[day].append(game)
    states:dict[str,Latent]={}
    elo:dict[str,TeamState]={}
    diffs=[]
    total=0
    state_brier=elo_brier=0.
    state_right=elo_right=0.
    for day in sorted(grouped):
        batch=sorted(grouped[day],key=lambda g:g["id"])
        # Every prediction uses frozen pre-day means and variances.
        for g in batch:
            home,away=g["home"],g["away"]
            for name in (home,away):
                states.setdefault(name,Latent())
                elo.setdefault(name,TeamState(team_id=len(elo)+1,name=name))
            p=matchup_probability(states[home].mean,states[away].mean,HOME_ADVANTAGE)
            ep=matchup_probability(elo[home].rating,elo[away].rating,HOME_ADVANTAGE)
            y=int(g["homeScore"]>g["awayScore"])
            state_brier+=(p-y)**2
            elo_brier+=(ep-y)**2
            state_right+=int((p>.5 and y==1) or (p<.5 and y==0)) if p!=.5 else .5
            elo_right+=int((ep>.5 and y==1) or (ep<.5 and y==0)) if ep!=.5 else .5
            total+=1
        # Never use within-day results to score any other same-day game.
        for g in batch:
            h,a=g["home"],g["away"]
            y=int(g["homeScore"]>g["awayScore"])
            ep=matchup_probability(elo[h].rating,elo[a].rating,HOME_ADVANTAGE)
            change=24*(y-ep)
            elo[h].rating+=change
            elo[a].rating-=change
            _posterior(states[h],states[a],g["homeScore"]-g["awayScore"])
    output={}
    for name,state in sorted(states.items()):
        increments=state.changes[-5:]
        avg=sum(increments)/len(increments) if increments else 0
        output[name]={"mean":round(state.mean,3),
                      "standardDeviation":round(math.sqrt(state.variance),3),
                      "trend":round(avg,3),
                      "shockFlags":state.shock_count,
                      "history":[round(v,2) for v in state.history[-12:]],
                      "games":len(state.changes)}
    return {"schemaVersion":1,"mode":"research-only","type":"causal-gaussian-latent-skill",
            "season":2027,"ratingRetrievedAtUtc":ratings.get("retrievedAtUtc"),
            "asOfDateExclusive":cutoff,"trainedThroughDate":max(grouped) if grouped else None,
            "gameDays":len(grouped),"evaluatedGames":total,
            "brier":round(state_brier/total,6) if total else None,
            "eloSameDayBrier":round(elo_brier/total,6) if total else None,
            "accuracy":round(state_right/total,6) if total else None,
            "eloSameDayAccuracy":round(elo_right/total,6) if total else None,
            "strengths":output,
            "assumptions":{"initialVariance":INITIAL_VARIANCE,"observationVariance":OBSERVATION_VARIANCE,
                           "processVariancePerGame":PROCESS_VARIANCE,"eloPerMarginPoint":MARGIN_TO_ELO,
                           "homeCourtElo":HOME_ADVANTAGE},
            "warnings":["Causal retrospective game-date evaluation, not real pretipoff publication.",
                       "Gaussian score-margin observation and variance are fixed heuristic assumptions.",
                       "Elo and state-space baseline share same frozen-date source outcomes; exact tipoff order is unavailable.",
                       "Experimental probabilities are not promoted to the operational forecast without additional verification."]}

def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games",type=Path,default=Path("web/public/current/2027-games.json"))
    parser.add_argument("--ratings",type=Path,default=Path("web/public/current/2027.json"))
    parser.add_argument("--out",type=Path,default=Path("web/public/current/2027-state-space.json"))
    args=parser.parse_args()
    gamefile=json.loads(args.games.read_text(encoding="utf-8"))
    ratings=json.loads(args.ratings.read_text(encoding="utf-8"))
    if gamefile.get("retrievedAtUtc")!=ratings.get("retrievedAtUtc") or gamefile.get("season")!=2027:
        raise ValueError("State-space source files must share exact 2027 retrieval")
    output=build_state_space(gamefile["games"],ratings)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(output,indent=2)+"\n",encoding="utf-8")
    print(f"State-space research: {output['evaluatedGames']} as-of-date games, "
          f"{len(output['strengths'])} team states; Brier {output['brier']} vs baseline {output['eloSameDayBrier']}")

if __name__=="__main__":
    main()
