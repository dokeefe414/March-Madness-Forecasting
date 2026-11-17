"""Readable, derived settlement observability without altering immutable evidence.

A pending pick is not a failed settlement. The classification depends on UTC
scheduled start and age. Missing source finals can never be imputed.
"""
from __future__ import annotations
import argparse
import json
from datetime import datetime,timezone,timedelta
from pathlib import Path
from .snapshot import parse_time

def settlement_diagnostics(folder:Path,now:datetime|None=None)->dict:
    now=(now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    snapshots=[]
    for path in sorted((folder/"snapshots").glob("*.json")):
        snapshots.append(json.loads(path.read_text(encoding="utf-8")))
    settled=set()
    for path in sorted((folder/"settlements").glob("*.json")):
        for row in json.loads(path.read_text(encoding="utf-8")).get("results",[]):
            settled.add(row["predictionKey"])
    counters={"future":0,"recentlyStarted":0,"awaitingVerifiedFinal":0,
              "delayedOver48h":0,"settledSnapshots":0}
    pending=[]
    for s in snapshots:
        for p in s.get("predictions",[]):
            key=s["snapshotId"]+":"+str(p["eventId"])
            if key in settled:
                counters["settledSnapshots"]+=1
                continue
            tip=parse_time(p["scheduledStartUtc"])
            delay=(now-tip).total_seconds()/3600
            if delay<0:status="future"
            elif delay<5:status="recentlyStarted"
            elif delay<=48:status="awaitingVerifiedFinal"
            else:status="delayedOver48h"
            counters[status]+=1
            pending.append({"eventId":str(p["eventId"]),"home":p["home"],"away":p["away"],
                            "scheduledStartUtc":p["scheduledStartUtc"],"status":status,
                            "hoursSinceListedStart":round(max(0,delay),1)})
    # Count snapshots separately from unique fixture IDs so multiple public
    # captures of the same contest are not called independent future games.
    unique={r["eventId"]:r for r in pending}
    index=folder/"index.json"
    data=json.loads(index.read_text(encoding="utf-8")) if index.exists() else {}
    forward=data.get("uniqueGames") or {}
    return {"schemaVersion":1,"checkedAtUtc":now.isoformat().replace("+00:00","Z"),
            "archiveUpdatedAtUtc":data.get("generatedAtUtc"),"snapshots":len(snapshots),
            "sourceVerifiedUniqueGames":forward.get("forecastedUniqueGames",0),
            "settledUniqueGames":forward.get("settledUniqueGames",0),
            "counters":counters,
            "pendingUniqueEvents":len(unique),
            "oldestDelayed":sorted((r for r in unique.values() if r["status"]=="delayedOver48h"),
                                   key=lambda r:r["scheduledStartUtc"])[:25],
            "policy":"Descriptive delays since scheduled tipoff, not confirmation of actual game completion. No speculative settlement or changed probabilities."}
def main()->None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ledger",type=Path,default=Path("web/public/forecasts"))
    p.add_argument("--out",type=Path,default=Path("web/public/current/settlement-health.json"))
    a=p.parse_args()
    result=settlement_diagnostics(a.ledger)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result))
if __name__=="__main__":
    main()
