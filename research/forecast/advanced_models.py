"""Causal *full* gradient-boosted decision trees and Gaussian Bayesian rating research.

No external dependency required: small Newton-boosted CART trees are fitted
on *previous* calendar-day game predictions only. A Bayesian Bradley-Terry
filter uses a Gaussian assumed-density/Laplace update to posterior team skill.
Both are benchmark experiments, never eligible for live promotion simply because
their retrospectively evaluated Brier improves.

The chronological unit is the Eastern source-game date: all games on a day
receive predictions from a frozen copy of the previous-day model. Only after
all probabilities are scored may their outcomes update the skill states and
the next training batch. Hyperparameters are explicitly fixed a priori.
"""
from __future__ import annotations
import argparse
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime,timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .core import matchup_probability
EASTERN=ZoneInfo("America/New_York")
LOGISTIC_SCALE=math.log(10)/400
PRIOR_MEAN=1500.
PRIOR_SD=200.
HOME_ELO=65.
K=24.
MIN_TRAIN=60
REFIT_EVERY_DAYS=7
TREES=12
LEARNING_RATE=.12
RIDGE=12.
MIN_LEAF=12
MAX_STEPS=3
def sigmoid(x:float)->float:
    return 1/(1+math.exp(-max(-16.,min(16.,x))))
@dataclass
class GaussianSkill:
    mean:float=PRIOR_MEAN
    variance:float=PRIOR_SD**2
    games:int=0

def bayesian_probability(h:GaussianSkill,a:GaussianSkill)->float:
    # Logistic-Gaussian moment-matching approximation, not exact integration.
    gap=LOGISTIC_SCALE*(h.mean-a.mean+HOME_ELO)
    variance=(LOGISTIC_SCALE**2)*(h.variance+a.variance)
    return sigmoid(gap / math.sqrt(1+math.pi*variance/8))

def update_bayesian(h:GaussianSkill,a:GaussianSkill,y:int)->None:
    p=bayesian_probability(h,a)
    residual=y-p
    # A damped one-step local Gaussian Laplace approximation.
    vh=h.variance+9**2
    va=a.variance+9**2
    curvature=p*(1-p)*(LOGISTIC_SCALE**2)
    denominator=1+curvature*(vh+va)
    step_h=vh*LOGISTIC_SCALE*residual/denominator
    step_a=va*LOGISTIC_SCALE*residual/denominator
    h.mean+=step_h
    a.mean-=step_a
    h.variance=max(100.,vh/(1+curvature*vh))
    a.variance=max(100.,va/(1+curvature*va))
    h.games+=1;a.games+=1

# Tree encoding: either ("leaf",constant) or ("split",feature,threshold,left,right).
def tree_output(node:tuple,x:tuple[float,...])->float:
    if node[0]=="leaf":return node[1]
    return tree_output(node[3] if x[node[1]]<=node[2] else node[4],x)

def _leaf(rows:list[tuple[tuple[float,...],float,float]])->float:
    return max(-1.5,min(1.5,sum(z[1] for z in rows)/(RIDGE+sum(z[2] for z in rows))))

def train_tree(rows:list[tuple[tuple[float,...],float,float]],depth:int=2)->tuple:
    if depth==0 or len(rows)<2*MIN_LEAF:return ("leaf",_leaf(rows))
    whole_g=sum(z[1] for z in rows);whole_h=sum(z[2] for z in rows)
    base=whole_g*whole_g/(RIDGE+whole_h)
    best_gain=0.;best=None
    for feature in range(len(rows[0][0])):
        samples=sorted(rows,key=lambda z:z[0][feature])
        gl=hl=0.
        for i,row in enumerate(samples[:-1]):
            gl+=row[1];hl+=row[2]
            if i+1<MIN_LEAF or len(samples)-i-1<MIN_LEAF:continue
            if samples[i][0][feature]==samples[i+1][0][feature]:continue
            gr=whole_g-gl;hr=whole_h-hl
            gain=gl*gl/(RIDGE+hl)+gr*gr/(RIDGE+hr)-base
            if gain>best_gain+1e-10:
                best_gain=gain
                best=(feature,(samples[i][0][feature]+samples[i+1][0][feature])/2,
                      samples[:i+1],samples[i+1:])
    if best is None:return ("leaf",_leaf(rows))
    feature,threshold,left,right=best
    return ("split",feature,threshold,train_tree(left,depth-1),train_tree(right,depth-1))

