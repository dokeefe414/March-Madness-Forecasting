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
