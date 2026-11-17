"""Hermetic chronological 2027 retraining and model rollout safeguards."""
import copy
import unittest
from datetime import datetime, date, timedelta, timezone
from forecast.retrain import build_report, validate_for_pick, probability

NOW=datetime(2026,12,21,18,tzinfo=timezone.utc)
def mock_games(days=34,per_day=10):
    first=date(2026,11,1)
    games=[]
    for d in range(days):
        for i in range(per_day):
            a=(d*3+i*2)%48
            b=(d*3+i*2+13)%48
            games.append({"id":f"{d:03}-{i:02}","date":(first+timedelta(days=d)).isoformat(),
                          "home":f"H{a}","away":f"H{b}",
                          "homeScore":75+(d+i)%17,"awayScore":65+(d*3+i)%15})
    return games
def rating(games):
    return {"mode":"current","season":2027,"regularSeasonGames":len(games),
            "lastGameDate":games[-1]["date"],
            "sourceUrl":"https://example.org/2027.csv","retrievedAtUtc":"2026-12-21T17:50:00Z"}

class RetrainTests(unittest.TestCase):
    def test_walk_forward_train_before_date_and_model_generation(self):
        g=mock_games()
        r=build_report(g,rating(g),NOW)
        self.assertEqual(r["trainingGames"],len(g))
        self.assertEqual(r["trainingDays"],34)
        self.assertGreater(r["evaluationGames"],120)
        self.assertEqual(len(r["modelWeights"]),4)
        self.assertTrue(r["mode"] in ("shadow","active"))
        self.assertTrue(all(t["date"] > g[0]["date"] and
                            t["priorTrainingGames"]<len(g) for t in r["walkForward"]["sampleEvaluation"]))

    def test_no_same_day_information_even_when_scores_appear(self):
        g=mock_games()
        same_day=[{"id":"late01","date":"2026-12-21","home":"H0","away":"H1",
                   "homeScore":99,"awayScore":50}]
        r=build_report(g+same_day,{**rating(g),"regularSeasonGames":len(g)+1,
            "lastGameDate":"2026-12-21"},NOW)
        earlier=build_report(g,rating(g),NOW)
        self.assertEqual(r["trainingGames"],earlier["trainingGames"])
        self.assertEqual(r["modelWeights"],earlier["modelWeights"])
        self.assertEqual(r["excludedCurrentDateGames"],1)

    def test_future_date_cannot_be_trained(self):
        g=mock_games()
        source=rating(g)
        invalid={**source,"lastGameDate":"2026-12-25",
                 "regularSeasonGames":len(g)+1}
        with self.assertRaisesRegex(ValueError,"game archive"):
            build_report(g,invalid,NOW)

    def test_date_group_validation_has_no_same_day_training(self):
        g=mock_games(25,12)
        result=build_report(g,rating(g),NOW)
        full_by_day={}
        for t in result["walkForward"]["sampleEvaluation"]:
            day=t["date"]
            earlier=sum(1 for game in g if game["date"]<day)
            self.assertEqual(t["priorTrainingGames"],earlier)
            full_by_day[day]=1
        self.assertGreater(len(full_by_day),1)

    def test_active_model_has_strict_asof_and_valid_coefficients(self):
        sample={"type":"current-season-chronological-logistic","mode":"active",
                "season":2027,"ratingRetrievedAtUtc":"2026-12-21T17:50:00Z",
                "trainedThroughDate":"2026-12-19","modelWeights":[.1,0,0,0]}
        self.assertIsNotNone(validate_for_pick(sample,rating(mock_games()),"2026-12-22"))
        self.assertIsNone(validate_for_pick({**sample,"mode":"shadow"},rating(mock_games()),"2026-12-22"))
        for bad in ({**sample,"trainedThroughDate":"2026-12-22"},
                    {**sample,"ratingRetrievedAtUtc":"2026-12-21T16:00:00Z"},
                    {**sample,"modelWeights":[float("nan"),0,0,0]}):
            with self.assertRaises(ValueError):
                validate_for_pick(bad,rating(mock_games()),"2026-12-22")

    def test_probability_bounded_and_elo_at_zero(self):
        self.assertAlmostEqual(probability((0,0,0,1),[0]*4),.5)
        self.assertAlmostEqual(probability((1,0,0,1),[0]*4),10/11)
