"""Auditable unique-game forward scorecard; never confuse snapshots with games.

One ESPN event may have several immutable predictions. For public accuracy we
select the EARLIEST archived snapshot of each event BEFORE looking at outcomes.
Only that frozen first forecast may later be settled and counted. Distinct
experimental model probabilities are scored against the same settled games.
No retrospective rolling-date test is presented as an actual pretipoff pick.
"""
from __future__ import annotations

import math
from collections import defaultdict

def _mean(rows: list[dict], field: str) -> float | None:
    return round(sum(float(r[field]) for r in rows)/len(rows),6) if rows else None

def _rate(p: float, observed: int) -> dict:
    if not 0 < p < 1 or not math.isfinite(p):
        raise ValueError("Invalid original forward forecast probability")
    return {"brier":(p-observed)**2,
            "logLoss":-math.log(p if observed else 1-p),
            "correct":float((p>.5 and observed==1) or (p<.5 and observed==0)) if p!=.5 else .5}

def _stats(items: list[dict]) -> dict:
    return {"games":len(items), "accuracy":_mean(items,"correct"),
            "brier":_mean(items,"brier"), "logLoss":_mean(items,"logLoss")}

def summarize_forward(snapshots: list[dict], settlements: list[dict]) -> dict:
    """Deterministic from source immutable files; no guessing on unsettled picks."""
    first: dict[str, tuple[dict,dict]] = {}
    for snap in sorted(snapshots,key=lambda s:(s["generatedAtUtc"],s["snapshotId"])):
        for pred in snap["predictions"]:
            first.setdefault(str(pred["eventId"]),(snap,pred))
    settled = {r["predictionKey"]:r for r in settlements}
    selected = []
    for eid,(snap,pred) in first.items():
        key=snap["snapshotId"]+":"+eid
        if key not in settled:
            continue
        row=settled[key]
        y=int(row["observedHome"])
        if y not in (0,1):
            raise ValueError("Settled outcome must be binary")
        p=float(pred["homeWinProbability"])
        scored=_rate(p,y)
        confidence=max(p,1-p)
        selected.append({"eventId":eid,"date":row["actualResultDate"],
                         "home":pred["home"],"away":pred["away"],
                         "model":pred["model"],"probability":round(p,7),
                         "observedHome":y,"confidence":round(confidence,7),
                         **scored,
                         "elo":(float(pred["baselineHomeWinProbability"])
                                if pred.get("baselineHomeWinProbability") is not None else None),
                         "challenger":(float(pred["challengerHomeWinProbability"])
                                if pred.get("challengerHomeWinProbability") is not None else None),
                         "stateSpace":(float(pred["stateSpaceHomeWinProbability"])
                                if pred.get("stateSpaceHomeWinProbability") is not None else None)})
    selected.sort(key=lambda r:(r["date"],r["eventId"]))
    by_model=defaultdict(list)
    comparable=defaultdict(list)
    for row in selected:
        by_model[row["model"]].append(row)
        for key,label in (("elo","Elo reference"),("challenger","Online challenger"),
                          ("stateSpace","State-space research")):
            if row[key] is not None:
                comparable[label].append(_rate(row[key],row["observedHome"]))
    timeline=[]
    cumulative=[]
    for r in selected:
        cumulative.append(r)
        timeline.append({"date":r["date"],"eventId":r["eventId"],
                         "games":len(cumulative),"accuracy":_mean(cumulative,"correct"),
                         "brier":_mean(cumulative,"brier")})
    calibration=[]
    for i in range(5):
        lo=.5+i*.1
        hi=lo+.1
        bucket=[r for r in selected if lo<=r["confidence"]<(hi if i<4 else 1.01)]
        calibration.append({"bin":f"{int(lo*100)}–{int(hi*100)}%",
                            "count":len(bucket),
                            "predictedConfidence":round(sum(r["confidence"] for r in bucket)/len(bucket),6) if bucket else None,
                            "realizedAccuracy":_mean(bucket,"correct")})
    misses=[{"date":r["date"],"eventId":r["eventId"],"home":r["home"],"away":r["away"],
             "probability":r["probability"],"confidence":r["confidence"],
             "model":r["model"],"note":("Higher-confidence upset: investigate whether recent strength and opponent quality were overestimated."
                          if r["confidence"]>=.7 else "Toss-up or moderate favorite lost; one outcome alone is not a reason to retune.")}
            for r in selected if r["correct"]==0]
    elo_rows=[r for r in selected if r["elo"] is not None]
    paired_elo=[_rate(r["elo"],r["observedHome"]) for r in elo_rows]
    paired_used=[_rate(r["probability"],r["observedHome"]) for r in elo_rows]
    duel=[r for r in selected if r["elo"] is not None and r["challenger"] is not None]
    brier_gain=(sum((_rate(r["elo"],r["observedHome"])["brier"]-
                      _rate(r["challenger"],r["observedHome"])["brier"]) for r in duel)/len(duel)
                if duel else None)
    return {
        "schemaVersion":1,
        "unit":"one earliest archived pre-tipoff prediction per source ESPN event ID",
        "forecastedUniqueGames":len(first), "settledUniqueGames":len(selected),
        "score":_stats(selected),
        "byModel":{model:_stats(rows) for model,rows in sorted(by_model.items())},
        "reference":{
            "pairedGames":len(elo_rows),
            "eloBrier":_mean(paired_elo,"brier"),
            "actualModelBrier":_mean(paired_used,"brier"),
        },
        "shadowComparison":{
            "pairedGames":len(duel),
            "eloBrier":_mean([_rate(r["elo"],r["observedHome"]) for r in duel],"brier"),
            "challengerBrier":_mean([_rate(r["challenger"],r["observedHome"]) for r in duel],"brier"),
            "challengerBrierGain":round(brier_gain,6) if brier_gain is not None else None,
        },
        "experimentalComparisons":{label:_stats(rows) for label,rows in comparable.items()},
        "calibration":calibration, "trajectory":timeline[-400:],
        "recentMisses":list(reversed(misses[-12:])),
        "warnings":[
            "No winner accuracy is shown until genuine before-tipoff predictions have settled.",
            "Accuracy is for one earliest forecast per ESPN event; it is not a guarantee of future prediction success.",
            "Opposing probability models are compared on the same outcomes only when their probabilities were frozen before game start.",
            "A wrong prediction is evidence for later scheduled retraining, not permission for immediate post-hoc adjustment.",
        ],
    }
