# March Forecast v2.0 — Basketball Intelligence & Model Championship

## Release goal

Train stronger models on **actually available, source-verified basketball features**, evaluate on chronologically unseen tournament seasons, expand full-field bracket simulations, and give users a practical browser-only team watchlist. Do not interrupt the current-season first-pick experiment.

**Non-negotiable boundaries:** Historical winner models are research-only and do not change the production Elo probabilities, existing immutable `web/public/forecasts/{snapshots,settlements}`, live online retraining, independent finals, or scheduled capture. Repeatedly observing historical test results can bias model development, even when season-blocked.

## 1. Verified data: two separate datasets, no fabricated statistics

The pinned `web/data/history-index.json`, `web/public/seasons/YYYY.json` and `web/public/tournaments/YYYY.json` archive supplies pre-tournament day-132 Elo ratings, projected trends, win-loss records and real tournament labels. `research/forecast/historical_dataset.py` verifies the common source commit, exact file hashes, complete main draws and recorded game outcomes.

A new optional `research/forecast/historical_box_store.py` ingests externally supplied official NCAA *game-level* box scores. It deliberately **does not claim that pre-tournament summary Elo files contain rebounds or possessions**. Input is a CSV containing season, NCAA game day, NCAA event ID, home/away NCAA team IDs, official NCAA source URI, paired final points, recorded possessions, field goal attempts and makes, 3PT makes, free-throw attempts, turnovers, offensive and defensive rebounds for both teams.

The validator rejects:
- postseason or missing day (`day > 132`), source seasons lacking verified day-132 ratings, mismatched source commit, unknown or identical team IDs
- duplicate season/event keys, missing official source URI, incomplete fields, nonfinite or negative totals, impossible rebounds, shots, turnovers, points or possessions
- eligibility for a team-season with fewer than five genuine recorded games

When trusted source rows exist, the tool computes effective FG%, turnovers/possession, ORB share of available rebounds, FTA/FGA, offensive and defensive efficiency per 100 source possessions, observed pace and mean opponent day-132 Elo. Those opponent Elo values are a **retrospective descriptive opponent-quality proxy**, not a fully chronological strength-of-schedule rating for every game. Data-source URI syntax alone cannot prove source authenticity; a human should check the origin for an externally supplied file.

If there is no official CSV, the published report explicitly states `available=false`, `sourceGames=0`, `teamSeasons=0`, with every missing season itemized. No box-score features or implied accuracy gains are invented.

Run with a real audited NCAA file:

```bash
PYTHONPATH=research python -m forecast.historical_box_store --web-dir web \
  --source /path/to/official-ncaa-event-boxes.csv \
  --out research/outputs/historical-box-coverage.json
```

Without `--source`, it creates only an honest missing-coverage report. No current production model uses this optional file until verified coverage exists and real time-safe experiments are completed.

## 2. Six-model historical championship

`research/forecast/model_championship.py` compares six independent candidates on the same pinned, actual historical NCAA tournament fixtures:

1. Frozen pre-tournament original Elo
2. L2-regularized symmetric logistic regression
3. Deterministic gradient-boosted classification stumps (winner-oriented training pairs and symmetric inference)
4. Prior-year calibrated projected-strength Elo
5. Ridge-scoring-margin Gaussian probability forecast
6. Conservative 20% rating-gap attenuation (Bayesian-style shrinkage heuristic; **not** a fitted hierarchical Bayesian posterior)

Every held-out year Y uses only `season < Y` tournament outcomes for fitting. The current test year contributes no training labels or model hyperparameter tuning. The first five eligible historical seasons are training-only; the first three out-of-time seasons use original Elo. From then onward, the champion for year Y is chosen only from previously evaluated out-of-time seasons, requiring at least 0.001 Brier gain over Elo. The selected model's Y outcomes are never used to decide its own Y selection.

