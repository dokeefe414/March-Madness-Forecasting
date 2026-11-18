"""Game-aware 2027 Elo tests: exact per-game updates, no same-day leakage."""
import unittest
from datetime import datetime, timezone

from forecast.core import EloEngine, Game
from forecast.game_aware_elo import GameAwareEloEngine, margin_multiplier
from forecast.live import build_current


def game(day, winner, loser, margin, *, location="N", ident=""):
    return Game(2027, day, winner, loser, 70 + margin, 70, location, ident)


class SourceAwareEloTests(unittest.TestCase):
    def test_each_game_changes_both_teams_and_conserves_points(self):
        games = [
            game(1, 1, 2, 4, ident="a"),
            game(2, 2, 3, 9, ident="b"),
            game(3, 1, 3, 16, ident="c"),
        ]
        engine = GameAwareEloEngine().fit(games, {1:"A",2:"B",3:"C"})
        self.assertEqual(len(engine.game_receipts), 3)
        self.assertEqual(len(engine.team_receipts[1]), 2)
        self.assertEqual(len(engine.team_receipts[2]), 2)
        self.assertEqual(len(engine.team_receipts[3]), 2)
        self.assertEqual(sum(t.games for t in engine.states.values()), 6)
        self.assertAlmostEqual(sum(x.rating for x in engine.states.values()), 4500)
        self.assertTrue(all(r["winnerDelta"] > 0 and r["loserDelta"] < 0 for r in engine.game_receipts))
        self.assertTrue(all(r["contestId"] in {"a","b","c"} for r in engine.game_receipts))
        # New result remains a real movement, not a static recalculated rank.
        earlier = GameAwareEloEngine().fit(games[:2], {})
        self.assertNotAlmostEqual(engine.states[1].rating, earlier.states[1].rating)

    def test_margin_weighting_is_bounded_and_symmetrical(self):
        self.assertLess(margin_multiplier(1), margin_multiplier(12))
        self.assertLess(margin_multiplier(12), margin_multiplier(25))
        self.assertEqual(margin_multiplier(25), margin_multiplier(80))
        self.assertGreaterEqual(margin_multiplier(1), .85)
        self.assertLessEqual(margin_multiplier(100), 1.5)
        with self.assertRaises(ValueError):
            margin_multiplier(0)
        close = GameAwareEloEngine().fit([game(1,1,2,1)],{})
        blowout = GameAwareEloEngine().fit([game(1,1,2,30)],{})
        baseline = GameAwareEloEngine(margin_sensitive=False).fit([game(1,1,2,30)],{})
        self.assertGreater(blowout.states[1].rating, close.states[1].rating)
        self.assertGreater(blowout.states[1].rating, baseline.states[1].rating)
        self.assertAlmostEqual(baseline.states[1].rating, 1512)
        self.assertAlmostEqual(blowout.states[1].rating+blowout.states[2].rating, 3000)

    def test_opponent_strength_and_venue_change_expectation(self):
        # A high-rated team gains little when it predictably beats a weak team.
        earlier = [game(i, 1, 2, 12, ident=str(i)) for i in range(1,5)]
        win = GameAwareEloEngine().fit(earlier+[game(5,1,2,8,ident="last")],{})
        upset = GameAwareEloEngine().fit(earlier+[game(5,2,1,8,ident="last")],{})
        self.assertLess(win.game_receipts[-1]["winnerDelta"], upset.game_receipts[-1]["winnerDelta"])
        home = GameAwareEloEngine().fit([game(1,1,2,10,location="H")],{})
        neutral = GameAwareEloEngine().fit([game(1,1,2,10,location="N")],{})
        away = GameAwareEloEngine().fit([game(1,1,2,10,location="A")],{})
        self.assertLess(home.game_receipts[0]["winnerDelta"],neutral.game_receipts[0]["winnerDelta"])
        self.assertLess(neutral.game_receipts[0]["winnerDelta"],away.game_receipts[0]["winnerDelta"])

    def test_prior_date_frozen_even_when_one_team_has_two_games_same_day(self):
        a = [game(1,1,2,5,ident="one"), game(1,1,3,10,ident="two")]
        b = list(reversed(a))
        first = GameAwareEloEngine().fit(a,{})
        second = GameAwareEloEngine().fit(b,{})
        self.assertEqual(first.rankings(),second.rankings())
        self.assertEqual(first.game_receipts,second.game_receipts)
        self.assertEqual(first.pregame_brier,[.25,.25])
        self.assertEqual(first.pregame_accuracy,[.5,.5])
        for receipt in first.game_receipts:
            self.assertEqual(receipt["preWinnerElo"],1500.0)
            self.assertEqual(receipt["preLoserElo"],1500.0)
        future = GameAwareEloEngine().fit(a+[game(2,1,2,3,ident="three")],{})
        self.assertNotEqual(future.game_receipts[-1]["preWinnerElo"],1500.0)

    def test_duplicate_source_id_and_invalid_score_fail_closed(self):
        with self.assertRaisesRegex(ValueError,"duplicate contest"):
            GameAwareEloEngine().fit([game(1,1,2,5,ident="x"),game(2,2,1,5,ident="x")],{})
        with self.assertRaisesRegex(ValueError,"invalid winning game"):
            GameAwareEloEngine().fit([Game(2027,1,1,2,70,70,"N","x")],{})
        with self.assertRaisesRegex(ValueError,"one season"):
            GameAwareEloEngine().fit([game(1,1,2,5),Game(2026,2,1,2,75,70)],{})
        # Historical engine remains K=24, not a silently rewritten tournament calibration.
        old = EloEngine().fit([Game(2025,1,1,2,95,75)],{})
        self.assertEqual(old.states[1].rating,1512.0)

    def test_public_team_rating_changes_and_explains_every_source_result(self):
        games = [
            {"id":"100","date":"2026-11-02","home":"A","away":"B","homeScore":78,"awayScore":69},
            {"id":"101","date":"2026-11-03","home":"B","away":"A","homeScore":85,"awayScore":75},
            {"id":"102","date":"2026-11-03","home":"A","away":"C","homeScore":79,"awayScore":55},
        ]
        captured = datetime(2026,11,5,tzinfo=timezone.utc)
        data = build_current(games,captured)
        self.assertEqual(data["regularSeasonGames"],3)
        self.assertEqual(len(data["recentEloUpdates"]),3)
        self.assertEqual(data["eloComparison"]["evaluatedGames"],3)
        self.assertEqual(data["eloMethodology"]["marginCapPoints"],25)
        self.assertEqual(data["pregameDiagnostics"]["evaluatedGames"],3)
        self.assertTrue(data["eloMethodology"]["priorDateFrozen"])
        team_a = next(x for x in data["teams"] if x["name"]=="A")
        self.assertEqual(team_a["eloLastGameDate"],"2026-11-03")
        self.assertEqual(len(team_a["eloRecentChanges"]),3)
        self.assertIn("opponentAverageEloAtGame",team_a)
        self.assertIn("classicElo",team_a)
        self.assertNotEqual(team_a["rating"],team_a["classicElo"])
        self.assertAlmostEqual(sum(x["rating"] for x in data["teams"]),4500,delta=.2)
        recalc = build_current(list(reversed(games)),captured)
        self.assertEqual(data["recentEloUpdates"],recalc["recentEloUpdates"])
        self.assertEqual(data["teams"],recalc["teams"])
        self.assertEqual(data["eloComparison"],recalc["eloComparison"])

if __name__=="__main__":
    unittest.main()
