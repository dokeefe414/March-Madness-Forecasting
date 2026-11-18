"""v2.2 regression tests: source-linked efficiency, historical stack, prequential ensemble."""
from __future__ import annotations
import copy
import unittest
from datetime import date,datetime,timedelta,timezone
from forecast.possession_research import source_game_boxes,evaluate
from forecast.forward_ensemble import prequential_adaptive_weights
from forecast.model_championship import choose_prior_year_stack
from forecast.accuracy_research import _calibration

NOW=datetime(2026,12,18,18,tzinfo=timezone.utc)

def build_games(days=24):
    games=[]
    first=date(2026,11,1)
    for d in range(days):
        for i in range(8):
            h="H"+str(2*i);a="H"+str(2*i+1)
            games.append({"id":f"{d}-{i}","date":(first+timedelta(days=d)).isoformat(),
              "home":h,"away":a,"homeScore":80+(d+i)%6,
              "awayScore":75 if (d+i)%3 else 88})
    return games

def box_data(games):
    head="contest_id,season,team,o_poss,d_poss,ortg,drtg"
    rows=[head]
    for g in games:
        for name,off,defn in ((g["home"],116,99),(g["away"],104,109)):
            rows.append(f'{g["id"]},2027,{name},71,72,{off},{defn}')
    return "\n".join(rows)+"\n"

def ratings(games):
    return {"mode":"current","season":2027,
       "regularSeasonGames":len(games),"retrievedAtUtc":"2026-12-18T17:00:00Z",
       "lastGameDate":max(g["date"] for g in games)}

