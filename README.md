# March Forecast — March Madness forecasting and analytics

A public basketball analytics website backed by a transparent Python forecasting research foundation. The goal is to estimate how teams change through the season, compare any two programs, and use calibrated win probabilities to simulate the NCAA tournament.

> **Status: initial research preview (v0.1).** The website currently uses **explicitly labeled fictional teams and synthetic ratings**, not real NCAA rankings or real 2027 March Madness predictions. The Python baseline works with historical CSV inputs but has not yet been validated on held-out tournaments.

## What works now

| Area | Status | Implementation |
| --- | --- | --- |
| Power rankings | Preview | Search and sort, team selection, win/loss records, projected rating and trajectory |
| Matchup comparison | Preview | Neutral-court probabilities and side-by-side metrics |
| Bracket Lab | Preview | An eight-team demonstration bracket and 2,000 Monte Carlo simulations |
| Python Elo model | Implemented | Chronological result/location updates, historical season filtering and bounded trend projection |
| Python simulation | Implemented | Deterministic seeded power-of-two bracket simulation |
| Data preparation | Implemented | Kaggle MTeams and regular-season compact results to JSON |
| Research tests | Implemented | Basic leakage safeguards, Brier sanity checks, CSV and probability tests |
| Tournament backtesting | Planned | Historical field and seeds, held-out tournament probabilities and calibration |
| Live 2026–27 feed | Planned | Dated, reproducible real data snapshots |
| 2027 field projection | Planned | Selection and bracket-format model (including play-ins) |

## Launch the website locally

Requirements: Node.js 20.9+ and npm.

    cd web
    npm install
    npm run check:data
    npm run dev

Open http://localhost:3000. To check the production build:

    npm run typecheck
    npm run build

This is a Next.js static-export website, so no account, paid database or API key is needed for the first version.

## Run the research engine

Requirements: Python 3.11+ (standard library only).

Windows PowerShell (from repository root):

    $env:PYTHONPATH="research"
    py -m unittest discover -s research/tests -v

macOS/Linux:

    PYTHONPATH=research python -m unittest discover -s research/tests -v

To generate a real **historical** snapshot, manually download the Kaggle March Machine Learning Mania men's datasets MTeams.csv and MRegularSeasonCompactResults.csv into research/data/raw/ (ignored by Git). Then, with PYTHONPATH set, run:

    py -m forecast.cli rank --data-dir research/data/raw --season 2025 --through-day 132 --out web/data/rankings.json

This command replaces demo data with a historical 2025 snapshot. It does **not** forecast March 2027. Additional CLI examples and evaluation caveats are in research/README.md.

## Repository structure

    web/
      app/                  Next.js App Router, styling and metadata
      components/           Rankings, comparison and simulator UI
      lib/                  Typed data model and demo simulation
      data/rankings.json    Clearly tagged demo or historical dataset
      scripts/              Data validation
    research/
      forecast/             Elo, CSV loader and CLI
      tests/                Python unittest coverage
      bracket.example.json  Example ordered bracket input
    docs/
      architecture.md       Design decisions, leakage policy and roadmap
      data-contract.md      Snapshot schema
    .github/workflows/
      ci.yml                Research tests, web typecheck and build
      deploy-pages.yml      Static GitHub Pages workflow

## Publish on GitHub Pages

1. Merge the feature pull request into main after CI checks pass.
2. In the repository's **Settings > Pages** set **Build and deployment > Source** to **GitHub Actions**.
3. Confirm the Deploy website to GitHub Pages workflow succeeds after the merge.

Expected website URL once deployed: https://dokeefe414.github.io/March-Madness-Forecasting/

**Public repository does not equal deployed website.** Until the workflow runs successfully, that URL may not load. The workflow exports a static build to the repository-specific base path.

## Scientific commitments

- Separate team selection, matchups, projected bracket seeds and title odds; each is a different prediction target.
- Avoid target leakage through chronological features and pregame-only evaluation.
- Beat straightforward baselines before introducing advanced adaptive models.
- Prioritize held-out tournament games, probability calibration, log loss/Brier score, and confidence intervals.
- Keep the public model label, underlying dataset cutoff, tournament assumptions and forecast timestamp visible.
- Never market simulated bracket outputs as guaranteed outcomes.

## Next milestones

First import authentic historical data and implement out-of-season tournament backtesting; then evaluate Elo against time-series models such as ARIMA, Kalman and adaptive Kalman filtering. After validation, add weekly real-season snapshots, projected 2027 selections and the expanded tournament format.

See docs/architecture.md for the longer-term research plan.
