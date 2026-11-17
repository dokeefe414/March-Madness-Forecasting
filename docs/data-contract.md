# Ratings JSON contract (v0.1)

File: web/data/rankings.json

Top-level fields:

- mode: demo or historical; the website visibly distinguishes them.
- season: integer season/tournament year.
- throughDay: Kaggle day cutoff (integer); null if synthetic.
- label: human-readable snapshot description.
- source: dataset provenance. Future live data must also include extraction time/hash.
- method: description of baseline and version.
- teams: array of teams, each with rank, teamId, name, rating, projectedRating, trend, wins, losses and history.

Per-team definitions:

- rating: most recent Elo, after included games.
- projectedRating: conservative projected Elo, NOT NCAA selection rank.
- trend: difference projectedRating minus current rating, in Elo points.
- wins, losses: records among included games.
- history: successive Elo estimates, oldest to newest, truncated to recent games.
- rank: one-based sorted by descending projectedRating.
- teamId: stable team identifier unique within the snapshot.

A championship probability is NOT part of the ranking record. It depends on a specific draw and simulation assumptions. An uploaded historical snapshot will only describe past games up to its cutoff, not a forward-looking 2027 prediction.

Check structural validity with npm run check:data in the web directory. The demo dataset contains imaginary teams and invented values, solely to exercise the interface.
