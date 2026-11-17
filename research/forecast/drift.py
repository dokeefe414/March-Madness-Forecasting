"""Prospective-only forecast error drift diagnostics, never an automatic model switch.

Input is the immutable-ledger-derived public first-pick scorecard. We compare
nonoverlapping consecutive windows of 25 individually settled ESPN games.
No historical replay, fabricated outcome, or within-date model refitting.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

WINDOW=25
def diagnose_forward(forward:dict)->dict:
    timeline=forward.get("trajectory") or []
    rolling=forward.get("rolling25") or []
    total=int(forward.get("settledUniqueGames",0))
    # The forward report retains at most 400 chronology entries. If 400
    # have accumulated, use only its documented visible recent segment.
    if total<2*WINDOW or len(timeline)<2*WINDOW:
        return {"schemaVersion":1,"status":"collecting","settledUniqueGames":total,
                "windowGames":WINDOW,"recentBrier":None,"priorBrier":None,
                "brierDelta":None,"alert":False,"consecutiveWindows":0,
                "reason":"At least 50 genuinely settled first picks are needed for nonoverlapping drift comparison."}
    # Recover per-game Brier from running cumulative sums, rather than use
    # rolling25 observations that overlap or peek into earlier periods.
    # This calculation is valid only if consecutive trajectory points have
    # cumulative counts separated by exactly one (bounded report retention).
    last=timeline[-50:]
    if len(last)!=50 or any(last[i]["games"]!=last[i-1]["games"]+1 for i in range(1,50)):
        return {"schemaVersion":1,"status":"insufficient-history","settledUniqueGames":total,
                "windowGames":WINDOW,"recentBrier":None,"priorBrier":None,
                "brierDelta":None,"alert":False,"consecutiveWindows":0,
                "reason":"Insufficient contiguous chronological first-pick evidence for reliable drift analysis."}
    # Cumulative Brier at game 0 is necessarily zero.
    previous_total=(timeline[-51]["games"]*timeline[-51]["brier"]
                    if len(timeline)>=51 else 0.)
    losses=[]
    for row in last:
        aggregate=row["games"]*row["brier"]
        losses.append(aggregate-previous_total)
        previous_total=aggregate
    prior=sum(losses[:WINDOW])/WINDOW
    recent=sum(losses[WINDOW:])/WINDOW
    delta=recent-prior
    # A single 25-game jump is a review cue, not a statistical claim or an
    # actionable model promotion. Error spikes can arise from small samples.
    alert=delta>=.05
    return {"schemaVersion":1,"status":"review" if alert else "observing",
            "settledUniqueGames":total,"windowGames":WINDOW,
            "priorBrier":round(prior,5),"recentBrier":round(recent,5),
            "brierDelta":round(delta,5),"alert":alert,"consecutiveWindows":1 if alert else 0,
            "reason":("Descriptive Brier deterioration of at least 0.05 across nonoverlapping 25-game periods; investigate, do not automatically retrain or promote."
                      if alert else "No predeclared material error increase in the latest two nonoverlapping 25-game windows."),
            "lastSettledEventId":last[-1]["eventId"],"lastSettledDate":last[-1]["date"],
            "policy":"Diagnostic only; no change to immutable picks or model promotion."}

def main()->None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger",type=Path,default=Path("web/public/forecasts/index.json"))
    parser.add_argument("--out",type=Path,default=Path("web/public/current/drift.json"))
    args=parser.parse_args()
    forward={}
    if args.ledger.exists():
        forward=json.loads(args.ledger.read_text(encoding="utf-8")).get("uniqueGames",{})
    result=diagnose_forward(forward)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result))
if __name__=="__main__":
    main()
