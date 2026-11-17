# Rolling held-out-year tournament benchmark

This is an **out-of-time diagnostic of actual March Madness games**, not a
prediction of bracket selection or results in 2027.

## Reproduce the evaluation

Run in the repository root (no downloads, API credentials, or Python packages):

```powershell
$env:PYTHONPATH="research"
py -m forecast.benchmark --web-dir web --out research/outputs/rolling-benchmark.json
```

Or in Bash: `PYTHONPATH=research python -m forecast.benchmark`.

CI executes the same command and uploads `rolling-tournament-benchmark` as a
downloadable GitHub Actions artifact. The artifact contains overall aggregate
Brier/log loss/accuracy, each held-out season's results, the calibration
temperature, training cutoff and omitted-matchup count.

## What is tested?

Each team's **Elo rating** and bounded recent-form **projected Elo** were
computed from that season's regular-season games (through Kaggle day 132),
before any tournament outcomes. Historical *realized tournament pairings*
are then scored without updating the ratings on NCAA tournament results.

Methods:

| Method | Matchup probability | Training on past tournament outcomes |
|---|---|---|
| `coin_flip` | Constant 50% | None |
| `elo` | Plain regular-season Elo (400-point scale) | None |
| `trend_elo` | Trend-adjusted Elo (400-point scale) | None |
| `calibrated_trend_elo` | Trend Elo divided by a temperature | Selects temperature **only** using preceding years |

A temperature changes *confidence*, not winner ordering. We choose the
temperature from a fixed grid using the previous years' tournament log loss.
The default first scored year has five preceding complete tournament seasons.
The current year is **never** used to choose its own temperature; scores for
past years are not backfilled with future information. Hyperparameters of the
underlying Elo engine are not retuned by this procedure.

### Metrics

- **Brier**: mean squared error between predicted win probability and realized
  binary outcome. Smaller is better.
- **Log loss**: mean negative log probability assigned to the realized winner.
  Smaller is better, strongly penalizes overconfidence.
- **Accuracy**: fraction of matchups favoring the winner; a tie counts 0.5.
  The 50% baseline therefore has a 50% accuracy and 0.25 Brier by definition.

Reporting is *game weighted* across all holdout years, and also shown by year.
Realized-winner orientation in code is mathematically equivalent to choosing a
fixed team orientation and scoring both 0 and 1 outcomes for Brier/log loss.

### Exclusion and reproducibility

- Complete years are eligible only when `isComplete=true`, `throughDay=132`,
  and tournament data is nonempty and not flagged main-draw-only.
- Canceled 2020 and truncated regular-season 2026 are excluded, not silently
  given predictions. The historical 2026 main draw is not a 2027 forecast.
- If a tournament opponent is absent from the frozen pre-tournament snapshot,
  that game is omitted and counted. No rating is inferred from their result.
- Input files are the committed, version-pinned `web/public/seasons/*.json`,
  `web/public/tournaments/*.json` and `web/data/history-index.json`.
- `sourceCommit` and game-count mismatches fail fast rather than mixing files.

## Interpretation and limitations

A held-out **season** is not the same as a held-out **tournament bracket**:
the matchups being evaluated are the *matchups that actually happened*.
The research question here is probability quality conditional on those
matchups. It does not evaluate bracket advancement or championship likelihood.

The same-season Elo model is not trained with previous tournaments, but its
fixed design choices are not yet independently optimized or compared with
possessions/efficiency-based systems. Early past years inform later calibration;
seasons are not assumed independent at the individual-game level.

**Next experiments:** reliability diagrams and season-block bootstrap
uncertainty; rolling-year selection of Elo K/home advantage from original
regular-season data (without test-year retuning); an independent possession-
based model and a true 64/68-team bracket evaluator.
