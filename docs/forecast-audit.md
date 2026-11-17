# v0.6 — Immutable pre-tipoff forecasting audit and settlement

## Why we built it

A historical replay that uses final scores to create pregame probabilities **after the fact** is a valid retrospective backtest, but it is not a real public forecast track record. v0.6 adds a different, append-only system that can make source-verifiable scheduled matchup claims **before tipoff**, commit them to GitHub and later grade them against NCAA-source results. It does not retroactively label forecasts "live."

Code: `research/forecast/snapshot.py`; offline regression tests: `research/tests/test_snapshot.py`; workflow: `.github/workflows/archive-pregame.yml`; UI: `web/components/ForecastTracker.tsx`.

## Data origins and trust boundaries

1. **Model strengths:** the latest independently computed 2027 NCAA-source Elo ratings from `forecast.live`; source snapshot metadata contains its UTC retrieval time and date of last accepted result.
2. **Future fixtures:** ESPN public men's NCAA basketball scoreboard `site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard`. The importer requests two Eastern calendar days with `dates=YYYYMMDD`, `groups=50`, `limit=500`. This public source has no guaranteed API uptime or schema.
3. **Future schedule guard:** only `STATUS_SCHEDULED`, with `completed=false`, start timestamp more than **15 minutes after actual forecast generation UTC**. Any missing/malformed/missing-timezone or ambiguous fixture is skipped or rejected, never filled.
4. **Identity guard:** exact canonically normalized name match between an ESPN team location/display name and **one unambiguous NCAA-source rated team**. When a label points to more than one team or both sides cannot be mapped, skip the game. Do not use a false cross-provider numeric-ID join.
5. **Probability:** baseline regular-season Elo with documented +65 home adjustment, neutral court 0; the result is P(home wins) with explicit game, start, timestamp, sources and match policy.
6. **Settlement:** later NCAA-source final scores only; match by exact canonical home/away and scheduled **Eastern calendar date**; require exactly one candidate. If a rescheduled game moves dates or sides, prefer **unsettled** rather than a wrong match. Do not edit original pick.
7. **Evaluation:** Brier squared error `(p_home - actual_home)^2`, log loss, winner accuracy, with 50/50 tied favorite counted 0.5.

A given game may be forecast more than once across daily runs if it appears in two distinct pregame windows. This creates **multiple auditable predictions** but they are correlated, not independent games. Distinguish snapshot-level scores from unique-game statistical claims.

### Before-game cutoff

Suppose the scheduled listed start is `2026-11-16T19:00:00-05:00` (00:00 UTC November 17), and forecast generated at 2026-11-16T14:00:00Z. A prediction qualifies because it was generated more than 15 minutes before the listed start. A forecast at 23:49 UTC does *not* qualify under a 15-minute buffer. A schedule time is still not independently observed actual tipoff; users must not equate it with verified historical tipoff clock, and canceled/delayed games can remain unsettled.

## Append-only directory and fields

```text
web/public/forecasts/
  snapshots/
    YYYYMMDDTHHMMSSZ.json    # immutable forecast: ID, UTC time, source, probabilities
  settlements/
    YYYYMMDDTHHMMSSZ.json    # independently appended once NCAA finals match
  index.json                  # derived public dashboard view, recalculated on append
```

Each snapshot carries `snapshotId`, `generatedAtUtc`, `ratingRetrievedAtUtc`, `lastIncludedResultDate`, `scheduleSource`, `ratingSource`, the 15-minute guard, counts by refusal reason, and the actual predicted matchups. The snapshot file is created with **exclusive write mode** and is never overwritten in-place. Settlement records refer to `snapshotId:eventId`, preventing double settlement, and aggregate all saved proof. A no-op run with no new picks or settlements preserves the old index timestamp.

The scheduled GitHub Action commits the append-only changes on `main` with the official `github-actions[bot]` author. GitHub's immutable commit history and upload timestamp are externally observable, although Git timestamps alone are not independent game start certificates. If the repository workflow lacks `contents:write` or push permission due to branch protection, the archiver **cannot** publish its output; check the Actions run. The companion Pages job updates the public site on the next main-branch or scheduled build, **not necessarily immediately on a bot push**.

