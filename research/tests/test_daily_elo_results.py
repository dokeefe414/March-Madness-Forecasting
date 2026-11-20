"""Daily ESPN-final Elo replay, source reconciliation and archival guarantees."""
from __future__ import annotations
import copy
import unittest
from datetime import datetime,timezone
from tempfile import TemporaryDirectory
from pathlib import Path

from forecast.elo_results import merge_games,load_receipts,save_receipts
from forecast.live import build_current
from forecast.recent_finals import build_finals

NOW=datetime(2026,11,20,3,48,tzinfo=timezone.utc)
NCAA=[{"id":"ncaa1","date":"2026-11-15","home":"Home U","away":"Away U",
       "homeScore":66,"awayScore":63}]
RATINGS={"mode":"current","season":2027,"lastGameDate":"2026-11-15",
         "retrievedAtUtc":"2026-11-20T03:30:00Z",
         "teams":[{"teamId":"ncaa-home","name":"Home U","espnSourceTeamId":"111"},
                  {"teamId":"ncaa-away","name":"Away U","espnSourceTeamId":"222"}]}

def event(ident="401-2",home=84,away=72,homeid="111",awayid="222",
          status="STATUS_FINAL",completed=True,stamp="2026-11-20T00:10:00Z"):
    return {"id":ident,"date":stamp,
      "status":{"type":{"name":status,"completed":completed}},
      "competitions":[{"competitors":[
        {"homeAway":"home","score":str(home),
         "team":{"id":homeid,"location":"Home U","displayName":"Home U Jets"}},
        {"homeAway":"away","score":str(away),
         "team":{"id":awayid,"location":"Away U","displayName":"Away U Bulls"}}]}]}

def provider(*events):
    boards=[{"events":list(events)}]
    return build_finals(boards,RATINGS,NCAA,NOW,requested_days=7,result_limit=None)["games"]

