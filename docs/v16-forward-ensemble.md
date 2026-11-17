# v1.6 — Forward-first conservative ensemble and scientific model review

## Objective

Improve the probability forecasting system by testing whether combining the existing *independently sourced, previously fitted* challengers with Elo is better on genuine future games. **No claim of greater accuracy is made until independent frozen predictions support it.** The existing public Elo model, first-pick ledger, historical seasons, score predictor, and score model are preserved.

## Frozen portfolio construction

At each scheduled pregame archive, `forecast.forward_ensemble` reads immutable source evidence and fits a portfolio coefficient only using previously independently settled *earliest* archived snapshots. It is not fitted on newly proposed games. The input signals already stored by the existing forecasting engine include:
- Online logistic correction to Elo
- Gaussian state-space strength
- Opponent-aware strength
- Adaptive Gaussian state-space

A portfolio is emitted only when **two or more distinct pregame signals** exist, so missing models never become guessed numerical values. It uses the arithmetic mean of available *previously fitted* research probabilities, then mixes that mean with the source Elo baseline:

```text
research_mean = mean(valid available original research probabilities)
ensemble P(home win) = (1 - w) × original Elo P(home) + w × research_mean
```

Weights are restricted to `{0, .1, .2, .3, .4}`. A conservative `w=.25` is the predetermined exploratory fallback before there is enough evidence. A candidate's probability is bounded by the original source probabilities; it is not a manufactured outcome.

The original archive stores `ensembleHomeWinProbability`, `ensembleResearchWeight`, and `ensembleComponentCount` in the **same immutable pregame snapshot** as the active probability and other candidates. The source matched Game Center may also display it as an explicitly experimental probability. No retrospective recalculation changes those snapshot fields.

**As-of guard:** each candidate must be a valid (0,1) finite probability, the current ratings retrieval timestamp must match the ensemble source, and the model's last trained date must precede the scheduled fixture's Eastern date. Original historical evidence is included only if its ratings retrieval is not newer than capture, capture is at least 15 minutes before the ESPN-listed start, the original earliest pick matches an independently verified ESPN/NCAA settlement, and the game result date is earlier than the current Eastern date. Changed dates and unknown finals are not silently incorporated.

## Strictly chronological weight selection

The preceding verified source dates are sorted and split by entire **game dates**, not randomly shuffled individual matches. The earliest 70% of observed dates serve as fitting data; the most recent 30% form a later test block.

- At least **80 training first picks** are required to choose a weight by Brier minimization; ties prefer Elo.
- At least **40 later holdout first picks**, **six distinct game dates**, a minimum Brier improvement of **0.002**, and a positive lower bound of a fixed-seed **95% date-block bootstrap** interval are required before the retrospective recombination gate can pass.
- The holdout is later than training by date and must have identical Elo and research components for every compared game.
- The holdout and weight fitting here use *retrospective recombination of individually frozen component forecasts*. This is not proof that the resulting ensemble combination itself was published before the older games; the UI labels it explicitly.

### Genuine prospective gate

In addition to the earlier historical recombination gate, **scientific-review eligibility** also requires:

- At least **100 original pregame-frozen ensemble probabilities**
- Independently verified outcomes from **12 distinct dates**
- At least **0.002** Brier improvement over *the frozen Elo probability from those identical events*
- Positive lower endpoint in a game-date-block 95% bootstrap interval

The later scientific-review gate is evaluated on **the actual original archived portfolio probability**. It never scores a reconstructed, newly selected combination in place of the original frozen candidate. This is a prospective measure, not just a historical tuning exercise.

**No automatic promotion:** `promoteAutomatically=false` regardless of observed apparent gains. Future model replacement would additionally require verifying independence from repeated tune/test cycles, sufficient calendar/season breadth, trustworthy data feeds, and accuracy/calibration robustness. This policy intentionally keeps the operational Elo probability unchanged.

## Existing online-logistic challenger: safer global model selection

The older in-season online logistic challenger previously required 40 verified first-picked pairs and a Brier margin of 0.002 for its forward gate. v1.6 increases this to **100 paired independently settled first picks on at least 12 different source dates**, a 0.002 gain, and a positive **95% game-date-block bootstrap lower bound**. These samples are matched with the *original frozen Elo probability* on the very same event. Its earlier separate walk-forward gate continues to apply.

More importantly, the nightly retraining workflow no longer automatically changes the active public policy even if both gates pass. It reports `eligibleForManualReview`, and the model remains a `shadow` until separately examined and approved via an explicit code/release change. This prevents a repeated evaluation campaign from silently deploying a retrospectively selected model.

## Publication and public UI

- `.github/workflows/archive-pregame.yml` generates an as-of portfolio policy **before** creating new frozen future picks.
- `.github/workflows/deploy-pages.yml` builds `web/public/current/forward-ensemble.json` to report the latest verifiable experiment without mutating original source data.
- `Model Lab → Does the ensemble win?` shows *two distinct sections*: true prospective originally frozen portfolio results and retrospective recombination of frozen component predictions.
- No imagined scoreboard win rate appears when there are no independently verified settlements.

## Reproduce and validate

```bash
PYTHONPATH=research python -m unittest discover -s research/tests -v
PYTHONPATH=research python -m forecast.forward_ensemble \
  --ratings web/public/current/2027.json \
  --ledger web/public/forecasts \
  --out web/public/current/forward-ensemble.json
PYTHONPATH=research python -m forecast.audit --dir web/public/forecasts
cd web
npm install --no-audit --no-fund
npm run test:score
npm run typecheck
npm run build
npm run test:e2e
```

The current source ratings file is dynamically generated during the website deployment; do not invent it if it is absent in a local repository checkout.

Tests use purely synthetic future-of-training probabilities and verified final receipts. They check source alignment, posted-time cutoffs, duplicate earliest entries, absent source evidence, correct date blocks and honest promotion withholding. They do **not** claim a production forecasting improvement from synthetic test outcomes.

## Future evidence

Once enough original portfolio outcomes have been frozen and independently settled, compare Brier, log loss, calibration, domain shift and tournament games with Elo on the same fixtures. Do not use random game-level cross-validation, favor a model because its historical fit has many parameters, or present illustrative score/spread estimates as independently validated odds.

See also [v1.5 scoring model](v15-causal-scoring-model.md), [v1.3 operations](v13-research-tournament-operations.md), and [verified first-pick scoring](pick-results-and-score-projection.md).