def train_boosted(history:list[dict])->list[tuple]:
    if len(history)<MIN_TRAIN:return []
    # The prior-date Elo probability is an offset, never changed by the trees.
    current=[math.log(r["elo"]/(1-r["elo"])) for r in history]
    trees=[]
    for _ in range(TREES):
        triples=[]
        for i,r in enumerate(history):
            p=sigmoid(current[i])
            triples.append((r["features"],r["outcome"]-p,max(.015,p*(1-p))))
        tree=train_tree(triples)
        trees.append(tree)
        for i,r in enumerate(history):
            current[i]+=LEARNING_RATE*tree_output(tree,r["features"])
    return trees

def _summary(rows:list[dict],key:str)->dict:
    if not rows:return {"games":0,"accuracy":None,"brier":None,"logLoss":None}
    n=len(rows)
    return {
      "games":n,
      "accuracy":round(sum(.5 if r[key]==.5 else float((r[key]>.5)==bool(r["outcome"])) for r in rows)/n,6),
      "brier":round(sum((r[key]-r["outcome"])**2 for r in rows)/n,6),
      "logLoss":round(-sum(math.log(max(1e-10,r[key] if r["outcome"] else 1-r[key])) for r in rows)/n,6)
    }

def build_advanced_models(games:list[dict],ratings:dict,now:datetime|None=None)->dict:
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:raise ValueError("Naive clock not permitted")
    if ratings.get("mode")!="current" or ratings.get("season")!=2027:
        raise ValueError("Expected sourced 2027 season")
    if len(games)!=ratings.get("regularSeasonGames") or not ratings.get("retrievedAtUtc"):
        raise ValueError("Ratings and results provenance mismatch")
    cutoff=now.astimezone(EASTERN).date().isoformat()
    groups=defaultdict(list)
    ids=set()
    for game in games:
        if game["id"] in ids:raise ValueError("Duplicate source game")
        ids.add(game["id"])
        if game["date"]>=cutoff:continue
        if game["date"]>ratings.get("lastGameDate",""):
            raise ValueError("Game newer than dated score source")
        if min(game["homeScore"],game["awayScore"])<=0 or game["homeScore"]==game["awayScore"] or game["home"]==game["away"]:
            raise ValueError("Invalid supposedly settled game")
        groups[game["date"]].append(game)
    elo:dict[str,float]={}
    played:dict[str,int]={}
    wins:dict[str,int]={}
    posterior:dict[str,GaussianSkill]={}
    prior_history:list[dict]=[]
    forecast_rows=[]
    audit=[]
    trained=[]
    last_refit=-100000
    for date_index,day in enumerate(sorted(groups)):
        # Refit using *only* earlier days, never same-day answers.
        if date_index-last_refit>=REFIT_EVERY_DAYS and len(prior_history)>=MIN_TRAIN:
            trained=train_boosted(prior_history)
            last_refit=date_index
        frozen=[]
        for g in sorted(groups[day],key=lambda x:str(x["id"])):
            h,a=g["home"],g["away"]
            for t in (h,a):
                elo.setdefault(t,PRIOR_MEAN)
                played.setdefault(t,0)
                wins.setdefault(t,0)
                posterior.setdefault(t,GaussianSkill())
            p=matchup_probability(elo[h],elo[a],HOME_ELO)
            features=(
              (elo[h]-elo[a])/400.,
              (played[h]-played[a])/20.,
              (wins[h]+1)/(played[h]+2)-(wins[a]+1)/(played[a]+2),
              min(1.,(played[h]+played[a])/40.),
            )
            q=bayesian_probability(posterior[h],posterior[a])
            offset=math.log(p/(1-p))
            boost=sigmoid(offset+LEARNING_RATE*sum(tree_output(tree,features) for tree in trained))
            frozen.append({"id":str(g["id"]),"date":day,"home":h,"away":a,
                           "outcome":int(g["homeScore"]>g["awayScore"]),
                           "elo":p,"bayesian":q,"gbdt":boost,"features":features})
        forecast_rows.extend(frozen)
        if len(audit)<80:
            audit.extend({"id":r["id"],"date":day,"trainedOnPriorGames":len(prior_history),
                          "elo":round(r["elo"],7),"bayesian":round(r["bayesian"],7),
                          "gbdt":round(r["gbdt"],7)} for r in frozen[:max(0,80-len(audit))])
        # All scores for the same date frozen before any game contributes training.
        for row in frozen:
            h,a=row["home"],row["away"]
            d=K*(row["outcome"]-row["elo"])
            elo[h]+=d;elo[a]-=d
            wins[h]+=row["outcome"];wins[a]+=1-row["outcome"]
            played[h]+=1;played[a]+=1
            update_bayesian(posterior[h],posterior[a],row["outcome"])
        prior_history.extend(frozen)
    daily=[]
    for day in sorted(groups):
        batch=[r for r in forecast_rows if r["date"]==day]
        daily.append({"date":day,"games":len(batch),
                      "eloBrier":_summary(batch,"elo")["brier"],
                      "bayesianBrier":_summary(batch,"bayesian")["brier"],
                      "gradientBoostedBrier":_summary(batch,"gbdt")["brier"]})
    return {"schemaVersion":1,"mode":"research-only",
            "season":2027,"retrievedAtUtc":ratings["retrievedAtUtc"],"trainedThroughDate":max(groups) if groups else None,
            "evaluatedGames":len(forecast_rows),"evaluatedDates":len(groups),
            "hyperparameters":{"minimumTrainingGames":MIN_TRAIN,"refitEveryPriorDays":REFIT_EVERY_DAYS,
                               "trees":TREES,"depth":2,"learningRate":LEARNING_RATE,
                               "minimumLeaf":MIN_LEAF,"ridge":RIDGE,
                               "priorMean":PRIOR_MEAN,"priorSd":PRIOR_SD},
            "methods":{"elo":_summary(forecast_rows,"elo"),
                       "bayesianGaussian":_summary(forecast_rows,"bayesian"),
                       "gradientBoostedTrees":_summary(forecast_rows,"gbdt")},
            "perDate":daily[-80:],"auditFirst80":audit,
            "policy":"Research-only frozen previous-day benchmark; model weights depend on prior realized outcomes. This is not independently archived first-pick evidence and cannot promote any challenger.",
            "limitations":[
              "Bayesian posterior uses damped Laplace/assumed-density skill updating with an approximate logistic-Gaussian predictive integral, not MCMC or exact full posterior.",
              "Gradient boosting uses 12 fitted depth-2 Newton CART trees, 7-day previous-date refits and a fixed Elo-logit offset. No leakage from currently evaluated day.",
              "Hyperparameters and underlying game order remain research assumptions; historical model selection and cross-season stability must be externally verified."
            ]}
def main()->None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--games",type=Path,default=Path("web/public/current/2027-games.json"))
    p.add_argument("--ratings",type=Path,default=Path("web/public/current/2027.json"))
    p.add_argument("--out",type=Path,default=Path("web/public/current/advanced-models.json"))
    a=p.parse_args()
    games=json.loads(a.games.read_text(encoding="utf-8"))
    ratings=json.loads(a.ratings.read_text(encoding="utf-8"))
    if games.get("retrievedAtUtc")!=ratings.get("retrievedAtUtc"):
        raise ValueError("Mismatched source retrieval")
    result=build_advanced_models(games["games"],ratings)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"evaluatedGames":result["evaluatedGames"],"methods":result["methods"]}))
if __name__=="__main__":main()
