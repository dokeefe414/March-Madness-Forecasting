# v0.6 — Real browser, responsive, accessibility and visual regression checks

## Why actual browsers

A Next.js typecheck and static export can both succeed while navigation clicks, small-screen overflow, data unavailable states or keyboard accessibility fail. The v0.6 CI adds a Chromium Playwright smoke job across **1440×900 desktop** and **390×844 mobile**. Browser tests are additive to Python unit tests, historical source validation and TypeScript bracket invariant tests.

Files:
- `web/playwright.config.ts`: Chromium browsers, deterministic viewport sizes, serialized workers and production-exported web server.
- `web/e2e/platform.spec.ts`: 3 checks × 2 widths = 6 scenarios.
- `.github/workflows/ci.yml`: a dedicated browser job; publishes PNG and trace artifacts on completion.

## What is actually verified

1. Client hydration is confirmed via `main[data-hydrated="yes"]` before any interaction. This prevents clicking server-rendered HTML before React has attached handlers.
2. Navigation transitions through 2027 Pulse, Field Watch, Picks Ledger, Research, Historical, Matchups, Bracket and Archive.
3. Historical bracket simulation runs for the fixed, verified historical source field and produces a real result container.
4. On every tested tab, `document.documentElement.scrollWidth <= clientWidth + 3px` ensures no significant full-page horizontal overflow.
5. An `@axe-core/playwright` WCAG 2A/AA/2.1 scan on the watchlist screens checks **zero critical** violations. This is a limited automatic scan, not complete proof of accessibility.
6. Screenshots and failure traces are uploaded to GitHub Actions under `playwright-v06-visual-checks`. Golden image snapshot comparisons are **not** yet established, so do not claim automated pixel-perfect visual regression.

### Why the E2E runs against the static export

Early CI iterations served `next dev`, which generated server HTML but encountered failing Turbopack HMR WebSocket handshakes during tests, and client hydration wasn't available within the test window. The E2E harness now builds the **same static export** used by GitHub Pages and serves `web/out` via Python's localhost HTTP server, with one Chromium worker at a time. This avoids dev HMR and is closer to the deployed artifact. It also prevents tests from passing on HTML-only static content that cannot respond to clicks.

The browser artifact revealed a concrete **390px mobile width overflow** on the Predictions Ledger header's nowrap research pill. This was fixed by wrapping title and badge at <=650px; the overflow regression remains in CI.

## Reproduce on a Windows development machine

```powershell
cd web
npm install
npx playwright install chromium
npm run test:e2e
```

Python 3 must be runnable from `python3` in the shell used for the Playwright `webServer`. On Windows, if `python3` is unavailable but `py` works, run the exported site separately with `py -m http.server 3100 --directory out` after `npm run build`, and Playwright will reuse the active server for your local tests. In CI, Ubuntu's Python 3 is used.

To see interactive traces, download the `playwright-v06-visual-checks` GitHub Actions artifact and run `npx playwright show-trace <trace.zip>`. A screenshot is supporting evidence, not a substitute for interaction and model unit checks.

## Manual quality gate still required

Review the deployed page on real desktop and mobile browsers at 375, 390, 768, 850 and 1440px; check heading legibility, focus/keyboard navigation, 200% zoom, contrast, reduced motion, simulated bracket performance, data freshness and source labels. CSS and browser automated checks are not a guaranteed professional UX assessment. Do not merge a large visual change if new E2E smoke checks fail.
