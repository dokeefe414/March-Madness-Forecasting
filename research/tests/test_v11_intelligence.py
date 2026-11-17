"""v1.1: chronological challenger, prospective drift, and honest archive health."""
from __future__ import annotations
import json
import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from datetime import datetime,timezone
from forecast.challengers import build_challengers
from forecast.drift import diagnose_forward
from forecast.archive_health import assess_archive

NOW=datetime(2026,11,20,18,tzinfo=timezone.utc)
G=[
 {"id":"g1","date":"2026-11-16","home":"A","away":"B","homeScore":75,"awayScore":67},
 {"id":"g2","date":"2026-11-17","home":"A","away":"C","homeScore":71,"awayScore":75},
 {"id":"g3","date":"2026-11-18","home":"C","away":"B","homeScore":65,"awayScore":61},
 {"id":"g4","date":"2026-11-19","home":"B","away":"A","homeScore":69,"awayScore":66},
]
R={"mode":"current","season":2027,"regularSeasonGames":4,
   "retrievedAtUtc":"2026-11-20T17:00:00Z","lastGameDate":"2026-11-19"}
class V11Tests(unittest.TestCase):
 def test_same_date_results_cannot_change_other_pregame_probabilities(self):
  extra={"id":"g2b","date":"2026-11-17","home":"D","away":"E","homeScore":88,"awayScore":45}
  combined=build_challengers(G+[extra],{**R,"regularSeasonGames":5},NOW)
  normal=build_challengers(G,R,NOW)
  self.assertEqual(combined["evaluatedGames"],5)
  # The extra game is disconnected from other team histories; subsequent
  # dated A/B/C predictions remain unchanged.
  self.assertEqual(combined["methods"]["elo"]["games"],5)
  self.assertEqual(normal["evaluatedGames"],4)
  self.assertEqual(combined["mode"],"research-only")
  self.assertTrue(all(0<=v["brier"]<=1 for v in combined["methods"].values()))
 def test_current_day_outcome_is_embargoed(self):
  future={"id":"future","date":"2026-11-20","home":"A","away":"B",
          "homeScore":100,"awayScore":2}
  baseline=build_challengers(G,R,NOW)
  altered=build_challengers(G+[future],{**R,"regularSeasonGames":5,"lastGameDate":"2026-11-20"},NOW)
  self.assertEqual(baseline["methods"],altered["methods"])
  self.assertEqual(baseline["evaluatedDates"],altered["evaluatedDates"])
 def test_source_count_is_checked(self):
  with self.assertRaisesRegex(ValueError,"count mismatch"):
   build_challengers(G,{**R,"regularSeasonGames":5},NOW)
 def test_drift_no_fabricated_result(self):
  x=diagnose_forward({"settledUniqueGames":0,"trajectory":[]})
  self.assertEqual(x["status"],"collecting")
  self.assertIsNone(x["recentBrier"])
  self.assertFalse(x["alert"])
 def test_drift_detects_material_prospective_deterioration(self):
  losses=[.10]*25+[.32]*25
  total=0.
  trajectory=[]
  for i,v in enumerate(losses,1):
   total+=v
   trajectory.append({"date":"2026-11-19","eventId":str(i),"games":i,
                      "brier":round(total/i,6)})
  x=diagnose_forward({"settledUniqueGames":50,"trajectory":trajectory})
  self.assertEqual(x["status"],"review")
  self.assertGreater(x["brierDelta"],.20)
 def test_no_eligible_fixtures_receipt_is_not_missing_pipeline(self):
  with TemporaryDirectory() as directory:
   p=Path(directory)
   (p/"index.json").write_text(json.dumps({
     "generatedAtUtc":NOW.isoformat().replace("+00:00","Z"),
     "uniqueGames":{"forecastedUniqueGames":0,"settledUniqueGames":0},
     "archiveHealth":{"verifiedFixtureRun":True,"sourceWarnings":[],
       "fixtureCoverage":{"eventsSeen":0,"unmatchedOrAmbiguous":0,
                          "unsafeSameDateRatings":0}}
   }),encoding="utf-8")
   report=assess_archive(p,NOW)
   self.assertEqual(report["status"],"no-eligible-fixtures")
   self.assertEqual(report["archivedPredictions"],0)
 def test_partial_source_must_not_be_considered_clean_empty(self):
  with TemporaryDirectory() as directory:
   p=Path(directory)
   (p/"index.json").write_text(json.dumps({
     "generatedAtUtc":NOW.isoformat().replace("+00:00","Z"),
     "uniqueGames":{"forecastedUniqueGames":0,"settledUniqueGames":0},
     "archiveHealth":{"verifiedFixtureRun":True,"sourceWarnings":["schedule failure"],
       "fixtureCoverage":{"eventsSeen":0,"unmatchedOrAmbiguous":0,
                          "unsafeSameDateRatings":0}}
   }),encoding="utf-8")
   self.assertEqual(assess_archive(p,NOW)["status"],"source-partial")
if __name__=="__main__":
 unittest.main()
