"""State-space uncertainty and daily embargo regression."""
import unittest
from datetime import datetime,timezone
from forecast.state_space import build_state_space
NOW=datetime(2026,11,20,6,tzinfo=timezone.utc)
GAMES=[
 {"id":"1","date":"2026-11-17","home":"A","away":"B","homeScore":90,"awayScore":70},
 {"id":"2","date":"2026-11-18","home":"B","away":"C","homeScore":60,"awayScore":72},
 {"id":"3","date":"2026-11-18","home":"A","away":"C","homeScore":68,"awayScore":71}
]
def rating(g):
 return {"mode":"current","season":2027,"regularSeasonGames":len(g),
         "lastGameDate":max(x["date"] for x in g),
         "retrievedAtUtc":"2026-11-20T05:00:00Z"}
class StateSpaceTests(unittest.TestCase):
 def test_predict_then_update_and_finite_uncertainty(self):
  r=build_state_space(GAMES,rating(GAMES),NOW)
  self.assertEqual(r["evaluatedGames"],3)
  self.assertEqual(r["gameDays"],2)
  self.assertTrue(0<r["brier"]<1)
  self.assertIn("A",r["strengths"])
  self.assertGreater(r["strengths"]["A"]["standardDeviation"],0)
  self.assertLess(r["strengths"]["A"]["standardDeviation"],150)
 def test_today_scores_do_not_change_prior_day_model(self):
  base=build_state_space(GAMES,rating(GAMES),NOW)
  g=GAMES+[{"id":"4","date":"2026-11-20","home":"A","away":"B","homeScore":100,"awayScore":60}]
  other=build_state_space(g,rating(g),NOW)
  self.assertEqual(base["strengths"],other["strengths"])
  self.assertEqual(base["evaluatedGames"],other["evaluatedGames"])
 def test_count_and_provenance_fail_closed(self):
  with self.assertRaisesRegex(ValueError,"count"):
   build_state_space(GAMES,{**rating(GAMES),"regularSeasonGames":4},NOW)
