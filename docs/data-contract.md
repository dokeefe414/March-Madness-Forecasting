# Historical JSON schema — v0.2

All public JSON is derived from documented data sources, not invented previews.

## web/data/history-index.json

    {
      "source": "...",
      "sourceCommit": "<pinned Git SHA>",
      "firstSeason": 1985,
      "lastSeason": 2026,
      "seasons": [
        {
          "season": 1985,
          "throughDay": 132,
          "isComplete": true,
          "regularSeasonGames": 3737,
          "teams": 282,
          "champion": "Villanova",
          "tournamentGames": 63,
          "tournamentBrier": 0.2199
        }
      ]
    }

This index is a discovery table: year, completeness, game counts and archive availability.

## web/public/seasons/<year>.json and web/data/rankings.json

Top-level metadata:

- mode: historical.
- season: year of the NCAA season.
- throughDay: last Kaggle DayNum present.
- isComplete: true only if the historical source covers DayNum 132. False for 2020 and partial 2026. This does not guarantee every possible game is represented.
- regularSeasonGames: number of compact game rows included, not total tournament games.
- label: explicit historical season and cutoff.
- source, sourceUrl, sourceCommit: traceable provenance.
- method: rating model and version description.
- tournament: champion, championId, games, evaluatedGames, missingTeams, brier, accuracy, source and optional mainDrawOnly flag.
- teams: historical rating rows sorted by projected Elo strength.

Each team:

- teamId, name: standardized Kaggle team identifier and name.
- rank: order by projected Elo strength, **not** NCAA seed or AP poll rank.
- rating: Elo points after all included regular-season games.
- projectedRating: conservative projected Elo from recent ratings, not a validated March prediction.
- trend: projectedRating - rating (Elo points).
- wins, losses: wins/losses among the included regular-season games.
- history: last twelve rating snapshots.
- seed (optional): official historical NCAA tournament seed for years present, or 2026 main-draw seed/region label. A value only for display; NOT a model feature.

## web/public/tournaments/<year>.json

    {
      "season": 2025,
      "champion": "Florida",
      "mainDrawOnly": false,
      "note": "Historical results...",
      "sourceCommit": "<pinned Git SHA>",
      "teams": {"1101": "Abilene Chr"},
      "seeds": {"1101": "W01"},
      "games": [
        {
          "day": 136,
          "winnerId": "1101",
          "loserId": "1102",
          "winnerScore": 71,
          "loserScore": 63
        }
      ]
    }

Tournament files are records of **actual historic results**, not bracket predictions. For 2026, each game includes round/region instead of Kaggle day, and mainDrawOnly=true because the four First Four games are not present. 2020 games is [] because the NCAA tournament was canceled.

## Validation

Run npm run check:data from web/ to verify the complete 42-year inventory, source commit consistency, counts, default year and empty 2020 tournament. Future changes in the pinned data, dataset cutoff or normalization require explicit rebuilds and review.

## Additional generated (not committed) schemas

### Current 2027 report: `web/public/current/2027.json`

Built by `PYTHONPATH=research python -m forecast.live --out web/public/current/2027.json`. Requires `mode="current"`, `season=2027`, `retrievedAtUtc`, `lastGameDate`, `cutoffDate`, `source`, `sourceUrl`, `regularSeasonGames`, `isOfficialBracket=false`, `teams`, and `recentGames`. Teams have `teamId` prefixed with `ncaa-` and include ordinary Elo, projected Elo, recent rating history, win/loss totals and descriptive points/average-opponent Elo. NCAA names are **not** silently mapped to historical Kaggle IDs.

The importer rejects future data, wrong-season games, invalid scores, duplicate contest conflicts and missing required columns. The snapshot marks the last result and retrieval UTC separately. See [2027 source contract](current-season.md).

### Research report: `web/public/research/benchmark.json`

Built by `PYTHONPATH=research python -m forecast.benchmark --out web/public/research/benchmark.json`. `aggregate` has game-weighted Brier/log loss/accuracy for coin flip, Elo, trend Elo, temperature-calibrated Elo and logistic. `yearByYear` includes test year, prior-year training boundary, calibration temperature, logistic weights and metrics. `reliability` has ten favorite-confidence bins with observation count, confidence and accuracy. `seasonBlockUncertainty` reports paired bootstrap Brier difference versus Elo with 95% intervals. See [scientific validation](validation.md).

Both generated JSON outputs are ignored by git, constructed in the deployment before Next.js static export and loaded on demand by React. A missing file is an explicit unavailable state, not a cue to display fake data.

### Historical simulator field source

Archive seed codes `W01`, `W16a`, `W16b` map archived team IDs to a region/seed position. A slot with two teams is an Opening Round match; 64 main slots plus 4 additional entrants describes a 68-team field; plus 12 describes the 76-team 2027 format. Actual 2027 positions remain unknown until selection. See [bracket-engine.md](bracket-engine.md).

## v0.6 team identity, group verification, models and audit fields

`current/2027.json` extends the per-team data contract with source-only `conference`, `ncaaSourceTeamId`, `conferenceVerified`; independently verified season-2027 membership `divisionIConfirmed` (boolean/null), `adaptiveRating`, `volatility`, `regimeShift`, `ewmaSlope`, and optional `offRating100`, `defRating100`, `pacePossessions`, `adjOff100`, `adjDef100`, `adjNet100`, `possessionGames`. Values are omitted when data is not verified.

Root-level `identityCoverage`, `divisionCoverage`, and `efficiencyCoverage` provide separate source URLs, availability, crosswalk match counts, D-I group verification counts and posseession coverage; `selectionWatchlist` is either `status=insufficient-coverage` or a 76-team **unofficial strength scenario** containing the source-backed candidates, conference power proxies and at-large proxies. `historicalCalibration` records earlier-year temperature/blend weight with a caveat about transferring March-neutral calibration to regular-season games.

`research/benchmark.json` now uses `schemaVersion=3`, with eight model keys (coin flip, Elo, trend Elo, adaptive form, calibrated Elo, logistic, gradient boosting and past-year blend), `productionCalibration`, sequential model cutoffs, reliability and season bootstrap uncertainty. See [model-zoo-v06.md](model-zoo-v06.md).

`web/public/forecasts/snapshots/*.json` and `settlements/*.json` are append-only Git-committed proof records; `forecasts/index.json` is a derived public dashboard aggregate with score counts, per-pick Brier/log loss, and source identity. A missing `index.json` is a **legitimate "not yet archived"** UI state, not license to fabricate an archive. See [forecast-audit.md](forecast-audit.md).
