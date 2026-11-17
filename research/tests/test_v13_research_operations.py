"""Regression gates for v1.3 chronological research and production provenance."""
from __future__ import annotations
import json
import unittest
from datetime import datetime,date,timedelta,timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from forecast.advanced_models import build_advanced_models,train_boosted,train_tree,tree_output,MIN_TRAIN
from forecast.operations import build_operations
from forecast.snapshot import detect_schedule_changes
NOW=datetime(2026,11,17,20,tzinfo=timezone.utc)
def games(count=85):
    start=date(2026,8,1)
    teams=["A","B","C","D","E","F"]
    output=[]
    for i in range(count):
        a=teams[i%6]
        b=teams[(i+1+i//6)%6]
        if a==b:b=teams[(i+3)%6]
        output.append({"id":str(i),"date":(start+timedelta(days=i)).isoformat(),
                       "home":a,"away":b,"homeScore":70+(i%17),"awayScore":62+(i%13)})
    return output
def ratings(rows):
    return {"mode":"current","season":2027,"regularSeasonGames":len(rows),
            "retrievedAtUtc":"2026-11-17T18:00:00Z","lastGameDate":rows[-1]["date"]}
class AdvancedResearchTests(unittest.TestCase):
    def test_boosted_model_is_fitted_and_finite(self):
        r=games()
        report=build_advanced_models(r,ratings(r),NOW)
        self.assertEqual(report["mode"],"research-only")
        self.assertEqual(report["methods"]["gradientBoostedTrees"]["games"],len(r))
        self.assertGreater(len(report["perDate"]),0)
        for name,stats in report["methods"].items():
            self.assertGreaterEqual(stats["brier"],0,name)
            self.assertLessEqual(stats["brier"],1,name)
    def test_same_date_does_not_use_that_dates_outcomes(self):
        r=games()
        a=build_advanced_models(r,ratings(r),NOW)
        modified=[dict(x) for x in r]
        modified[3]["homeScore"],modified[3]["awayScore"]=modified[3]["awayScore"],modified[3]["homeScore"]
        b=build_advanced_models(modified,ratings(modified),NOW)
        # The game on changed day is predicted identically before updating.
        original=next(x for x in a["auditFirst80"] if x["id"]=="3")
        altered=next(x for x in b["auditFirst80"] if x["id"]=="3")
        self.assertEqual(original,altered)
        # Previous-date outcomes eventually alter posterior / Elo states.
        self.assertNotEqual(a["auditFirst80"][-1],b["auditFirst80"][-1])
    def test_current_date_embargo(self):
        r=games()
        a=build_advanced_models(r,ratings(r),NOW)
        latest={"id":"not-before","date":"2026-11-17","home":"A","away":"B",
                "homeScore":100,"awayScore":2}
        altered=r+[latest]
        b=build_advanced_models(altered,ratings(altered),NOW)
        self.assertEqual(a["methods"],b["methods"])
        self.assertEqual(a["auditFirst80"],b["auditFirst80"])
    def test_source_count_and_duplicate_guard(self):
        r=games(4)
        with self.assertRaises(ValueError):
            build_advanced_models(r,{**ratings(r),"regularSeasonGames":3},NOW)
        with self.assertRaises(ValueError):
            build_advanced_models(r+[dict(r[0])],ratings(r+[r[0]]),NOW)
    def test_cart_can_learn_numeric_split(self):
        rows=[((float(i),0.,0.,0.),(1. if i>30 else -1.),.25) for i in range(70)]
        tree=train_tree(rows)
        self.assertEqual(tree[0],"split")
        self.assertGreater(tree_output(tree,(60.,0.,0.,0.)),tree_output(tree,(2.,0.,0.,0.)))
class OperationsTests(unittest.TestCase):
    def test_changed_espn_start_is_review_only(self):
        first={"snapshotId":"one","predictions":[{"eventId":"140","scheduledStartUtc":"2026-11-18T21:00:00Z",
                                  "home":"A","away":"B"}]}
        board={"events":[{"id":"140","date":"2026-11-18T22:00:00Z"}]}
        row=detect_schedule_changes([first],[board])
        self.assertEqual(len(row),1)
        self.assertEqual(row[0]["status"],"source-time-changed-review")
        self.assertEqual(first["predictions"][0]["scheduledStartUtc"],"2026-11-18T21:00:00Z")
        self.assertEqual(detect_schedule_changes([first],[{"events":[]}]),[])
    def test_duplicate_captures_do_not_inflate_unique_games(self):
        with TemporaryDirectory() as folder:
            root=Path(folder)
            (root/"snapshots").mkdir()
            (root/"settlements").mkdir()
            for n in ("s1","s2"):
                snap={"snapshotId":n,"generatedAtUtc":"2026-11-17T14:00:00Z",
                      "predictions":[{"eventId":"123","home":"A","away":"B",
                                      "scheduledStartUtc":"2026-11-18T22:00:00Z"}]}
                (root/"snapshots"/(n+".json")).write_text(json.dumps(snap))
            index={"generatedAtUtc":"2026-11-17T18:00:00Z",
                   "uniqueGames":{"forecastedUniqueGames":1,"settledUniqueGames":0},
                   "archiveHealth":{"sourceWarnings":[],"verifiedFixtureRun":True,
                       "fixtureCoverage":{"eventsSeen":30,"unmatchedOrAmbiguous":2},
                       "observedScheduleChanges":[]}}
            (root/"index.json").write_text(json.dumps(index))
            report=build_operations(root,NOW)
            self.assertEqual(report["uniqueArchivedEvents"],1)
            self.assertEqual(report["repeatSnapshots"],1)
            self.assertEqual(report["state"],"operational")
            self.assertEqual(report["checkedSourceEvents"],30)
    def test_missing_archive_is_not_healthy(self):
        with TemporaryDirectory() as folder:
            report=build_operations(Path(folder),NOW)
            self.assertEqual(report["state"],"degraded")
            self.assertEqual(report["uniqueArchivedEvents"],0)
if __name__=="__main__":
    unittest.main()
