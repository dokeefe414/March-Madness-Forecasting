"""Historical-only regularized scores, uncertainty, calibration and nested ensemble.

Works solely on the pinned 1985–2025 pre-tournament snapshots and held-out
NCAA tournament scores. Each test season is untouched during training,
hyperparameter selection and ensemble weighting; previously tested seasons
may inform later calibration/weights but NEVER their own prior predictions.
No production current-season game, archive, bookmaker line or live model is
read or modified. No claim is made that tournament-day-132 team features
represent regular-season per-game tipoff state.
"""
from __future__ import annotations
import argparse
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from .historical_dataset import HistoricalGame,load_dataset
from .benchmark import probability_of_winner,choose_temperature,Outcome

MIN_PRIOR_YEARS=5
MIN_META_YEARS=3
RIDGE_STRENGTH=18.
PROBABILITY_SCALES=(0.7,0.85,1.,1.15,1.35,1.6)
BLEND_WEIGHTS=(0.,.25,.5,.75,1.)
Z80=1.2815515655446004

def _features(row:HistoricalGame)->tuple[float,float,float,float]:
    return (1.,row.elo_difference/400.,row.projected_difference/400.,row.win_pct_difference)

def _solve(a:list[list[float]],b:list[float])->list[float]:
    n=len(b)
    m=[a[i][:]+[b[i]] for i in range(n)]
    for k in range(n):
        pivot=max(range(k,n),key=lambda i:abs(m[i][k]))
        if abs(m[pivot][k])<1e-10:raise ValueError("Singular historical ridge matrix")
        m[k],m[pivot]=m[pivot],m[k]
        q=m[k][k]
        m[k]=[v/q for v in m[k]]
        for i in range(n):
            if i==k:continue
            factor=m[i][k]
            m[i]=[m[i][j]-factor*m[k][j] for j in range(n+1)]
    return [m[i][-1] for i in range(n)]

def _ridge(rows:list[HistoricalGame],target:str)->list[float]:
    """Independent, auditable ridge scoring fit; no fitted external dependency."""
    if not rows:raise ValueError("Cannot train without previous tournament seasons")
    dims=4
    gram=[[0. for _ in range(dims)] for _ in range(dims)]
    right=[0. for _ in range(dims)]
    for row in rows:
        raw=_features(row)
        if target=="margin":
            value=(2*row.side_a_won-1)*(row.winner_score-row.loser_score)
            x=raw
        elif target=="total":
            value=row.winner_score+row.loser_score-140.
            # Favor stable combined-score baselines; difference direction
            # is deliberately not allowed to invent a venue scoring effect.
            x=(1.,abs(raw[1]),abs(raw[2]),abs(raw[3]))
        else:raise ValueError("Unknown score target")
        for i in range(dims):
            right[i]+=x[i]*value
            for j in range(dims):gram[i][j]+=x[i]*x[j]
    for i in range(dims):
        # Do not penalize the intercept to zero; 140 is the total baseline.
        if i:gram[i][i]+=RIDGE_STRENGTH
    return _solve(gram,right)

def _estimate(row:HistoricalGame,coeff:list[float],target:str)->float:
    f=_features(row)
    if target=="total":
        f=(1.,abs(f[1]),abs(f[2]),abs(f[3]))
    out=sum(v*w for v,w in zip(f,coeff))
    return out+140. if target=="total" else out

def _variance(rows:list[HistoricalGame],m:list[float],t:list[float])->tuple[float,float]:
    """Finite, shrinkage-stabilized *in-sample* training residual scales.

    Confidence coverage is measured independently in subsequent years;
    coverage is never claimed by fitting to test-season outcomes.
    """
    mr=[];tr=[]
    for row in rows:
        actual=(2*row.side_a_won-1)*(row.winner_score-row.loser_score)
        total=row.winner_score+row.loser_score
        mr.append((actual-_estimate(row,m,"margin"))**2)
        tr.append((total-_estimate(row,t,"total"))**2)
    margin=math.sqrt((sum(mr)+80*14**2)/(len(mr)+80))
    total=math.sqrt((sum(tr)+80*19**2)/(len(tr)+80))
    return max(8.,min(28.,margin)),max(10.,min(40.,total))

def _normal_cdf(x:float)->float:
    return max(.001,min(.999,.5*(1.+math.erf(x/math.sqrt(2.)))))

def _score(ps:list[tuple[float,int]])->dict:
    if not ps:return {"games":0,"brier":None,"logLoss":None,"accuracy":None}
    return {"games":len(ps),
        "brier":round(sum((p-y)**2 for p,y in ps)/len(ps),6),
        "logLoss":round(-sum(math.log(max(1e-12,p if y else 1-p)) for p,y in ps)/len(ps),6),
        "accuracy":round(sum(.5 if p==.5 else float((p>.5)==bool(y)) for p,y in ps)/len(ps),6)}

