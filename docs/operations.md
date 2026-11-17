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
