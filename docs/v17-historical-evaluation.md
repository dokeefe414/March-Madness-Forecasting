# v1.7: Historical Training Data, Provenance and Nested Walk-Forward Evaluation

## Scope and separation from active forecasts

This upgrade is entirely separate from the production current-season Elo model, ensemble weights, immutable forecast snapshots and independent final-score settlements. It **does not train, change, rescore or overwrite predictions for the 2026–27 season**. Historical data and evaluation reports are derived from the pinned source repository during CI/Pages publication. No data-provider credentials or network requests are needed.

## Reproducible training dataset

`research/forecast/historical_dataset.py` reads the committed `web/data/history-index.json`, `web/public/seasons/Y.json`, and `web/public/tournaments/Y.json`. It provides an optional deterministic `historical-training-rows.jsonl` training export and two JSON reports:

- `historical-data-manifest.json`: indexed source commit, SHA-256 hash of the exact index bytes and every included complete season and outcome file, game counts, team counts, year availability, pre-tournament cutoff, and exclusion reasons
- `historical-evaluation.json`: chronological, paired Elo/calibrated/nested-selected Brier, log loss and winner accuracy, per-season audit rows and paired year-block uncertainty

The loader requires the **same pinned source commit** in the index, source rating snapshot and tournament file. It rejects duplicate season IDs and team IDs, inconsistent year or game counts, impossible/duplicate tournament results, non-finite Elo/projections, missing or zero regular-season records, source-pin drift, or invalid pre-tournament cutoffs.

It **excludes** source-incomplete seasons, incomplete main draws, and seasons without tournament data; missing tournament participants are counted as omissions rather than assigned fabricated Elo ratings. Teams are deterministically represented by sorted source team IDs, *not* oriented toward the known winner. This avoids giving model features a label-derived identity and makes the binary `sideAWon` label meaningful.

The available source archive contains season-specific rating features **through regular-season day 132**, not complete snapshots as of each game within a regular season. Therefore these rows may be used to model historical *tournament* matchups only; they **must not** be used to simulate pregame performance earlier in that regular season. Possession-rate features are deliberately absent when a date-frozen box-score history cannot be verified. A genuine per-possession historical training dataset will require independent, timestamped game-date box-score data.

## Chronology and selection

For held-out season `Y`:

1. Fit Elo temperature on actual tournament outcomes from **strictly earlier seasons**; the eventual winner label is permitted in training years only
2. Assemble Elo and calibrated Elo probabilities for season `Y` using frozen season-`Y) pre-tournament features and the already-fitted coefficient
3. Choose whether to use Elo or calibrated Elo **using only at least three previous out-of-time evaluated tournament seasons**, requiring a Brier reduction greater than 0.001; otherwise default to Elo
4. Evaluate the selected policy on the untouched season-`Y` actual matchups; never update the model within that test season
5. Aggregate on identical games and resample **entire tournament seasons** for a reproducible descriptive 95% paired Brier-difference interval

This is a nested expanding-window historical validation. It does not establish that the published 2027 active model is better, and it is **not** a live pre-tipoff ledger. Repeatedly tuning features against the historical test results can still bias research claims.

## Tests and artifacts

```bash
PYTHONPATH=research python -m unittest discover -s research/tests -v

PYTHONPATH=research python -m forecast.historical_dataset \
  --web-dir web \
  --manifest research/outputs/historical-data-manifest.json \
  --evaluation research/outputs/historical-evaluation.json \
  --rows research/outputs/historical-training-rows.jsonl
```

CI uploads `audited-historical-model-dataset` with all three reports and runs the real committed archive alongside synthetic fixtures. Failures in source consistency block the release. GitHub Pages regenerates a public, summary-only research report under `/research/historical-*.json`, and Model Lab displays audit coverage, excluded seasons, held-out paired metrics and year-by-year evidence.

The forecast archive workflow `.github/workflows/archive-pregame.yml`, all files in `web/public/forecasts`, active selection `research/forecast/retrain.py` and snapshot writer `research/forecast/snapshot.py` **are not modified**.

## Research next

Future accuracy improvements should first obtain reliably date-stamped historical possessions, offense, defense, pace, turnover/rebound rates, injuries when sourced, and neutral-site identity. Fit increasingly flexible models with *nested chronological validation* on the same games, then compare actual prospective published probabilities before considering promotion.
