"""Source-pinned historical ML championship: no test-season tuning and no promotion.

All 40 eligible 1985–2025 historical tournament seasons are represented by
audited PRE-TOURNAMENT team-rating and record features, never hindsight
tournament seed results or future game scores. For season Y each model is
fitted using only season < Y; selection uses earlier OUT-OF-TIME years only.

Candidates are source-aligned for every fixture: Elo, earlier-season logistic
regression, gradient-boosted decision stumps, previous-season calibrated
trend-Elo, Gaussian margin model, and conservative Prior-based Elo shrinkage.
Historical NCAA tournament results are labels only.

This is an observational historical tournament benchmark, NOT an actual
prospectively frozen in-season 2026–27 archive, and NOT proof that a flexible
model beats Elo on future live basketball.
"""
from __future__ import annotations
import argparse
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from .historical_dataset import HistoricalGame,load_dataset
from .advanced import Features, train_logistic, predict as logistic_probability
from .boosted import train_boosted
from .benchmark import Outcome, choose_temperature, probability_of_winner
from .historical_probabilistic import _ridge,_estimate,_variance,_normal_cdf

MIN_PRIOR=5
META_YEARS=3
BRIER_MARGIN=0.001
MODEL_NAMES=("elo","logistic","boosted","calibratedTrendElo","scoreDistribution","priorShrinkage")
BOOTSTRAP_SEED=20027
STACK_WEIGHTS=(0.,.15,.30,.45)
STACK_MIN_PRIOR_YEARS=5
STACK_LOOKBACK_YEARS=8
STACK_MIN_GAIN=.002

def choose_prior_year_stack(prior:list[dict])->tuple[str,float]:
    """Predeclare a convex history-only stack; NEVER inspect current-year labels.

    Optimize on the most recent eight already-tested tournament years. Require
    five independently out-of-time years before any nonzero component enters.
    The complexity penalty makes it difficult to switch on a candidate based
    on a tiny historical advantage or short-term luck.
    """
    seasons=sorted({r["season"] for r in prior})
    if len(seasons)<STACK_MIN_PRIOR_YEARS:return ("elo",0.)
    seen=set(seasons[-STACK_LOOKBACK_YEARS:])
    train=[r for r in prior if r["season"] in seen]
    base=sum((r["elo"]-r["y"])**2 for r in train)/len(train)
    options=[("elo",0.,base)]
    for name in MODEL_NAMES:
        if name=="elo":continue
        for weight in STACK_WEIGHTS[1:]:
            brier=sum(((1-weight)*r["elo"]+weight*r[name]-r["y"])**2 for r in train)/len(train)
            complexity=.001*(weight/.45)**2
            if base-brier>=STACK_MIN_GAIN:
                options.append((name,weight,brier+complexity))
    candidate=min(options,key=lambda x:(x[2],x[1],MODEL_NAMES.index(x[0])))
    return candidate[:2]

def features(row:HistoricalGame, label_oriented:bool=False)->Features:
    direction=2*row.side_a_won-1 if label_oriented else 1
    return Features(row.elo_difference*direction,
                    row.projected_difference*direction,
                    row.win_pct_difference*direction)

def _evaluate(samples:list[dict],name:str)->dict:
    if not samples:return {"games":0,"brier":None,"logLoss":None,"accuracy":None}
    n=len(samples)
    return {"games":n,
       "brier":round(sum((r[name]-r["y"])**2 for r in samples)/n,6),
       "logLoss":round(-sum(math.log(max(1e-12,r[name] if r["y"] else 1-r[name])) for r in samples)/n,6),
       "accuracy":round(sum(.5 if r[name]==.5 else float((r[name]>.5)==bool(r["y"])) for r in samples)/n,6)}

