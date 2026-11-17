# March Forecast — historical NCAA basketball analytics

A public, research-driven college basketball ranking and March Madness forecasting platform. This repository includes a responsive Next.js website, reproducible men's NCAA historical data, and a standard-library Python Elo baseline for testing matchup and tournament probabilities.

**Historical dataset is real, not a demo.** The website contains 42 men's seasons (1985–2026): **198,079** regular-season games, **2,585** NCAA tournament games through 2025, and **63** independently sourced main-draw game results from 2026 (the 2026 First Four is not included). Rankings are *retrospective baseline model estimates* and NOT actual committee seeds or forecasts for the 2027 field.

## Website features

- **Historical season browser:** select any year from 1985 to 2026; default is the latest complete Selection Sunday year in this source, **2025**.
- **Power rankings:** filter, sort, compare actual team records and projected Elo-style ratings based on that year's games.
- **Matchup Lab:** neutral-court win probabilities for two selected teams under the simple Elo rating assumption.
- **Tournament archive:** actual historical game results, known champions, seeds, and tournament Brier scores where a complete pre-Selection-Sunday regular-season snapshot exists.
- **Bracket Lab:** run 2,000 Monte Carlo simulations on an *illustrative eight-team bracket built from the displayed year's highest-rated programs*. It is NOT the official NCAA bracket.
- **Source transparency:** historical provenance, season cutoff, and whether the source is incomplete are displayed prominently.

### Important data coverage details