## Operational schedule

`.github/workflows/archive-pregame.yml`: best-effort at **9:07 a.m. Eastern daily** during Nov–Apr plus manual dispatch. GitHub schedule dispatches can be delayed or skipped; do not represent silence as proof no games were available. Archive job must run from a branch with the workflow enabled (main). The index absence is a legitimate "no audited forecasts yet" UI state.

### Local offline test

```powershell
$env:PYTHONPATH="research"
py -m unittest research.tests.test_snapshot -v
```

To test the CLI with saved fixture sources without network access:

```powershell
py -m forecast.snapshot --ratings web/public/current/2027.json --scoreboard-json path/to/espn-scoreboard.json --finals-csv path/to/ncaa-finals.csv --out-dir local-test-forecasts
```

**Do not** commit results from fixtures into the public scored ledger. Synthetic fixtures belong only in `research/tests` or a separate ignored local directory.

### Audit step by step

1. Locate a card on the Predictions Ledger; inspect its `eventId`, listed start, `generatedAtUtc`, `snapshotId`.
2. Open the corresponding JSON file in the [public committed snapshots](https://github.com/dokeefe414/March-Madness-Forecasting/tree/main/web/public/forecasts/snapshots) and verify its Git commit history precedes the listed start; account for event delays.
3. Inspect the original ESPN event ID/status and later NCAA contest ID on the settlement record.
4. Recalculate `(p_home - observed_home)^2` or log loss locally.
5. Compare the raw settlement set to the index aggregate. The web index is derived, not primary evidence.

## Known limitations

- Source name matching sacrifices coverage for precision; the ESPN API and NCAA names can differ. Zero qualified matches is a valid, honest outcome.
- ESPN listed start is not authenticated actual tipoff, so the ledger is not indisputable proof of strictly pre-actual-tipoff. 15-minute buffer mitigates, but doesn't eliminate reschedule risk.
- Historical-only calibration is intentionally not used in archived live regular-season predictions until independently validated. The audit's model key remains baseline Elo.
- The 2027 current schedule may lag final results and omit contests; a settlement is possible only after the data source publishes a uniquely matched final.
- This is a public repository workflow, **not** a secure tamper-proof external timestamping authority. Maintainers with write privileges can rewrite Git history; auditability improves transparency but does not eliminate trust.

## v0.6.1 independent ledger integrity check

`research/forecast/audit.py` reconstructs the public index's aggregate scores from every immutable settlement file and verifies each settlement against the **original** per-event prediction. It rejects altered predicted probabilities, outcome arithmetic errors, duplicated settlements, missing original predictions, source ratings fetched after forecast generation, and forecasts created inside the 15-minute pretipoff buffer. It also checks that public score totals agree with the underlying evidence. The GitHub Actions archival job runs this audit **before committing**; CI runs it on every PR and main push.

```powershell
$env:PYTHONPATH="research"
py -m forecast.audit --dir web/public/forecasts
```

An empty ledger reports `verified` but **zero** predictions and settlements. That is not proof of a deployed pretipoff track record, only confirmation that no archived evidence has been tampered with. A valid internal archive cannot independently establish actual start times or the truth of the upstream ESPN/NCAA source; those limitations remain.

The settlement worker now defensively refuses to grade a forecast unless its source rating was obtained at or before forecast creation, and creation preceded the scheduled tipoff by the committed buffer. This is an extra defense even if someone manually deposits a malformed snapshot artifact.

## Nightly coordination

The current-season page refreshes at the scheduled **1:00 a.m. Eastern** every night, and at **5:17 a.m. Eastern** in season to pick up late-released results. The immutable forecast archiver runs separately at **9:07 a.m. Eastern** in-season, once the morning's latest available ratings have been assembled. Each cron uses GitHub Actions' native `timezone: America/New_York` to respect EDT/EST automatically. Archive jobs can be delayed; the event-time and source-retrieval guards apply regardless of how late the job starts. The website is rebuilt after archived bot commits (main branch push) or its own schedules. This **does not** certify the provider's actual tipoff or supply real-time score streaming.
