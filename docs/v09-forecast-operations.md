# v0.9 — Archived prediction reliability and automated operating schedule

## Why an apparently successful site might have shown no accuracy

The site rebuilds ratings and upcoming fixtures from provider files, but a **real forward accuracy percentage requires an independent Git-committed pregame prediction and later settlement**. A green GitHub Pages deployment alone does not prove that separate archive action ever ran.

The repository's previous first deployment had **no committed `web/public/forecasts/index.json`**. It was therefore correct to display **—** rather than 0% or a guessed success rate. v0.9 adds a monitor so a missing/delayed archive cannot go unnoticed as if everything were fine.

## Eastern time schedule

Local DST-aware GitHub Actions cron with `timezone: America/New_York`:

| Local time | Workflow | Purpose |
|---|---|---|
| 01:00 ET daily | `deploy-pages.yml` | New NCAA-source score/rating, all research models, ESPN upcoming schedule, public site |
| 05:17 ET Nov–Apr | `deploy-pages.yml` | Late-game and upstream refresh catch-up |
| 09:07 ET Nov–Apr | `archive-pregame.yml` | Freeze scheduled future predictions, verify previous final results, commit immutable receipts |
| 10:17 ET Nov–Apr | `deploy-pages.yml` | Republish the newest Git-committed archive results on the public website |
| 11:35 ET Nov–Apr | `monitor-archive.yml` | Fail audibly in GitHub Actions if archive missing/stale/no-picks |
| 16:07 ET Nov–Apr | `archive-pregame.yml` | Capture additional evening fixtures and result corrections |
| 17:17 ET Nov–Apr | `deploy-pages.yml` | Republish afternoon archive and latest models |
| 18:35 ET Nov–Apr | `monitor-archive.yml` | Recheck same-day before-tipoff archive evidence |

GitHub Actions is **best effort**; scheduled jobs may run late, be skipped under load or fail if third-party endpoints are unavailable. The monitor itself is best-effort. The page never guarantees second-by-second scores.

Important: GitHub Actions runs made with the default `GITHUB_TOKEN` do not reliably fire downstream `push` workflows, so the explicit **10:17/17:17** Pages refreshes serve the immutable archive captured at 09:07/16:07 respectively.

## Final-status validation and failure behavior

`forecast.snapshot` now fetches real ESPN source scoreboard for future scheduled dates and for previously archived game dates within a bounded ten-day lookback. The original NCAA scored-game source still builds the 2027 team strength.

**For a settlement to count**, there must be exactly one matching NCAA source result and an independently retrieved ESPN status of `STATUS_FINAL`, `completed=true`, with the exact ESPN event ID, matching date and **identical positive home/away score**. A postponed or still-in-progress match is not graded. A provider rate-limit/timeout is recorded as a source warning and leaves that event pending. Nothing is settled simply because the NCAA feed shows a nonzero score.

New and historical scores in the public Git archive are immutable files; only `index.json` is regenerated as a derived rollup. Repeated workflow runs must not create a second settlement for the same `snapshotId:eventId`. The audit checks source/as-of, time buffer, original forecast probability, actual score arithmetic, frozen candidate probability bounds, result identity, and index aggregation.

The daily archive outputs **`archiveHealth`** in `index.json`: run time, new predictions, verified new settlements, total archived predictions, count of completed ESPN events checked, source warnings and current status. The independent Pages rebuild evaluates age and publishes **`/current/archive-health.json`** with state `current`, `stale`, `source-partial`, `no-picks-yet`, or `awaiting-first-archive`. The website displays that honestly; a missing index is not replaced by a manufactured percentage.

`monitor-archive.yml` runs at **11:35/18:35 ET** and fails if during season the archive is missing, older than **26 hours**, or has no verified pregame predictions. It also runs the integrity audit. GitHub's workflow failure notifications are the alert mechanism, not a promise this chat can autonomously send notifications.

## Model training and score audit

Every site refresh rebuilds `2027.json`, `2027-games.json`, `2027-online-model.json`, `2027-opponents.json`, `2027-state-space.json`, `upcoming.json`, `archive-health.json` from exact current provider captures. The morning and afternoon archiver rebuild the underlying rating/model artifacts before it freezes future predictions, and commits **only** the public immutable archive receipts.

Opponent-adjusted margins and fixed/adaptive state-space predictions are **research alternatives**. All are frozen with their name and source as-of in each future-game snapshot where valid. The selected main chance remains Elo or the carefully gated online logistic correction. Missed games are permanently recorded. New **previous-date** sourced outcomes feed the next fit; no instant retroactive correction is permitted.

The new `uniqueGames.pairedModelComparisons` provides actual paired first-pick Brier, accuracy, date counts, and descriptive bootstrap interval for each challenger. The model lab displays the unambiguous distinction from retrospective date-frozen experiments.

## Runbook for a failed refresh or missing picks

1. Open [GitHub Actions archive](https://github.com/dokeefe414/March-Madness-Forecasting26-27/actions/workflows/archive-pregame.yml), [monitor](https://github.com/dokeefe414/March-Madness-Forecasting26-27/actions/workflows/monitor-archive.yml), and [Pages](https://github.com/dokeefe414/March-Madness-Forecasting26-27/actions/workflows/deploy-pages.yml).
2. Check whether the archive workflow exists/has run on `main`, and whether a provider failed or a Git push was rejected. The previous green Pages build cannot substitute for this check.
3. Use `workflow_dispatch` on **main** to re-run the archive action after the source becomes available. Do not manually fill an unseen predicted probability or alter immutable snapshot contents.
4. Inspect `web/public/forecasts/index.json`, `archiveHealth`, and the source-explicit `/current/archive-health.json`. Expect the game picker to display **—** for accuracy if no first-pick settlement has been verified.
5. If there was a source mismatch, preserve the original forecast. Recheck ESPN final status and NCAA final score; do not force its settlement.
6. After a successful archival commit, the next scheduled Pages build republishes it. The monitor will fail if the archive remains overdue.

### Reproduce locally

```powershell
$env:PYTHONPATH="research"
py -m unittest discover -s research/tests -p "test_archive_reliability.py" -v
py -m unittest discover -s research/tests -p "test_archive_health.py" -v
py -m forecast.archive_health --ledger web/public/forecasts --out web/public/current/archive-health.json
py -m forecast.audit --dir web/public/forecasts
```

Monitoring `--require-recent` is intentionally strict and exits nonzero in season when no genuine archive exists or it is stale. A dry-run/CI unit test can validate code but does **not** certify an actual daily provider schedule has happened before its first local time.

### Limitations

The ESPN scoreboard and NCAA-derived schedule may both lag and could share data-origin errors. The absence of a final status prevents settlement but does not establish a canceled game. Sources have dates but not independently guaranteed true tipoff clocks; a valid archived forecast asserts timing relative to the ESPN *listed* start. Date changes and conflicting scores are handled conservatively. A completed flow cannot guarantee future game prediction accuracy. No forecasts for seasons beyond the explicitly sourced 2027 regular season are invented.