class DailyRatingTests(unittest.TestCase):
    def test_final_learns_once_before_ncaa_feed_and_both_ratings_change(self):
        finals=provider(event())
        self.assertEqual(len(finals),1)
        self.assertTrue(finals[0]["espnIdentityIdsMatch"])
        joined,report,stored=merge_games(NCAA,finals,RATINGS,observed=NOW)
        self.assertEqual(report["ratedEspnOnlyFinals"],1)
        self.assertEqual(report["ncaaAcceptedGames"],1)
        self.assertEqual(len(joined),2)
        self.assertEqual(joined[-1]["source"],"ESPN-confirmed STATUS_FINAL")
        base=build_current(NCAA,NOW)
        after=build_current(joined,NOW)
        original={t["name"]:t["rating"] for t in base["teams"]}
        latest={t["name"]:t["rating"] for t in after["teams"]}
        self.assertGreater(latest["Home U"],original["Home U"])
        self.assertLess(latest["Away U"],original["Away U"])
        self.assertEqual(after["lastGameDate"],"2026-11-19")
        self.assertEqual(after["regularSeasonGames"],2)
        self.assertAlmostEqual(sum(latest.values()),sum(original.values()),places=1)
        self.assertEqual(stored["receipts"][0]["eventId"],"401-2")

    def test_ncaa_catchup_replaces_espn_without_double_counting(self):
        finals=provider(event())
        first,r,stored=merge_games(NCAA,finals,RATINGS,observed=NOW)
        late=NCAA+[{"id":"ncaa2","date":"2026-11-19","home":"Home U",
                    "away":"Away U","homeScore":84,"awayScore":72}]
        second,rr,st=merge_games(late,finals,RATINGS,stored,observed=NOW)
        self.assertEqual(rr["ratedEspnOnlyFinals"],0)
        self.assertEqual(rr["ncaaAcceptedGames"],2)
        self.assertEqual(rr["rejectedOrReconciled"]["alreadyInNcaa"],1)
        self.assertEqual(len(second),len(first))
        self.assertEqual(st,stored)
        old_elo=build_current(first,NOW)
        new_elo=build_current(second,NOW)
        self.assertEqual({x["name"]:x["rating"] for x in old_elo["teams"]},
                         {x["name"]:x["rating"] for x in new_elo["teams"]})

    def test_receipt_persists_when_provider_window_no_longer_contains_game(self):
        finals=provider(event())
        first,_,saved=merge_games(NCAA,finals,RATINGS,observed=NOW)
        with TemporaryDirectory() as d:
            path=Path(d)/"scores.json"
            save_receipts(path,saved)
            loaded=load_receipts(path)
            replay,stats,stored=merge_games(NCAA,[],RATINGS,loaded,observed=NOW)
            self.assertEqual(first,replay)
            self.assertEqual(saved,stored)
            self.assertEqual(stats["ratedEspnOnlyFinals"],1)

    def test_ambiguous_or_conflicting_ncaa_score_is_quarantined(self):
        finals=provider(event())
        conflicting=NCAA+[{"id":"ncaa2","date":"2026-11-19",
                           "home":"Home U","away":"Away U",
                           "homeScore":83,"awayScore":72}]
        replay,report,_=merge_games(conflicting,finals,RATINGS,observed=NOW)
        self.assertEqual(report["ratedEspnOnlyFinals"],0)
        self.assertEqual(report["rejectedOrReconciled"]["ncaaScoreOrDateConflict"],1)
        self.assertEqual(len(replay),len(conflicting))
        # Identical score with reversed venue and a nearby NCAA date
        # must also be considered one contest rather than a second win.
        reversed_ncaa=[{**NCAA[0],"id":"n-venue","date":"2026-11-18",
                        "home":"Away U","away":"Home U",
                        "homeScore":72,"awayScore":84}]
        replay2,stats2,_=merge_games(reversed_ncaa,finals,RATINGS,observed=NOW)
        self.assertEqual(len(replay2),1)
        self.assertEqual(stats2["rejectedOrReconciled"]["alreadyInNcaa"],1)

    def test_source_id_mismatch_does_not_add_score_to_elo(self):
        row=provider(event(homeid="999"))[0]
        self.assertFalse(row["espnIdentityIdsMatch"])
        joined,stats,_=merge_games(NCAA,[row],RATINGS,observed=NOW)
        self.assertEqual(len(joined),1)
        self.assertEqual(stats["ratedEspnOnlyFinals"],0)
        self.assertEqual(stats["rejectedOrReconciled"]["noAuthoritativeTeamIdPair"],1)

    def test_later_espn_score_edit_is_not_silently_accepted(self):
        finals=provider(event())
        _,_,saved=merge_games(NCAA,finals,RATINGS,observed=NOW)
        changed=provider(event(home=85))
        replay,report,stored=merge_games(NCAA,changed,RATINGS,saved,observed=NOW)
        self.assertEqual(len(replay),1)
        self.assertEqual(report["ratedEspnOnlyFinals"],0)
        self.assertEqual(report["rejectedOrReconciled"]["changedVerifiedEspnScore"],1)
        self.assertEqual(stored["receipts"],saved["receipts"])
        self.assertEqual(stored["quarantinedEventIds"],["401-2"])
        # The disputed ESPN final stays quarantined on subsequent refreshes
        # after it leaves the provider's seven-day rolling lookback.
        again,details,_=merge_games(NCAA,[],RATINGS,stored,observed=NOW)
        self.assertEqual(len(again),1)
        self.assertEqual(details["ratedEspnOnlyFinals"],0)

    def test_unverified_espn_game_does_not_train_model(self):
        unverified=provider(event(status="STATUS_SCHEDULED",completed=False))
        self.assertEqual(unverified,[])
        game,report,_=merge_games(NCAA,unverified,RATINGS,observed=NOW)
        self.assertEqual(len(game),1)
        self.assertEqual(report["ratedEspnOnlyFinals"],0)

    def test_duplicate_espn_id_same_day_suppressed(self):
        both=provider(event("one"),event("two",home=82,away=70))
        games,report,_=merge_games(NCAA,both,RATINGS,observed=NOW)
        self.assertEqual(len(games),1)
        self.assertEqual(report["rejectedOrReconciled"]["ambiguousEspnSameDayPair"],2)

    def test_tampered_saved_receipts_fail_closed(self):
        _,_,stored=merge_games(NCAA,provider(event()),RATINGS,observed=NOW)
        tampered=copy.deepcopy(stored)
        tampered["receipts"][0]["homeScore"]=0
        with self.assertRaisesRegex(ValueError,"Invalid purported"):
            merge_games(NCAA,[],RATINGS,tampered,observed=NOW)
        tampered=copy.deepcopy(stored)
        tampered["receipts"]*=2
        with self.assertRaisesRegex(ValueError,"Duplicate saved"):
            merge_games(NCAA,[],RATINGS,tampered,observed=NOW)

    def test_elo_is_deterministic_when_no_new_scores_are_available(self):
        finals=provider(event())
        prior,_,stored=merge_games(NCAA,finals,RATINGS,observed=NOW)
        replay,_,_=merge_games(NCAA,finals,RATINGS,stored,observed=NOW)
        self.assertEqual(prior,replay)
        self.assertEqual({t["name"]:t["rating"] for t in build_current(prior,NOW)["teams"]},
                         {t["name"]:t["rating"] for t in build_current(replay,NOW)["teams"]})

if __name__=="__main__":unittest.main()
