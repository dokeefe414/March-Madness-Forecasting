# v2.0 — Basketball Intelligence, Model Championship, Bracket Uncertainty & Watchlist

## Executive scope and production safety

v2.0 introduces an independent, season-blocked multi-model tournament benchmark; a structured, guarded ingestion path for historical NCAA game-box possessions and Four Factors; more informative historical bracket simulations; and a private favorite-team watchlist.

**Production is explicitly separated:** No change to `research/forecast/snapshot.py`, `research/forecast/retrain.py`, `.github/workflows/archive-pregame.yml`, or any immutable files in `web/public/forecasts/**`. The 2026–27 Elo winner prediction and v1.6 frozen ensemble policy are unchanged. Neither v2.0 history nor the browser watchlist may write to original forecast history. Any tournament simulation is a research scenario, not the official 2027 field.

## 1. The actual historical data, and the Four Factors coverage gap

The already pinned, reproducible historical archive contains 1985–2025 *pre-tournament* day-132 team Elo, projected Elo, regular-season win-loss summaries and matched real tournament results. This is useful for testing models on future-of-training **tournament years**, but it does NOT contain a consistently complete game-by-game historical NCAA box-score table. You cannot derive eFG%, possessions, rebound percentage or turnovers from Elo values. Claims of a full historical possessions dataset without independent box rows would be dishonest.

The new `forecast.historical_box_store` is a fail-closed **optional** data ingestion and auditing pipeline. If no source is supplied, it publishes `available=false`, `sourceGames=0`, `teamSeasons=0`, and explicit missing seasons. It does not fill missing features or award fictitious score improvements to any model.

If an independently checked NCAA official event CSV is supplied, the loader validates source identity, team keys against the pinned season archive, pre-tournament day `<=132`, unique event IDs, finite two-sided game-box statistics, points and shooting arithmetic, plausible possessions, rebounds and turnovers, and SHA-256 of the exact file. It requires at least five source games per team and calculates the following empirical descriptors:

| Feature | Verified box arithmetic |
|---|---|
| Offensive efficiency per 100 | 100 × total points / sum of team possessions |
| Defensive efficiency per 100 | 100 × sum opponent points / sum opponent possessions |
| eFG% | (FGM + 0.5 × 3PM) / FGA |
| Turnover rate | team turnovers / team possessions |
| Offensive rebound share | team ORB / (team ORB + opposing DRB) |
| Free-throw rate | team FTA / FGA |
| Pace | mean team recorded possessions across accepted source games |
| Opponent-quality proxy | mean **day-132 source Elo** of opponents, clearly labeled retrospective SOS proxy |

CSV required columns (one row per independently source-checkable NCAA contest):

```text
season,day,eventId,homeTeamId,awayTeamId,sourceUri,
homePoints,awayPoints,homePossessions,awayPossessions,
homeFga,awayFga,homeFgm,awayFgm,homeFg3m,awayFg3m,
homeFta,awayFta,homeTov,awayTov,homeOrb,awayOrb,homeDrb,awayDrb
```

Names like `homeTeamId` and `awayTeamId` must match the pinned NCAA source IDs, not fuzzy school names. `sourceUri` must be an official NCAA stats or NCAA.com HTTPS page. The URL and CSV fields are **claimed provenance supplied by the dataset maintainer**, not proof that an independently authenticated NCAA API was retrieved during this build. Original source verification and event-level retention are prerequisites to using these values in an actual predictive model. A malicious or inaccurate CSV could still falsify claims despite schema validation. No such 40-season complete file is included in this release.

Use:

```bash
PYTHONPATH=research python -m forecast.historical_box_store \
  --web-dir web --source research/data/historical-box/official-event-boxes.csv \
  --out research/outputs/historical-box-coverage.json
```

No file? Run without `--source` and the report openly indicates unavailable records. **The new historical model championship does not secretly use or substitute missing Four Factors.** Those source features are staged for later verified integration once meaningful, independently checked coverage exists.

## 2. Actual trainable ML challengers and the championship

`research/forecast/model_championship.py` now trains/evaluates six methods against the **same actual historical tournament matchups**:

1. Pre-tournament source Elo (unchanged reference)
2. Three-feature regularized logistic regression (Elo gap, projected-vs-current form and win-percentage difference)
3. Twelve-round Newton-gradient-boosted *decision stumps* with antisymmetric opponent orientation, bounded leaf predictions and ridge penalty
4. Earlier-tournament calibrated trend Elo temperature
5. Prior-season regularized Gaussian score-margin distribution converted to winner probability
6. Fixed 80% prior-based Elo shrinkage sensitivity control (NOT a claim of Bayesian posterior inference)

The latter is deliberately simple; statistical complexity is not assumed to be more accurate. The others are actually fitted on past tournament labels, rather than hand-written guesses. **No tournament result, seeding or opponent outcome from the evaluated year enters a model's features.** Team ID ordering, rather than knowledge of the winner, fixes the feature orientation; training years may of course use their true labels.

