"""v1.2 settlement backlog is derived only from immutable public artifacts."""
import json
import unittest
from datetime import datetime,timezone,timedelta
from tempfile import TemporaryDirectory
from pathlib import Path
from forecast.settlement_health import settlement_diagnostics
NOW=datetime(2026,11,19,17,tzinfo=timezone.utc)
def build(root:Path,starts:datetime,settled=False):
 (root/"snapshots").mkdir(exist_ok=True)
 (root/"settlements").mkdir(exist_ok=True)
 snapshot={"snapshotId":"20261117T150000Z",
   "generatedAtUtc":"2026-11-17T15:00:00Z",
   "predictions":[{"eventId":"espn-1","home":"A","away":"B","scheduledStartUtc":starts.isoformat()}]}
 (root/"snapshots"/"20261117T150000Z.json").write_text(json.dumps(snapshot))
 if settled:
  (root/"settlements"/"one.json").write_text(json.dumps({"results":[{"predictionKey":"20261117T150000Z:espn-1"}]}))
 (root/"index.json").write_text(json.dumps({"generatedAtUtc":"2026-11-17T15:00:00Z",
   "uniqueGames":{"forecastedUniqueGames":1,"settledUniqueGames":int(settled)}}))
class SettlementHealthTests(unittest.TestCase):
 def test_before_tipoff_pending_not_failure(self):
  with TemporaryDirectory() as p:
   root=Path(p);build(root,NOW+timedelta(hours=10))
   d=settlement_diagnostics(root,NOW)
   self.assertEqual(d["counters"]["future"],1)
   self.assertEqual(d["counters"]["delayedOver48h"],0)
 def test_old_unverified_is_review_only(self):
  with TemporaryDirectory() as p:
   root=Path(p);build(root,NOW-timedelta(hours=60))
   d=settlement_diagnostics(root,NOW)
   self.assertEqual(d["counters"]["delayedOver48h"],1)
   self.assertEqual(d["oldestDelayed"][0]["eventId"],"espn-1")
   self.assertEqual(d["settledUniqueGames"],0)
 def test_settled_is_not_pending(self):
  with TemporaryDirectory() as p:
   root=Path(p);build(root,NOW-timedelta(hours=60),True)
   d=settlement_diagnostics(root,NOW)
   self.assertEqual(d["counters"]["settledSnapshots"],1)
   self.assertEqual(d["pendingUniqueEvents"],0)
 def test_empty_repo_does_not_fabricate_records(self):
  with TemporaryDirectory() as p:
   d=settlement_diagnostics(Path(p),NOW)
   self.assertEqual(d["sourceVerifiedUniqueGames"],0)
   self.assertEqual(d["pendingUniqueEvents"],0)
if __name__=="__main__":unittest.main()
