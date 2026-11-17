# v0.6 — Forecasting models, formulas, and leakage controls

## Goal and scope

The March Forecast research objective is to minimize **out-of-time NCAA tournament matchup probability error**. It measures P(A defeats B) for *real historical tournament matchups*, with features frozen at the end of each regular season. This is NOT an evaluation of predicting which teams participate, NCAA seeds, a bracket path, injuries, or future 2027 game outcomes.

At publication, the eligible benchmark covers **35 held-out seasons, 1990–2025, 2,270 games**, excluding canceled 2020, incomplete 2026 regular-season data, and missing matchups. Every model scores the same games.

## Eight implemented algorithms

| Key | Method | Data and training |
| --- | --- | --- |
| `coin_flip` | Reference 50% | No information, Brier 0.25 |
| `elo` | Baseline Elo | Season start 1500, K=24, regular-season home advantage 65, neutral tournament probabilities |
| `trend_elo` | Bounded recent form | Existing bounded Elo slope heuristic |
| `adaptive_form` | Time-series regime model | Causal EWMA of Elo updates, recent change of slope, volatility shrinkage; bounded ±24 points |
| `calibrated_trend_elo` | Past-year temperature | Select temperature using *earlier seasons'* NCAA tournament log loss |
| `logistic` | Regularized classifier | Prior tournaments only; Elo delta, trend correction, wins/played differential |
| `boosted` | Symmetric gradient boosting | Fit Newton-log-loss decision stumps as *earlier-year* residual corrections to Elo; paired winner/loser orientations |
| `blend` | Chronologically tuned ensemble | Combine regular Elo and calibrated trend-Elo with weight chosen on **previous out-of-time test-year predictions only** |

### Elo equation

For a neutral-court rating difference `d = R_A-R_B`:

```math
p_A = \frac{1}{1+10^{-d/400}}
```

Regular-season games use ±65 Elo home advantage and K=24 sequential updates; tournament probabilities freeze the Selection Sunday rating. Home/road game semantics remain part of the imported source, not tournament evaluation.

### Causal dynamics

Let `Δ_i = Elo_i - Elo_(i-1)` denote the rating increment after observed game i. The adaptive baseline computes a smoothed EWMA `m_i = 0.4Δ_i + 0.6m_(i-1)`, the difference between the latest three and previous three increment means, and the standard deviation over the last six increments. The adjustment shrinks at small sample sizes and high volatility; `|adjustment| ≤ 24` Elo points. When there are fewer than three increments the adjustment is zero. **This is a manually specified time-series heuristic**, not a fitted ARIMA/Kalman or neural model.

### Symmetric gradient-boosted Elo

`research/forecast/boosted.py` initializes the logit from regular Elo:
`logit_base = log(10) * (Elo_A-Elo_B)/400`.

Weak learners are decision stumps on the three pre-tournament features: scaled rating gap, recent form gap and win-percent gap. Stump values use regularized second-order residuals (Newton approximation). The training set includes the winner-oriented record `(x,1)` **and** its reflected example `(-x,0)` to avoid an all-winner-label classifier. A paired antisymmetrized final logit enforces exactly `P(A>B)=1-P(B>A)`.

Hyperparameters: 14 stumps maximum, learning rate 0.12, ridge 4.0 and min 20 examples per leaf. The grid of candidate stump thresholds is predetermined and not tuned on the held-out season. A boost score better than Elo in one rolling test does not establish repeatability under different selection years or a 2027 data distribution.

### Chronological blend

The ensemble candidate weights are `0, 0.25, 0.5, 0.75, 1`. For test season Y, the weight is selected to minimize Brier on **previous completed test seasons** where each past year's temperature was fitted only on its own earlier training years. The first eligible test season has no meta-training history and defaults to plain Elo. This differs importantly from re-fitting a blend to the same test-year outcomes.

The `productionCalibration` report provides historically learned temperature and ensemble weight for 2027 UI **scenarios**; March neutral tournament calibration is not known to transfer to early-season home-court games, and the UI must display this caveat. Actual forward prediction audit logs currently use baseline Elo.

