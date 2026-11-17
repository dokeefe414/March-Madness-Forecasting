# March Forecast v0.2 — historical data architecture

## Source and lineage

The upstream statistical record is the men's Kaggle March Machine Learning Mania 2026 CSV set, from a public GitHub mirror pinned at commit f8c521735ec41580711ce2d3e27dfd40f24e9e29. The Python downloader verifies exact Git blob IDs before using files.

Data pipeline:

    raw CSV mirror (pinned commit + verified blob SHA)
                   |
             forecast.download
                   |
      research/data/raw/ (gitignored)
                   |
      forecast.history (yearly chronological Elo)
                   |
    +--------------+------------------+
    |              |                  |
    v              v                  v
    historical ratings     tournament results     historical index
    web/public/seasons/    web/public/tournaments/ web/data/history-index.json
    |              |                  |
    +--------------+------------------+
                   |
         Next.js static export
                   |
        GitHub Pages/public site

The committed static season JSON is source-derived and browseable without a paid API.

## Method design

**Regular-season strength:** Start every team with 1500 Elo at each season's beginning. Apply K=24 and 65-point home-court adjustment. Sort each season by Kaggle DayNum and team IDs; same-day matches are not necessarily chronological in tip-off time.

**Projection:** Display current Elo plus a clipped recent five-game slope shrunk to a three-game projection. This is a transparent baseline heuristic, not ARIMA, a Kalman filter, or learned time series.

**Tournament evaluation:** After the season cutoff, freeze each team's projected rating. Apply the neutral-site Elo logistic function to actual tournament matchups. Calculate Brier score against eventual outcomes *without updating on the tournament results*. Seeds and tournament outcomes are observed after the forecast cutoff and never used as model features.

**Historical tournaments:** Kaggle compact results provide scores/teams through 2025. 2026 is a separate 64-team main-draw file containing 63 games, missing play-ins. Its champion is independently confirmed by NCAA reporting, but 2026 is excluded from Brier evaluation because the mirror's regular season ends at DayNum 118, not 132.

## Web behavior

- On initial load, import complete 2025 data as the default season.
- Historical selector fetches /seasons/<year>.json from the static site's public directory.
- Archive tab loads /tournaments/<year>.json on demand. Empty result for 2020 is shown.
- Matchup and eight-team simulation always use the selected historical season's teams; they are NOT 2027 forecasts and the demo bracket is NOT a real NCAA tournament bracket.
- NEXT_PUBLIC_BASE_PATH supports /March-Madness-Forecasting deployment on GitHub Pages.

## Research integrity constraints

- Do not use actual future results or tournament selection information to fit pre-Selection-Sunday model probabilities.
- Distinguish regular-season pregame Brier from held-out tournament Brier.
- Mark historical snapshots and incomplete 2020/2026 regular-season cutoffs. Do not silently imply current/live 2027 rankings.
- Treat model K/home advantage/projection slope as fixed design choices; future work must select them using previous seasons and report out-of-time test performance, not retune on test years.
- Separate published historical outcomes, projected seeds, selection odds and simulated title probabilities.
- Keep raw file checksums, commit pins and transformation code accessible for reproduction.

## Follow-on architecture

Add detailed possession-based efficiency metrics, formal rolling-year cross-validation, calibrators fit on past years only, Kalman/filter-based adaptation to changes and confidence bands. Later introduce actual 2026–27 data feeds with a dated immutable prediction snapshot and model version. Do not schedule scraping or claim live updates without a reliable data provider.

## Chronological tournament benchmark (v0.3)

`forecast.benchmark` reads the committed complete pre-tournament Elo season snapshots and subsequently observed NCAA tournament pairings. Each holdout year uses its own frozen regular-season features. Only **earlier** years' tournament outcomes choose a scalar probability temperature for the trend-Elo model. No selection seeds, tourney outcomes, or later-season results train that held-out year's estimator. The CI-generated JSON artifact records per-year and aggregate scores and missing-team omissions. See [rolling-benchmark.md](rolling-benchmark.md). This is a conditional matchup evaluation, *not* 2027 bracket/selection forecasting.

## Platform v0.5 architecture

The upgrade adds four independently testable systems without replacing frozen historical data:

1. `forecast.advanced` fits an L2-regularized no-intercept logistic matchup model on previous NCAA tournament seasons, using only each team's already completed regular-season Elo, trend and win percentage features. `forecast.benchmark` adds reliability bins and paired whole-season bootstrap intervals to existing rolling-year evaluation.
2. `forecast.live` ingests the separate NCAA-source 2027 results via SportsDataverse, validates scores, dates and contests, computes **independent 2027** Elo ratings and writes a generated snapshot with explicit freshness. Historical Kaggle IDs are *not* joined to NCAA name-based IDs.
3. `web/lib/fullBracket.ts` validates 64/65/68/76-entrant structures and performs deterministic Monte Carlo from sourced historical seed slots, with opening-round and advancement outputs. It does not invent the unselected 2027 field.
4. `LiveSeason.tsx`, `ResearchLab.tsx` and `FullBracketLab.tsx` provide distinct visual experiences accessible through the existing Dashboard shell, preserving historical ranking/matchup/archive functions.

`web/public/current/2027.json` and `web/public/research/benchmark.json` are generated **only during deploy or explicit local rebuild**, not committed. The Pages workflow ensures fresh validated inputs before creating the static export. The CI tests remain independent of network availability.

Expanded 2027 tournament entrants: **76**; Opening Round games: **12**. Details: [bracket engine](bracket-engine.md). Other contracts: [2027 pipeline](current-season.md), [validation](validation.md), [visual system](design-system.md), [operations](operations.md).

## v0.6 scientific and frontend layering

