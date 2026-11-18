"""v1.9: earliest-first, verified-only daily accuracy and score shadow tests."""
import json
import math
import unittest
from datetime import datetime,timedelta,timezone
from tempfile import TemporaryDirectory
from pathlib import Path
from forecast.score_shadow import score_shadow
from forecast.accuracy_research import derive

NOW=datetime(2026,12,30,18,tzinfo=timezone.utc)

def team(name,off=108,defn=98,n=8):
    return {"teamId":name,"name":name,"wins":12,"losses":2,"possessionGames":n,
        "adjOff100":off,"adjDef100":defn,"offRating100":off,"defRating100":defn,
        "pacePossessions":70,"pointsForPerGame":77,"pointsAgainstPerGame":71}

def write(root,day="2026-11-18",frozen=True,results=True):
    (root/"snapshots").mkdir(exist_ok=True)
    (root/"settlements").mkdir(exist_ok=True)
    snapshot={"snapshotId":"early","generatedAtUtc":"2026-11-17T12:00:00Z",
      "ratingRetrievedAtUtc":"2026-11-17T11:00:00Z",
      "timeBufferMinutes":15,
      "predictions":[{"eventId":"one","scheduledStartUtc":day+"T23:00:00Z",
        "scheduledEasternDate":day,"home":"Home","away":"Away",
        "homeWinProbability":.68,"baselineHomeWinProbability":.65,
        "ensembleHomeWinProbability":.64,"challengerHomeWinProbability":.62,
        "model":"Elo",
        "researchScoreProjection":score_shadow(team("H"),team("A")) if frozen else None}]}
    (root/"snapshots"/"early.json").write_text(json.dumps(snapshot))
    late={**snapshot,"snapshotId":"late","generatedAtUtc":"2026-11-18T12:00:00Z",
         "ratingRetrievedAtUtc":"2026-11-18T11:00:00Z",
         "predictions":[{**snapshot["predictions"][0],"homeWinProbability":.09}]}
    (root/"snapshots"/"late.json").write_text(json.dumps(late))
    if results:
        (root/"settlements"/"verified.json").write_text(json.dumps({"results":[
            {"predictionKey":"early:one","eventId":"one","home":"Home","away":"Away",
             "actualResultDate":day,"homeScore":72,"awayScore":68,"observedHome":1,
             "espnFinalVerified":True},
            {"predictionKey":"late:one","eventId":"one","home":"Home","away":"Away",
             "actualResultDate":day,"homeScore":72,"awayScore":68,"observedHome":1,
             "espnFinalVerified":True}]}))
    (root/"index.json").write_text(json.dumps({"generatedAtUtc":"2026-11-18T23:00:00Z",
       "archiveHealth":{"completedEspnEventsChecked":1,"sourceWarnings":[]},
       "uniqueGames":{"forecastedUniqueGames":1,"settledUniqueGames":int(results)}}))

class SourceScoreTests(unittest.TestCase):
 def test_verified_possession_model_then_valid_scoring_fallback(self):
    a=score_shadow(team("H"),team("A"))
    self.assertEqual(a["method"],"opponent-adjusted-possessions")
    self.assertEqual(a["verifiedPossessionGamesMinimum"],8)
    self.assertEqual(a["projectedTotal"],round(a["projectedHomeScore"]+a["projectedAwayScore"],1))
    low=score_shadow(team("H",n=2),team("A"))
    self.assertEqual(low["method"],"raw-scoring-means")
    self.assertIsNone(low["verifiedPossessionGamesMinimum"])
    missing=team("A",n=0)
    missing.pop("pointsForPerGame")
    self.assertIsNone(score_shadow(team("H"),missing))
 def test_side_swap_symmetry_and_source_risk(self):
    a=team("H",off=118,defn=94)
    b=team("A",off=101,defn=107)
    ab=score_shadow(a,b);ba=score_shadow(b,a)
    self.assertEqual(ab["projectedHomeScore"],ba["projectedAwayScore"])
    self.assertEqual(ab["projectedAwayScore"],ba["projectedHomeScore"])
    broken=team("A");broken["pacePossessions"]=130
    self.assertEqual(score_shadow(a,broken)["method"],"raw-scoring-means")

class AccuracyResearchTests(unittest.TestCase):
 def test_empty_ledger_shows_no_invented_accuracy(self):
    with TemporaryDirectory() as d:
        report=derive(Path(d),NOW)
        self.assertEqual(report["immutableFirstPicks"],0)
        self.assertEqual(report["verifiedUniqueFinals"],0)
        self.assertIsNone(report["overall"]["brier"])
        self.assertEqual(report["frozenScoreResults"]["games"],0)
        self.assertIsNone(report["frozenScoreResults"]["marginMAE"])
        self.assertFalse(any(x["reviewEligible"] for x in report["pairedComparisons"]))
 def test_original_frozen_first_pick_not_cherry_picked_from_later_capture(self):
    with TemporaryDirectory() as d:
        root=Path(d);write(root)
        r=derive(root,NOW)
        self.assertEqual(r["immutableFirstPicks"],1)
        self.assertEqual(r["verifiedUniqueFinals"],1)
        self.assertAlmostEqual(r["overall"]["brier"],(.68-1)**2)
        ensemble=next(x for x in r["pairedComparisons"] if x["model"]=="Frozen ensemble")
        self.assertEqual(ensemble["pairedGames"],1)
        self.assertAlmostEqual(ensemble["candidateBrier"],(.64-1)**2)
        self.assertIsNone(ensemble["dateBlockGain95"])
        self.assertFalse(ensemble["reviewEligible"])
        self.assertEqual(r["daily"][0]["games"],1)
        self.assertEqual(r["weekly"][0]["games"],1)
        self.assertEqual(r["frozenScoreResults"]["games"],1)
        self.assertGreater(r["frozenScoreResults"]["marginMAE"],0)
 def test_no_backfill_and_source_unverified_never_settles(self):
    with TemporaryDirectory() as d:
        root=Path(d);write(root,frozen=False)
        r=derive(root,NOW)
        self.assertEqual(r["verifiedUniqueFinals"],1)
        self.assertEqual(r["frozenScoreResults"]["games"],0)
        self.assertIsNone(r["frozenScoreResults"]["totalMAE"])
        p=root/"settlements"/"verified.json"
        rows=json.loads(p.read_text())
        for x in rows["results"]:x["espnFinalVerified"]=False
        p.write_text(json.dumps(rows))
        unverified=derive(root,NOW)
        self.assertEqual(unverified["verifiedUniqueFinals"],0)
        self.assertEqual(unverified["pendingByStatus"]["delayed-review"],1)
        self.assertEqual(unverified["overall"]["accuracy"],None)
 def test_unverified_future_and_recent_games_are_not_called_losses(self):
    with TemporaryDirectory() as d:
        root=Path(d);write(root,results=False)
        p=derive(root,datetime(2026,11,18,20,tzinfo=timezone.utc))
        self.assertEqual(p["pendingByStatus"]["upcoming"],1)
        self.assertEqual(p["verifiedUniqueFinals"],0)
        self.assertEqual(p["pendingUniqueGames"],1)
        self.assertEqual(len(p["pendingReview"]),0)
 def test_original_metadata_reversal_is_rejected(self):
    with TemporaryDirectory() as d:
        root=Path(d);write(root)
        p=root/"snapshots"/"early.json"
        s=json.loads(p.read_text());s["ratingRetrievedAtUtc"]="2026-11-19T11:00:00Z";p.write_text(json.dumps(s))
        with self.assertRaisesRegex(ValueError,"source"):
            derive(root,NOW)
if __name__=="__main__":unittest.main()
