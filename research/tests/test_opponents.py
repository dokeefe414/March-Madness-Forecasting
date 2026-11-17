"""Opponent strength and zero-lookahead regression tests."""
from datetime import datetime,timezone
import unittest
from forecast.opponents import build_opponent_report

NOW=datetime(2026,11,21,17,tzinfo=timezone.utc)
G=[
 {"id":"1","date":"2026-11-17","home":"A","away":"B","homeScore":85,"awayScore":68},
 {"id":"2","date":"2026-11-18","home":"C","away":"A","homeScore":65,"awayScore":80},
 {"id":"3","date":"2026-11-18","home":"B","away":"C","homeScore":75,"awayScore":71},
 {"id":"4","date":"2026-11-19","home":"B","away":"A","homeScore":65,"awayScore":68},
]
def rating(g):
 return {"mode":"current","season":2027,"retrievedAtUtc":"2026-11-21T16:00:00Z",
         "lastGameDate":max(x["date"] for x in g),"regularSeasonGames":len(g)}

class OpponentResearchTests(unittest.TestCase):
 def test_prior_opponent_margin_and_same_day_frozen_evaluation(self):
  report=build_opponent_report(G,rating(G),NOW)
  self.assertEqual(report["games"],4)
  self.assertEqual(report["chronological"]["perDate"][-1]["games"],1)
  self.assertNotEqual(report["strengths"]["A"]["eloAdjustment"],0)
  self.assertLessEqual(abs(report["strengths"]["A"]["eloAdjustment"]),75)
  self.assertTrue(0<report["chronological"]["eloBrier"]<1)
  self.assertTrue(0<report["chronological"]["opponentAdjustedBrier"]<1)
 def test_current_date_is_embargoed(self):
  extra={"id":"new","date":"2026-11-21","home":"A","away":"B","homeScore":110,"awayScore":40}
  a=build_opponent_report(G,rating(G),NOW)
  b=build_opponent_report(G+[extra],rating(G+[extra]),NOW)
  self.assertEqual(a["strengths"],b["strengths"])
  self.assertEqual(a["chronological"],b["chronological"])
 def test_missing_score_and_duplicate_abort(self):
  with self.assertRaisesRegex(ValueError,"count"):
   build_opponent_report(G,{**rating(G),"regularSeasonGames":5},NOW)
  with self.assertRaisesRegex(ValueError,"Duplicate"):
   build_opponent_report(G+[G[0]],rating(G+[G[0]]),NOW)
 def test_team_strength_is_bounded_after_large_margin(self):
  huge=[{**G[0],"homeScore":150,"awayScore":10}]+G[1:]
  r=build_opponent_report(huge,rating(huge),NOW)
  self.assertTrue(all(abs(s["eloAdjustment"])<=75. for s in r["strengths"].values()))