The current-season model is derived from four independent sources: (a) NCAA-source completed games; (b) NCAA team/conference directory; (c) game-level box-score possessions; (d) SportsDataverse season-2027 subdivision membership table joined by explicitly named `Division I` group ID. The last three are optional and publish transparent unavailable states. Crucially, neither an NCAA directory label nor a source-confirmed D-I subdivision guarantees individual postseason eligibility.

`forecast.dynamics` supplies an explicitly heuristic causal EWMA/regime Elo projection; `forecast.boosted` learns regularized residual decision stumps from earlier-year historical tournament results; `forecast.benchmark` trains a chronologically chosen calibrated blend using only older already-held-out predictions. The current game predictor's model selector distinguishes base Elo from **historically calibrated scenarios**, not an already-validated 2027 tournament forecast.

`forecast.snapshot` runs independently of Next.js: current rating snapshot → exact future ESPN events/start timestamps → append-only source-stamped Git records → later NCAA-source final score settlement. A bot commit can update the audit index on main without overwriting prior record files. Frontend `SelectionLab`, `ForecastTracker`, and `TeamTrend` expose source coverage, evidence and interaction separately. The Playwright suite runs desktop/mobile against the real static Next export and uploads failure traces.

Detailed specs: [model zoo](model-zoo-v06.md), [division and conference identity](identity-and-conferences.md), [adjusted efficiency](adjusted-efficiency.md), [field watchlist](selection-watchlist.md), [pregame archive](forecast-audit.md), [browser QA](browser-quality.md).


## v0.8 game-first interface, genuine future scoring and research variants

```text
NCAA-derived scored games → live.py → 2027.json + 2027-games.json
                                 ├→ retrain.py (past-date logistic + prospective gate)
                                 └→ state_space.py (causal Gaussian uncertainty)
ESPN future schedule ───────────────────┬→ gamecenter.py → /current/upcoming.json
2027 ratings + learned model + states ─┘                 ↓
                                              GameCenter.tsx (homepage)

Morning scheduled fixtures → snapshot.py (freeze selected odds, shadow and Elo)
                            → immutable public Git snapshots → later result settlements
                            → performance.py (earliest prediction for each event)
                            → audit.py (recompute source provenance and scores)
                            → /forecasts/index.json → ForwardScorecard + ForecastTracker
```

The HTML/JS site is a **static GitHub Pages build** and does not query a private real-time backend or silently publish new picks when a user clicks. Historical tournament simulations and the provisional 2027 power-watchlist remain distinct from sourced scheduled games and actual archived pretipoff predictions. See [Game Center](game-center.md), [forward scoring](forward-performance.md), and [state-space equations](state-space.md).


## v0.9 source trust, model experiments and direct game audit

```text
Source NCAA scores + ESPN season membership → live.py 2027 current ratings / games
  ├── retrain.py         previous-date logistic; requires true frozen forward evidence
  ├── opponents.py       prior-opponent-Elo adjusted margin surprise, research only
  └── state_space.py     fixed + adaptive Gaussian skill/innovation/drift watch, research only

ESPN scheduled future fixtures + current as-of reports → gamecenter.py
  └── upcoming.json → GameCenter.tsx  ← team link from LiveSeason
                                     ├── recent source game evidence / team trend
                                     ├── common opponent/season strength
                                     └── GameAudit.tsx (immutable snapshot probability history)

GitHub Actions 09:07/16:07 ET → snapshot.py
  → freeze selected & shadow odds at least 15min before scheduled tipoff
  → ESPN independent completed FINAL status + NCAA identical result & Eastern date
  → immutable snapshots/settlements → performance.py first-pick unique-game scores
                                     → audit.py integrity check
                                     → index.json → ForwardScorecard / ModelLab

GitHub Actions 10:17/17:17 ET → Pages rebuild → current/archive-health.json
GitHub Actions 11:35/18:35 ET → monitor-archive.yml stale/absent/no-pick failure
```

The website is not a live scoring daemon. It reads public, versioned, source-backed artifacts. No outside user-specific infrastructure or manually entered previous game is required, but GitHub Actions may be late or the ESPN/NCAA-derived feeds may temporarily disagree. The model lab explicitly separates prospective first-pick Brier from retrospective date-frozen research cohorts.

[Source and integrity methodology](v09-model-validation.md) · [Recovery runbook](v09-forecast-operations.md).


## v1.1 additions

`forecast.challengers` evaluates Bayesian-style shrinkage and online residual-stump experiments against causal same-day Elo on identically dated prior games; outputs `current/challengers.json` during static site builds only. `forecast.drift` consumes the earliest-first-pick settled ledger `uniqueGames` to publish `current/drift.json`. The default Game Center displays a sourced daily desk and the Field Watch page displays a provisional top-eight Road to March strength studio; neither changes archived odds or fabricates a future bracket. The archiver emits a durable zero-pick source-coverage receipt when appropriate. See [the methods and caveats](v11-season-intelligence.md).


## v1.3 operational and research boundary

`forecast.operations` and `forecast.snapshot.detect_schedule_changes` write **derived read-only source receipts**; they never alter immutable original pick timestamps or settled results. `forecast.advanced_models` fits true depth-two Newton CART boosting trees and approximate Gaussian Bradley–Terry posterior states on prior-date observations, outputting retrospective research-only `current/advanced-models.json`. The Model Lab's `ResearchVisualization` displays independently separated retrospective replay curves, actual first-pick rolling Brier and calibration, and sampled source ratings; no data sample is conflated. `BracketDuel` shares the canonical historical play-in/round resolver with `BracketBuilder`, keeps two local competitor states, and counts only identically reachable matchups. See [the implementation, assumptions and tests](v13-research-tournament-operations.md).
