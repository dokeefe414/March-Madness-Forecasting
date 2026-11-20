# Daily games and final-score reliability (v2.4)

## Why the site previously appeared to stop updating

On November 19, 2026, the automatic deployment and archive workflows were
**running successfully**. The 9:15 p.m. Eastern website rebuild processed
**953 NCAA-derived scored games** and built 174 rated future fixtures. Its
latest NCAA source-accepted scored game was dated **November 18**.
The underlying SportsDataverse schedule CSV updates with upstream latency.
Passing a source retrieval and data-quality check does **not** guarantee
that same-day NCAA final scores have appeared.

In addition, the Game Center's **Find a Game** browser was intentionally
future-only. Once an ESPN-listed tipoff passed, the game vanished from the
default fixture list even if its score was not yet in the lagging NCAA
source. An already-open browser tab fetched the published JSON only on
mount, so a subsequent successful site deployment was invisible until
manual page reload.

These were three different freshness dimensions: (1) scheduled production
build, (2) ESPN final-status score availability, and (3) separately accepted
NCAA scored games used by models and archived prediction settlement.
They must never be mislabeled as the same data.

## Fix: display verified ESPN final scores without corrupting Elo

`forecast.recent_finals` collects ESPN college basketball public
scoreboards for the last **four Eastern calendar days**, starting with
the present day. The report is generated at each scheduled Pages build:

```text
web/public/current/recent-finals.json
schemaVersion=1, season=2027, type=ESPN-recent-final-scoreboard
generatedAtUtc, ratingRetrievedAtUtc, ncaaResultsThroughDate
source, boardDaysRetrieved, lookbackDays, sourceWarnings
confirmedFinalCount, ncaaRatingInputMatched
mostRecentEspnFinalDate, games[]
```

A game enters this visual scoreboard **only** if ESPN reports both
`status.type.name == STATUS_FINAL` and `status.type.completed == true`,
there is a single competition with exactly one home and one away side,
both scores are positive integers and are unequal, and the ESPN source
supplies a valid timestamp and event ID.

NCAA rating-source confirmation has stronger identity rules:
- A unique NCAA team match is established via exact season-2027
  provider-authored ESPN-ID mapping, or permitted exact school names.
  Ambiguous, contradictory or unknown team identities never yield a match.
- The accepted NCAA result must have the exact **Eastern scheduled date**,
  home and away names, and **identical** scores, and there must be
  exactly one matching result record.
- A recent ESPN final without this exact match is shown as
  `ncaaRatingInputConfirmed=false`; it **does not update Elo** and is
  **not graded** as a correct/incorrect published forecast.
- A missing source date/status is disclosed as partial/unavailable;
  if the network fails, no fake zero scores or completed games are inserted.

The separate established immutable first-pick settlement system **still
requires independent ESPN `STATUS_FINAL` plus NCAA identical final
scores**, a before-tipoff snapshot, correct event identity and a timestamp
audit. A new public ESPN-only scoreboard can therefore be fresher than
official model inputs without rewriting or inflating real forecast accuracy.

The scoreboard displays up to 30 newest results in an accessible, responsive
layout, with counts, source capture timestamp, latest ESPN-final date,
latest NCAA-Elo accepted date, and explicit labels when these dates differ.

## Open tab refresh and same-evening scheduling

`GameCenter.tsx` now fetches current static JSON with `cache:no-store`,
and retries **every ten minutes** while mounted and when a previously
backgrounded tab becomes visible. A visible **Check for Updates** button
performs an immediate re-fetch. Selected matchup, followed teams and
filters are retained where the newly published snapshots still contain
the selected identifiers. A failed source request does not invent a
fresh data snapshot.

Daily Eastern GitHub workflows gain an extra seasonal slot:

| Eastern time | Task |
|---|---|
| 2:07, 6:07, 9:07 a.m.; 4:07, **10:07 p.m.** | Source-backed forecast archive, recheck old finals and freeze only still-future picks |
| 2:47 a.m.; 6:47 a.m.; 10:17 a.m.; 5:17 p.m.; **10:47 p.m.** | Website rebuild: NCAA Elo, upcoming fixtures, current ESPN finals, model reports |
| 3:41, 7:41, 11:41 a.m.; 6:41, **11:41 p.m.** | Independent archive watchdog; dispatch safe recovery only when stale |

The existing archive-success `workflow_run` Pages trigger remains,
so a successful source-backed archive may cause an extra website refresh.
`GITHUB_TOKEN` archival commits alone must not be assumed to trigger
GitHub push workflows; scheduled and `workflow_run` backups remain.

**Important:** These are best-effort GitHub times, *not* a continuously
running sports stream. A game ending after 10:47 p.m. might first appear
on the overnight run; source outages, delayed ESPN updates and GitHub
scheduling can cause further delay. A browser-tab refresh checks for
newly published source data—it cannot create a new server deployment
or force a basketball provider to update its scores.

## Verification and rollback

```powershell
$env:PYTHONPATH="research"
py -m unittest discover -s research/tests -p "test_recent_finals.py" -v
py -m unittest discover -s research/tests -p "test_nightly_automation.py" -v
py -m unittest discover -s research/tests -v
cd web
npm install
npm run typecheck
npm run build
npm run test:e2e
```

The browser E2E suite injects source fixtures to confirm the scoreboard
renders a newer independently ESPN-confirmed final while the NCAA rating
snapshot remains older, and it verifies an explicit refresh updates visible
results without changing the already-frozen original pick ledger.

Production verification after merge requires a green updated Pages
workflow, green CI and ideally an actual source-ready
`recent-finals.json`. Inspect the URL under GitHub Pages
`/current/recent-finals.json` for `generatedAtUtc`, compare
`mostRecentEspnFinalDate` with `ncaaResultsThroughDate`, and inspect
`sourceWarnings`. Do **not** claim that same-day ESPN games have updated
Elo until the separate NCAA accepted-result date advances.

## Scientific limitations

The ESPN final score display is a convenience for seeing games promptly,
not a new input into the active predictor. Its origin is a single ESPN
status source, whereas prospective grading still demands ESPN and NCAA
confirmation. The source includes ESPN listed timestamps rather than a
second independent actual tipoff clock. The NCAA feed may lag or omit
non-Division-I games, and exact source identity joins can be incomplete.
Do not treat `ncaaRatingInputConfirmed=false` as proof the ESPN score is
incorrect; it only means the required exact NCAA source match is absent.
