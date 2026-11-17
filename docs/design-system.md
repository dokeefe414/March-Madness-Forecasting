# Visual language, interaction, and accessibility

March Forecast uses a custom **after-dark basketball research studio** design rather than a generic dashboard template. Its visual identity makes every metric feel exciting without passing generated artwork or decorative numbers off as real scores.

## Design tokens

| Color token | Hex | Purpose |
| --- | --- | --- |
| `--bg` | `#070e16` | Dark midnight background |
| `--panel` | `#0e1b26` | Layered content surfaces |
| `--line` | `#25414a` | Deliberately subdued borders |
| `--mint` | `#a6ffce` | Calls to action, winning model signal |
| `--blue` | `#8bd8ff` | Secondary model comparisons |
| `--amber` | `#ffc47b` | Opening Round/caution indicator |
| `--red` | `#ff8f83` | Errors and unfavorable changes |

Headlines use **Barlow Condensed**, while body/control labels use **DM Sans**. Large condensed numbers, linear court-style grids and subtle rings build a recognizable sporting identity. The banners are CSS backgrounds and typography, not photo imports or simulated athlete imagery.

## Information architecture

Main tabs: 2027 Pulse → Historical → Matchups → Bracket → Research → Archive → About.

- **2027 Pulse** is the default page, because recent-season activity is the most actionable experience. A source-date card sits adjacent to its statistical content.
- **Historical** has a rich hero and source-note treatment. This large hero does not repeat on every other tab, reducing unnecessary vertical scrolling.
- **Matchups** uses high-contrast probability bars and comparative records.
- **Bracket** emphasizes a region selector, verified seed slots and an interactive progression probability spotlight.
- **Research** compares models first, then shows calibration/reliability, uncertainty and detailed holdout-year data.
- **Archive** retains source-specific actual final scores for historical inspection.
- **About** explains the transparent modeling boundaries.

## Responsive behavior

- Desktop max-width shell: 1540 px; sticky navigation minimizes lost scroll context.
- ~1200 px: compact header controls; bracket pairing grid becomes two columns.
- ~990 px: research/live/contender two-column analysis surfaces collapse to one column; side spotlights cease to be sticky.
- ~880 px: horizontal sticky navigation instead of dense desktop links.
- ~600 px: two-column metric tiles, single-column bracket fixtures and scorecards, condensed mobile table, no large decorative banner watermarks.
- Tables with many columns scroll horizontally instead of clipping values or hiding source metadata.

## Accessibility

Semantic navigation, keyboard-operable buttons, visible focus outlines and native labels remain mandatory. Probability visuals have numeric text in addition to bars. The calibration SVG has labeled confidence/accuracy axes and tooltips to make points interpretable. Color is **not the sole carrier** of win probabilities or good/bad changes; values are printed. `prefers-reduced-motion` disables transitions and decorative movement.

Some SVG visuals and tables need continued manual audit with screen readers. Before a release, check 375 px/850 px/1440 px layouts, browser zoom at 200%, keyboard focus order, color contrast, pointer interactions and loading/error states.

## Data integrity as a design requirement

- Never display a fabricated "live" ranking from demo team names.
- Current source status must show **latest included game date** and **UTC retrieval time** separately.
- Research scores come from `web/public/research/benchmark.json`, not a hard-coded chart.
- Historical results, unknown 2027 selections and Monte Carlo outputs must have distinct labels.
- External failures produce useful unavailable states rather than placeholder predictions.
- The future 76-team field is shown as a *format capability*, not a known selection.

CSS lives in `web/app/globals.css`; the complete component list and design ownership are in the root README.

## v0.6 editorial additions and source status

New studio workspaces: `SelectionLab.tsx` has an amber 76-slot motif, per-conference power cards, restrained provisional seed tiers, and a visible **source-coverage gate**. `ForecastTracker.tsx` has an ink-blue pregame receipt concept with locked timestamps, scored-result cards and separate unsettled status. `TeamTrend.tsx` is a focusable SVG trajectory of true sequential Elo updates, not a generic stock chart. `LiveSeason.tsx` adds three visibly separate evidence categories — NCAA team/conference source, independent 2027 Division I subdivision membership, and actual box-score possessions — with an honest empty state per source.

Responsive breakpoints progressively collapse from multi-column cards to one-column sheets under 990/730/500px. A Playwright test on real Chromium at **390px** detected an overflow from a non-wrapping "Immutable Forecast Archive" pill; fixed by allowing section headings and badges to wrap at 650px while preserving text legibility. The test remains in CI, rather than simply setting `overflow-x:hidden` to conceal the problem.

For sourced study, the chart and number labels must be independently readable without color. Keyboard focusable SVG points support Enter/Space and `title` values; a full screen-reader and 200%-zoom audit remains a manual review item.

Visual quality CI: [browser-quality.md](browser-quality.md).