| Data | Available coverage | What it means |
| --- | --- | --- |
| Men's regular season | 1985–2026 | 198,079 records; 2026 mirror stops at Kaggle day 118, **not Selection Sunday** |
| Official Kaggle-format men's NCAA tournament results | 1985–2025 | 2,585 recorded games; no NCAA tournament in 2020 |
| Tournament seed records | 1985–2025 | Dataset's region/seed records; known after bracket selection, **not used as a forecasting input** |
| 2026 tournament main draw | 2026 | 63 game results and 64 seed positions from an independently compiled community archive; **missing four First Four games** |
| 2026 champion | 2026 | Michigan; separately verified using [NCAA reporting](https://www.ncaa.com/news/basketball-men/article/2026-04-06/michigan-beats-uconn-wins-2026-mens-basketball-national-championship) |
| 2027 live data/predictions | Not available | The site does not currently ingest 2026–27 scores or forecast 2027 tournament selection |

Historical season rankings are derived from results available at each model's cutoff; 2026 should be treated as partial, not complete. Training/evaluation of 2026's tournament is intentionally **not** reported because the source regular season ends early.

## Run locally (Windows)

Requirements: Python 3.11+, Node.js 20.9+, npm.

From a PowerShell terminal in the repository root:

    $env:PYTHONPATH="research"
    py -m unittest discover -s research/tests -v
    cd web
    npm install
    npm run check:data
    npm run typecheck
    npm run dev

Open http://localhost:3000. To build the deployable static website: npm run build.

The repository **already contains the derived JSON season/tournament archives**. You can explore all historical years offline once the frontend dependencies are installed; downloading raw Kaggle data is not necessary to start the site.

## Regenerate every historical season

The project never commits unmodified raw CSV files. It pins a community mirror of the Kaggle March Machine Learning Mania 2026 men's data at Git commit:

    f8c521735ec41580711ce2d3e27dfd40f24e9e29

Source: [Andreachurchwell/march-madness-bracket-simulator](https://github.com/Andreachurchwell/march-madness-bracket-simulator/tree/f8c521735ec41580711ce2d3e27dfd40f24e9e29/data/raw)

Original dataset documentation: [Kaggle March Machine Learning Mania 2026](https://www.kaggle.com/competitions/march-machine-learning-mania-2026).

Run these from the root:

    $env:PYTHONPATH="research"
    py -m forecast.download --out-dir research/data/raw
    py -m forecast.history --data-dir research/data/raw --out-dir web --default-season 2025
    cd web
    npm run check:data

The downloader checks the **Git blob SHA-1** of each of the six pinned source files before writing any raw data, and fails if source contents change. Generated files include:

    web/data/rankings.json            # Default season (2025)
    web/data/history-index.json       # 42-year index
    web/public/seasons/1985.json      # ... through 2026.json
    web/public/tournaments/1985.json  # ... through 2026.json

The archive contains derived ratings, actual recorded scores/teams and summary metadata, not raw commercial data exports.

You can also run the GitHub Actions **Rebuild historical snapshots** workflow manually to regenerate an artifact without changing committed data.

## Model and evaluation

The Python baseline trains separately on each season's chronologically ordered *regular season* games:

- Initial Elo strength = 1500; K = 24; home-court adjustment = 65 Elo points.
- The rating is updated after every game; a bounded, shrunk slope of the recent Elo history produces a conservative displayed projected rating.
- Held-out NCAA tournament probabilities use *frozen post-regular-season projected Elo*, without fitting on tournament outcomes.
- The archived Brier metric is the mean squared probability error on the historical tournament winners. **No seed values or future tournament outcomes are used to calculate the probabilities.**
- This is *not* a learned Kalman filter/ARIMA model, not a calibrated 2027 win predictor, and not a 2027 bracket simulation.

Caveats: this Elo parameterization has not undergone independent held-out-year hyperparameter selection or formal calibration. Historical tournament Brier scores are diagnostic baselines, not a claim of statistically validated superiority. Same-day ordering comes from Kaggle DayNum + IDs, not real tip-off timestamps.

## Repository map

    research/
      forecast/core.py         Elo model, projection and seeded bracket simulator
      forecast/io.py           Kaggle compact CSV import
      forecast/download.py     Version-pinned, SHA-verified public mirror download
      forecast/history.py      Generate all seasons, seed metadata, tournament results
      forecast/cli.py          Single-season ratings and simulations
      tests/                   Model, data import, downloader and archival tests
    web/
      app/                     Next.js site and responsive design
      components/Dashboard.tsx Rankings, comparisons, bracket simulations, archive
      data/                    History index and default season
      public/seasons/          42 public historical ratings snapshots
      public/tournaments/      42 public game-result archives
      scripts/check-data.mjs   Structural integrity and coverage checks
    docs/architecture.md       Design, scientific limitations and next milestones
    docs/data-contract.md      JSON schema and provenance details
    .github/workflows/         CI, static site deployment, reproducible data workflow

## Deploy

This project exports a static Next.js site to GitHub Pages.

1. In Settings > Pages choose **GitHub Actions** as Build and deployment Source.
2. Run or re-run the **Deploy website to GitHub Pages** workflow from Actions.
3. After a successful deploy, browse [March Forecast](https://dokeefe414.github.io/March-Madness-Forecasting/).

If Pages is not enabled, the repo and CI can be healthy but the website will not yet publish. No login, paid API keys or database is required.

## Rolling-year forecasting benchmark

The repository includes a **leakage-aware walk-forward evaluation** on real historical tournament games. It compares 50/50, base Elo, trend-adjusted Elo, and a trend-Elo probability calibrated using **only earlier tournament years**. The report separates test-season scores from the prior-year calibration history and excludes 2020 and the incomplete 2026 regular season.

```powershell
$env:PYTHONPATH="research"
py -m forecast.benchmark --web-dir web --out research/outputs/rolling-benchmark.json
```

See [benchmark methodology](docs/rolling-benchmark.md) for exact assumptions and caveats. Every CI run produces a downloadable `rolling-tournament-benchmark` JSON artifact; the metric is conditional on the **actual historical matchups**, not a simulated field or a validated 2027 forecast.

## Research roadmap

1. Audit data completeness against the canonical Kaggle competition export and add verified full 2026 regular-season and play-in data.
2. Extend the **implemented chronological rolling held-out-season tournament benchmark** with model selection for Elo, last-value, static power metrics, ARIMA, standard Kalman and adaptive Kalman. Study response to distribution shifts.
3. Add pace-adjusted offensive/defensive efficiency and strength of schedule using detailed historical game data (available from 2003 for men).
4. Add probability calibration and uncertainty intervals. Publish season-by-season benchmark results with honest limitations.
5. Build a full format-aware bracket simulator with projected field selection, actual seeds, year-specific First Four/play-in slots, a custom bracket interface and immutable forecast timestamps.
6. Source legitimate 2026–27 data feeds, then produce real 2027 forecasts without leaking results from future games.

A public data site should make it **easy to audit the model**, not just make bold claims about upsets. Contributions and reproducible corrections are welcome.