For each evaluated year Y:

- Train all model coefficients on actual tournaments from seasons strictly **before** Y (minimum five complete seasons).
- Freeze six candidate probabilities for every observed tournament matchup in Y.
- Choose the "nested champion" **only** from models whose Brier has beaten Elo by at least **0.001** on the same previous *out-of-time* tournament games over at least **three earlier test seasons**. Before this gate, select Elo.
- Evaluate the *preselected* model on the entire untouched year Y; never change it after that year's outcomes.
- Compute paired winner accuracy, log loss, and Brier for every contender on the identical games, year-by-year selection, close/balanced/mismatch Elo-gap strata, and 95% descriptive uncertainty resampling **whole seasons**.

The championship results must never be interchanged with genuinely independently archived first-pick results. Repeated research across the same 40 historical seasons can still bias comparisons even with nested forward splits. No model is automatically promoted. An observed Brier improvement without a positive uncertainty bound is inconclusive.

Run:

```bash
PYTHONPATH=research python -m forecast.model_championship \
  --web-dir web --out research/outputs/model-championship.json
```

The GitHub Pages build generates `/research/model-championship.json` and `/research/historical-box-coverage.json`, paired to the pinned historical source commit/index hash. The Model Lab checks these source pins before displaying scores; it does not use the latest 2027 outcome to retune old probabilities. CI separately uploads the research artifacts.

## 3. More honest, more useful complete-bracket simulation

The existing `simulateFullBracket` still generates seeded 64-, 65-, 68- and 76-entrant fields using deterministic pseudorandom runs and a symmetric Elo-style matchup probability. The new `BracketResult` adds:

- **Expected tournament wins per team**: sum of win/advance probabilities across the 63 main-draw games, plus the first opening-round contest where applicable. Field-wide expected wins must sum to exactly 63 + the verified number of opening games (allowing numerical rounding tolerance).
- **Wilson 95% champion Monte Carlo sampling interval**: uncertainty from running a *finite number of simulations*. It does NOT reflect model structural uncertainty, roster/injury uncertainty, nor demonstrate 95% empirical coverage.
- **Source-field seed-line upset scenarios**: seed-identified lower-seeded teams with Elo-model upset probabilities for *fully resolved* Round-of-64 matchups. Any game involving an undecided First Four entrant is explicitly withheld instead of assuming the winner.

The user can choose 1,000/5,000/20,000 reproducible simulations; the UI exposes expected wins and champion sampling band for each contender and an expandable upset watch. Historical seeds and entrants are real. The generic W–X/Y–Z semifinal pairing is a documented scenario; official historical semifinal pairings can differ. The site does not invent a real 2027 NCAA bracket.

## 4. Private watchlist and fast everyday experience

The Game Center now contains a **My Teams** panel where you can follow up to 12 NCAA-source teams, see their next source-listed matchups, filter the fixture browser to only those teams, and star/unstar either program from its detailed matchup. Controls are accessible with a labeled team selector, clear pressed state, and a remove-team affordance. The watchlist is saved **only** to browser `localStorage` key `marchforecast-watchlist-v20`, so it needs no account or back-end mutation and does not transmit favorites to GitHub or analytics. Browser storage can be reset/cleared and does not sync across devices.

A team absent from a bounded upcoming ESPN schedule is not declared to have no further games; the UI says the current source snapshot has no qualifying future fixture. Existing five top-level tabs and every `?view=` route remain unchanged.

## 5. Tests and release checks

```bash
PYTHONPATH=research python -m unittest discover -s research/tests -v
PYTHONPATH=research python -m forecast.historical_box_store --web-dir web --out research/outputs/historical-box-coverage.json
PYTHONPATH=research python -m forecast.model_championship --web-dir web --out research/outputs/model-championship.json
PYTHONPATH=research python -m forecast.audit --dir web/public/forecasts

cd web
npm ci
npm run test:bracket
npm run test:score
npm run typecheck
npm run build
npm run test:e2e
```

New tests cover actual 40-season model evaluation, identical games, strict future-season leakage prevention, deterministic winner-independent feature orientation, Four Factors arithmetic and invalid sources, 64/65/68/76 field-wide expected-wins invariants, probabilistic title intervals, unknown First Four outcomes, watchlist persistence and clearing, and source-linked Model Lab evidence. Existing historical source-loading and mobile/browser tests remain required for merge.

## Subsequent accuracy research

The next **data** milestone is obtaining complete, independently verifiable timestamped historical game-box events from NCAA sources for multiple seasons. Then design an *actual prior-game-date* possession-based training dataset (not end-of-year aggregates reused as if available earlier), redo expanding-window held-out evaluations, and archive any new score-distribution candidate *before* actual upcoming games. Only consider a live promotion after paired pretipoff source-verified results beat Elo with robust uncertainty evidence.
