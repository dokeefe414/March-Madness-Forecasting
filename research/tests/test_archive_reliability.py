"""Reproducible reliability contract for real future game archiving."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from forecast.snapshot import (
    forecast_scheduled, independently_verified_finals, settle_snapshots,
    write_ledger,
)
from forecast.audit import audit_ledger

NOW = datetime(2026,11,16,14,tzinfo=timezone.utc)
RATINGS = {"mode":"current","season":2027,
 "retrievedAtUtc":"2026-11-16T13:30:00Z",
 "lastGameDate":"2026-11-15",
 "teams":[
    {"name":"Duke","teamId":"ncaa-duke","rating":1580.0,"espnSourceTeamId":"150"},
    {"name":"North Carolina","teamId":"ncaa-unc","rating":1550.0,"espnSourceTeamId":"153"},
 ]}
def event(state="STATUS_SCHEDULED", done=False, h="78",a="72", starts="2026-11-17T01:00:00Z"):
    return {"id":"101","date":starts,
     "status":{"type":{"name":state,"completed":done}},
     "competitions":[{"neutralSite":False,"competitors":[
       {"homeAway":"home","score":h,"team":{"id":"150","location":"Blue Devils"}},
       {"homeAway":"away","score":a,"team":{"id":"153","location":"Tar Heels"}},
     ]}]}
FINAL={"id":"ncaa-001","date":"2026-11-16","home":"Duke","away":"North Carolina",
       "homeScore":78,"awayScore":72}

class ArchiveReliability(unittest.TestCase):
 def test_only_finished_score_matches_settle(self):
    original=forecast_scheduled([{"events":[event()]}],RATINGS,NOW)
    original["snapshotId"]="pre-001"
    now=NOW+timedelta(days=2)
    premature=independently_verified_finals([{"events":[event("STATUS_IN_PROGRESS",False)]}])
    self.assertEqual(premature,{})
    self.assertEqual(settle_snapshots([original],[FINAL],set(),now, premature),[])
    certified=independently_verified_finals([{"events":[event("STATUS_FINAL",True)]}])
    self.assertEqual(certified["101"]["homeScore"],78)
    settled=settle_snapshots([original],[FINAL],set(),now,certified)
    self.assertEqual(len(settled),1)
    self.assertTrue(settled[0]["espnFinalVerified"])
    wrong=independently_verified_finals([{"events":[event("STATUS_FINAL",True,h="79")]}])
    self.assertEqual(settle_snapshots([original],[FINAL],set(),now,wrong),[])
    moved=independently_verified_finals([{"events":[event("STATUS_FINAL",True,
       starts="2026-11-18T01:00:00Z")]}])
    self.assertEqual(settle_snapshots([original],[FINAL],set(),now,moved),[])
 def test_previous_day_retrieval_never_uses_current_day_results(self):
    unsafe={**RATINGS,"lastGameDate":"2026-11-16"}
    report=forecast_scheduled([{"events":[event()]}],unsafe,NOW)
    self.assertEqual(report["predictions"],[])
    self.assertEqual(report["coverage"]["unsafeSameDateRatings"],1)
    safe=forecast_scheduled([{"events":[event()]}],RATINGS,NOW)
    self.assertEqual(len(safe["predictions"]),1)
 def test_index_and_immutable_audit_and_no_regrade(self):
    with TemporaryDirectory() as tmp:
      root=Path(tmp)
      snap=forecast_scheduled([{"events":[event()]}],RATINGS,NOW)
      before=write_ledger(root,snap,[],NOW,verified_finals={})
      self.assertEqual(before["archiveHealth"]["everArchivedPredictions"],1)
      self.assertEqual(before["archiveHealth"]["verifiedNewSettlements"],0)
      first=next((root/"snapshots").glob("*.json")).read_bytes()
      later=NOW+timedelta(days=2)
      certified=independently_verified_finals([{"events":[event("STATUS_FINAL",True)]}])
      updated=write_ledger(root,{"predictions":[]},[FINAL],later,
                           verified_finals=certified,source_warnings=["ESPN date partial"])
      self.assertEqual(updated["uniqueGames"]["settledUniqueGames"],1)
      self.assertEqual(updated["archiveHealth"]["status"],"source-partial")
      self.assertEqual(updated["archiveHealth"]["verifiedNewSettlements"],1)
      self.assertEqual(audit_ledger(root)["settledPredictions"],1)
      self.assertEqual(next((root/"snapshots").glob("*.json")).read_bytes(),first)
      reread=write_ledger(root,{"predictions":[]},[FINAL],later+timedelta(days=1),
                          verified_finals=certified)
      self.assertEqual(reread["archiveHealth"]["verifiedNewSettlements"],0)
      self.assertEqual(reread["uniqueGames"]["settledUniqueGames"],1)

if __name__=="__main__":
 unittest.main()