Metrics include Brier score, log loss, winner accuracy, exact paired test-game count, 95% seeded **whole-year block-bootstrap** intervals, and matchup tiers by absolute *pre-tournament Elo* gap (close, competitive, mismatch). Matchup-tiers are descriptive, not separately optimized submodels. Bootstrap intervals account for season clustering only; repeated researcher selection still risks optimistic historical generalization.

The dataset is `day 132` pre-tournament information. **This does not imply a true date-frozen regular-season efficiency training history exists.** Optional box-score features are not fitted into the model tournament until sufficient verified season coverage permits a fair feature-complete future evaluation.

Run:

```bash
PYTHONPATH=research python -m forecast.model_championship \
  --web-dir web --out research/outputs/model-championship.json
```

The CI workflow publishes the paired JSON audit results as artifacts. GitHub Pages regenerates read-only summaries under `web/public/research/model-championship.json` and `historical-box-coverage.json`. The public Model Lab checks both reports against the existing pinned manifest **before** rendering them, and labels them historical research, never real archived 2027 forward accuracy.

## 3. Bracket predictions with uncertainty

The existing `web/lib/fullBracket.ts` already supports full real historical 64/65/68-team fields and **future 76-team fields only when complete official seeded placements are available**. Each simulation models First Four matchups, 63 main bracket games, and an illustrative region crossover.

New outputs:
- `expectedWins`: mean total tournament wins from the simulation, including any First Four win, summed from each team's stage-advancement probabilities.
- `championMonteCarlo95`: Wilson 95% binomial Monte Carlo sampling interval for *the estimated title probability*. This is **not** calibrated model-strength or injury uncertainty.
- `firstRoundUpsetCandidates`: source-seeded Round of 64 lower-seeded team winning under the same pre-tournament Elo win formula. Unresolved play-in slots are omitted rather than inventing winners.

The UI exposes these on the existing Bracket tab, with tooltip-style explanations and simulation-dependent estimates. It does not secretly use actual historical tournament results to assign simulated winners. No hypothetical 2027 official bracket is fabricated.

Invariant checks: 64 entrant main bracket, sum of `champion` probabilities exactly one, sum of `final4` equals four, and expected **total tournament wins = field entrants - 1** (63 main games plus opening games). Repeat simulations with the same seed for reproducibility.

## 4. Private, easy-to-use team favorites

The Game Center's **My Teams** panel lets a visitor follow up to twelve schools for upcoming ESPN-listed matchups, filter the fixture list to those teams, and jump directly to game analysis. It persists in the visitor's browser `localStorage` under `marchforecast-watchlist-v20`.

No account, login, server profile, analytics upload, personalized betting recommendation or user-specific GitHub modification occurs. Deleting browser storage clears the list. The existing five primary site destinations and seven grouped More pages remain intact.

## 5. Verification and publication

```bash
PYTHONPATH=research python -m unittest discover -s research/tests -v
PYTHONPATH=research python -m forecast.historical_box_store --web-dir web --out research/outputs/historical-box-coverage.json
PYTHONPATH=research python -m forecast.model_championship --web-dir web --out research/outputs/model-championship.json
PYTHONPATH=research python -m forecast.audit --dir web/public/forecasts
cd web
npm install --no-audit --no-fund
npm run check:data
npm run test:bracket
npm run test:score
npm run typecheck
npm run build
npm run test:e2e
```

Python regression cases use the **real full history** plus synthetic box examples to establish label embargoes, deterministic scores, source metadata and no hallucinated box values. Node tests enforce tournament probability conservation and upset candidate exclusions. Playwright tests exercise real browser rendering, the model championship report, and favorited team persistence.

### Future research boundary

Fully verified historical NCAA per-game possession/shooting/turnover/rebounding archives are still a separate data acquisition effort. The validator now makes such files consumable and auditable; it **does not pretend they were obtained**. Only after that source coverage is sufficient would we add richer feature ML variants to the historical tournament championship and, much later, consider any live challenger that beats Elo on genuinely archived prospective games.
