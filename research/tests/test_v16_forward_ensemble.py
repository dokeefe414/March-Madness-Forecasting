"""Independent original-first-pick ensemble evidence and no-hindsight safeguards."""
from __future__ import annotations
import json
import tempfile
import unittest
from datetime import datetime,date,timedelta,timezone
from pathlib import Path
from forecast.forward_ensemble import candidate,build_report,validate_for_fixture
NOW=datetime(2026,12,31,16,tzinfo=timezone.utc)
RATINGS={"mode":"current","season":2027,"retrievedAtUtc":"2026-12-31T15:00:00Z"}
def pred(event="evt",base=.65,other=.7):
    return {"eventId":event,"scheduledStartUtc":"2026-11-20T23:00:00Z",
            "baselineHomeWinProbability":base,"challengerHomeWinProbability":other,
            "opponentAdjustedHomeWinProbability":other,
            "stateSpaceHomeWinProbability":other,"adaptiveStateSpaceHomeWinProbability":None,
            "home":"Team A","away":"Team B","ensembleHomeWinProbability":.7}

class EnsembleTests(unittest.TestCase):
 def test_symmetric_missing_and_bad_probabilities(self):
    p=pred()
    result=candidate(p)
    self.assertEqual(result["componentCount"],3)
    self.assertAlmostEqual(result["homeWinProbability"],.6625)
    self.assertIsNone(candidate({"baselineHomeWinProbability":.6,"challengerHomeWinProbability":.8}))
    self.assertIsNone(candidate({"baselineHomeWinProbability":float("nan"),**{"stateSpaceHomeWinProbability":.8,"challengerHomeWinProbability":.6}}))
    self.assertIsNone(candidate({**p,"baselineHomeWinProbability":None}))
    with self.assertRaises(ValueError):
        candidate(p,.9)
 def test_source_date_and_asof_guards(self):
    r={"schemaVersion":1,"mode":"shadow","season":2027,
       "sourceRetrievedAtUtc":RATINGS["retrievedAtUtc"],
       "weight":.25,"trainedThroughDate":"2026-11-20"}
    self.assertEqual(validate_for_fixture(r,RATINGS,"2026-11-21"),.25)
    self.assertIsNone(validate_for_fixture(r,RATINGS,"2026-11-20"))
    with self.assertRaisesRegex(ValueError,"different"):
        validate_for_fixture(r,{**RATINGS,"retrievedAtUtc":"2026-12-31T14:00:00Z"},"2026-11-21")
    with self.assertRaises(ValueError):
        validate_for_fixture({**r,"weight":2},RATINGS,"2026-11-21")
 def test_empty_ledger_is_fully_shadow_and_no_accuracy_claim(self):
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder)
        result=build_report(root,RATINGS,NOW)
        self.assertEqual(result["pairedSettledGames"],0)
        self.assertEqual(result["archivedPortfolioGames"],0)
        self.assertIsNone(result["archivedPortfolioBrier"])
        self.assertFalse(result["scientificReviewEligible"])
        self.assertFalse(result["promoteAutomatically"])
        self.assertEqual(result["weight"],.25)
 def test_previously_verified_picks_get_date_blocked_and_frozen_evidence(self):
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder)
        (root/"snapshots").mkdir()
        (root/"settlements").mkdir()
        settlements=[]
        start=date(2026,11,1)
        for d in range(20):
            day=start+timedelta(days=d)
            events=[]
            for i in range(7):
                key=f"{d}-{i}"
                # Predictions are intentionally informative to exercise a
                # prospective positive candidate without invoking any live API.
                y=int((d+i)%3!=0)
                elo=.65 if y else .35
                cand=.8 if y else .2
                q=(1-.25)*elo+.25*cand
                events.append({**pred(key,elo,cand),
                     "ensembleHomeWinProbability":round(q,7),
                     "scheduledStartUtc":day.isoformat()+"T23:00:00Z"})
                settlements.append({"predictionKey":f"snap-{d}:{key}",
                     "actualResultDate":day.isoformat(),"espnFinalVerified":True,
                     "observedHome":y,"home":"Team A","away":"Team B"})
            (root/"snapshots"/f"snap-{d}.json").write_text(json.dumps({
                "snapshotId":f"snap-{d}","generatedAtUtc":day.isoformat()+"T10:00:00Z",
                "ratingRetrievedAtUtc":day.isoformat()+"T09:00:00Z",
                "predictions":events}))
        (root/"settlements"/"verified.json").write_text(json.dumps({"results":settlements}))
        report=build_report(root,RATINGS,NOW)
        self.assertEqual(report["pairedSettledGames"],140)
        self.assertEqual(report["archivedPortfolioGames"],140)
        self.assertGreaterEqual(report["trainingGames"],80)
        self.assertGreaterEqual(report["untouchedHoldoutGames"],40)
        self.assertEqual(report["trainingDates"]+report["untouchedHoldoutDates"],20)
        self.assertGreater(report["archivedPortfolioBrierGain"],0)
        self.assertGreater(report["archivedPortfolioDateBlockGain95"][0],0)
        self.assertTrue(report["prospectiveGatePassed"])
        self.assertTrue(report["scientificReviewEligible"])
        self.assertFalse(report["promoteAutomatically"])
        # Tampered later capture cannot replace the earliest original outcome.
        first=root/"snapshots"/"snap-1.json"
        repeated=json.loads(first.read_text())
        repeated["snapshotId"]="snap-second-1"
        repeated["generatedAtUtc"]="2026-11-02T11:00:00Z"
        for g in repeated["predictions"]:
            g["ensembleHomeWinProbability"]=.01
        (root/"snapshots"/"later-duplicate.json").write_text(json.dumps(repeated))
        after=build_report(root,RATINGS,NOW)
        self.assertEqual(after["archivedPortfolioBrier"],report["archivedPortfolioBrier"])
 def test_posttipoff_and_unverified_rows_are_not_eligible(self):
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder)
        (root/"snapshots").mkdir()
        (root/"settlements").mkdir()
        (root/"snapshots"/"bad.json").write_text(json.dumps({
          "snapshotId":"bad","generatedAtUtc":"2026-11-20T23:01:00Z",
          "ratingRetrievedAtUtc":"2026-11-20T22:00:00Z",
          "predictions":[pred("bad")]}))
        (root/"settlements"/"bad.json").write_text(json.dumps({
          "results":[{"predictionKey":"bad:bad","actualResultDate":"2026-11-20",
            "espnFinalVerified":True,"home":"Team A","away":"Team B","observedHome":1}]}))
        self.assertEqual(build_report(root,RATINGS,NOW)["pairedSettledGames"],0)
if __name__=="__main__":unittest.main()
