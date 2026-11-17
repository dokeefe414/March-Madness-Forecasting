"""Independent operational status from immutable source evidence.

This is not a live API uptime monitor: stale timestamps, unverified expected
finals, repeated snapshots and partial feed coverage are review signals only.
The status file can be published even if the recorder has never succeeded.
"""
from __future__ import annotations
import argparse
import json
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from .archive_health import assess_archive
from .settlement_health import settlement_diagnostics
from .snapshot import parse_time

def build_operations(folder:Path,now:datetime|None=None)->dict:
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:raise ValueError("Operations status requires aware as-of clock")
    now=now.astimezone(timezone.utc)
    health=assess_archive(folder,now)
    settlement=settlement_diagnostics(folder,now)
    snapshots=[]
    for path in sorted((folder/"snapshots").glob("*.json")):
        raw=json.loads(path.read_text(encoding="utf-8"))
        snapshots.append(raw)
    events=Counter(str(p["eventId"]) for snap in snapshots for p in snap.get("predictions",[]))
    repeated=sum(max(0,n-1) for n in events.values())
    delays=settlement["counters"]["delayedOver48h"]
    warnings=list(health.get("sourceWarnings") or [])
    # Severity reflects verifiability, not predictive skill; delayed finals
    # alone are a review notice, never an automatic prediction failure.
    status=health["status"]
    state=("degraded" if status in {"stale","source-partial","no-picks-yet","awaiting-first-archive"}
           else "review" if delays>0 else
           "off-season" if status=="off-season" else "operational")
    latest=health.get("lastArchiveUtc")
    return {
      "schemaVersion":1,"checkedAtUtc":now.isoformat().replace("+00:00","Z"),
      "state":state,"archiveStatus":status,"lastSuccessfulCaptureUtc":latest,
      "captureAgeHours":health.get("ageHours"),
      "checkedSourceEvents":(health.get("fixtureCoverage") or {}).get("eventsSeen"),
      "unmatchedSourceEvents":(health.get("fixtureCoverage") or {}).get("unmatchedOrAmbiguous"),
      "sourceWarnings":warnings,
      "uniqueArchivedEvents":len(events),"repeatSnapshots":repeated,
      "uniqueSettledEvents":settlement["settledUniqueGames"],
      "delayedSnapshotEntries":delays,
      "delayedExamples":settlement["oldestDelayed"][:8],
      "checks":[
        {"name":"Archived source-capture freshness","state":"review" if state=="off-season" else "pass" if status=="current" else "fail" if state=="degraded" else "pass",
         "detail":health["message"]},
        {"name":"Source-day availability","state":"review" if not latest else "fail" if warnings else "pass",
         "detail":f"{len(warnings)} feed-day warnings in last completed archive; unverified source days never become picks"},
        {"name":"Verified-final backlog","state":"review" if delays else "pass",
         "detail":f"{delays} timestamped snapshot entries older than 48h without independently verified settlement"},
        {"name":"Repeat captures","state":"review" if repeated else "pass",
         "detail":f"{repeated} additional pregame snapshots for previously captured ESPN event IDs; only first pick counts for unique-game forward accuracy"}
      ],
      "policy":"Static immutable Git receipt, not a continuous service probe. No fabricated outcomes, no inference that rescheduled games began as listed, and no auto model promotion."}
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ledger",type=Path,default=Path("web/public/forecasts"))
    p.add_argument("--out",type=Path,default=Path("web/public/current/operations.json"))
    a=p.parse_args()
    report=build_operations(a.ledger)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report))
if __name__=="__main__":main()
