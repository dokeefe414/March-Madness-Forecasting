"""Poll rank comparison tests: true prior-week Elo, exact ESPN IDs and frozen history."""
from __future__ import annotations

import copy
import unittest
from datetime import datetime,timezone

from forecast.ap_poll import (baseline,extract_ap_poll,snapshot,update_history,
                               _spearman)
from forecast.live import build_current

AT=datetime(2026,11,20,16,tzinfo=timezone.utc)


def games():
    records=[]
    for d in range(2,16):
        for j in range(15):
            h=f"Program {j*2:02}"
            a=f"Program {j*2+1:02}"
            # games completed from Nov 2 to Nov 15: well before Monday's
            # Nov 16 poll. Every team has 14 date-frozen games.
            records.append({
                "date":f"2026-11-{d:02}","id":f"g-{d:02}-{j}",
                "home":h,"away":a,
                "homeScore":85+(d+j)%11,
                "awayScore":65+(d+j)%17,
            })
    return records


def current(records=None):
    rows=records if records is not None else games()
    rating=build_current(rows,AT)
    for team in rating["teams"]:
        index=int(team["name"].split()[-1])
        team["espnSourceTeamId"]=str(5000+index)
        team["divisionIConfirmed"]=True
    return rating


def poll(ranks,week="2026-11-16",week_num=3):
    return {
        "season":2027,
        "latestWeek":{"number":week_num,"startDate":week},
        "rankings":[
            {"name":"USA Today Coaches Poll","shortName":"Coaches Poll",
             "type":"coaches","ranks":[]},
            {"name":"AP Top 25","shortName":"AP Poll","type":"ap",
             "ranks":[{"current":i+1,
                       "team":{"id":t["espnSourceTeamId"],"displayName":t["name"]},
                       "points":1500-(i*40)} for i,t in enumerate(ranks)]},
        ],
    }


def ordered(rating):
    return sorted(rating["teams"],key=lambda t:(-t["rating"],t["name"]))


