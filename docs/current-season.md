# Current 2026–27 NCAA source and freshness contract

The published 2027 results originate from NCAA statistics via the **SportsDataverse NCAA men's basketball** dataset. Documentation: [data pipeline](https://github.com/sportsdataverse/ncaa-mbb-hoops-data); [public season schedule release](https://github.com/sportsdataverse/sportsdataverse-data/releases/tag/ncaa_mbb_schedule). This is a third-party publication of NCAA-source data, not a guaranteed real-time live-scoring service.

## Data flow

```text
stats.ncaa.org → SportsDataverse NCAA raw/pipeline
              → ncaa_mbb_schedule_2027.csv.gz (GitHub public release)
              → research/forecast/live.py (strict validation)
              → independent 2027 Elo & descriptive scores
              → web/public/current/2027.json (generated at deploy)
              → current-season dashboard with visible timestamps
```

The input must have `contest_id, game_date, home, away, home_score, away_score, season`. Games are accepted only when:
1. `season=2027`, dates are from **Nov 1, 2026 through March 14, 2027**, and game date is not in the future relative to UTC;
2. both team names are provided and are different;
3. both scores are positive integers, not equal; missing scores and unplayed schedules are skipped;
4. contest ID is present and unambiguous; duplicates with conflicting content fail loudly.

The cutoff protects against letting 2027 postseason results leak into pre-tournament ratings. The real **Selection Sunday is March 14, 2027**, and the tournament has **76 participants and 12 Opening Round games**. See the [NCAA announcement](https://www.ncaa.com/news/basketball-men/article/2026-05-07/2027-march-madness-mens-ncaa-tournament-schedule-dates).

## Current rating computation

Every recorded team begins at Elo 1500 in the new season. Score winner and home/away location update Elo via `K=24`, home advantage 65 points. A bounded recent-slope projection creates a displayed projected rating. From final scores, the importer also computes points for/against per game, margin-per-game, and mean **current Elo** of recorded opponents. All are descriptive; no pace adjustment or proprietary efficiency claims are made. Same-day chronological ordering is approximate, not actual tipoff timing.

To avoid unsupported cross-source identity mapping, NCAA team names become deterministic `ncaa-` prefixed SHA-256 identifiers. They are **not** merged into historical Kaggle integer IDs. In particular, a 2027 field of 76 is not projected from those identities.

## Run from Windows PowerShell

```powershell
$env:PYTHONPATH="research"
py -m forecast.live --out web/public/current/2027.json
```

For a network-independent test, use `--input path/to/fixture.csv` (accepts `.csv` and `.csv.gz`). The code uses only Python's standard library.

The output includes `mode=current`, `season=2027`, `retrievedAtUtc`, `lastGameDate`, `cutoffDate`, `sourceUrl`, `regularSeasonGames`, `teams`, `recentGames`, and `isOfficialBracket=false`. Freshness is **two separate things**: retrieval timestamp is when our runner obtained a published file; last game date is when the most recent accepted final occurred. Neither implies zero-delay live coverage.

## Automation and fail-safe publication

The GitHub Pages workflow pulls the feed on main pushes, manually, and best-effort each day at **14:22 UTC during November–April**. GitHub may delay scheduled jobs. It then generates both current and historical reports before building the site.

If the release disappears, contains inconsistent scores, is empty, exceeds size limits or cannot be fetched, **the deploy fails** and leaves the last successful website intact. It must never substitute fabricated results. An absent local JSON displays an explicit unavailable state in the app.

## Troubleshooting

- [Open the Pages deployment workflow](https://github.com/dokeefe414/March-Madness-Forecasting/actions/workflows/deploy-pages.yml) and inspect the Python final-score validation step.
- Compare release asset freshness with dashboard `retrievedAtUtc` and `lastGameDate`.
- If the input column schema changes, update validation and offline regression tests before merging.
- Do not turn a failed source into mock rankings or a fake official 2027 field.
- The 2027 season is a version-specific feed. Before the 2028 season, explicitly review year, source URL, cutoff, tests and docs. No accidental stale carry-over.

## Sequential source-score model tracking

The published `pregameDiagnostics` object reports `evaluatedGames`, `brier`, `accuracy`, `coinFlipBrier=0.25`, method and caveat. These values are accumulated **before each regular-season game updates Elo**, and they come from actual final scores in the published source. This is a retrospective chronological *pre-game backtest*, **not** an audited history of probabilities posted publicly prior to tipoff. As in the historical Kaggle source, same-day real tipoff order may be unavailable. The interface clearly labels this limitation.

`forecast.core.EloEngine` tracks both pregame Brier and winner accuracy; `forecast.live` serializes them for the web. No fabricated win/loss streak chart or unobserved performance statistic is displayed.

### Date-format compatibility (deployment incident, Nov 16, 2026)

The first v0.5 deployment intentionally failed before publication because the real schedule release contained U.S. calendar dates such as `11/07/2026`, while the initial parser expected ISO dates. `parse_source_date` now accepts **explicit ISO `YYYY-MM-DD` and U.S. `MM/DD/YYYY`** formats, normalizes both to a Python `date`, and rejects ambiguous/unknown date styles instead of guessing. A hermetic test now includes the observed U.S. format. This fixes the source-format mismatch without bypassing any cutoff or quality validation.

### Incomplete score rows in the real release (deployment correction)

The actual 2027 schedule feed included at least one contest with score fields
that did not represent a valid completed NCAA men's basketball game
(identified in the publish logs as contest `6625413`).
The exporter does not guarantee every nonempty scoreboard entry is a final.
Our ingest now **excludes** scoreboards with zero for either side or tied
scores; a true NCAA basketball final is never tied. Records with missing scores
remain excluded. **Negative scores, conflicting contest IDs, invalid team
identities and malformed dates still abort ingestion.** This is a conservative
final-score inference based on scores because no authoritative final-status
field is present in the currently documented schedule schema.
The live results page should be interpreted as the completed-score subset,
not a guarantee of exhaustively ingesting every NCAA game.
