# GitHub Actions, publishing, maintenance and incident runbook

## Automated workflows

| Workflow | Trigger | Guarantees |
|---|---|---|
| `CI` | feature branch push, main push, pull request | Hermetic Python tests, held-out historical benchmark, JSON report artifact, 42-year data consistency, TypeScript bracket simulations, TypeScript typecheck and production Next build |
| `Deploy website to GitHub Pages` | main push, dispatch, daily best-effort 14:22 UTC Nov–Apr | Real NCAA-source 2027 finals → current Elo snapshot → historical research report → data check → static Next export → GitHub Pages |
| `Rebuild historical snapshots` | manual dispatch | Regenerate source-pinned historical artifacts without silently changing main |

Historical unit tests and website builds do not require a live network feed. Only the publishing job fetches it, and an upstream error must **fail closed**. GitHub's scheduled cron is best-effort; it may skip or delay a run under load.

## Published files versus committed historical archives

```text
web/data/rankings.json                   # committed, frozen complete 2025 season
web/data/history-index.json              # committed, 42-year historical metadata
web/public/seasons/*.json                # committed historical Elo snapshots
web/public/tournaments/*.json            # committed historical tournament results
web/public/current/2027.json             # generated only on deployment
web/public/research/benchmark.json       # generated only on deployment
```

Generated reports are in `.gitignore` to avoid committing stale daily feed data. Site API routes are **not** required: Next.js exports a static site under the Pages repository base path.

## Local release checks

```powershell
$env:PYTHONPATH="research"
py -m unittest discover -s research/tests -v
py -m forecast.benchmark --out web/public/research/benchmark.json
py -m forecast.live --out web/public/current/2027.json
cd web
npm install
npm run check:data
npm run test:bracket
npm run typecheck
npm run build
```

If your machine is offline, omit only `forecast.live`; the frontend explicitly marks the current feed unavailable. Do not skip test coverage or substitute synthetic results as live.

## GitHub Pages deployment fails at configure-pages

