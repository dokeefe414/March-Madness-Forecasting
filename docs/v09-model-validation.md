# v0.9 — Research-first adaptive forecasting and valid model comparisons

## Goal

The user can open any supported **real future ESPN scheduled game**, inspect the source-data and previous-game evidence behind the projected winning probabilities, and later review the actual **original before-tipoff prediction** against a confirmed final result. Every model receives a transparent prospective score. Candidate models must demonstrate improvements over the baseline **on precisely the same games** rather than gaining credit for sample differences or postgame hindsight.

The source data and scheduled workflows must be inspected by **exact retrieval and published timestamp**. A source cannot be considered final just because a nonzero score appeared. An ESPN game ID cannot be mapped to an NCAA team merely by fuzzy nicknames.

## Source evidence and settlement

### Actual pregame prediction

`research/forecast/snapshot.py` requires the ESPN `STATUS_SCHEDULED` state, participant identity matched to independently sourced same-season NCAA↔ESPN identifiers, and **at least 15 minutes** between archived UTC forecast creation and ESPN's listed start. It also requires the last included NCAA game date to be **strictly earlier than the fixture's Eastern date**: the third-party NCAA schedule can temporarily contain nonfinal scores on the same calendar date.

An archived snapshot freezes the selected probability plus the contemporaneous Elo, shadow logistic, opponent-adjusted, fixed state-space, and adaptive state-space research alternatives **when available**. All alternatives share the same pretipoff timestamp and source retrieval; none is later backfilled.

### Verified final result

A scored NCAA schedule row is **not enough** to settle an earlier forecast. Settlement now requires:

1. The forecast existed strictly before tipoff (15-minute margin and source-as-of audit).
2. Exactly one completed NCAA-source result matches canonical home, away, and the original ESPN scheduled Eastern date.
3. The independent ESPN event **with the exact archived ESPN event ID** has type `STATUS_FINAL` and `completed: true`.
4. ESPN home/away final scores are positive, unequal and **identical** to the corresponding NCAA-source home/away scores.
5. The ESPN event's Eastern date equals the originally recorded fixture date. Postponed/rescheduled games with a changed date cannot be silently accepted.

If the third-party sources disagree, the forecast remains *unsettled*, and the monitor explains source coverage; the system does **not** assume it was right or wrong. This is two-provider *consistency* verification, **not a signed official NCAA certification**. Source providers can still share mistaken information.

### Distinct-game accuracy

`research/forecast/performance.py` selects the **earliest** immutable published snapshot per ESPN event ID before looking at winners. If the first pick is unsettled but a later capture settled, the game remains unscored in the one-game-one-vote headline. It computes accuracy, Brier, log loss, cumulative accuracy and confidence/reliability bins on actual graded first picks.

The new `pairedModelComparisons` compares every archived research candidate to Elo *only where both source-frozen probabilities are available for the same event*: mean Brier, correct-winner rate, paired-game count, number of independent dates, and game-date-block descriptive 95% Brier improvement interval (only after >=40 paired games and >=5 independent dates). An interval spanning zero is insufficient evidence of advantage. These intervals are **descriptive**, not controlled false-discovery guarantees.

A single loss never rewrites its past probability, fabricates a cause, or automatically promotes another model. Correct and incorrect predictions join the next *previous-date* retraining as source results become available.

## Opponent-adjusted margin research

Module: `research/forecast/opponents.py`; public generated artifact `/current/2027-opponents.json`.

**Problem:** a raw 20-point win means different things against a 1700 Elo opponent and a 1300 Elo opponent. The opponent-aware challenger retains the opponent's *actual prior-date* Elo at each previous game, then computes **surprise margin**:

```text
expected_home_margin = (Elo_home_pre + 65 - Elo_away_pre) / 28
surprise_home = clip(actual_home_margin - expected_home_margin, -24, 24)
surprise_away = -surprise_home

residual_new = 0.7 × residual_pre + 0.3 × surprise
shrink_factor = previous_games / (previous_games + 6)
opponent_adjustment_elo = clip(8 × residual_new × shrink_factor, -75, +75)
opponent_adjusted_rating = prior_day_elo + opponent_adjustment_elo

p_adjusted_home = sigmoid(log(10)/400 ×
                          (adjusted_elo_home + 65 - adjusted_elo_away))
```

These coefficients are **documented research assumptions**, not magically trained coefficients. Opponents' later game outcomes cannot rewrite the opponent rating used when calculating any earlier margin surprise. This is an *adjusted team-form signal*, not a claim that game margin causally identifies skill.