## Metrics

Brier `mean((p_winner - 1)^2)`, log loss `mean(-log(p_winner))` and winner accuracy, with 50/50 ties counted as half-correct. The chart uses ten favorite-confidence reliability bins from 50–100%, with sample counts and realized favorite win rates. Descriptive 95% intervals are calculated with 2,000 reproducibly seeded paired **season-block** bootstrap draws, preserving intraseason dependence.

### Measured v0.6 historical results

| Model | Brier ↓ | Log loss ↓ | Winner accuracy |
| --- | ---: | ---: | ---: |
| Coin flip | 0.2500 | 0.6931 | 50.0% |
| Elo | 0.2225 | 0.6360 | 63.6% |
| Trend Elo | 0.2240 | 0.6391 | 63.5% |
| Adaptive form | 0.2274 | 0.6460 | 62.0% |
| Calibrated trend Elo | 0.2207 | 0.6296 | 63.5% |
| Logistic | 0.2291 | 0.6506 | 63.2% |
| Boosted Elo | **0.2181** | **0.6255** | 63.6% |
| Past-year ensemble | 0.2205 | 0.6296 | 63.6% |

These values were taken from a **successful historical benchmark GitHub Actions run** using the current feature branch. All metrics are descriptive; refer to generated 95% intervals to interpret a model-vs-Elo difference. We did not secretly select winner accuracy as the primary objective after testing; Brier is the main metric.

## Reproduction

```powershell
$env:PYTHONPATH="research"
py -m unittest discover -s research/tests -v
py -m forecast.benchmark --web-dir web --out web/public/research/benchmark.json
```

No third-party Python packages are necessary. Benchmark outputs: model metrics, `yearByYear` cutoffs and coefficients/stump descriptions, `reliability`, `seasonBlockUncertainty`, and `productionCalibration`.

The 2026 Kaggle regular season is incomplete and the bracket archive excludes First Four; exclude both from chronological tournament evaluation instead of treating them as an actual complete Selection Sunday snapshot.

## Limitations and valid next experiments

- The historical Kaggle snapshot lacks possession-based advanced metrics; **v0.6 possession estimates are sourced from a different 2027 NCAA-derived box dataset and cannot be injected into the historical backtest** without a verified season-spanning ID/data join.
- Same-day historical game ordering is deterministic, not known tipoff.
- Current-season "adjusted efficiency" is regularized opponent-informed descriptive per-100 production, *not* a proven matchup-calibrated forecasting feature.
- A real, forward record of probabilities committed before tipoff is tracked independently, and should be evaluated as a separate study from this historical benchmark.
- Next valid work: hierarchical shrinkage of Elo, multi-year source-linked possession experiments, rolling sports-specific shift detectors, injury/transfer source licensing, forecast calibration and independent 2027 test sets.

## 2027 source-based model extensions: careful distinction

The current dashboard additionally shows `adaptiveRating`, `regimeShift`, `volatility` from **already completed** 2027 Elo increments and optional `adjOff100`, `adjDef100` from genuine NCAA box-score possessions with source coverage. The adjusted possession metrics are a *team-profile descriptive model*, not features in the historical eight-way comparison.

The selection watchlist requires independent 2027 Division I **group-season membership** as well as a sourced NCAA conference identity before proposing any strength-only candidates. This prevents promoting non-D-I games to hypothetical March selection based solely on their presence in the schedule. Confirmed D-I membership still does not imply postseason eligibility. Unknown teams are neither assumed D-I nor declared ineligible.

## v0.7 regular-season retrained model (separate from historical tournament benchmark)

The eight historical models above continue to be evaluated on **historical actual tournament matchups**. Separately, `forecast.retrain` now learns a logistic Elo residual on 2027 **regular-season** games after every source refresh, holding entire dates out during rolling-origin evaluation and excluding the current date completely. It automatically promotes or demotes only after meeting fixed paired Brier and date-block bootstrap gates. Its measured errors are **not comparable across populations** to the historical tournament benchmark. [2027 in-season model methodology](online-retraining.md).