def _bootstrap_by_year(rows:list[list[dict]],name:str,draws:int=1000)->list[float]|None:
    if len(rows)<5:return None
    rng=random.Random(BOOTSTRAP_SEED)
    vals=[]
    for _ in range(draws):
        selected=[rows[rng.randrange(len(rows))] for _ in rows]
        flat=[r for group in selected for r in group]
        vals.append(sum((r["elo"]-r["y"])**2-(r[name]-r["y"])**2 for r in flat)/len(flat))
    vals.sort()
    return [round(vals[int(.025*draws)],6),round(vals[int(.975*draws)-1],6)]

def _bucket(rows:list[dict],name:str)->list[dict]:
    # Source-pre-tournament Elo is the same segmentation input for all models.
    bins=(("close",0,75),("competitive",75,200),("mismatch",200,float("inf")))
    result=[]
    for label,lo,hi in bins:
        group=[r for r in rows if lo<=abs(r["eloDiff"])<hi]
        result.append({"label":label,"eloGapMin":lo,
          "eloGapMax":hi if math.isfinite(hi) else None,
          "elo":_evaluate(group,"elo"),"candidate":_evaluate(group,name)})
    return result

def evaluate(rows:list[HistoricalGame],manifest:dict,min_prior:int=MIN_PRIOR)->dict:
    years=sorted({r.season for r in rows})
    if min_prior<2 or len(years)<min_prior+5:raise ValueError("Insufficient separate chronological training and validation seasons")
    groups=defaultdict(list)
    for r in rows:
        if r.season not in years:raise ValueError("Unexpected historical year")
        if not all(math.isfinite(x) for x in (r.elo_difference,r.projected_difference,r.win_pct_difference)):
            raise ValueError("Invalid archived historical feature")
        groups[r.season].append(r)
    held_out=[]
    yearly=[]
    all_rows=[]
    year_blocks=[]
    for idx in range(min_prior,len(years)):
        year=years[idx]
        training=[r for previous in years[:idx] for r in groups[previous]]
        labels=[features(r,True) for r in training]
        lr=train_logistic(labels,iterations=160,learning_rate=.3,ridge=.025)
        gbdt=train_boosted(labels,rounds=12,min_leaf=15,learning_rate=.10,ridge=6.)
        temp=choose_temperature([Outcome((2*r.side_a_won-1)*r.elo_difference,
                                         (2*r.side_a_won-1)*r.projected_difference)
                                 for r in training])
        margin_model=_ridge(training,"margin")
        total_model=_ridge(training,"total")
        sigma,_=_variance(training,margin_model,total_model)
        # Held-out yearly model policy, chosen before observing current year.
        # A model needs three earlier OOS tournament seasons and a meaningful
        # Brier gain versus Elo on exactly the same earlier held-out games.
        prior_years={r["season"] for r in held_out}
        eligible=len(prior_years)>=META_YEARS
        if eligible:
            def loss(name:str)->float:
                return sum((r[name]-r["y"])**2 for r in held_out)/len(held_out)
            baseline=loss("elo")
            options=[name for name in MODEL_NAMES if name!="elo" and loss(name)+BRIER_MARGIN<baseline]
            selected=min(options,key=lambda name:(loss(name),MODEL_NAMES.index(name))) if options else "elo"
        else:selected="elo"
        stack_source,stack_weight=choose_prior_year_stack(held_out)
        current=[]
        for r in groups[year]:
            f=features(r)
            p=probability_of_winner(r.elo_difference)
            current.append({
                "season":year,"y":r.side_a_won,"day":r.day,
                "eloDiff":r.elo_difference,"elo":p,
                "logistic":logistic_probability(f,lr),
                "boosted":gbdt.probability(f),
                "calibratedTrendElo":probability_of_winner(r.projected_difference,temp),
                "scoreDistribution":_normal_cdf(_estimate(r,margin_model,"margin")/sigma),
                "priorShrinkage":probability_of_winner(r.elo_difference*.8),
            })
        for x in current:
            x["nestedChampion"]=x[selected]
            x["priorYearStack"]=(1-stack_weight)*x["elo"]+stack_weight*x[stack_source]
        yearly.append({"season":year,"trainedThroughSeason":years[idx-1],
            "trainingSeasons":idx,"previousOosSeasons":len(prior_years),
            "championSelectedBeforeResults":selected,
            "stackChosenBeforeResults":stack_source,
            "stackWeightChosenBeforeResults":stack_weight,
            "stackPriorOutOfTimeSeasons":len(prior_years),
            "modelScores":{m:_evaluate(current,m) for m in MODEL_NAMES},
            "nestedChampion":_evaluate(current,"nestedChampion"),
            "priorYearStack":_evaluate(current,"priorYearStack")})
        all_rows.extend(current)
        year_blocks.append(current)
        held_out.extend(current)
    return {
        "schemaVersion":1,"mode":"historical-only","sourceCommit":manifest["sourceCommit"],
        "indexSha256":manifest["historicalIndexSha256"],
        "featureCutoff":"pinned pre-tournament source rating and win-loss snapshot (day 132)",
        "evaluatedSeasons":len(yearly),"heldOutGames":len(all_rows),
        "models":{name:_evaluate(all_rows,name) for name in MODEL_NAMES},
        "nestedChampion":_evaluate(all_rows,"nestedChampion"),
        "priorYearStack":_evaluate(all_rows,"priorYearStack"),
        "priorYearStackGainVsElo":round(
            _evaluate(all_rows,"elo")["brier"]-_evaluate(all_rows,"priorYearStack")["brier"],6),
        "priorYearStackGain95":_bootstrap_by_year(year_blocks,"priorYearStack"),
        "nestedGainVsElo":round(_evaluate(all_rows,"elo")["brier"]-_evaluate(all_rows,"nestedChampion")["brier"],6),
        "nestedGainYearBlock95":_bootstrap_by_year(year_blocks,"nestedChampion"),
        "modelGainYearBlock95":{name:_bootstrap_by_year(year_blocks,name) for name in MODEL_NAMES if name!="elo"},
        "matchupTiers":_bucket(all_rows,"nestedChampion"),
        "yearByYear":yearly,
        "modelSelection":{"minimumPriorTrainingSeasons":min_prior,
            "minimumPriorOosSelectionSeasons":META_YEARS,
            "minimumBrierGainForSelection":BRIER_MARGIN,
            "candidateNames":list(MODEL_NAMES),
            "stackCandidateWeights":list(STACK_WEIGHTS),
            "stackLookbackYears":STACK_LOOKBACK_YEARS,
            "stackMinimumOutOfTimeYears":STACK_MIN_PRIOR_YEARS,
            "stackMinimumPriorBrierGain":STACK_MIN_GAIN,
            "stackPolicy":"Prior OOS years only; one candidate blended with Elo, complexity penalized, scored on an entirely later tournament season.",
            "noAutomaticProductionPromotion":True},
        "safety":{
            "livePredictionsModified":False,
            "sourcesAndFeatures":"Scores used only as prior-year labels; tournament seed/rank/finals unavailable as features",
            "prospectiveStatus":"Historical held-out simulation; no originally archived first-pick model scoring"},
        "limitations":[
            "No genuine date-stamped historical possessions or Four Factors exist in the pinned snapshots; no such features were manufactured.",
            "The tournament bracket field and seed are not used for winner prediction; teams' pre-tournament ratings are source-derived.",
            "Model selection is nested by season but repeated development on these historical test years can still overfit.",
            "New historical stacking is prequential, not a fit to the currently scored test year; retrospective reuse across releases still demands external confirmation.",
            "No candidate is promoted to the current live Elo forecast."]}
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--web-dir",type=Path,default=Path("web"))
    p.add_argument("--out",type=Path,default=Path("web/public/research/model-championship.json"))
    args=p.parse_args()
    rows,manifest=load_dataset(args.web_dir)
    result=evaluate(rows,manifest)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"seasons":result["evaluatedSeasons"],"games":result["heldOutGames"],
         "elo":result["models"]["elo"]["brier"],
         "nested":result["nestedChampion"]["brier"],"gain":result["nestedGainVsElo"]}))
if __name__=="__main__":main()
