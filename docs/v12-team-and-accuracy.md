# v1.2 — Verified outcomes, teams, fair models, brackets and accessible web app

## Release principles
All real-world prediction claims must originate from original before-tipoff immutable snapshots and independently verified final scores. New comparisons, bracket picks and static application features **cannot** rewrite or backfill original predictions.

## 1. Settlement observability and catch-up
`research/forecast/settlement_health.py` reads the repository's immutable `forecasts/snapshots/*.json` and `forecasts/settlements/*.json` and the derived public index. It outputs `current/settlement-health.json` during Pages deployment. It keeps distinct counts for still-future archived entries, games less than five hours after listed start, entries five to 48 hours after listed start pending independently verified finals, and entries older than 48 hours requiring investigation.

These are **snapshot entries**, not necessarily independent games; the report separately shows unique first-pick and settled game counts. The 48-hour threshold is an investigation queue, **not evidence of an error**, cancellation or finished event. Started games are not auto-scored. The existing settlement evaluator still insists upon a matching scheduled Eastern date, home/away identity, uniquely sourced NCAA final, and matching independently completed ESPN final with identical score. A published archive health report cannot prove that source APIs are infallible or confirm actual tip-off.

The archive job now revisits up to 12 earliest unresolved Eastern game dates from a rolling 45-day window, plus recent final dates; this avoids permanently abandoning a late result after only 10 days while limiting ESPN requests. No speculative score is inserted. Previously settled snapshot keys are excluded. If the source is unavailable, it remains unresolved and the verified audit policy stays in force.

**Operations:** compare the `current/settlement-health.json` status with [GitHub archive workflows](https://github.com/dokeefe414/March-Madness-Forecasting/actions/workflows/archive-pregame.yml), inspect the source's listed start and actual rescheduling, and check NCAA vs ESPN outcomes. Do not delete a missing original snapshot or manually create a retroactive settlement.

## 2. Team intelligence
`?view=teams` loads the generated, source-linked `current/2027.json`, `current/2027-games.json`, and `current/upcoming.json`. The user's search selects one actual current-season team and displays current Elo, wins/losses, form, a time-series rating curve, average opponent Elo, source-backed offensive/defensive efficiency, recent scored contests and scheduled upcoming matchups where the same verified source team ID is available.

Absent efficiency metrics remain unavailable. Records are chronological from NCAA-derived accepted games, not simulated results. Buttons select comparable teams. Shareable links use `?view=teams&team=<canonical-source-linked-team-id>`; no account or database required. The site does not claim injury, lineup or betting-market information.

## 3. Forward model evidence
The Model Lab adds a table of **genuinely settled, paired first-pick** challenger comparisons against Elo. Each candidate's Brier and the reference Elo Brier are calculated from the same exact games; candidate gain is Elo minus candidate Brier (positive favors candidate). When available, date-block bootstrap intervals resample days rather than treating all games as independent. Small samples explicitly show insufficient evidence.

Calibration bins compare original confidence vs observed favorite success. Historical prior-date Bayesian shrinkage, residual stumps, Kalman variants, opponent-aware Elo, and logistic research cannot automatically become the active deployed model without the existing forward validation and promotion gates.

## 4. Historical bracket pick'em
The [Bracket Lab](https://dokeefe414.github.io/March-Madness-Forecasting/?view=bracket) now includes `BracketBuilder` after a complete, sourced historical seed field successfully loads. It respects verified 64/65/68-team and future explicit 76-entrant slot structures, including opening-round player selections. Users choose winners at each stage. A later match waits for both predecessor picks, eliminating invented participants.

Selections are locally persisted in browser storage per year. **Copy Scenario Link** encodes only valid picks into a URL query; recipients can explore that same hypothetical outcome without login. Each new click invalidates a previously selected downstream champion in the UI unless the selection is still reachable. Reset clears local picks. No shared cloud persistence is implied.

The generic historical W–X / Y–Z Final Four crossover is a documented scenario assumption; season-specific national semifinal placements must be separately sourced before any official bracket claim. Selection-day 2027 field participants, seeds and champion are never fabricated. User picks are not included in actual forecasting accuracy.

## 5. Mobile/PWA
A static `manifest.webmanifest` points to the public GitHub Pages base path, and a scoped service worker enables a best-effort offline page shell on HTTPS. The worker intentionally **does not cache** forecasts, JSON, or current ratings; when offline, their retrieval fails visibly rather than presenting stale odds as current. A service worker is not a background-score updater, notification subscription or guarantee of platform installation. Browser installation UI and SVG icon support differ by browser/platform.

All main mobile navigation uses the same shareable `?view=...` query as desktop. The web app supports keyboard skip navigation, responsive overflow handling, and reduced-motion preferences.

## Test commands
```bash
PYTHONPATH=research python -m unittest discover -s research/tests -v
PYTHONPATH=research python -m forecast.settlement_health --ledger web/public/forecasts --out web/public/current/settlement-health.json
cd web
npm install --no-audit --no-fund
npm run check:data
npm run test:bracket
npm run typecheck
npm run build
npm run test:e2e
```

CI checks source integrity, chronological models, production types/build and browser/mobile accessibility. Dedicated v1.2 tests cover pending-before-tipoff, delayed unverified, fully settled, and empty-ledger health diagnostics, plus team browsing, round selection, and app manifest.

## Production acceptance
A green PR build is insufficient to claim actual ongoing result settlement. Check immutable Git history, verify the live `settledUniqueGames` count only rises on independent finals, and distinguish source-eligible matching from delayed/missed results. The archived pick ledger remains the source of truth; the website is a published snapshot, not a real-time betting-odds platform.

See [v1.1 operations](v11-season-intelligence.md), [forecast audit](forecast-audit.md), [forward evaluation](forward-performance.md), and [state-space research](state-space.md).
