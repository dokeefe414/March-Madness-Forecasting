"""Immutable-first-pick, source-verified forward ensemble research.

The portfolio is a deliberately conservative *shadow* of already trained
models. Each component comes from the original pregame artifact and may be
used only if the corresponding prediction was published before that matchup.
Weight fitting uses earlier independently settled and originally frozen
games only; never tune or recalculate past predictions retrospectively.

Production Elo remains unchanged. The evidence gate reports readiness for
manual scientific review; it does not silently promote an ensemble.
"""
from __future__ import annotations
import argparse
import json
import math
import random
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

EASTERN=ZoneInfo("America/New_York")
COMPONENTS=("challengerHomeWinProbability","stateSpaceHomeWinProbability",
            "opponentAdjustedHomeWinProbability","adaptiveStateSpaceHomeWinProbability")
WEIGHTS=(0.,.1,.2,.3,.4)
DEFAULT_SHADOW=.25
MIN_TRAIN=80
MIN_VALIDATION=40
MIN_DATE_BLOCKS=6
MIN_GAIN=.002

def _prob(value:object)->float|None:
    if value is None or isinstance(value,bool):return None
    try:p=float(value)
    except (TypeError,ValueError):return None
    return p if math.isfinite(p) and 0<p<1 else None

def candidate(prediction:dict,weight:float=DEFAULT_SHADOW)->dict|None:
    """A fixed mean across available valid frozen shadow signals.

    A same-game ESPN record cannot produce a candidate by postgame training:
    inputs are pre-computed in a separate strictly before-tipoff artifact.
    At least two independently constructed current-source signal families
    are required for a meaningful mixture; otherwise withhold the candidate.
    """
    baseline=_prob(prediction.get("baselineHomeWinProbability"))
    if baseline is None:return None
    if not(0<=weight<=.4):raise ValueError("Unapproved ensemble weight")
    found=[(name,p) for name in COMPONENTS if (p:=_prob(prediction.get(name))) is not None]
    if len(found)<2:return None
    research=sum(p for _,p in found)/len(found)
    prob=(1-weight)*baseline+weight*research
    return {"homeWinProbability":round(prob,7),"eloHomeWinProbability":baseline,
            "researchMeanHomeWinProbability":round(research,7),
            "componentCount":len(found),
            "components":[name for name,_ in found],"weight":weight}

def _rows(folder:Path,now:datetime)->list[dict]:
    originals={}
    for path in sorted((folder/"snapshots").glob("*.json")):
        item=json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(item.get("predictions"),list):raise ValueError("Corrupt immutable snapshot")
        for pred in item["predictions"]:
            event=str(pred["eventId"])
            key=(item["generatedAtUtc"],item["snapshotId"])
            if event not in originals or key<originals[event][0]:
                originals[event]=(key,item,pred)
    confirmed={}
    for path in sorted((folder/"settlements").glob("*.json")):
        item=json.loads(path.read_text(encoding="utf-8"))
        for row in item["results"]:
            key=row["predictionKey"]
            if key in confirmed and confirmed[key]!=row:raise ValueError("Conflicting immutable final")
            confirmed[key]=row
    rows=[]
    cutoff=now.astimezone(EASTERN).date().isoformat()
    for event,(_,snap,pred) in originals.items():
        original_key=snap["snapshotId"]+":"+event
        settled=confirmed.get(original_key)
        if settled is None or settled["actualResultDate"]>=cutoff:continue
        if settled.get("espnFinalVerified") is not True:continue
        if settled.get("home")!=pred["home"] or settled.get("away")!=pred["away"]:continue
        baseline=_prob(pred.get("baselineHomeWinProbability"))
        formula=candidate(pred,DEFAULT_SHADOW)
        if baseline is None or formula is None:continue
        y=settled["observedHome"]
        if type(y) is not int or y not in (0,1):raise ValueError("Nonbinary verified final")
        frozen=_prob(pred.get("ensembleHomeWinProbability"))
        rows.append({"eventId":event,"date":settled["actualResultDate"],"y":y,
                     "frozenEnsemble":frozen,
                     "elo":baseline,"research":formula["researchMeanHomeWinProbability"],
                     "originalAtUtc":snap["generatedAtUtc"]})
    rows.sort(key=lambda row:(row["date"],row["eventId"]))
    return rows

def _brier(rows:list[dict],w:float)->float|None:
    if not rows:return None
    return sum(((1-w)*r["elo"]+w*r["research"]-r["y"])**2 for r in rows)/len(rows)

def _date_interval(rows:list[dict],weight:float,reps:int=700)->list[float]|None:
    groups=defaultdict(list)
    for row in rows:
        delta=(row["elo"]-row["y"])**2-((1-weight)*row["elo"]+weight*row["research"]-row["y"])**2
        groups[row["date"]].append(delta)
    if len(groups)<MIN_DATE_BLOCKS:return None
    days=sorted(groups)
    rng=random.Random(16027)
    draws=[]
    for _ in range(reps):
        sample=[groups[days[rng.randrange(len(days))]] for _ in days]
        values=[d for group in sample for d in group]
        draws.append(sum(values)/len(values))
    draws.sort()
    return [round(draws[int(.025*reps)],6),round(draws[int(.975*reps)-1],6)]

