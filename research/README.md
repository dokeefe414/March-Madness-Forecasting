# Historical men's NCAA research engine

This is a dependency-free (Python 3.11+) chronological Elo baseline plus season-by-season tournament evaluation and source archival tooling. It is NOT a fitted ARIMA, Kalman or neural forecaster.

## Real data source and verification

We pin the men's 2026 Kaggle March Machine Learning Mania CSVs as mirrored by Andreachurchwell/march-madness-bracket-simulator at the Git commit f8c521735ec41580711ce2d3e27dfd40f24e9e29. See root README for source and Kaggle links.

The public mirror includes 198,079 regular-season records from 1985 through an **incomplete 2026 season (day 118)**, 2,585 tournament games and 2,626 seed assignments through 2025. It separately has a community 2026 main-draw file: 63 results, not the four First Four play-in games.

Raw CSV files stay in research/data/raw (gitignored); SHA-1 Git blob hashes are checked against the frozen Git tree. To regenerate website data:

    PYTHONPATH=research python -m forecast.download --out-dir research/data/raw
    PYTHONPATH=research python -m forecast.history --data-dir research/data/raw --out-dir web --default-season 2025

Windows PowerShell:

    $env:PYTHONPATH="research"
    py -m forecast.download
    py -m forecast.history

## Research tests

    PYTHONPATH=research python -m unittest discover -s research/tests -v

For historical single-season exports:

    PYTHONPATH=research python -m forecast.cli rank --data-dir research/data/raw --season 2025 --through-day 132 --out research/outputs/2025.json

For regular-season pregame Brier diagnostics:

    PYTHONPATH=research python -m forecast.cli backtest --data-dir research/data/raw --seasons 2022 2023 2024 2025

For a small seeded bracket simulation:

    PYTHONPATH=research python -m forecast.cli simulate --bracket research/bracket.example.json --runs 10000 --seed 42 --out research/outputs/bracket.json

The championship simulation requires entrants supplied in bracket order and supports a power-of-two draw. A real 2027 76-team bracket requires play-in handling before the main 64-team draw.

## Evaluation and leakage controls

- The model resets Elo at 1500 each season (no assumption of unchanged rosters).
- Ratings use the result/location of each regular-season match and never use NCAA tournament outcomes during fitting.
- The tournament Brier score freezes postseason predictions at the end of the included regular season.
- Historical seeds are for metadata and past-bracket visualization, not inputs to probabilities.
- 2020 has no tournament; 2026's partial source does not yield a tournament Brier score.
- Small data imperfections and Kaggle same-day ordering can affect results; some same-day predictions are not guaranteed to be temporally ordered in the real world.
- No held-out-year hyperparameter tuning or uncertainty quantification has been performed yet. Do not treat these scores as calibrated evidence of superiority.

## Chronological tournament benchmark

From the repository root, run `PYTHONPATH=research python -m forecast.benchmark` to score real observed tournament matchups by held-out year. This compares 50%/base Elo/trend Elo with a temperature-calibrated trend Elo whose temperature is fitted **only on earlier years**. Unlike a full bracket simulator, evaluation is conditional on realized historical opponents. See [docs/rolling-benchmark.md](../docs/rolling-benchmark.md).

## v0.5 expanded research engine

- `forecast.advanced`: prior-year-trained, no-intercept L2 logistic classifier with Elo-strength, recent-form and win-percentage differences. It does **not** use 2027 tournament outcomes or claim possession-based offensive/defensive efficiency.
- `forecast.benchmark`: five-method walk-forward tournament evaluations, reliability plots, calibration temperature, logistic weight audit and 2,000-replicate whole-season bootstrap.
- `forecast.live`: NCAA-source independent 2027 Elo from confirmed SportsDataverse schedule final scores, with strict deduplication/date/score validation and a distinct `ncaa-` identity namespace.
- `web/lib/fullBracket.ts`: historical 64/65/68 full fields and verified 76-entry field simulation support, without fabricating new-season seeds.

From the root:

```powershell
$env:PYTHONPATH="research"
py -m unittest discover -s research/tests -v
py -m forecast.benchmark --out web/public/research/benchmark.json
py -m forecast.live --out web/public/current/2027.json
```

See [validation](../docs/validation.md), [current source](../docs/current-season.md), and [bracket algorithm](../docs/bracket-engine.md) for equations, scientific limitations and reproducibility.

## v0.6 research additions and reproducibility

```powershell
$env:PYTHONPATH="research"
py -m unittest discover -s research/tests -v
py -m forecast.benchmark --out research/outputs/rolling-benchmark.json
py -m forecast.live --model-report research/outputs/rolling-benchmark.json --out web/public/current/2027.json
```

