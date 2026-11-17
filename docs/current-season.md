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

The GitHub Pages workflow pulls the feed on main pushes, manually, and best-effort at **1:00 a.m. America/New_York daily**, with a **5:17 a.m. Eastern** catch-up during November–April. GitHub may delay scheduled jobs. It then generates both current and historical reports before building the site.

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

## Season-specific D-I group membership verification

In addition to the NCAA-source 2027 `team_ids` directory, the live importer optionally fetches two independent SportsDataverse basketball group files from release tag `mbb_groups`: `mbb_group_seasons.csv` (resolve the explicitly named Division I subdivision in 2027) and `mbb_team_group_seasons_2027.csv` (verify each team's season membership references that subdivision). See [identity-and-conferences.md](identity-and-conferences.md) for robust interpretation.

Flags `divisionIConfirmed` are `true`, `false` or `null` (unknown). Unknown is never automatically interpreted as ineligible, nor promoted to D-I. The `divisionCoverage` JSON object contains `status`, `matchedRatedTeams`, `divisionIConfirmed`, `explicitlyNonDI`, `unmatchedRatedTeams`, `sourceDivisionIConferenceGroups` and provenance URLs. Field Watch requires both independently sourced D-I membership and NCAA-source conference name matching; an unavailable group feed leaves the watchlist in a transparent insufficient-coverage state.

Offline CLI:
```powershell
$env:PYTHONPATH="research"
py -m forecast.live --input fixture-schedule.csv --directory-input fixture-2027-team-ids.csv --box-input fixture-box.csv --group-seasons-input fixture-mbb-groups.csv --membership-input fixture-2027-memberships.csv --out web/public/current/2027.json
```

For reproducible source validation, run `py -m unittest discover -s research/tests -v`. Do not commit fixture-generated JSON as a real 2027 current report.

### NCAA-to-ESPN reference alias reconciliation

A fifth **optional** source `mbb_team_aliases.csv` under the `mbb_groups` release supplies season-dated NCAA-name aliases attached to the source's ESPN group-team IDs. This permits a documented identity join where the NCAA score feed says, for example, a school-only name but the group reference uses an ESPN mascot display name. Only `source=ncaa`, `name_kind=name`, `team_id_source=espn` and a valid 2027 year window can contribute. Conflicting aliases are rejected and the fallback is an **unverified** team, not a guessed identity.

Offline flag: `--alias-input fixture-mbb-team-aliases.csv`. The live task fetches the public source automatically unless `--input` is used. Logs report how many scored programs are actually D-I group-linked after this source join.

### Source-native same-season numeric crosswalk

To resolve the NCAA-name versus ESPN-group team gap, `forecast.live` additionally fetches `ncaa_espn_team_crosswalk.csv` (SportsDataverse `mbb_crosswalk` release). It validates explicit season `2026-27`, source `ncaa_team_id`, source `espn_team_id`, and a genuine non-unmatched `match_method`. The source-defined ESPN ID matches the season-2027 division group membership ID; no integer equality or school nickname inference is used. `divisionCoverage.seasonNCAAIdMatchedTeams` and `crosswalkSource` report actual results. Missing mappings remain unknown, not D-I certified.

Offline flag: `--crosswalk-input local-ncaa-espn-team-crosswalk.csv`. Use this alongside `--group-seasons-input` and `--membership-input` to verify the join locally.

### Division I source conference IDs for the provisional field

Where the source provider has 32 2027 Division I `conferenceGroupId` values but only 31 display labels, `divisionConferenceGroupId` is attached to each confirmed D-I team (null otherwise). Field Watch uses the verified group ID for unique conference/automatic-bid proxy grouping; it never invents a missing conference to reach 32. `selectionWatchlist.matchedConferences`, `distinctConferenceDisplayNames`, and `groupingKey` make this discrepancy explicit.

## 1 a.m. Eastern pipeline and status endpoint

The main website's GitHub Pages workflow uses native timezone-aware GitHub Actions `schedule` events: `0 1 * * *` with `timezone: America/New_York` every night, plus `17 5 * 1,2,3,4,11,12 *` for a 5:17 a.m. catch-up in basketball season. UTC time changes automatically with DST. GitHub Actions and the upstream provider can be delayed: these are **scheduled checks**, not a permanent score-stream subscription or a guarantee that all 1 a.m. games are final.

After pulling NCAA-derived results, `forecast.freshness` independently checks that the 2027 report has been freshly retrieved, contains valid unique IDs and finite ratings, and satisfies `sum(team.wins) = sum(team.losses) = regularSeasonGames`. It also checks the most-recent accepted game, the source timestamp and retrospective diagnostic counts. If a necessary invariant is broken, the deployment fails closed.

A successful build exposes `/current/refresh-status.json` with `auditTimeUtc`, `retrievedAtUtc`, `lastIncludedGameDate`, `sourceLagCalendarDaysUtc`, accepted-game and rated-team counts, verified D-I count, and a descriptive staleness status. A game from the latest provider file is **not** evidence that an in-progress scoreboard represents a final: nonzero unequal scores may still be provisional when no verified final-state flag is present. The engine excludes blank, zero and tied scores and re-reads all source games each pass, so late corrections can be incorporated on subsequent refreshes, but it does not pretend to authenticate every final.

For pregame picks, `archive-pregame.yml` runs at **9:07 a.m. Eastern November–April**, keeping the earlier prediction and later result settlement paths separate. At the season's Selection Sunday cutoff (2027-03-14) the 2027 regular-season snapshot freezes; postcutoff postseason scores do **not** retroactively alter the regular-season model's historical features. Migrating to 2028 requires an intentional code/data revision.

## v0.7 automatic current-season learning

`forecast.live --games-out` can save the exact deduplicated scored-game source alongside `2027.json`, linked by `retrievedAtUtc`. `forecast.retrain` refits an L2 logistic correction to home-advantaged Elo using **only previous-date** outcomes, publishes per-day prequential Brier comparisons and a 2027 model report, and never assumes new coefficients outperform Elo. The web dashboard labels shadow vs active status and the remaining Elo fallback. The actual model-selection and as-of safeguards are in [online-retraining.md](online-retraining.md).


## v0.8 real game schedule joins and source availability

The scoreboard's completed-score source remains NCAA-derived SportsDataverse. `gamecenter.py` independently requests *ESPN public scheduled fixtures* for the next five Eastern days. The existing season-2027 team identity pipeline now exposes `espnSourceTeamId` only when backed by verified same-season membership/alias evidence. A conflicting ESPN ID cannot be overridden by a similar display name. Games without unambiguous match are visible without odds. The page also lists source-confirmed previous-date results, common opponents and team factors. No newly sourced result from **today's Eastern calendar date** is used for past-game explanation, guarding incomplete scoreboards. [Game Center source contract](game-center.md).

Generated `/current/upcoming.json` and `/current/2027-state-space.json` are refreshed only during Pages builds; no per-click request to a live prediction server occurs. The state-space report is retrospective `research-only`, not a promoted NCAA win probability or certified change-point sensor.


## v0.9 source-backed scheduled matchup and model audit

`forecast.opponents` builds bounded opponent-strength-adjusted Elo signals and date-frozen retrospective performance from the exact `2027-games.json` retrieval as `2027.json`, published at `/current/2027-opponents.json`. The independently scored **adaptive Gaussian state-space** research filter uses previous signed innovation evidence to change only *subsequent* process variance. The selected outcome prediction is still Elo unless a previously defined, source-verified logistic challenger passes prospective and chronological gates. No same-day provisional results are intentionally used to fit future game-day probabilities.

`forecast.archive_health` now publishes `/current/archive-health.json` from actual Git-committed snapshot artifacts, and `ModelLab.tsx` reads it alongside current-season sources; the website distinguishes no first-pick settled data from an honest zero percentage and from a published research replay. A player's identity, injury, roster or game status is not guessed. [Detailed model methodology](v09-model-validation.md) · [Operating schedule](v09-forecast-operations.md).
