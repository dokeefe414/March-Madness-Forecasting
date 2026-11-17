"""Expose and monitor whether the Git-committed forecast archive is updating.

No false '0% correct' or fictional live predictions when the autonomous
archiver has not yet run. This report is derived from source-controlled public
evidence; GitHub scheduling and provider responses can still be delayed.
"""
from __future__ import annotations
import argparse
import json
from datetime import datetime,date,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from .snapshot import parse_time
EASTERN=ZoneInfo("America/New_York")
SEASON_START=date(2026,11,1)
SEASON_END=date(2027,3,14)

def assess_archive(folder:Path,now:datetime|None=None,max_age_hours:float=26.)->dict:
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:raise ValueError("Archive monitor requires UTC-aware time")
    now=now.astimezone(timezone.utc)
    local_day=now.astimezone(EASTERN).date()
    active=SEASON_START<=local_day<=SEASON_END
    index=folder/"index.json"
    if not index.exists():
        return {"schemaVersion":1,"status":"awaiting-first-archive" if active else "off-season",
                "lastArchiveUtc":None,"ageHours":None,"archivedPredictions":0,
                "settledUniqueGames":0,"sourceWarnings":[],
                "checkedAtUtc":now.isoformat().replace("+00:00","Z"),
                "message":"No actual before-tipoff predictions have yet been committed to Git. Accuracy is unavailable."}
    data=json.loads(index.read_text(encoding="utf-8"))
    stamped=parse_time(data["generatedAtUtc"])
    age=(now-stamped).total_seconds()/3600
    if age<-.05:raise ValueError("Archive manifest timestamp is in the future")
    oldest=data.get("uniqueGames",{}).get("forecastedUniqueGames",0)
    scored=data.get("uniqueGames",{}).get("settledUniqueGames",0)
    archive_meta=data.get("archiveHealth") or {}
    warnings=archive_meta.get("sourceWarnings") or []
    coverage=archive_meta.get("fixtureCoverage") or {}
    clean_empty=bool(archive_meta.get("verifiedFixtureRun") and not warnings and
                     coverage.get("eventsSeen") is not None and
                     coverage.get("unmatchedOrAmbiguous",0)==0 and
                     coverage.get("unsafeSameDateRatings",0)==0 and
                     not oldest)
    status=("off-season" if not active else
            "stale" if age>max_age_hours else
            "source-partial" if warnings else
            "no-eligible-fixtures" if clean_empty else
            "no-picks-yet" if not oldest else "current")
    msg={
      "current":"Archive has a recent source-backed run; outcomes may still be pending.",
      "stale":"Archived prediction evidence is older than expected; inspect the GitHub pregame workflow.",
      "source-partial":"Recent archive exists but an ESPN schedule day was unavailable.",
      "no-picks-yet":"Archiver ran but no verified, strictly pre-tipoff predictions have been committed.",
      "no-eligible-fixtures":"A verified source check ran but found no currently eligible, unambiguous future fixtures.",
      "off-season":"Archive is outside the regular-season update period.",
    }[status]
    return {"schemaVersion":1,"status":status,
            "checkedAtUtc":now.isoformat().replace("+00:00","Z"),
            "lastArchiveUtc":data["generatedAtUtc"],"ageHours":round(age,2),
            "archivedPredictions":oldest,"settledUniqueGames":scored,
            "verifiedFixtureRun":bool(archive_meta.get("verifiedFixtureRun")),
            "fixtureCoverage":coverage,
            "sourceWarnings":warnings,"message":msg,
            "ageThresholdHours":max_age_hours,
            "policy":"This status is a repository artifact check, not a real-time feed monitor"}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ledger",type=Path,default=Path("web/public/forecasts"))
    p.add_argument("--out",type=Path)
    p.add_argument("--require-recent",action="store_true")
    p.add_argument("--max-age-hours",type=float,default=26.)
    args=p.parse_args()
    report=assess_archive(args.ledger,max_age_hours=args.max_age_hours)
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2))
    if args.require_recent and report["status"] in {"awaiting-first-archive","stale","no-picks-yet"}:
        raise SystemExit(f"Pregame archiver needs attention: {report['status']}")
if __name__=="__main__":
    main()
