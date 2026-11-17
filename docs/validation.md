# Scientific model validation

Version 0.5 · Implementations: `research/forecast/core.py`, `advanced.py`, and `benchmark.py`. Every displayed metric is derived from the deployed `research/benchmark.json`; no report score is hard-coded into the website.

## 1. Research question and boundary

Given two specific teams that actually played an NCAA tournament game, can their **frozen regular-season** strength features estimate the probability of either team winning? This is **conditional matchup evaluation**: we use the historically realized pair of opponents but not the game's outcome for features or model fitting in the held-out year. It is not yet evaluation of who will be selected, bracket advancement pathways or national championship probability predictions.

The original source archive includes regular-season games 1985–2026 and tournament outcomes through 2026. Only complete regular-season snapshots with tournament records are eligible: canceled 2020 is excluded; 2026's source regular season ends at day 118, so its 63-game main-draw supplement cannot create a valid tournament benchmark.

## 2. Chronological Elo baseline

Each team resets to 1500 points each season. With a current rating difference `d = R_A + H_A - R_B`, the model assigns

`P(A wins) = 1 / (1 + 10^(-d/400))`.

`H_A` = +65 for home A, -65 for away, zero at neutral games. Winner updates by `K*(1-p)`, loser by the opposite amount, `K=24`. The tournament assessment **freezes** model ratings before any NCAA tourney results. Recent projection uses a bounded rating slope over recent games; it is a heuristic, not a learned Kalman filter.

### Same-day caveat

Historical Kaggle DayNum gives the calendar day but not actual tip-off time. The baseline orders same-day games deterministically by team identifiers, not verifiable start times. This matters for regular-season pregame Brier diagnostics.

## 3. Five evaluated forecasting systems

| Method | Model inputs | Learned from older NCAA tournaments? |
|---|---|---|
| `coin_flip` | none: p=.5 | no |
| `elo` | historical raw Elo difference | no |
| `trend_elo` | recent-form-adjusted Elo difference | no |
| `calibrated_trend_elo` | trend Elo scaled by scalar temperature T | yes, T selected by **prior seasons only** |
| `logistic` | Elo strength, trend increment and win percentage differential | yes, coefficients fit on **prior seasons only** |

The logistic classifier uses three scaled features:

```text
x1 = (EloA - EloB) / 400
x2 = ((ProjectedA - EloA) - (ProjectedB - EloB)) / 40
x3 = (WinsA / GamesA) - (WinsB / GamesB)
p  = sigmoid(w1*x1 + w2*x2 + w3*x3)
```

Weights are optimized by deterministic batch gradient descent, 240 iterations, learning rate 0.3 and L2 penalty 0.025, initialized from standard Elo. Zero intercept preserves `p(A>B)=1-p(B>A)`. Although outcomes are stored winner-oriented, training equivalently pairs `(x,label 1)` with `(-x,label 0)`: their average gradient equals a single winner-oriented no-intercept gradient. Therefore the procedure does **not** pretend that every game labels the same side as a winner.

Calibration selects a scalar temperature from a fixed grid by minimizing the **previous years'** tournament log loss. Never fit a season's weights or temperature on that season's tournament outcome.

## 4. Walk-forward testing

Start after five complete historical NCAA tournament seasons. To score test year Y, use only earlier years' tournament outcomes for model selection. The regular-season rating snapshots for Y are frozen before Y's tournament; seeds and Y's outcomes are evaluation/display metadata only. Advance the test year by one season and repeat. Report each test year's training-through cutoff, calibrated temperature, logistic coefficients, game count, omitted missing-team rows and scoring metrics.

## 5. Statistics

