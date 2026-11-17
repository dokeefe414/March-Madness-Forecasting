# Architecture and development plan

## Data flow

The project separates data science code from the public static UI.

    Kaggle men's compact game results
                  |
          research/forecast/io.py      (CSV + season/day cutoff)
                  |
          research/forecast/core.py    (chronological Elo updates)
                  |
          research/forecast/cli.py     (versioned JSON snapshot)
                  |
             web/data/rankings.json
                  |
             Next.js static export
                  |
             GitHub Pages website

The committed snapshot is intentionally synthetic. Historical data is never described as a live prediction. No external API key or database is needed for the first version.

## Design decisions

- **No lookahead:** Regular-season results are processed by season/day. Pre-game Brier calculations happen before rating updates.
- **One season at a time:** The Elo baseline starts fresh at 1500 rather than assuming team rosters stay the same across years.
- **Honest model labels:** A bounded recent-trend adjustment is a heuristic, not a Kalman filter, ARIMA or trained ensemble.
- **Simple public contract:** One validated snapshot file drives the entire frontend. With future provenance and model version metadata, old forecasts can be audited.
- **Portable simulator:** Both Python and JavaScript implement the same neutral-site Elo probability equation. Their random draws need not match.
- **Static deployment:** GitHub Pages provides simple public viewing; data refresh currently requires committing a new JSON snapshot.

## Research roadmap

1. Acquire historical men's NCAA Kaggle data, preserve provenance and licensing information.
2. Add *tournament-specific* rolling-origin yearly holdouts, using game features available before Selection Sunday and the correct actual bracket for each year.
3. Compare Elo, last-value, rolling efficiencies, ARIMA, standard Kalman, adaptive Kalman, and possibly more advanced time-series models.
4. Measure Brier score, log loss, expected calibration error, and bootstrap uncertainty; assess if methods beat simple baselines.
5. Introduce calibrated bracket simulation, conference automatic bid/at-large selection and format-aware play-in handling.
6. Ingest reproducible 2026–27 current-season snapshots; archive prediction timestamps, dataset release and fitted model version.
7. Improve website with bracket editing, historical forecast playback, inter-model comparisons and CI checks against data leakage.

## Known limitations

The baseline only uses outcomes/location, not pace, offensive/defensive efficiency, injury status or opponent-specific tactics. Same-day Kaggle DayNum is not guaranteed to represent real tip-off order. The bracket model starts with an ordered power-of-two field (such as the 64-team main draw); it does not currently model 2027 play-ins, field selection or seeding. Pre-game regular-season Brier is not a held-out tournament validation metric.