class WeeklyAPTests(unittest.TestCase):
    def setUp(self):
        self.records=games()
        self.rating=current(self.records)
        self.top=ordered(self.rating)[:25]
        self.payload=poll(self.top)
        self.ap=extract_ap_poll(self.payload,AT)

    def test_source_ap_poll_not_coaches_and_complete_ids(self):
        self.assertEqual(self.ap["sourceWeekStart"],"2026-11-16")
        self.assertEqual(self.ap["sourceWeekNumber"],3)
        self.assertEqual([r["apRank"] for r in self.ap["ranks"]],list(range(1,26)))
        self.assertEqual(self.ap["ranks"][0]["espnTeamId"],self.top[0]["espnSourceTeamId"])
        bad=copy.deepcopy(self.payload)
        bad["rankings"][1]["ranks"][1]["team"]["id"]=bad["rankings"][1]["ranks"][0]["team"]["id"]
        with self.assertRaisesRegex(ValueError,"Duplicate AP"):
            extract_ap_poll(bad,AT)
        bad=copy.deepcopy(self.payload)
        bad["rankings"][1]["ranks"].pop()
        with self.assertRaisesRegex(ValueError,"25"):
            extract_ap_poll(bad,AT)
        bad=copy.deepcopy(self.payload)
        bad["rankings"][1]["type"]="coaches"
        bad["rankings"][1]["name"]="Coaches"
        bad["rankings"][1]["shortName"]="Coaches Poll"
        with self.assertRaisesRegex(ValueError,"exactly one"):
            extract_ap_poll(bad,AT)
        bad=copy.deepcopy(self.payload)
        bad["season"]=2026
        with self.assertRaisesRegex(ValueError,"season"):
            extract_ap_poll(bad,AT)

    def test_equal_poll_and_elo_rankings_have_full_overlap(self):
        report=snapshot(self.ap,self.rating,self.records,AT)
        self.assertEqual(report["status"],"ready")
        self.assertEqual(report["eloGameCutoffDate"],"2026-11-15")
        self.assertEqual(report["top25Overlap"],25)
        self.assertEqual(report["top10Overlap"],10)
        self.assertEqual(report["meanAbsoluteRankGap"],0)
        self.assertAlmostEqual(report["spearmanWithinMatched"],1.0)
        self.assertEqual(report["matchedApTeams"],25)
        self.assertEqual(len(report["eloTop25"]),25)
        self.assertEqual(report["ncaaPlusEspnRatedGamesThroughCutoff"],len(self.records))

    def test_week_elo_does_not_see_games_played_after_poll_week_start(self):
        first=snapshot(self.ap,self.rating,self.records,AT)
        latest=self.records+[{
            "id":"after","date":"2026-11-18",
            "home":"Program 29","away":"Program 28","homeScore":190,"awayScore":30,
        }]
        after=current(latest)
        second=snapshot(self.ap,after,latest,AT)
        self.assertEqual(first["eloTop25"],second["eloTop25"])
        self.assertEqual(first["teams"],second["teams"])
        self.assertEqual(first["top25Overlap"],second["top25Overlap"])
        self.assertEqual(first["ncaaPlusEspnRatedGamesThroughCutoff"],
                         second["ncaaPlusEspnRatedGamesThroughCutoff"])

    def test_ranks_change_when_ap_voters_disagree(self):
        changed=poll(list(reversed(self.top)))
        report=snapshot(extract_ap_poll(changed,AT),self.rating,self.records,AT)
        self.assertEqual(report["top25Overlap"],25)
        self.assertEqual(report["top10Overlap"],0)
        self.assertLess(report["spearmanWithinMatched"],-.9)
        self.assertGreater(report["meanAbsoluteRankGap"],10)

    def test_identity_gap_not_guessed_or_falsely_marked_as_agreement(self):
        altered=copy.deepcopy(self.ap)
        for i in range(9):
            altered["ranks"][i]["espnTeamId"]=str(90000+i)
        report=snapshot(altered,self.rating,self.records,AT)
        self.assertEqual(report["matchedApTeams"],16)
        self.assertEqual(report["status"],"incomplete-source-coverage")
        self.assertIsNone(report["top25Overlap"])
        self.assertIsNone(report["meanAbsoluteRankGap"])
        self.assertIsNone(report["spearmanWithinMatched"])
        self.assertTrue(all(r["eloRank"] is None for r in report["teams"][:9]))

    def test_immutable_history_blocks_poll_revision_and_elo_backfill(self):
        original=snapshot(self.ap,self.rating,self.records,AT)
        h,changed=update_history(baseline(),original)
        self.assertTrue(changed)
        changed_poll=copy.deepcopy(original)
        changed_poll["teams"][0]["eloRank"]=900
        again,wrote=update_history(h,changed_poll)
        self.assertFalse(wrote)
        self.assertEqual(again,h)
        self.assertEqual(again["weeks"][0]["teams"][0]["eloRank"],1)
        next_week=copy.deepcopy(original)
        next_week["pollKey"]="AP-2027-2026-11-23"
        next_week["sourceWeekStart"]="2026-11-23"
        later,yes=update_history(again,next_week)
        self.assertTrue(yes)
        self.assertEqual(len(later["weeks"]),2)
        self.assertEqual(h["weeks"],[original])


    def test_actual_november_16_ap_tie_18_is_preserved_without_made_up_rank_19(self):
        # November 16, 2026 source poll had Michigan and USC tied for
        # No. 18 with 341 points; official No. 19 was skipped.
        source=copy.deepcopy(self.payload)
        ranked=source["rankings"][1]["ranks"]
        ranked[17]["points"]=341
        ranked[18]["current"]=18
        ranked[18]["points"]=341
        ap=extract_ap_poll(source,AT)
        self.assertEqual([p["apRank"] for p in ap["ranks"][17:20]],[18,18,20])
        result=snapshot(ap,self.rating,self.records,AT)
        self.assertEqual(result["matchedApTeams"],25)
        self.assertEqual(result["top25Overlap"],25)
        self.assertEqual([x["apRank"] for x in result["teams"][17:20]],[18,18,20])
        self.assertIsNotNone(result["spearmanWithinMatched"])
        self.assertGreater(result["spearmanWithinMatched"],.95)

    def test_invalid_rank_skip_or_false_vote_tie_is_rejected(self):
        bad=copy.deepcopy(self.payload)
        bad["rankings"][1]["ranks"][18]["current"]=18
        with self.assertRaisesRegex(ValueError,"inconsistent vote"):
            extract_ap_poll(bad,AT)
        bad=copy.deepcopy(self.payload)
        bad["rankings"][1]["ranks"][18]["current"]=17
        # Give the fabricated tie equal voting points so the test reaches
        # the *rank-skipping* validation rather than failing on points first.
        bad["rankings"][1]["ranks"][18]["points"]=bad["rankings"][1]["ranks"][16]["points"]
        with self.assertRaisesRegex(ValueError,"competition ranking"):
            extract_ap_poll(bad,AT)

    def test_spearman_tie_aware_and_never_overwrites_one_school(self):
        self.assertAlmostEqual(_spearman([(1,1),(2,2),(2,3),(4,4)]),.94868,places=4)
        self.assertAlmostEqual(_spearman([(1,4),(2,3),(2,2),(4,1)]),-.94868,places=4)

    def test_early_week_without_games_is_explicitly_incomplete(self):
        altered=copy.deepcopy(self.ap)
        altered["sourceWeekStart"]="2026-11-02"
        report=snapshot(altered,self.rating,self.records,AT)
        self.assertEqual(report["status"],"incomplete-source-coverage")
        self.assertIsNone(report["top25Overlap"])
        self.assertEqual(report["matchedApTeams"],0)

    def test_spearman_handles_missing_cohort(self):
        self.assertIsNone(_spearman([]))
        self.assertEqual(_spearman([(1,4),(2,6),(3,5)]),.5)


if __name__=="__main__":
    unittest.main()
