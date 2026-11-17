"""Forward performance is sourced only from earliest immutable actual pregame picks."""
import unittest
from forecast.performance import summarize_forward

def snap(sid,p=.8,model="Elo",extra=None):
    return {"snapshotId":sid,"generatedAtUtc":sid+"T00:00:00Z",
            "predictions":[{"eventId":"same","home":"A","away":"B","model":model,
                            "homeWinProbability":p, **(extra or {})}]}
def result(sid,won):
    return {"predictionKey":sid+":same","actualResultDate":"2026-12-06",
            "observedHome":won}
class ForwardPerformanceTests(unittest.TestCase):
    def test_empty_forward_is_not_backfilled_accuracy(self):
        s=summarize_forward([],[])
        self.assertEqual(s["settledUniqueGames"],0)
        self.assertIsNone(s["score"]["accuracy"])
        self.assertEqual(s["calibration"][0]["count"],0)

    def test_multiple_snapshots_count_as_one_earliest_game(self):
        first=snap("2026-12-04",.8,extra={"baselineHomeWinProbability":.7,
                    "challengerHomeWinProbability":.6})
        later=snap("2026-12-05",.3)
        score=summarize_forward([later,first],[result("2026-12-04",0),result("2026-12-05",0)])
        self.assertEqual(score["forecastedUniqueGames"],1)
        self.assertEqual(score["settledUniqueGames"],1)
        self.assertEqual(score["score"]["accuracy"],0.)
        self.assertAlmostEqual(score["score"]["brier"],.64)
        self.assertEqual(score["shadowComparison"]["pairedGames"],1)
        self.assertAlmostEqual(score["shadowComparison"]["eloBrier"],.49)
        self.assertAlmostEqual(score["shadowComparison"]["challengerBrier"],.36)
        self.assertEqual(len(score["recentMisses"]),1)

    def test_confidence_groups_and_negative_brier_skill_are_honest(self):
        report=summarize_forward([snap("2026-12-04",.9)], [result("2026-12-04",0)])
        self.assertEqual(report["confidenceBands"]["strong"]["games"],1)
        self.assertEqual(report["confidenceBands"]["tossUp"]["games"],0)
        self.assertEqual(report["confidenceBands"]["moderate"]["games"],0)
        self.assertLess(report["coinFlipBrierSkill"],0)
        self.assertEqual(report["rolling25"],[])
        self.assertAlmostEqual(report["confidenceBands"]["strong"]["brier"],.81)

    def test_empty_statistics_not_painted_as_a_win(self):
        report=summarize_forward([],[])
        self.assertIsNone(report["coinFlipBrierSkill"])
        self.assertIsNone(report["confidenceBands"]["strong"]["accuracy"])

    def test_unsettled_earlier_pick_does_not_cherry_pick_later_one(self):
        score=summarize_forward([snap("2026-12-04"),snap("2026-12-05")],
                                 [result("2026-12-05",1)])
        self.assertEqual(score["settledUniqueGames"],0)
        self.assertEqual(score["forecastedUniqueGames"],1)
