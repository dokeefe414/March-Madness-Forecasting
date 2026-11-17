# v1.8 — Historical Probabilistic Models, Calibration and Simpler Navigation

## Scope and safety

This release implements five research and usability improvements while protecting the live pretipoff experiment. **None** of these files are modified: `.github/workflows/archive-pregame.yml`, `research/forecast/snapshot.py`, `research/forecast/retrain.py`, or immutable contents of `web/public/forecasts/`. The public active Elo prediction is **not** replaced or refitted by these historical experiments.

The archive source is the pinned historical NCAA tournament data under `web/data/history-index.json`, `web/public/seasons/Y.json`, and `web/public/tournaments/Y.json`. Team rating features describe a *pre-tournament day-132 snapshot*; no per-game earlier regular-season box-score history is reconstructed or invented. Evaluation is of actual historical NCAA tournament matchups—not hypothetical bracket paths or genuine originally published prospective predictions.

## 1. Regularized historical point margin and total regression

`research/forecast/historical_probabilistic.py` fits independent four-coefficient ridge models for (a) the **signed** game margin and (b) the combined point total. Input features use a deterministic source team-ID orientation, with ratings and win-percentage differences from the pre-tournament snapshot. The total model uses absolute differences; its intercept is relative to a fixed 140-point scale. The signed margin's target comes from the actual tournament score only in *past* training seasons.

An explicit 18-unit coefficient penalty limits sensitivity to highly correlated Elo and projected Elo features. This is a deliberately interpretable historical baseline, not an automatically selected neural network or a live game-score policy.

For each held-out season Y, fit the coefficients on *all* eligible earlier tournament seasons, then estimate score margin and total for Y without seeing that season's outcome. Training-season residual standard deviations, regularized toward historical 14-point margin and 19-point total priors, provide illustrative Gaussian 80% intervals:

```text
margin forecast   = ridge(prediction features, fitted only on seasons before Y)
total forecast    = 140 + ridge(absolute features, fitted before Y)
P(team A wins)    = normal_cdf(projected margin / (margin sigma × scale))
margin interval   = projected margin ± 1.28155 × training-only margin sigma
total interval    = projected total ± 1.28155 × training-only total sigma
```

Evaluation reports margin MAE/RMSE, total MAE/RMSE, observed margin/total 80% interval coverage and mean interval widths. Nominal coverage and actual coverage are separately displayed; no score interval is claimed for a live game until a supported pregame scoring model has been verified.

## 2. Probability calibration and loss metrics

The historical score model is assessed with Brier, log loss and winner accuracy on the same untouched season-Y games as Elo and prior-year calibrated Elo. The score-to-probability standard-deviation multiplier is chosen from a fixed grid `{0.7,0.85,1,1.15,1.35,1.6}` using **only previously held-out seasons**; the earliest test years default to 1.0. Never tune the multiplier to the held-out season itself.

The Model Lab also reports fixed ten-bin probability reliability curves and ECE (expected calibration error) for Elo, scoring model and nested ensemble. ECE is a descriptive aggregate; small bins and repeated exploratory analysis can mislead. A lower numerical Brier or ECE on one historical sample is not a sufficient model promotion criterion.

## 3. Historical conservative ensemble

A second nested training layer chooses a blend between original Elo and the new historical scoring probability using earlier out-of-time results only:

```text
P_ensemble = (1 - w) P_Elo + w P_score
w in {0, .25, .5, .75, 1}
```

The first three eligible held-out years are excluded from meta-fitting (weight 0), then the weight is chosen to minimize previous out-of-time Brier with a simplicity penalty. Previously tested seasons may inform *later* model choice but never change their own frozen evaluation. This experiment does not replace the separate prospective v1.6 ensemble and is not a pregame-archived model. Year-block bootstrap uncertainty resamples entire tournament years for the Brier difference against Elo.

## 4. Historical training and independent evaluation infrastructure

The v1.7 source-hashed data manifest is required as the foundation. The study's report includes `sourceCommit` and `datasetIndexSha256`, which the Model Lab validates against the published historical manifest before rendering results. No source mismatch or missing model report silently becomes an accuracy claim. Unit tests validate absence of test-year training, previous-year OOS selection, input integrity, finite metrics, calibrated Brier and score uncertainty.

Builds run `forecast.historical_probabilistic` entirely from existing historical source files without accessing the current forecast ledger. CI uploads the complete `historical-probabilistic-evaluation` report; GitHub Pages generates `web/public/research/historical-probabilistic.json` and publishes the Model Lab comparisons. The active forecast pipeline remains unchanged.

## 5. Simpler website navigation while preserving all content

Previously twelve primary tabs competed for space. Navigation now shows five clear daily destinations:

**Find a Game · Teams · Bracket · Accuracy & Picks · Model Lab**

A keyboard-accessible **More** menu groups all seven other pages:
- This Season: 2027 Pulse, Field Watch, Matchups
- History & Research: Historical, Archive, Research, About

The underlying `?view=games|teams|bracket|predictions|models|current|selection|compare|rankings|history|research|method` links continue to work. Existing deep links and browser Back/Forward navigation are preserved; a location breadcrumb displays the current view, and a Back to Games shortcut appears on secondary pages. Mobile navigation no longer displays an extra duplicate quick-tab bar.

The Game Center retains detailed statistics but adds a collapsed, readable guide distinguishing active Elo winner probability, separate source-based score projections, archived experimental ensemble probabilities, and historical accuracy. This keeps valuable information without putting it all in the user's face at once.

## Reproduce

```bash
PYTHONPATH=research python -m unittest discover -s research/tests -v
PYTHONPATH=research python -m forecast.historical_dataset --web-dir web \
    --manifest research/outputs/historical-data-manifest.json \
    --evaluation research/outputs/historical-evaluation.json
PYTHONPATH=research python -m forecast.historical_probabilistic --web-dir web \
    --out research/outputs/historical-probabilistic.json
PYTHONPATH=research python -m forecast.audit --dir web/public/forecasts

cd web
npm install --no-audit --no-fund
npm run check:data
npm run test:score
npm run typecheck
npm run build
npm run test:e2e
```

Research extensions should first acquire source-auditable historical per-game *pregame* efficiency/possession features and score-only calibration data, instead of treating end-of-year ratings as accessible at each regular-season tipoff. The promotion standard remains repeated forward first-pick comparisons against the identical original Elo games with uncertainty estimates.