def build_report(folder:Path,source_ratings:dict,now:datetime|None=None)->dict:
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:raise ValueError("Timezone-aware clock required")
    if source_ratings.get("season")!=2027 or source_ratings.get("mode")!="current" or not source_ratings.get("retrievedAtUtc"):
        raise ValueError("Expected verified current 2027 source metadata")
    samples=_rows(folder,now)
    dates=sorted({r["date"] for r in samples})
    # Never split through a single date: every contest on one game date
    # is in the same train or holdout block. No shuffled random CV.
    cut=max(1,int(len(dates)*.7))
    train=[r for r in samples if r["date"] in set(dates[:cut])]
    test=[r for r in samples if r["date"] in set(dates[cut:])]
    weight=(min(WEIGHTS,key=lambda w:(_brier(train,w),w))
            if len(train)>=MIN_TRAIN else DEFAULT_SHADOW)
    test_elo=_brier(test,0)
    test_candidate=_brier(test,weight)
    gain=(test_elo-test_candidate) if test_elo is not None and test_candidate is not None else None
    interval=_date_interval(test,weight) if len(test)>=MIN_VALIDATION else None
    published=[r for r in samples if r["frozenEnsemble"] is not None]
    published_comparison=[{**r,"research":r["frozenEnsemble"]} for r in published]
    # The published ensemble probability is already final: compare it directly
    # with first-pick Elo; do NOT apply the current fitted weight a second time.
    frozen_elo=_brier(published,0)
    frozen_ensemble=_brier(published_comparison,1.)
    frozen_gain=(frozen_elo-frozen_ensemble) if frozen_elo is not None and frozen_ensemble is not None else None
    frozen_interval=_date_interval(published_comparison,1.) if len(published)>=MIN_VALIDATION else None
    prospective_ready=(len(published)>=100 and len({r["date"] for r in published})>=12
                       and frozen_gain is not None and frozen_gain>=MIN_GAIN
                       and frozen_interval is not None and frozen_interval[0]>0)
    eligible=(prospective_ready and len(train)>=MIN_TRAIN and len(test)>=MIN_VALIDATION
              and len({r["date"] for r in test})>=MIN_DATE_BLOCKS
              and weight>0 and gain is not None and gain>=MIN_GAIN
              and interval is not None and interval[0]>0)
    return {
      "schemaVersion":1,"season":2027,"mode":"shadow","model":"conservative-sourced-prospective-ensemble",
      "sourceRetrievedAtUtc":source_ratings["retrievedAtUtc"],
      "generatedAtUtc":now.astimezone(timezone.utc).isoformat().replace("+00:00","Z"),
      "trainedThroughDate":max(dates) if dates else None,
      "weight":weight,"defaultShadowWeight":DEFAULT_SHADOW,
      "components":list(COMPONENTS),"minimumComponentFamilies":2,
      "pairedSettledGames":len(samples),"pairedSettledDates":len(dates),
      "trainingGames":len(train),"trainingDates":len({r["date"] for r in train}),
      "untouchedHoldoutGames":len(test),"untouchedHoldoutDates":len({r["date"] for r in test}),
      "eloHoldoutBrier":round(test_elo,6) if test_elo is not None else None,
      "ensembleHoldoutBrier":round(test_candidate,6) if test_candidate is not None else None,
      "holdoutBrierGain":round(gain,6) if gain is not None else None,
      "dateBlockBrierGain95":interval,
      "archivedPortfolioGames":len(published),
      "archivedPortfolioDates":len({r["date"] for r in published}),
      "archivedPortfolioEloBrier":round(frozen_elo,6) if frozen_elo is not None else None,
      "archivedPortfolioBrier":round(frozen_ensemble,6) if frozen_ensemble is not None else None,
      "archivedPortfolioBrierGain":round(frozen_gain,6) if frozen_gain is not None else None,
      "archivedPortfolioDateBlockGain95":frozen_interval,
      "prospectiveGatePassed":bool(prospective_ready),
      "scientificReviewEligible":bool(eligible),"promoteAutomatically":False,
      "candidateWeights":list(WEIGHTS),
      "policy":"Research weight tuning uses older independently verified first-pick frozen component probabilities and a later date-block holdout. Scientific review additionally requires at least 100 independently settled ORIGINAL frozen ensemble forecasts on 12 dates with positive date-block 95% evidence. No auto-promotion.",
      "caveats":["One fixed holdout selection is a monitoring diagnostic, not an unbiased repeated external evaluation after continued research.",
                 "The reconstructed prior-component holdout is retrospective recalibration, not original frozen ensemble outcomes. Only archivedPortfolio* fields constitute genuinely prospective portfolio scoring.",
                 "The mean combines heterogeneous models; correlations and missing component coverage can reduce realized accuracy.",
                 "Unavailable or invalid source features withhold a candidate rather than silently switching to a falsely advertised ensemble."]
    }

def validate_for_fixture(report:dict|None,ratings:dict,game_date:str)->float|None:
    if not report:return None
    if report.get("schemaVersion")!=1 or report.get("mode")!="shadow" or report.get("season")!=2027:
        raise ValueError("Unexpected ensemble policy or schema")
    if report.get("sourceRetrievedAtUtc")!=ratings.get("retrievedAtUtc"):
        raise ValueError("Ensemble and rating source are from different dates")
    if report.get("trainedThroughDate") and report["trainedThroughDate"]>=game_date:
        return None
    w=report.get("weight")
    if type(w) not in (float,int) or w not in WEIGHTS and w!=DEFAULT_SHADOW:
        raise ValueError("Invalid ensemble coefficient")
    return float(w)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ledger",type=Path,default=Path("web/public/forecasts"))
    p.add_argument("--ratings",type=Path,default=Path("web/public/current/2027.json"))
    p.add_argument("--out",type=Path,default=Path("web/public/current/forward-ensemble.json"))
    a=p.parse_args()
    ratings=json.loads(a.ratings.read_text(encoding="utf-8"))
    report=build_report(a.ledger,ratings)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:report[k] for k in ("weight","pairedSettledGames","trainingGames","untouchedHoldoutGames","scientificReviewEligible")}))
if __name__=="__main__":main()
