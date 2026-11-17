"""Daily archive freshness status is honest about missing and stale Git evidence."""
import json
import unittest
from datetime import datetime,timedelta,timezone
from tempfile import TemporaryDirectory
from pathlib import Path
from forecast.archive_health import assess_archive

NOW=datetime(2026,11,21,16,tzinfo=timezone.utc)
class ArchiveMonitorTests(unittest.TestCase):
 def test_missing_source_never_claims_healthy(self):
  with TemporaryDirectory() as p:
   x=assess_archive(Path(p),NOW)
   self.assertEqual(x["status"],"awaiting-first-archive")
   self.assertEqual(x["settledUniqueGames"],0)
 def test_recent_source_count_and_staleness(self):
  with TemporaryDirectory() as p:
   root=Path(p)
   (root/"index.json").write_text(json.dumps({
     "generatedAtUtc":(NOW-timedelta(hours=3)).isoformat().replace("+00:00","Z"),
     "uniqueGames":{"forecastedUniqueGames":21,"settledUniqueGames":12},
     "archiveHealth":{"sourceWarnings":[]}
   }))
   self.assertEqual(assess_archive(root,NOW)["status"],"current")
   self.assertEqual(assess_archive(root,NOW+timedelta(hours=30))["status"],"stale")
 def test_archived_fixture_with_no_first_pick_does_not_get_success(self):
  with TemporaryDirectory() as p:
   root=Path(p)
   (root/"index.json").write_text(json.dumps({
      "generatedAtUtc":NOW.isoformat().replace("+00:00","Z"),
      "uniqueGames":{"forecastedUniqueGames":0,"settledUniqueGames":0},
      "archiveHealth":{"sourceWarnings":[]}
   }))
   self.assertEqual(assess_archive(root,NOW)["status"],"no-picks-yet")
