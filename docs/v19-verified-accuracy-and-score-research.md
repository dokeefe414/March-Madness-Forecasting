# v1.9 — Verified first-pick accuracy, frozen scoring research, source diagnostics

## Objective and evidence boundary

v1.9 builds a complete auditable prospective performance system around existing independently sourced **ESPN scheduled fixtures** and **NCAA completed results**, with cross-checking against independent ESPN `STATUS_FINAL` events. No backfilled game prediction may enter the ledger, and no existing immutable `snapshots/*.json` or `settlements/*.json` file is overwritten. The currently active Elo selection policy is **not** changed.

This release improves the infrastructure and presentation of prediction accuracy. It does **not** promise better numerical accuracy before real first-pick results and independently verified final scores accumulate.

## 1. Original pick audit and automatic settlement monitoring

The existing scheduled `.github/workflows/archive-pregame.yml` remains the sole publisher of original pregame snapshots and independently sourced settlements. It already scans unresolved historical fixture days (subject to a bounded request budget), reconciles exact canonical NCAA team identities and Eastern scheduled dates, and checks ESPN's completed status, event identity, and the same final scores. Missing, incomplete or conflicting source data **never** becomes a scored game.

The derived `research/forecast/accuracy_research.py` process reads saved snapshots and settlements **without writing to the original ledger**. For each ESPN event ID it selects the chronologically earliest original pretipoff forecast, checks its source timestamp and at least 15-minute pregame buffer, and only accepts verified finals with matching team identities and score arithmetic. Later snapshots never replace the first prediction, even when their probability would improve the final result. An unverified, postponed, recently started, or canceled fixture is never labeled as a model loss or a win.

The accuracy dashboard explicitly distinguishes unique outcomes from repeated snapshots and shows pending classes: upcoming, recently started (<5 hours since listed start), awaiting verification (5–48 hours), and review (older than 48 hours). These are time-based **diagnostics**, not authoritative confirmation that a game was played. Source API errors, documented original schedule changes and older unresolved events are made visible. Last publication and last archive timestamps let users identify stale reports.

## 2. Daily and weekly scoring and calibration

A separate read-only artifact `web/public/current/accuracy-research.json`, generated on each Pages release, contains daily and ISO-weekly first-pick winner accuracy, Brier, log loss and count of original favorite upsets. The source is the same unique-game immutable ledger used for the existing Accuracy & Picks report. It does not aggregate 419 repeated snapshots into 419 independent predictions.

If no verified finals exist, the report has **zero games** and `null` accuracy/Brier, not 0% or 100%. Confidence-calibration evidence in the existing `ForwardScorecard` remains based only on genuinely settled first picks. The new daily/weekly controls make it easier to understand which days drove the season average.

## 3. Matched multi-model comparison

The original snapshot can contain Elo, online logistic, opponent-adjusted, fixed state-space, adaptive state-space and the v1.6 independent ensemble. `accuracy_research.derive` compares a candidate *only when the original earliest snapshot stored both it and Elo for the identical verified event*. No candidate receives credit for a game it never predicted.

For each model: paired sample size, independent settled game dates, candidate and Elo Brier/accuracy, paired Brier advantage, and an optional 95% game-date-block bootstrap interval. No interval is reported before 40 paired games spanning six dates. A conservative `reviewEligible` diagnostic requires 100 paired real first picks on at least 12 dates, at least 0.002 Brier gain, and a positive lower bootstrap bound; **no automatic promotion** occurs. A small apparent advantage is not a proven future improvement.

## 4. Prospective scoring/margin accuracy without backfill

The previous v1.5 score estimates appeared in the client-side Game Center but were not necessarily archived as pregame forecasts. To make future score predictions meaningfully testable, new snapshots now contain optional research-only `researchScoreProjection` metadata from `research/forecast/score_shadow.py`. It is computed **at the original capture time from that capture's source ratings**, before the scheduled tipoff, with the existing source as-of guards. The metadata includes expected home/away points, signed margin, combined total, model version/method, and minimum verified possession coverage. The model never changes the active winning-team probability.

The research score calculation uses a symmetric opponent-adjusted per-100-possession offense/defense and real source team pace when both teams have at least five verified source possession games. If that is unavailable, it can fall back to source points-for/points-allowed season averages, with a separate `raw-scoring-means` method label. Implausible or missing scores are withheld.

Once a **first** archived score estimate has an independently verified final, the report computes home/away scoring MAE, absolute signed-margin error, combined-total absolute error and a separate by-method breakdown. Earlier first picks without an archived score estimate are **not backfilled**, even if later snapshots have one. Score errors from this simple live scoring calculation must not be confused with the separate historical Bayesian/Gaussian score-distribution experiment in v1.8. There is no validated prospective interval coverage, source bookmaker spread, or betting promise in this release.

## 5. Game Center usability

The primary site continues to use the simplified five-tab layout introduced in v1.8. The Game Center now offers a compact at-a-glance view of the selected matchup's favorite, original active winner probability and valid available research model agreement/disagreement. Users can jump directly to the full matchup breakdown rather than scrolling through every fixture. The established collapsible model-explanation panel distinguishes the winner probability, score/total scenario and exploratory research models.

The Accuracy & Picks page adds a distinct verified-performance panel without deleting the previous full public ledger, correct/missed game receipts, operational reports or source audit links.

## CI, methodology and reproducibility

```bash
PYTHONPATH=research python -m unittest discover -s research/tests -v
PYTHONPATH=research python -m forecast.accuracy_research --ledger web/public/forecasts --out research/outputs/accuracy-research.json
PYTHONPATH=research python -m forecast.audit --dir web/public/forecasts
cd web
npm install --no-audit --no-fund
npm run check:data
npm run test:score
npm run typecheck
npm run build
npm run test:e2e
```

Tests enforce the verified-first-pick rule, no retroactive score-imputation, missing/implausible possession fallbacks, source time embargoes, duplicate later forecasts, paired challenger eligibility, empty-result truthfulness, daily/weekly correctness and mobile browser rendering. The GitHub Pages deployment includes the current research-only report, generated from immutable files, and refuses publication on CI/provenance errors. Existing historical tournament loading tests remain mandatory.

**Important:** Archive and Pages scheduled actions are best-effort jobs; the site updates after successful capture/verification and publication rather than instantaneously when a game reaches the final buzzer. Pending source resolution can require later scheduled runs.
