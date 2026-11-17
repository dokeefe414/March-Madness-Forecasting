"""Causal margin model: date embargo, source completeness and honest metrics."""
from __future__ import annotations
import unittest
from datetime import date,datetime,timedelta,timezone
from forecast.score_research import evaluate,_fitted,_prior_sigma
NOW=datetime(2026,11,17,20,tzinfo=timezone.utc)
def sample(n=160):
    teams=["A","B","C","D","E","F","G","H"]
    start=date(2026,9,1)
    rows=[]
    for i in range(n):
        h=teams[i%8]
        a=teams[(i+3+(i//8)%4)%8]
        if h==a:a=teams[(i+1)%8]
        hs=78+(i%11) if i%3!=0 else 68+(i%9)
        ass=70+(i%7) if i%3!=0 else 81+(i%5)
        if hs==ass:ass+=1
        rows.append({"id":"e-"+str(i),"date":(start+timedelta(days=i//4)).isoformat(),
                     "home":h,"away":a,"homeScore":hs,"awayScore":ass})
    return rows
def ratings(rows):
    return {"mode":"current","season":2027,"regularSeasonGames":len(rows),
            "retrievedAtUtc":"2026-11-17T13:00:00Z","lastGameDate":rows[-1]["date"]}
class MarginResearchTests(unittest.TestCase):
 def test_research_scores_same_exact_games_against_controls(self):
    rows=sample()
    report=evaluate(rows,ratings(rows),NOW)
    self.assertEqual(report["mode"],"research-only")
    self.assertGreater(report["evaluatedGames"],50)
    self.assertEqual(report["methods"]["rawScoringMeans"]["games"],report["methods"]["opponentAdjusted"]["games"])
    self.assertEqual(report["methods"]["elo"]["games"],report["evaluatedGames"])
    self.assertGreater(report["evaluatedDays"],10)
    for name in ("rawScoringMeans","opponentAdjusted"):
        m=report["methods"][name]
        self.assertTrue(0<=m["brier"]<=1)
        self.assertGreater(m["marginMAE"],0)
        self.assertGreater(m["totalMAE"],0)
    self.assertTrue(report["auditFirst40"])
 def test_same_calendar_date_results_cannot_leak_into_other_predictions(self):
    rows=sample()
    before=evaluate(rows,ratings(rows),NOW)
    altered=[dict(g) for g in rows]
    altered[70]["homeScore"],altered[70]["awayScore"]=altered[70]["awayScore"],altered[70]["homeScore"]
    after=evaluate(altered,ratings(altered),NOW)
    b={x["eventId"]:x for x in before["auditFirst40"]}
    a={x["eventId"]:x for x in after["auditFirst40"]}
    self.assertIn("e-70",b)
    for key in ("e-70","e-71"):
        for metric in ("adjustedMargin","rawMargin","adjustedProbability","rawProbability","eloProbability"):
            self.assertEqual(b[key][metric],a[key][metric],(key,metric))
    # Later scoring data may respond to the new outcome, but the same date
    # cannot be used to select a win probability retroactively.
 def test_future_day_has_no_effect_on_past_outputs(self):
    rows=sample()
    normal=evaluate(rows,ratings(rows),NOW)
    added=rows+[{"id":"future","date":"2026-11-17","home":"A","away":"B",
                 "homeScore":150,"awayScore":51}]
    with_future=evaluate(added,ratings(added),NOW)
    self.assertEqual(normal["methods"],with_future["methods"])
    self.assertEqual(normal["auditFirst40"],with_future["auditFirst40"])
 def test_source_provenance_and_duplicates_rejected(self):
    rows=sample(12)
    with self.assertRaises(ValueError):
        evaluate(rows,{**ratings(rows),"regularSeasonGames":13},NOW)
    with self.assertRaises(ValueError):
        evaluate(rows+[dict(rows[0])],ratings(rows+[rows[0]]),NOW)
    with self.assertRaises(ValueError):
        evaluate(rows,[].__class__(),NOW)
 def test_rare_teams_are_not_given_fictitious_scoring_results(self):
    rows=sample(40)
    report=evaluate(rows,ratings(rows),NOW)
    self.assertEqual(report["evaluatedGames"],0)
    self.assertIsNone(report["methods"]["opponentAdjusted"]["brier"])
    self.assertIsNone(report["methods"]["elo"]["brier"])
    self.assertGreaterEqual(report["excluded"]["notEnoughLeagueGames"],40)
 def test_early_season_strengths_are_regularized(self):
    rows=sample(8)
    fit=_fitted(rows)
    self.assertGreater(fit["league"],60)
    self.assertTrue(all(abs(v)<20 for v in fit["offense"].values()))
    self.assertTrue(all(abs(v)<20 for v in fit["defense"].values()))
    self.assertTrue(9<=_prior_sigma(rows,fit)<=30)
if __name__=="__main__":unittest.main()