- **Brier score:** mean squared error of observed winner probability, `mean((1-p_winner)^2)`; lower is better. Winner-oriented storage is exactly equivalent to fixed-side binary Brier scoring.
- **Log loss:** mean `-log(max(p_winner,1e-15))`; lower is better, penalizes confidently wrong outcomes.
- **Winner accuracy:** 1 for favored winner, 0 for favored loser, and 0.5 when both teams receive exactly 50% probability.
- **Reliability:** 10 bins spanning predicted **favorite confidence 50–100%**. For each bin, plot mean confidence versus the *observed favorite win frequency* and include sample size. Because raw outcomes are stored winner-oriented, favorite success is computed as 1 when p_winner>0.5, 0 when <0.5, and 0.5 on a tie; it is not an artificially all-success chart.
- **Season-block uncertainty:** 2,000 deterministic paired bootstrap draws, sampling entire *held-out seasons* with replacement. Game-weighted mean Brier delta vs ordinary Elo and its empirical 2.5%/97.5% quantile interval are reported. Negative delta favors the compared model. Correlated games within a year remain together. Intervals crossing zero cannot establish a robust improvement. Even an interval excluding zero is descriptive, not proof of future reliability.

## 6. Reproduce

```powershell
$env:PYTHONPATH="research"
py -m unittest discover -s research/tests -v
py -m forecast.benchmark --web-dir web --out web/public/research/benchmark.json
```

Check the generated JSON keys `aggregate`, `yearByYear`, `reliability` and `seasonBlockUncertainty`. The deployed UI reads this report; GitHub Actions uploads an additional copy as a downloadable CI artifact.

## 7. What is NOT claimed

- These simple models are not a calibrated 2027 predictor just because they performed better historically.
- The committed data does not contain possession-level 2027 offensive and defensive efficiency metrics. Raw points-per-game and margin-per-game **cannot be labeled adjusted efficiency**.
- No injury, roster change, travel, rest, referee, bookmaker, or real tip-off order is available to these forecasts.
- Hyperparameters for historical baseline Elo were fixed in advance but have not undergone a complete multi-year nested backtest.
- Historical known opponents cannot measure the actual task of forecasting the committee's selected field.

Next scientifically defensible experiments: possession-informed ratings from sourced box scores, actual 2027 holdouts, season-specific drift monitoring, verified bracket slot import, and model calibration constrained by independent test years.

## v0.6 continuation

This file documents the original base Elo + five-model v0.5 evaluation. The **current authoritative eight-model design, real Brier/log-loss table, chronological meta-training, gradient-boosted residual equations and adaptive EWMA feature** are now in [model-zoo-v06.md](model-zoo-v06.md). The reference report uses `schemaVersion=3`.

The v0.6 **historically trained** calibrated/ensemble matchup options are displayed only as explicitly labeled *scenarios* when 2027 current ratings are loaded; the 2027 matchups are not the historical neutral tournament holdout distribution. The forward pregame proof system uses baseline Elo and must not retroactively promote an OOS historical score to a genuine live-prediction record. See [forecast-audit.md](forecast-audit.md).

Live possession-based team stats are sourced for 2027 but are **not** included as historical model features without a comparable history of pre-selection possession and opponent source data. See [adjusted-efficiency.md](adjusted-efficiency.md). No current D-I source membership is invented from conference names; see [identity-and-conferences.md](identity-and-conferences.md).


## v0.9 source integrity, model evaluation and accessible browser controls

New Python regressions: `test_archive_reliability.py` (independently completed ESPN finals and exact NCAA score/date match, postponements, nonfinal scores, immutable idempotent settlement), `test_archive_health.py` (absent/late/no-pick statuses), `test_opponents.py` (pre-date opponent strengths, no same-day leakage, bounded adjustment), expanded `test_state_space.py` (repeated innovation drift watch and fixed/adaptive comparable data), `test_v09_validation.py` (recorded first-pick paired Brier, Elo and candidates' same-source checks, no fake automatic challenger advantage). Browser tests visit the direct Model Lab and mock an **unpublished test-only fixture** for individual game probability evolution and a correctly graded miss; mobile responsive checks, navigation, WCAG critical smoke checks and Next.js static build are retained.

CI must pass `python -m unittest discover -s research/tests -v`, historical benchmark validation, TypeScript and production build, and Chromium desktop/mobile Playwright before merge. A production Pages build is checked separately because it consumes current external NCAA-derived and ESPN feeds. A green CI does not certify a *genuine pregame archive* until the independently scheduled prediction workflow has actually generated and committed artifacts.
