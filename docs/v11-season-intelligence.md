# v1.1 — Season intelligence, verified archive operation and causal model research

## Purpose

This release turns March Forecast into an easier daily destination while keeping **scientific provenance and chronological safety** ahead of feature count. The intended sequence is archive reliability → sourced game discovery → causal challengers → prospective drift → carefully labeled tournament outlook.

It does **not** claim that a model has learned to predict the 2027 NCAA field, that any new challenger has beaten Elo prospectively, or that a 2027 tournament bracket is official.

## 1. Reliable forecast ledger

### Inputs and proofs
The archive workflow runs 09:07 and 16:07 Eastern during basketball months, can be dispatched manually, and also runs once when its workflow definition is changed on `main`. This last trigger creates a concrete opportunity to test an actual archive run after deployment. Every run independently downloads current results and the ESPN schedule and uses the same identity, future-tipoff buffer, before-date embargo, and source-verification policy as v0.9. An archive run cannot assert forecasts after tipoff; no unresolved or contradictory team IDs are guessed.

The `web/public/forecasts/index.json` derived manifest is always written after a successful source check—even if **zero** future games were eligible. `archiveHealth.fixtureCoverage` and `verifiedFixtureRun` are audit fields, not invented picks. The append-only `snapshots/` and `settlements/` remain source-controlled, with later finals independently verified against both ESPN completed-event status and NCAA-derived score/date/identity. Existing predictions are never overwritten.

The archive workflow uses up to three non-forced Git push attempts with a fetch/rebase if concurrent changes raced the commit. A conflict exits with failure, preserving the previous public ledger rather than forcing an unsafe rewrite.

### Monitoring semantics
`forecast.archive_health` now distinguishes:
- `awaiting-first-archive`: no derived ledger manifest, never healthy.
- `stale`: elapsed time above 26 hours in season.
- `source-partial`: a run exists but at least one source-day failed.
- `no-picks-yet`: run exists without evidence supporting an unambiguous empty day.
- `no-eligible-fixtures`: verified complete zero-pick run with no unmatched or same-date-unsafe candidate.
- `current`: recent archive evidence with at least one original pregame forecast.
- `off-season`: outside configured season period.

The health workflow fails for missing/stale/no-picks when appropriate; a genuine clean no-fixture day is not an automatic failure. On monitor failure, the existing issue workflow writes a **de-duplicated GitHub recovery issue**. The Pages refresh publishes a separate public source-status artifact; GitHub Actions schedules remain best effort, not a streaming system. The deployment can pass even if the archive needs attention.

**Recovery checks:** inspect the archive workflow run and `web/public/forecasts/index.json` on the main branch, check ESPN and NCAA source availability, confirm `contents: write` permissions and the `[skip ci]` GitHub Action commit behavior, and verify that any settled game had an original timestamped pretipoff prediction. Never backfill earlier outcomes as if forecasts were made before games.

## 2. Daily accessible Game Center

The front page now contains a daily desk showing the number of published source-backed fixtures still in the future, source-matched estimates, uniquely settled first picks, and archive status. Three clickable spotlight cards prioritize a verified future game today, the strongest favorite, and the closest projected matchup. All cards link into the existing full Game Center reports. Fixture records that have passed listed tipoff are omitted from the future highlights.

Four fast paths lead to today's games, Accuracy & Picks, Model Lab, and Road to March. A keyboard **Skip to Content** link bypasses the large site navigation. Narrow mobile layouts stack cards without horizontal page overflow. The generated ESPN schedule is a static timestamped snapshot; users are informed when its age exceeds 36 hours. Missing feeds are not represented as zero games with perfect accuracy.

## 3. New independently evaluated forecasting challengers

`research/forecast/challengers.py` consumes the **same current-season scored games and retrieval timestamp** as the Elo ratings.

**Bayesian-style shrinkage:** a research prior shrinks each team's Elo estimate toward 1500 by `n/(n+8)` and attenuates matchup logits when either team has limited prior games. Prior strength and uncertainty constants are assumptions and have not been historically optimized or prospectively calibrated. The label deliberately says *Bayesian shrinkage research*, not a statistically rigorous posterior from a fully specified generative Bayesian basketball model.

**Online gradient residual stumps:** three fixed binary rule leaves (large Elo gap, relative prior win percentage, prior games imbalance) accumulate regularized residual gradients. On a game's day, all predictions are frozen, then leaf updates and Elo updates occur **after** that day's entire prediction batch. This is an interpretable gradient correction ensemble, not a full gradient-boosted decision tree package or a demonstrated accuracy improvement.

The published `current/challengers.json` reports paired same-day Elo, shrinkage and residual-stump Brier, log loss and winner accuracy; its `mode` remains `research-only`. All three are evaluated on identical accepted prior-date games and **never** auto-replace the public forecaster. The historical boosted Elo benchmark remains separately documented and uses a different dataset/evaluation cohort. The existing Kalman and opponent-aware challengers are preserved.

## 4. Prospective error shift review

`forecast.drift` uses only **real earliest archived picks** and independently settled actual games from `uniqueGames.trajectory`. It compares two nonoverlapping groups of 25 games on Brier loss. Before 50 games, the status is `collecting`, not a manufactured zero. A predeclared Brier rise of 0.05 is flagged `review`, not considered conclusive statistical evidence of shift and not a model-promotion trigger.

The Model Lab displays the previous/current 25-game scores, their signed change, and source status. Results may differ sharply due to sampling noise, strength-of-schedule changes, and concentrated upsets. Formal evaluation of change detection should use out-of-time seasons, false-positive rates, and uncertainty intervals before any claim of robustness.

## 5. Road to March — clearly provisional

For a verified 76-team power-only field watchlist, the Field Watch page now shows the top eight rating leaders, their actual records/sample sizes, and a closest-rated top-eight peer comparison using the **same neutral-site Elo matchup formula** used elsewhere. A comparison is explicitly hypothetical; it is **not** a forecast of selection, matchup, bracket seed, NCAA eligibility, or championship probability.

The application intentionally withholds the panel when the complete source-verified field-watch coverage gate fails. The older historical 64/65/68-team bracket engine and 76-team slot validator remain unchanged. No nonexistent future tournament entries are filled in.

## Testing and local operation

From repository root:

```bash
PYTHONPATH=research python -m unittest discover -s research/tests -v
PYTHONPATH=research python -m forecast.challengers --games web/public/current/2027-games.json --ratings web/public/current/2027.json --out web/public/current/challengers.json
PYTHONPATH=research python -m forecast.drift --ledger web/public/forecasts/index.json --out web/public/current/drift.json
cd web
npm install --no-audit --no-fund
npm run check:data
npm run test:bracket
npm run typecheck
npm run build
npm run test:e2e
```

The full source feeds are retrieved during Pages deployment; current-season generated files are not permanently committed. The drift module handles a missing ledger gracefully. Unit tests cover source-count consistency, present-date embargo, missing-versus-verified-empty archive status, and nonoverlapping error deterioration. Playwright exercises accessible cross-page navigation, real game lookup and the new research-only labels.

## Release acceptance and limitations

A passed CI workflow verifies code, build and hermetic browser behavior. An actual successful archive run on `main`, committed source-verifiable index, and independent eventual final settlement are **additional operational checks**. If GitHub scheduled workflows have not run or no eligible future fixtures are found, disclose that explicitly rather than saying the full production prediction service is proven.

Primary references: [operations](v09-forecast-operations.md), [audit](forecast-audit.md), [forward scoring](forward-performance.md), [state-space methods](state-space.md), [v1.0 release](v10-prediction-intelligence.md).
