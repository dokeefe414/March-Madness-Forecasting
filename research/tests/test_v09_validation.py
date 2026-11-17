"""Exact before-tipoff paired comparisons and experimental source-match guards."""
import unittest
from datetime import datetime,timezone
from forecast.performance import summarize_forward
from forecast.snapshot import forecast_scheduled
from forecast.state_space import build_state_space
from forecast.opponents import build_opponent_report

NOW=datetime(2026,11,20,12,tzinfo=timezone.utc)
G=[
 {"id":"1","date":"2026-11-16","home":"A","away":"B","homeScore":80,"awayScore":67},
 {"id":"2","date":"2026-11-17","home":"B","away":"C","homeScore":76,"awayScore":64},
 {"id":"3","date":"2026-11-18","home":"C","away":"A","homeScore":70,"awayScore":72},
]
R={
 "mode":"current","season":2027,"regularSeasonGames":3,"lastGameDate":"2026-11-18",
 "retrievedAtUtc":"2026-11-20T11:00:00Z",
 "teams":[
   {"name":"A","teamId":"ncaa-a","espnSourceTeamId":"1","rating":1540.,"wins":2,"losses":0},
   {"name":"B","teamId":"ncaa-b","espnSourceTeamId":"2","rating":1490.,"wins":1,"losses":1},
   {"name":"C","teamId":"ncaa-c","espnSourceTeamId":"3","rating":1470.,"wins":0,"losses":2},
 ]}
def fixture():
 return {"events":[{"id":"espn-4","date":"2026-11-21T01:00:00Z",
    "status":{"type":{"name":"STATUS_SCHEDULED","completed":False}},
    "competitions":[{"neutralSite":False,"competitors":[
      {"homeAway":"home","team":{"id":"1","location":"A"}},
      {"homeAway":"away","team":{"id":"2","location":"B"}}
    ]}]}]}
def archived(sid,p=.7,alt=.63):
 return {"snapshotId":sid,"generatedAtUtc":sid+"T12:00:00Z",
         "predictions":[{"eventId":"X","home":"A","away":"B",
           "model":"as-of regular-season Elo","homeWinProbability":p,
           "baselineHomeWinProbability":.65,
           "challengerHomeWinProbability":alt,
           "stateSpaceHomeWinProbability":.57,
           "adaptiveStateSpaceHomeWinProbability":.59,
           "opponentAdjustedHomeWinProbability":.61}]}
class V09ValidationTests(unittest.TestCase):
 def test_unpromoted_challengers_not_actual_pick(self):
    state=build_state_space(G,R,NOW)
    opp=build_opponent_report(G,R,NOW)
    snap=forecast_scheduled([fixture()],R,NOW,
             state_space=state,opponent_model=opp)
    self.assertEqual(len(snap["predictions"]),1)
    actual=snap["predictions"][0]
    self.assertEqual(actual["model"],"as-of regular-season Elo")
    self.assertIsNotNone(actual["opponentAdjustedHomeWinProbability"])
    self.assertIsNotNone(actual["adaptiveStateSpaceHomeWinProbability"])
    self.assertEqual(snap["coverage"]["unsafeSameDateRatings"],0)
    with self.assertRaisesRegex(ValueError,"opponent model"):
      forecast_scheduled([fixture()],R,NOW,opponent_model={**opp,"retrievedAtUtc":"wrong"})
 def test_same_future_day_trained_result_never_promoted(self):
    opp=build_opponent_report(G,R,NOW)
    bad={**opp,"trainedThroughDate":"2026-11-20"}
    result=forecast_scheduled([fixture()],R,NOW,opponent_model=bad)
    self.assertIsNone(result["predictions"][0]["opponentAdjustedHomeWinProbability"])
 def test_genuine_paired_comparison_multiple_models_same_game(self):
    snap=archived("2026-11-15")
    settled=[{"predictionKey":"2026-11-15:X","actualResultDate":"2026-11-19","observedHome":1}]
    report=summarize_forward([snap],settled)
    self.assertEqual(report["settledUniqueGames"],1)
    models=report["pairedModelComparisons"]
    self.assertEqual(models["Opponent-aware research"]["pairedGames"],1)
    self.assertEqual(models["Adaptive state-space research"]["pairedGames"],1)
    self.assertIsNone(models["Adaptive state-space research"]["dateBlockGain95"])
    self.assertGreater(models["Online logistic challenger"]["candidateBrierGain"],0)
 def test_earliest_first_pick_wins_against_late_cherrypicking(self):
    first=archived("2026-11-15",p=.85,alt=.75)
    next_=archived("2026-11-16",p=.20,alt=.10)
    scored=[{"predictionKey":"2026-11-15:X","actualResultDate":"2026-11-19","observedHome":0},
            {"predictionKey":"2026-11-16:X","actualResultDate":"2026-11-19","observedHome":0}]
    report=summarize_forward([next_,first],scored)
    self.assertEqual(report["settledUniqueGames"],1)
    self.assertAlmostEqual(report["score"]["brier"],.7225)
    self.assertEqual(report["pairedModelComparisons"]["Opponent-aware research"]["pairedGames"],1)
