# Research engine (v0.1 baseline)

The Python code is dependency-free (standard library, Python 3.11+). It provides a chronological Elo baseline, a deliberately simple bounded recent-trend forecast, pre-game regular-season Brier evaluation, and a generic power-of-two tournament simulator.

## Data source

Download data from Kaggle's March Machine Learning Mania competition and place these files in research/data/raw/ (ignored by Git):

- MTeams.csv
- MRegularSeasonCompactResults.csv

No data is downloaded automatically and no dataset license is implied. Kaggle's Season and DayNum are used to select information available by a historical cutoff. Historical team IDs are not assumed to represent unchanged rosters.

## Commands (from repository root)

Run tests:

    PYTHONPATH=research python -m unittest discover -s research/tests -v

Export a historical snapshot for website display:

    PYTHONPATH=research python -m forecast.cli rank --data-dir research/data/raw --season 2025 --through-day 132 --out web/data/rankings.json

Evaluate pre-game regular-season probabilities:

    PYTHONPATH=research python -m forecast.cli backtest --data-dir research/data/raw --seasons 2022 2023 2024 2025

Run a simulation with a manually supplied bracket JSON:

    PYTHONPATH=research python -m forecast.cli simulate --bracket research/bracket.example.json --runs 10000 --seed 42 --out research/outputs/bracket.json

For Windows PowerShell, set PYTHONPATH via:

    $env:PYTHONPATH="research"; py -m unittest discover -s research/tests -v

A bracket input contains an entrants array with unique teamId and numeric rating, in actual bracket matchup order. This simulator starts at a power-of-two main draw. For a 76-team event, play-in entrants must be resolved before handing the remaining 64 teams to it. Ratings are not seeding or selection predictions.

## Important limits

- The baseline uses win/loss outcomes and location, not offensive efficiency or injuries.
- The projection is a clipped, shrunk slope of recent Elo changes; it is *not* a Kalman filter, ARIMA, or a trained model.
- The Brier number measures chronological **regular-season** game predictions, not the accuracy of March Madness brackets. Tournament validation, calibration studies, yearly holdouts, selection forecasts, and distribution-shift detection remain future work.
- Team rankings can change if new games or cutoff dates change. Do not present sample/demo data as real NCAA predictions.
