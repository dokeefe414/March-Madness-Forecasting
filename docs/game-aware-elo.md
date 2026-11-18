# 2026–27 game-aware Elo: complete scored-game updates and honest limits

## Purpose

Every **accepted, source-backed 2026–27 regular-season game** updates BOTH teams'
published Elo. This is a source-aware, bounded-margin extension of the previous
K=24 classic Elo. The pipeline rebuilds team ratings from the full accepted
source schedule at each scheduled refresh; it is **not** an event-stream callback
after each final buzzer. New scores appear when NCAA-derived data and the GitHub
job become available. The source's nonzero, nontied score subset is NOT itself
an independently authenticated completed-status feed. The public forward
prediction ledger maintains stricter independent ESPN `STATUS_FINAL` + matching
NCAA-score requirements for grading predictions.

## Equation

Let `R_h` and `R_a` be the start-of-date home and away team strength. Using
the source-designated home designation (which might be neutral in reality):

```text
P(home win) = 1 / (1 + 10 ^ (-(R_h + 65 - R_a) / 400))
y           = 1 if home wins else 0
m           = abs(home_score - away_score)            (positive final score margin)
w(m)        = 0.85 + 0.65 * min(1, log(1 + m) / log(26))
delta       = 24 * w(m) * (y - P(home win))
R_h_new     = R_h + delta
R_a_new     = R_a - delta
```

The margin multiplier is capped at 1.50 for winning margins of 25 points or
greater and is approximately 0.99 for a 1-point result. A 50-point rout
therefore cannot scale Elo arbitrarily, and a strong favorite's ordinary
victory still provides limited surprise because its pregame probability was
already high. The update is strictly zero-sum. The Elo strength of the
opponent *at the time* of the game affects the update automatically; an average
of opponents' eventual season-end Elo is never used in prediction. Regular-season
initial Elo is 1500 for each rated program; no unverified historical crosswalk
or season-to-season transfer is invented.

**Venue**: The schedule's home/away designation gets a 65-point adjustment.
It does not supply reliable neutral-site confirmation, so no neutral-site
classification is fabricated. **Time**: all games with a given source calendar
date are scored using ratings at the beginning of that date; only afterward
are their updates applied in a stable source-ID order. This intentionally
prevents knowing the result of an earlier-processed same-date game from helping
a prediction that may actually have happened first. Team-rating histories
and most-recent-game deltas still record each game separately.

## What the model does—and does not—consider

- **Directly in Elo**: actual winner and loser, score margin, game-time opponent
  strength, source-designated home/away location, and every accepted prior result.
- **Shown separately**: recent trend/projection, previous-opponent strength
  averages, raw scoring, and verified source-linked adjusted offense/defense
  and possessions where available.
- **Not assumed**: injuries, lineups, transfers, player availability, travel,
  authoritative neutral court, strength of an unseen team, unverified box-score
  coverage, seed or official tournament selection. Those require source-aligned,
  causally available feature feeds and out-of-time evaluation, not guesses.

## Operational behavior and prediction integrity

1. `forecast.live` validates and de-duplicates source scores; `build_current`
   constructs both the new game-aware Elo and an identically date-frozen
   classic K=24 reference for an **apples-to-apples historical replay**.
2. For each game it records pregame Elo, win chance, effective K, score
   margin and a signed rating change. The final public JSON publishes
   `eloMethodology`, `eloComparison`, `recentEloUpdates`, each team's
   `eloRecentChanges`, `eloLastGameChange`, and `classicElo`.
3. The logistic research challenger uses the SAME margin-aware state-update
   calculation and date embargo as the current team's source-aware rating.
   Opponent/Kalman challengers still report their separately implemented models
   rather than misleadingly claiming to reuse the new Elo state.
4. The published **actual first-pick** forecast archive stays immutable.
   Newly computed Elo ratings only affect as-of new predictions. Grading
   previous games never rewrites their original probabilities.
5. `eloComparison` reports paired classic and margin-aware pre-date Brier and
   winner accuracy, including NEGATIVE improvements where applicable. It is
   not cross-validated hyperparameter selection or prospective evidence of
   superior accuracy. Do not claim this change automatically "gets stronger".
   Consider any model promotion separately using original frozen prospective
   picks and date-block evaluation.

The already configured GitHub Actions archive+Pages pipeline schedules verified
result checks at 02:07 and 06:07 Eastern during the season, with site updates at
02:47 and 06:47, plus daytime runs (see
[v0.9 operating schedule](v09-forecast-operations.md)). Re-computing source
ratings is automatic on each deployment. This is a periodic polling service,
not guaranteed immediately after every buzzer.

## Reproduce and validate

```powershell
$env:PYTHONPATH="research"
py -m unittest discover -s research/tests -p "test_game_aware_elo.py" -v
py -m unittest discover -s research/tests -p "test_retrain.py" -v
py -m unittest discover -s research/tests -v

# Use a real downloaded source or fixture in offline mode:
py -m forecast.live --input fixture.csv --out web/public/current/2027.json --games-out web/public/current/2027-games.json
py -m forecast.retrain --games web/public/current/2027-games.json --ratings web/public/current/2027.json --out web/public/current/2027-online-model.json
```

The tests cover source-ID duplicate rejection, per-game zero-sum movement,
bounded score-margin scaling, high/low-strength opponent sensitivity,
home/away/neutral mechanics in the Elo engine, complete same-date pregame
embargo, input reordering stability, unaltered historical Elo and published
team-level game receipts.
