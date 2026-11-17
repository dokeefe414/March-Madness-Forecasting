"""Causal opponent-strength-adjusted margin model for 2027 men's games.

An opponent-aware candidate scores each result relative to what the *opponent's
PREVIOUS-DATE strength* predicted. A big win over a weak team is not mistaken
for the same evidence as a big win over a strong team. Inputs use only NCAA-
derived previous-date scores and same-source opponent Elo states.

This challenger is research-only. It is not retroactively labelled a real
pregame pick, and it cannot replace baseline Elo until frozen prospective
paired observations demonstrate advantage under a separate promotion policy.
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

from .core import matchup_probability

EASTERN=ZoneInfo("America/New_York")
ELO_HOME=65.
K=24.
MARGIN_PER_ELO=28.  # assumed Elo difference -> expected margin conversion
EMA_GAIN=.30
POINT_TO_ELO=8.
ADJUSTMENT_CAP=75.
EARLY_SHRINK_GAMES=6.

@dataclass
class Signal:
    elo:float=1500.
    wins:int=0
    losses:int=0
    residual:float=0.
    opponents:list[float]=field(default_factory=list)
    margin_surprises:list[float]=field(default_factory=list)
    adjustment_history:list[float]=field(default_factory=list)
    @property
    def n(self):return self.wins+self.losses
    def adjustment(self)->float:
        shrink=self.n/(self.n+EARLY_SHRINK_GAMES)
        return max(-ADJUSTMENT_CAP,min(ADJUSTMENT_CAP,
                   self.residual*POINT_TO_ELO*shrink))
    def rating(self):return self.elo+self.adjustment()

def _predict(states:dict[str,Signal],h:str,a:str)->tuple[float,float]:
    home,away=states[h],states[a]
    return (matchup_probability(home.elo,away.elo,ELO_HOME),
            matchup_probability(home.rating(),away.rating(),ELO_HOME))

def build_opponent_report(games:list[dict],ratings:dict,
                          now:datetime|None=None)->dict:
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:raise ValueError("Opponent model clock must have timezone")
    cutoff=now.astimezone(EASTERN).date().isoformat()
    if ratings.get("mode")!="current" or ratings.get("season")!=2027:
        raise ValueError("Opponent model requires sourced 2027 current season")
    if len(games)!=ratings.get("regularSeasonGames"):
        raise ValueError("Opponent model game count differs from source")
    if not ratings.get("retrievedAtUtc"):
        raise ValueError("Missing current ratings source retrieval")
    groups=defaultdict(list)
    ids=set()
    for game in games:
        if game["id"] in ids:raise ValueError("Duplicate NCAA contest in opponent model")
        ids.add(game["id"])
        day=game["date"]
        if day>=cutoff:continue
        if day>ratings["lastGameDate"]:raise ValueError("Game beyond current ratings")
        if game["home"]==game["away"] or game["homeScore"]<=0 or game["awayScore"]<=0 or game["homeScore"]==game["awayScore"]:
            raise ValueError("Malformed final score in opponent-adjusted model")
        groups[day].append(game)
    states:dict[str,Signal]={}
    records=[]
    for day in sorted(groups):
        batch=sorted(groups[day],key=lambda g:str(g["id"]))
        daily=[]
        # Freeze ALL same-date predictions and pregame surprise observations.
        for g in batch:
            h,a=g["home"],g["away"]
            states.setdefault(h,Signal())
            states.setdefault(a,Signal())
            x,y=states[h],states[a]
            baseline,adjusted=_predict(states,h,a)
            observed=int(g["homeScore"]>g["awayScore"])
            margin=g["homeScore"]-g["awayScore"]
            expected=(x.elo+ELO_HOME-y.elo)/MARGIN_PER_ELO
            residual=max(-24.,min(24.,margin-expected))
            daily.append({"game":g,"baseline":baseline,"adjusted":adjusted,
                          "outcome":observed,"surprise":residual,
                          "preHomeElo":x.elo,"preAwayElo":y.elo})
            records.append({"date":day,"eventId":g["id"],
                            "baselineBrier":(baseline-observed)**2,
                            "opponentBrier":(adjusted-observed)**2,
                            "baselineCorrect":float((baseline>.5)==bool(observed)) if baseline!=.5 else .5,
                            "opponentCorrect":float((adjusted>.5)==bool(observed)) if adjusted!=.5 else .5})
        # Only after evaluating the full date can its observed games change
        # either team's pre-future Elo strength and opponent-adjusted margin.
        for row in daily:
            g=row["game"]
            h,a=g["home"],g["away"]
            home,away=states[h],states[a]
            y=row["outcome"]
            d=K*(y-row["baseline"])
            home.elo+=d;away.elo-=d
            home.wins+=y;home.losses+=1-y
            away.wins+=1-y;away.losses+=y
            home.residual=(1-EMA_GAIN)*home.residual+EMA_GAIN*row["surprise"]
            away.residual=(1-EMA_GAIN)*away.residual-EMA_GAIN*row["surprise"]
            home.opponents.append(row["preAwayElo"])
            away.opponents.append(row["preHomeElo"])
            home.margin_surprises.append(row["surprise"])
            away.margin_surprises.append(-row["surprise"])
            home.adjustment_history.append(home.adjustment())
            away.adjustment_history.append(away.adjustment())
    def mean(field:str,rows:list[dict])->float|None:
        return round(sum(r[field] for r in rows)/len(rows),6) if rows else None
    team_states={}
    for name,x in sorted(states.items()):
        team_states[name]={
            "baselineElo":round(x.elo,2),
            "opponentAdjustedElo":round(x.rating(),2),
            "eloAdjustment":round(x.adjustment(),2),
            "opponentResidual":round(x.residual,3),
            "games":x.n,
            "meanOpponentEloAtGame":round(sum(x.opponents)/len(x.opponents),2) if x.opponents else None,
            "recentUnexpectedMargins":[round(v,2) for v in x.margin_surprises[-6:]],
            "adjustmentHistory":[round(v,2) for v in x.adjustment_history[-12:]],
        }
    by_date=defaultdict(list)
    for row in records:by_date[row["date"]].append(row)
    last_days=sorted(by_date)[-7:]
    last=[r for day in last_days for r in by_date[day]]
    latest=[
        {"date":day,"games":len(by_date[day]),
         "eloBrier":mean("baselineBrier",by_date[day]),
         "opponentBrier":mean("opponentBrier",by_date[day])}
        for day in sorted(by_date)[-28:]
    ]
    return {"schemaVersion":1,"season":2027,
            "type":"opponent-adjusted-elo-margin","mode":"research-only",
            "retrievedAtUtc":ratings["retrievedAtUtc"],
            "trainedThroughDate":max(groups) if groups else None,
            "trainingCutoffExclusive":cutoff,
            "games":len(records),"teamCount":len(team_states),
            "chronological":{
                "method":"all date D fixtures evaluated with only prior-date states",
                "eloBrier":mean("baselineBrier",records),
                "opponentAdjustedBrier":mean("opponentBrier",records),
                "eloAccuracy":mean("baselineCorrect",records),
                "opponentAdjustedAccuracy":mean("opponentCorrect",records),
                "lastSevenDatesEloBrier":mean("baselineBrier",last),
                "lastSevenDatesOpponentBrier":mean("opponentBrier",last),
                "perDate":latest,
            },
            "parameters":{
                "eloK":K,"eloHomeAdvantage":ELO_HOME,
                "eloPointsPerExpectedMargin":MARGIN_PER_ELO,
                "marginResidualCap":24,"residualEmaGain":EMA_GAIN,
                "eloPointsPerResidualPoint":POINT_TO_ELO,
                "earlyGameShrinkCount":EARLY_SHRINK_GAMES,
                "maxAbsoluteAdjustment":ADJUSTMENT_CAP,
            },
            "strengths":team_states,
            "limitations":[
                "Margin-vs-expectation correction is a fixed assumption, not a proven learned causal treatment.",
                "All fixtures on a game date are tested before seeing any same-day outcome.",
                "Today is entirely embargoed and not used to update prior-day team strength.",
                "Opponent game-time Elo is preserved as it was before the event; no future opponent rating leak.",
                "Retrospective same-day-frozen scores are NOT archived before-tipoff accuracy.",
                "Research only; a lower Brier on replays does not permit promotion without genuine new-game evidence.",
            ]}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ratings",type=Path,default=Path("web/public/current/2027.json"))
    parser.add_argument("--games",type=Path,default=Path("web/public/current/2027-games.json"))
    parser.add_argument("--out",type=Path,default=Path("web/public/current/2027-opponents.json"))
    args=parser.parse_args()
    ratings=json.loads(args.ratings.read_text(encoding="utf-8"))
    scored=json.loads(args.games.read_text(encoding="utf-8"))
    if scored.get("season")!=2027 or scored.get("retrievedAtUtc")!=ratings.get("retrievedAtUtc"):
        raise ValueError("Opponent model's score archive and ratings snapshot differ")
    report=build_opponent_report(scored["games"],ratings)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(f"Opponent-adjusted research: {report['games']} causal date-frozen games, "
          f"Elo Brier {report['chronological']['eloBrier']}, "
          f"opponent Brier {report['chronological']['opponentAdjustedBrier']}")
if __name__=="__main__":
    main()
