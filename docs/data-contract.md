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
