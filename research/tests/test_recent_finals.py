"""Independent ESPN final-score display must not bypass archived pick validation."""
from __future__ import annotations
import copy
import unittest
from datetime import datetime,timezone
from forecast.recent_finals import build_finals

NOW=datetime(2026,11,20,3,30,tzinfo=timezone.utc)
RATINGS={"mode":"current","season":2027,"retrievedAtUtc":"2026-11-20T03:00:00Z",
         "lastGameDate":"2026-11-18",
         "teams":[
            {"name":"Home U","teamId":"ncaa-home","espnSourceTeamId":"111"},
            {"name":"Away U","teamId":"ncaa-away","espnSourceTeamId":"222"}]}
GAME={"date":"2026-11-19","home":"Home U","away":"Away U",
      "homeScore":85,"awayScore":72,"id":"ncaa-contest"}
def score_event(eid="401-test",home=85,away=72,status="STATUS_FINAL",
                completed=True,event_date="2026-11-20T00:15:00Z"):
    return {"id":eid,"date":event_date,
      "status":{"type":{"name":status,"completed":completed}},
      "competitions":[{"competitors":[
        {"homeAway":"home","score":str(home),
          "team":{"id":"111","location":"Home U","displayName":"Home U Cougars"}},
        {"homeAway":"away","score":str(away),
          "team":{"id":"222","location":"Away U","displayName":"Away U Falcons"}}]}]}
def boards(*events):return [{"events":list(events)}]

class RecentFinalSourceTests(unittest.TestCase):
    def test_espn_newer_than_ncaa_is_visible_but_does_not_change_ratings(self):
        r=build_finals(boards(score_event()),RATINGS,[],NOW)
        self.assertEqual(r["status"],"source-ready")
        self.assertEqual(r["mostRecentEspnFinalDate"],"2026-11-19")
        self.assertEqual(r["ncaaResultsThroughDate"],"2026-11-18")
        self.assertEqual(r["confirmedFinalCount"],1)
        self.assertEqual(r["ncaaRatingInputMatched"],0)
        self.assertFalse(r["games"][0]["ncaaRatingInputConfirmed"])
        self.assertEqual((r["games"][0]["homeScore"],r["games"][0]["awayScore"]),(85,72))
        self.assertEqual(r["games"][0]["winner"],"Home U")
        self.assertNotIn("homeWinProbability",r["games"][0])

    def test_only_identical_ncaa_final_can_confirm_rating_input(self):
        matched=build_finals(boards(score_event()),RATINGS,[GAME],NOW)
        self.assertTrue(matched["games"][0]["ncaaRatingInputConfirmed"])
        different=build_finals(boards(score_event()),RATINGS,[{**GAME,"homeScore":86}],NOW)
        self.assertFalse(different["games"][0]["ncaaRatingInputConfirmed"])
        # Never select among contradictory source rows just to claim a match.
        duplicate=build_finals(boards(score_event()),RATINGS,[GAME,GAME],NOW)
        self.assertFalse(duplicate["games"][0]["ncaaRatingInputConfirmed"])
        wrong_date=build_finals(boards(score_event()),RATINGS,[{**GAME,"date":"2026-11-18"}],NOW)
        self.assertFalse(wrong_date["games"][0]["ncaaRatingInputConfirmed"])

    def test_unverified_and_live_games_never_appear_as_final(self):
        events=[score_event("before",status="STATUS_SCHEDULED",completed=False),
                score_event("during",status="STATUS_IN_PROGRESS",completed=False),
                score_event("not-complete",completed=False),
                score_event("tie",home=71,away=71),
                score_event("zero",home=0,away=72)]
        r=build_finals(boards(*events),RATINGS,[],NOW)
        self.assertEqual(r["confirmedFinalCount"],0)
        self.assertEqual(r["games"],[])
        self.assertIsNone(r["mostRecentEspnFinalDate"])

    def test_duplicate_events_merge_safely_but_conflicts_fail(self):
        e=score_event()
        r=build_finals([{"events":[e]},{"events":[copy.deepcopy(e)]}],RATINGS,[],NOW)
        self.assertEqual(r["confirmedFinalCount"],1)
        change=score_event(home=82)
        with self.assertRaisesRegex(ValueError,"Conflicting ESPN final"):
            build_finals([{"events":[e]},{"events":[change]}],RATINGS,[],NOW)

    def test_identity_mismatch_never_claims_ncaa_elo_coverage(self):
        fake=score_event()
        fake["competitions"][0]["competitors"][0]["team"]["id"]="999"
        fake["competitions"][0]["competitors"][0]["team"]["location"]="Different U"
        fake["competitions"][0]["competitors"][0]["team"]["displayName"]="Different U Sharks"
        r=build_finals(boards(fake),RATINGS,[GAME],NOW)
        self.assertFalse(r["games"][0]["ncaaRatingInputConfirmed"])
        self.assertFalse(r["games"][0]["ncaaIdentityMatchConfirmed"])
        self.assertEqual(r["games"][0]["home"],"Different U")

    def test_provider_outage_is_partial_or_unavailable_not_fake_zero(self):
        r=build_finals([],RATINGS,[],NOW,["2026-11-19: timeout"])
        self.assertEqual(r["status"],"source-unavailable")
        self.assertEqual(r["boardDaysRetrieved"],0)
        r2=build_finals(boards(score_event()),RATINGS,[],NOW,["2026-11-18: timeout"])
        self.assertEqual(r2["status"],"source-partial")
        self.assertEqual(r2["confirmedFinalCount"],1)
        self.assertEqual(len(r2["sourceWarnings"]),1)

if __name__=="__main__":
    unittest.main()