For each calendar date D, every game's Elo and opponent-adjusted predictions are scored with **only game dates less than D**. All updates for D happen after all D predictions, with a conservative embargo of the entire *current Eastern date*. `chronological.eloBrier` and `chronological.opponentAdjustedBrier` score the *same* fixtures. The report includes seven-date and per-date paired values, source identity, and team changes.

A lower retrospective paired Brier does **not** automatically make this the operational game picker. It stays `mode:research-only` and is frozen as a shadow alternative for future independently verifiable outcome comparisons.

## Adaptive Gaussian/Kalman-style skill experiment

Module: `research/forecast/state_space.py`; public generated artifact `/current/2027-state-space.json`.

The original fixed-filter assumptions continue: each team has latent Gaussian mean/variance, observation from capped game margin, fixed home advantage, observation variance of `250²`, process variance baseline `18²`, and linear gain update. This is **not** a fitted NCAA possession/roster model.

v0.9 adds an **adaptive research copy** of the same filter evaluated on identical date-frozen outcomes. For each previous game's innovation `e=z−(mean_home−mean_away)` and predictive standard deviation `sqrt(S)`, the filter records normalized innovation `e / sqrt(S)`.

A team enters **drift watch** only after at least 2 of its last 3 normalized innovations are above **+0.8** or at least 2 are below **−0.8**. This is *persistent signed evidence*, not one dramatic outcome. On **subsequent games**, a watched team's process noise is multiplied by **2.5** to allow quicker variance/strength response; it returns to normal after the watch clears. The indicator is heuristic: it does **not** certify a new roster, coaching change, injury, or statistical change point. No hyperparameter is secretly tuned on the currently held-out game.

The report publishes fixed-versus-adaptive Brier, Elo benchmark on the *identical* date-frozen fixtures, the last seven dates, per-team normalized innovation history, the watch state/episode count, and variance. Both variants remain research-only until independently archived prospective evidence is sufficient.

## Promotion policy: learn, don't overfit

The *operational* forecast remains Elo except for the separately documented logistic model. The logistic correction becomes eligible for a future **non-neutral regular-season** forecast only after **both**:

- Chronological test: >=160 games across 10 previous days before the walk-forward evaluation, >=120 later-date scored games across >=12 dates, paired mean Brier improvement >=0.002 and a positive date-block bootstrap lower bound.
- Real-forward gate: >=40 **unique first-published, independently graded** real future games with frozen Elo and shadow logistic predictions, and mean Brier gain >=0.002 on that same paired sample.

Promotion and demotion can happen on the next schedule-triggered retrain. **Neither the opponent-aware nor the adaptive state-space research model is automatically promoted** merely by lower historical Brier; their prospective sample and venue suitability require separate research validation. This is a bounded honest model-selection process, not perfect prediction.

## Interpret the model lab correctly

`ModelLab.tsx` provides:

- **Forward scoreboard:** paired real before-tipoff Brier and winner accuracy for each candidate versus Elo; confidence interval withheld before enough dates/games; real number of distinct games.
- **Date-frozen replay:** opponent-aware, fixed, adaptive and logistic experiments **each paired with Elo within that experiment**. Different experiment rows may have *different dates and samples*, so comparing scores across rows without controlling cohorts is invalid.
- **Recent-date signals:** opponent experiment's per-date paired Brier and state-space last-seven-date Brier/drift watch. More models do not make a stronger product without genuine validation.

The model lab's research status is separate from the selected model on the real game's headline percentage. The live browser does not retrain when a tab opens; it reads versioned artifacts from GitHub Pages after scheduled Actions.

## Tests and reproducibility

```powershell
$env:PYTHONPATH="research"
py -m unittest discover -s research/tests -v
py -m forecast.opponents --games web/public/current/2027-games.json --ratings web/public/current/2027.json --out web/public/current/2027-opponents.json
py -m forecast.state_space --games web/public/current/2027-games.json --ratings web/public/current/2027.json --out web/public/current/2027-state-space.json
py -m forecast.audit --dir web/public/forecasts
```

CI includes hermetic tests for model bounds, opposing-team shocks, same-day embargo, opponent historical state, match-identity protection, source mismatch, idempotent settlement, exact finished-score consistency, and authentic first-pick/non-cherry-picked paired evaluation. The website uses desktop/mobile Playwright with a **test-only mocked event**, never posted as real data.

See [reliable scheduled archiving](v09-forecast-operations.md), [online logistic model](online-retraining.md), [Game Center](game-center.md), and [real forward accuracy](forward-performance.md). Data and parameters are scoped to the **2026–27 season**; 2028 requires an intentional source migration.