def _calibration(rows:list[dict],key:str)->dict:
    """Only untouched test-year predictions; no refitting or bucket optimization."""
    if not rows:return {"ece":None,"bins":[]}
    buckets=[[] for _ in range(10)]
    for row in rows:
        p=row[key]
        if not math.isfinite(p) or not 0<=p<=1:
            raise ValueError("Nonfinite prediction in held-out calibration audit")
        buckets[min(9,int(p*10))].append(row)
    bins=[]
    for i,group in enumerate(buckets):
        conf=sum(r[key] for r in group)/len(group) if group else None
        actual=sum(r["y"] for r in group)/len(group) if group else None
        bins.append({"lower":i/10,"upper":(i+1)/10,"games":len(group),
                     "averageProbability":round(conf,5) if conf is not None else None,
                     "realizedFrequency":round(actual,5) if actual is not None else None})
    ece=sum(len(g)/len(rows)*abs(sum(x[key] for x in g)/len(g)-sum(x["y"] for x in g)/len(g))
            for g in buckets if g)
    return {"ece":round(ece,6),"bins":bins}

def _score_intervals(rows:list[dict])->dict:
    if not rows:return {"games":0,"marginMAE":None,"totalMAE":None,"marginRMSE":None,"totalRMSE":None,"margin80Coverage":None,"total80Coverage":None,"margin80MeanWidth":None,"total80MeanWidth":None}
    n=len(rows)
    return {"games":n,
        "marginMAE":round(sum(abs(r["margin"]-r["actualMargin"]) for r in rows)/n,5),
        "totalMAE":round(sum(abs(r["total"]-r["actualTotal"]) for r in rows)/n,5),
        "marginRMSE":round(math.sqrt(sum((r["margin"]-r["actualMargin"])**2 for r in rows)/n),5),
        "totalRMSE":round(math.sqrt(sum((r["total"]-r["actualTotal"])**2 for r in rows)/n),5),
        "margin80Coverage":round(sum(abs(r["margin"]-r["actualMargin"])<=Z80*r["marginSigma"] for r in rows)/n,5),
        "total80Coverage":round(sum(abs(r["total"]-r["actualTotal"])<=Z80*r["totalSigma"] for r in rows)/n,5),
        "margin80MeanWidth":round(sum(2*Z80*r["marginSigma"] for r in rows)/n,4),
        "total80MeanWidth":round(sum(2*Z80*r["totalSigma"] for r in rows)/n,4)}

def _season_bootstrap(years:list[list[dict]],draws:int=900)->list[float]|None:
    if len(years)<5:return None
    rng=random.Random(18027)
    metrics=[]
    for _ in range(draws):
        sampled=[years[rng.randrange(len(years))] for _ in years]
        games=[r for season in sampled for r in season]
        metrics.append(sum((r["baseline"]-r["y"])**2-(r["ensemble"]-r["y"])**2 for r in games)/len(games))
    metrics.sort()
    return [round(metrics[int(.025*draws)],6),round(metrics[int(.975*draws)-1],6)]