Current versioned modules:
- `forecast.boosted`: symmetric, regularized gradient-boosted Elo residual stumps. Fit only using earlier NCAA tournament seasons.
- `forecast.dynamics`: causal EWMA of Elo changes, season regime-delta and recent volatility shrinkage; a transparent bounded heuristic, **not** a fitted Kalman filter.
- `forecast.benchmark`: now **eight** model comparisons including the `blend` using earlier years' *already out-of-time* predictions to choose the ensemble weight. Generated JSON `schemaVersion=3`.
- `forecast.reference`: validated 2027 NCAA team/conference directory; strict normalized name join.
- `forecast.division`: independent SportsDataverse season-2027 basketball subdivision membership. `divisionIConfirmed` true/false/null. Unknown is not ineligible.
- `forecast.efficiency`: source game-ID-matched, per-100 possession offense/defense and opponent-shrunk net estimates.
- `forecast.selection`: source coverage-gated, 32+44 power-only 76-team hypothetical field, bubble and deliberately heuristic wide strength tiers.
- `forecast.snapshot`: source-stamped before-ESPN-start pick ledger and later NCAA final-score settlement, append-only public Git history; does not retroactively generate "live" predictions.

Source files: `research/forecast/`; offline tests: `research/tests/test_{v06_data,division,boosted,dynamics,snapshot}.py`. The Python standard library covers the full modeling stack. Source fetching needs internet only when generating current 2027 data or a real pregame pick.

Additional details: [model math](../docs/model-zoo-v06.md), [D-I season reference](../docs/identity-and-conferences.md), [possession ratings](../docs/adjusted-efficiency.md), [watchlist](../docs/selection-watchlist.md), [pregame audit](../docs/forecast-audit.md).

## v0.7 current-season model fitting

Use `python -m forecast.retrain --games web/public/current/2027-games.json --ratings web/public/current/2027.json --out web/public/current/2027-online-model.json` following a source-fresh `forecast.live --games-out`. The model excludes every current Eastern-date game, fits from earlier day groups, and tests against later days before any game-day updates. It remains in shadow unless paired Elo Brier and game-date bootstrap evidence clears the documented thresholds; eligible real pregame picks keep an immutable model fingerprint. See [online retraining](../docs/online-retraining.md).


## v0.8 current game lookup, research challenger and independent forward grading

`forecast.gamecenter` requests source-verifiable ESPN upcoming fixtures and builds real opponent context using NCAA-derived previous-date scored games. `forecast.state_space` fits a research-only Gaussian latent-strength filter, with assumed observation and process noise and independent same-day-frozen retrospective evaluation. `forecast.performance.summarize_forward` computes the truly independent earliest before-tipoff accuracy percentage, by-model Brier/reliability, cumulative accuracy and recent miss labels; `forecast.audit` checks it against immutable archive evidence.

`forecast.retrain --ledger web/public/forecasts` now adds an actual prospective shadow-vs-Elo gate (>=40 distinct settled first picks and >=0.002 mean paired Brier gain) on top of earlier chronological validation before promoting any learned model. This is a **guard**, not a claim of guaranteed accuracy improvement after every loss.

See [Game Center](../docs/game-center.md), [Forward performance](../docs/forward-performance.md), [State-space model](../docs/state-space.md).


## v0.9 versioned forecasting reliability and chronological research

New modules: `forecast/opponents.py` (team performance adjusted for prior-opponent Elo at the time of each game, with previous-date-only score-margin residual), `forecast/archive_health.py` (source-controlled archive age/presence monitor), and extended `forecast/state_space.py` (bounded adaptive Gaussian process noise after repeated signed standardized innovations). Each research model publishes the same previously sourced outcome cohort's Elo-vs-challenger retrospective Brier and explicitly states that this is **not** an actual archived pretipoff forecast.

`forecast/snapshot.py` now requires independently completed ESPN `STATUS_FINAL` and exact NCAA score/date/ID agreement before new public results are settled; its selected forecast, Elo and research-alternative probabilities are frozen ahead of the scheduled game start. `forecast/performance.py` audits model competitors on genuinely published earliest first-pick games only. A standalone 11:35/18:35 ET GitHub monitor fails visibly if an in-season daily archive is missing, stale or has no confirmed pregame picks. Site refreshes after 09:07/16:07 ET archive ensure today's source results become visible without relying on bot commits to retrigger the Pages build.

Model equations and chronological-trust caveats: [v09-model-validation](../docs/v09-model-validation.md). Test/check and recovery: [v09-forecast-operations](../docs/v09-forecast-operations.md). Public UX includes direct `?view=models` and individual verified game `?view=games&game=<ESPN event id>` links. Missing verified evidence means no accuracy claim and no post-hoc rewriting of missed forecasts.