The repository must have **Settings → Pages → Build and deployment → Source: GitHub Actions** configured. The failure `Get Pages site failed / Not Found` happens before any app build and is a Pages setting issue, not a Python forecasting error. After setup, use [the deploy workflow](https://github.com/dokeefe414/March-Madness-Forecasting/actions/workflows/deploy-pages.yml) to run a fresh build.

Expected URL: `https://dokeefe414.github.io/March-Madness-Forecasting/`. The production build sets `NEXT_PUBLIC_BASE_PATH=/March-Madness-Forecasting` so season/tournament/current/research JSON loads under the correct static prefix.

## 2027 refresh fails

Inspect the `Validate and build 2027 NCAA-source results` step:
1. Confirm [SportsDataverse schedule release](https://github.com/sportsdataverse/sportsdataverse-data/releases/tag/ncaa_mbb_schedule) exposes `ncaa_mbb_schedule_2027.csv.gz`.
2. Compare upstream source update timestamp to the last accepted result date.
3. Confirm expected CSV headers, season=2027, no inconsistent duplicates, positive final scores, and valid dates.
4. If the source is late/unavailable, **do not** publish fictitious results: keep previous successful site and display its recorded timestamps.
5. Any upstream format change needs a documented importer/schema change and new hermetic tests.

## Research or bracket regressions

If benchmarking fails, check source pin matches for history-index/snapshots/tournament files and avoid arbitrarily omitting difficult seasons. If bracket validation fails, verify exactly four regions with ordered slots and actual source team ratings. The Opening Round slot count should be 0, 1, 4 or 12 (fields 64, 65, 68 or 76). Expected simulated advancement sums: Round of 32 = 32, Final Four = 4, finalists = 2, champion = 1.

## Maintenance responsibility

- Update `docs/validation.md` if models/features/calibration shift.
- Update `docs/current-season.md` for external source contracts and dates.
- Update `docs/bracket-engine.md` when official field formats or region crossover rules change.
- Update `docs/design-system.md` for tab/component redesigns.
- Before the 2028 season, explicitly review the feed name, source URL, Python `SEASON` and cutoff, unit tests and front-end year label. A 2027 snapshot must not accidentally masquerade as live 2028.

## v0.6 additional workflows and production verification

### Pre-tipoff forecast archiver

`.github/workflows/archive-pregame.yml` schedules a **13:07 UTC best-effort** daily run during Nov–Apr and permits manual dispatch. It fetches validated 2027 source Elo data, lists ESPN scheduled games that start >15 minutes after forecast creation, and Git-commits **new** snapshot/settlement JSON files under `web/public/forecasts` with bot author. GitHub branch protection / token `contents:write` may block bot pushes. Inspect the scheduled job and archive files before saying the audit is operational. Missing future matches is not an error; no forecast is backfilled. After archiver commits, the next regular Pages rebuild will make the derived index visible.

### Source coverage runbook

Four source families determine the 2027 UI, with different fail policies:
1. SportsDataverse NCAA schedule (`ncaa_mbb_schedule_2027.csv.gz`): **mandatory** and strict on invalid core schema; no published scores if broken.
2. NCAA 2027 team IDs/conferences (`ncaa_mbb_team_ids_2027.csv.gz`): optional. Exact full-name join; reports source match count, never guesses other teams.
3. NCAA 2027 team box (`ncaa_mbb_team_box_2027.csv.gz`): optional. Only game-ID-matched, genuine possession rows become per-100 efficiency profiles.
4. Season group reference (`mbb_group_seasons.csv` and `mbb_team_group_seasons_2027.csv`): optional. Independently confirms `divisionIConfirmed` when a documented season-2027 Division I `subdivision_id` matches the scored team by exact normalized name. Otherwise status unavailable or team unverified. **This is not postseason eligibility certification.**

The watchlist requires both D-I subdivision membership and NCAA conference matching, and at least 76 candidates in exactly 32 mapped leagues. Source absence returns an explicitly missing/hypothetical field, not 76 invented selections.

### Historical model order

Deploy runs `forecast.benchmark` **before** `forecast.live`, so `productionCalibration` contains only historical outcomes through 2025 and is available for clearly labeled regular-season *scenarios*. Never train the current production calibration with 2027 scores or tune it to the same day's held-out outcome. `forecast.snapshot` intentionally records baseline Elo for pregame audit, not these unvalidated March-to-November scenarios.

### CI and browser quality

The third `CI` job now executes Playwright desktop and mobile against the **Next static export**, preventing false confidence from dev-server HMR. Checks include navigation, actual historical bracket interaction, full-page horizontal width, and automated critical WCAG axe violations. Upload `playwright-v06-visual-checks` includes test traces/screenshots for CI failures. All three CI jobs must pass before merging. [Browser guide](browser-quality.md).

### Fixing a failed production release

Inspect the first failure in the [Pages workflow](https://github.com/dokeefe414/March-Madness-Forecasting/actions/workflows/deploy-pages.yml). If the mandatory source, historical calibration generation or production build fails, do not invent data or bypass a cutoff. Fix source parsing using a new hermetic regression test, merge through passing CI, and confirm the next Pages deployment returns success with a current `lastGameDate` and `retrievedAtUtc`. A successful web build alone does not prove the user's website has been deployed.

The 2027 source convention must be reviewed before the 2028 season; never display a 2027 report as new-season 2028 ratings.

### 2027 name-space reconciliation runbook

The initial v0.6 source-run returned **365 exact NCAA directory matches but 0 direct ESPN-subdivision-name matches**. Check [SportsDataverse `mbb_groups`](https://github.com/sportsdataverse/sportsdataverse-data/releases/tag/mbb_groups) asset `mbb_team_aliases.csv`. The importer now consumes only NCAA-source name aliases with a matching 2027-valid season window and the original ESPN group team ID, then checks the source team's 2027 Division I membership. If no matches appear, inspect schema, provider alias dates and coverage **without relaxing** the ID/season validation. The watchlist is deliberately unavailable until joined Division I membership is actually verified.

### Season-specific NCAA-to-ESPN ID crosswalk

The team-group source uses ESPN team IDs, while the NCAA schedule/team-directory uses distinct, season-specific stats.ncaa.org team IDs. The 2026–27 `ncaa_espn_team_crosswalk.csv` in [`mbb_crosswalk`](https://github.com/sportsdataverse/sportsdataverse-data/releases/tag/mbb_crosswalk) provides the explicit dated numeric mapping. It is now the **primary** cross-provider lookup when a 2027 mapping exists; old/source-dated NCAA name aliases are additional conservative fallback.

Check deployed `divisionCoverage.seasonNCAAIdMatchedTeams` and `divisionIConfirmed` after refreshing. If zero, confirm whether the upstream crosswalk already contains `season=2026-27` rows before considering fixes. **Do not** use 2025–26 NCAA IDs for 2026–27 because the NCAA issues new team IDs each year. Keep the hypothetical watchlist unavailable rather than inventing a field.

### 32 source conferences but 31 display labels

The deployment artifact may report 32 independently verified 2027 D-I conference groups and only 31 distinct NCAA team-directory conference display strings. This is not evidence of missing a D-I league; it is a difference in data labeling. Field Watch now requires and groups by `divisionConferenceGroupId` from verified season-2027 group membership, not the display label. Validate output `selectionWatchlist.matchedConferences=32`, `distinctConferenceDisplayNames=31`, `conferenceLeaders=32`, `atLargeCandidates=44`, and `len(teams)=76` on the first successful production build, and confirm the UI still calls it hypothetical. Do not bypass D-I verification or re-label an Elo AQ proxy as a real conference champion.