def evaluate(rows:list[HistoricalGame],manifest:dict,min_train:int=MIN_PRIOR_YEARS)->dict:
    seasons=sorted({r.season for r in rows})
    if min_train<2 or len(seasons)<min_train+5:raise ValueError("Too few chronological tournament years")
    by=defaultdict(list)
    for r in rows:by[r.season].append(r)
    old_oos=[]
    reports=[]
    all_predictions=[]
    season_samples=[]
    for i in range(min_train,len(seasons)):
        year=seasons[i]
        prior=[r for s in seasons[:i] for r in by[s]]
        m=_ridge(prior,"margin")
        t=_ridge(prior,"total")
        sigma,tau=_variance(prior,m,t)
        # The existing calibration control fits ONLY earlier years' labels.
        temperature=choose_temperature([
            Outcome((2*r.side_a_won-1)*r.elo_difference,
                    (2*r.side_a_won-1)*r.projected_difference)
            for r in prior])
        # Tune the margin-to-probability scale AND ensemble only from
        # previously out-of-time season predictions, never this test year.
        can_tune=len({r["season"] for r in old_oos})>=MIN_META_YEARS
        if can_tune:
            scale=min(PROBABILITY_SCALES,key=lambda s:(
                sum((_normal_cdf(r["z"]/s)-r["y"])**2 for r in old_oos)/len(old_oos)+.0001*abs(math.log(s)),
                abs(math.log(s))))
            weight=min(BLEND_WEIGHTS,key=lambda w:(
                sum(((1-w)*r["baseline"]+w*_normal_cdf(r["z"]/scale)-r["y"])**2 for r in old_oos)/len(old_oos)+.0005*w,w))
        else:
            scale=1.
            weight=0.
        sample=[]
        for row in by[year]:
            margin=_estimate(row,m,"margin")
            total=_estimate(row,t,"total")
            y=row.side_a_won
            baseline=probability_of_winner(row.elo_difference)
            # Distinct calibrated-Elo control available for comparison.
            cal=probability_of_winner(row.projected_difference,temperature)
            z=margin/sigma
            score_probability=_normal_cdf(z/scale)
            ensemble=(1-weight)*baseline+weight*score_probability
            sample.append({"season":year,"sideAId":row.side_a_id,"sideBId":row.side_b_id,
              "day":row.day,"y":y,"baseline":baseline,"calibrated":cal,
              "scoreProbability":score_probability,"ensemble":ensemble,
              "margin":margin,"total":total,"marginSigma":sigma,"totalSigma":tau,
              "actualMargin":(2*y-1)*(row.winner_score-row.loser_score),
              "actualTotal":row.winner_score+row.loser_score})
            old_oos.append({"season":year,"baseline":baseline,"z":z,"y":y})
        all_predictions.extend(sample)
        season_samples.append(sample)
        reports.append({"season":year,"trainingThrough":seasons[i-1],"trainingYears":i,
          "priorOutOfTimeSeasons":len({r["season"] for r in old_oos if r["season"]<year}),
          "modelWeight":weight,"scoreProbabilityScale":scale,
          "elo":_score([(r["baseline"],r["y"]) for r in sample]),
          "calibratedElo":_score([(r["calibrated"],r["y"]) for r in sample]),
          "scoreProbability":_score([(r["scoreProbability"],r["y"]) for r in sample]),
          "ensemble":_score([(r["ensemble"],r["y"]) for r in sample]),
          "scoreIntervals":_score_intervals(sample)})
    get=lambda key:_score([(r[key],r["y"]) for r in all_predictions])
    control=get("baseline");ensemble=get("ensemble")
    return {"schemaVersion":1,"mode":"historical-research-only",
      "sourceCommit":manifest["sourceCommit"],"datasetIndexSha256":manifest["historicalIndexSha256"],
      "trainingData":"source-verified pre-tournament day-132 team snapshots; actual historical NCAA tournament matchups only",
      "trainedThroughSeason":seasons[-1],"evaluatedYears":len(reports),
      "heldOutGames":len(all_predictions),
      "metrics":{"elo":control,"calibratedElo":get("calibrated"),
        "scoringProbability":get("scoreProbability"),"nestedEnsemble":ensemble,
        "projectedScores":_score_intervals(all_predictions)},
      "ensembleBrierGainVsElo":round(control["brier"]-ensemble["brier"],6),
      "calibration":{name:_calibration(all_predictions,key) for name,key in
        (("elo","baseline"),("scoring","scoreProbability"),("ensemble","ensemble"))},
      "seasonBlockGain95":_season_bootstrap(season_samples),
      "yearByYear":reports,
      "policy":{"minimumPriorSeasons":min_train,"minimumPriorOosSeasons":MIN_META_YEARS,
        "candidateWeights":list(BLEND_WEIGHTS),"candidateProbabilityScales":list(PROBABILITY_SCALES),
        "ridgePenalty":RIDGE_STRENGTH,"marginIntervalNominalCoverage":.80,
        "noAutomaticPromotion":True,"liveForecastsChanged":False},
      "limitations":[
        "The historical data is frozen after the regular season but before tournament play, not before each regular-season game.",
        "The score model learns tournament totals/margins from prior tournament years only; it is not a possession-model backtest because per-game box features are unavailable.",
        "Marginal Gaussian errors are a model assumption; tested 80% interval coverage is empirical and may be miscalibrated.",
        "Nested weights are selected only on earlier held-out years; repeated research against these same historical archives can overfit them.",
        "Ten-bin expected calibration error is descriptive; ECE can look artificially small for extreme imbalance or sparse bins.",
        "The ensemble was NEVER automatically promoted to the public pregame Elo model."]}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--web-dir",type=Path,default=Path("web"))
    p.add_argument("--out",type=Path,default=Path("research/outputs/historical-probabilistic.json"))
    args=p.parse_args()
    rows,manifest=load_dataset(args.web_dir)
    report=evaluate(rows,manifest)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"years":report["evaluatedYears"],"heldOutGames":report["heldOutGames"],
        "eloBrier":report["metrics"]["elo"]["brier"],
        "ensembleBrier":report["metrics"]["nestedEnsemble"]["brier"],
        "marginMAE":report["metrics"]["projectedScores"]["marginMAE"],
        "totalMAE":report["metrics"]["projectedScores"]["totalMAE"]}))
if __name__=="__main__":main()