class ModelUpgradeTests(unittest.TestCase):
    def test_source_box_join_only_accepts_both_sides(self):
        g=build_games(1)
        data=source_game_boxes(g,box_data(g),ratings(g)["retrievedAtUtc"])
        self.assertEqual(data["pairedGameBoxes"],8)
        self.assertEqual(data["completeFourFactorGames"],0)
        self.assertEqual(data["status"],"matched")
        first=data["games"][0]
        self.assertEqual(first["homeBox"]["off"],116)
        self.assertEqual(first["awayBox"]["poss"],71.5)
        # A single team-game line cannot establish its opponent's metrics.
        lines=box_data(g).splitlines()
        partial=source_game_boxes(g,"\n".join(lines[:-1])+"\n",ratings(g)["retrievedAtUtc"])
        self.assertEqual(partial["pairedGameBoxes"],7)
        missing=source_game_boxes(g,None,ratings(g)["retrievedAtUtc"])
        self.assertEqual(missing["status"],"unavailable")
        self.assertEqual(missing["games"],[])

    def test_full_date_frozen_efficiency_evaluates_both_models_same_cohort(self):
        g=build_games()
        r=ratings(g)
        b=source_game_boxes(g,box_data(g),r["retrievedAtUtc"])
        report=evaluate(g,r,b,NOW)
        self.assertEqual(report["pairedPriorDateBoxGames"],len(g))
        self.assertGreater(report["evaluatedGames"],0)
        self.assertEqual(report["metrics"]["elo"]["games"],report["metrics"]["efficiencyResidual"]["games"])
        self.assertGreater(report["evaluatedDates"],1)
        self.assertEqual(len(report["currentWeights"]),6)
        self.assertEqual(report["mode"],"research-only")
        self.assertIs(report["automaticPromotion"],False)
        self.assertGreaterEqual(report["coldStartEligible"],0)
        self.assertEqual(report["fourFactorSourceGames"],0)
        again=evaluate(list(reversed(g)),r,b,NOW)
        self.assertEqual(report,again)

    def test_current_date_result_cannot_change_earlier_date_learning(self):
        g=build_games()
        r=ratings(g)
        b=source_game_boxes(g,box_data(g),r["retrievedAtUtc"])
        original=evaluate(g,r,b,NOW)
        extra={"id":"today","date":"2026-12-18","home":"H0","away":"H1",
               "homeScore":150,"awayScore":50}
        r2={**r,"regularSeasonGames":len(g)+1,"lastGameDate":extra["date"]}
        b2=source_game_boxes(g+[extra],box_data(g+[extra]),r["retrievedAtUtc"])
        changed=evaluate(g+[extra],r2,b2,NOW)
        self.assertEqual(changed["metrics"],original["metrics"])
        self.assertEqual(changed["currentWeights"],original["currentWeights"])
        self.assertEqual(changed["evaluatedGames"],original["evaluatedGames"])
        self.assertEqual(changed["acceptedPriorDateGames"],original["acceptedPriorDateGames"])

    def test_tampered_source_box_identity_timestamp_and_duplicate_fail(self):
        g=build_games(3);r=ratings(g)
        b=source_game_boxes(g,box_data(g),r["retrievedAtUtc"])
        bad=copy.deepcopy(b);bad["games"][0]["away"]="Wrong Team"
        with self.assertRaisesRegex(ValueError,"Box-game identity"):
            evaluate(g,r,bad,NOW)
        bad=copy.deepcopy(b);bad["games"].append(copy.deepcopy(bad["games"][0]))
        bad["pairedGameBoxes"]+=1
        with self.assertRaisesRegex(ValueError,"Box-game identity"):
            evaluate(g,r,bad,NOW)
        with self.assertRaisesRegex(ValueError,"timestamps"):
            evaluate(g,{**r,"retrievedAtUtc":"2026-12-18T16:00:00Z"},b,NOW)

    def test_historical_stack_only_uses_prior_oos_seasons(self):
        previous=[{"season":year,"y":1,"elo":.51,"logistic":.9,
                   "boosted":.49,"calibratedTrendElo":.5,
                   "scoreDistribution":.5,"priorShrinkage":.5}
                   for year in range(2010,2018)]
        label,w=choose_prior_year_stack(previous)
        self.assertEqual(label,"logistic")
        self.assertIn(w,(.15,.30,.45))
        self.assertEqual(choose_prior_year_stack(previous[:3]),("elo",0.))
        # The most recent forecast label is never used for the prior choice.
        self.assertEqual((label,w),choose_prior_year_stack(list(reversed(previous))))

    def test_adaptive_ensemble_weights_only_learn_from_prior_dates(self):
        first=date(2026,11,1)
        sample=[]
        for d in range(24):
            for j in range(6):
                y=int((d+j)%3!=0)
                sample.append({"eventId":f"{d}-{j}",
                   "date":(first+timedelta(days=d)).isoformat(),
                   "elo":.56 if y else .44,
                   "research":.9 if y else .1,"y":y})
        a=prequential_adaptive_weights(sample)
        self.assertGreater(a["evaluatedGames"],0)
        self.assertEqual(a["mode"],"research-only")
        self.assertGreater(a["latestPastWeight"],0.)
        self.assertTrue(all(r["priorDates"]>=6 and
                            r["trainedFromPriorGames"]>=80
                            for r in a["weightChanges"]))
        # Labels on the most recent date must not affect the weight selected
        # FOR that same date.
        modified=copy.deepcopy(sample)
        last=modified[-1]["date"]
        for r in modified:
            if r["date"]==last:r["y"]=1-r["y"]
        b=prequential_adaptive_weights(modified)
        self.assertEqual(a["weightChanges"],b["weightChanges"])
        self.assertEqual(prequential_adaptive_weights([])["evaluatedGames"],0)

    def test_calibration_uses_only_real_settled_picks(self):
        self.assertEqual(_calibration([],"official")["status"],"insufficient-evidence")
        r=[{"official":.8,"observedHome":1} for _ in range(60)]
        stats=_calibration(r,"official")
        self.assertEqual(stats["status"],"observing")
        self.assertEqual(stats["games"],60)
        self.assertAlmostEqual(stats["expectedCalibrationError"],.2)
        self.assertEqual(sum(q["games"] for q in stats["bins"]),60)

if __name__=="__main__":unittest.main()
