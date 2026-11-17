# v1.3 — Prospective reliability, causal forecasting research and bracket competition

## Scope and decision rule

v1.3 adds operational transparency, substantive learned challengers, two-person bracket play, evidence-based research visualizations, and mobile accessibility. **It does not claim to outperform Elo on real future games unless there are independently settled earliest-snapshot observations that establish that result.** Existing pregame picks, source timestamps and final-score proofs are never rewritten by these features.

## 1. Production forecast reliability

### Recorder evidence

The active archiver continues to run at 09:07 and 16:07 Eastern in basketball months, and can be manually dispatched. GitHub Actions' scheduler is best effort. The archive's latest `index.json` is derived from exclusive-create immutable snapshot and settlement files and audited against source time buffers and score arithmetic before commit.

The v1.3 `forecast.operations` builder produces `current/operations.json` with:

- Date of latest source-verified archived capture and calculated age from the build clock
- ESPN events checked, unmatched/ambiguous events, source-day warnings
- Unique ESPN event IDs and additional immutable snapshots per ID (repeat captures are allowed; first snapshot governs genuine unique-game forward score)
- Independently settled unique games and unresolved snapshot entries exceeding 48h since **listed** start (review, not proof of cancellation or failure)
- A visible checklist for feed availability, archive freshness, final verification backlog, repeated captures and observed schedule-time changes

`forecast.snapshot.detect_schedule_changes` compares each original archived ESPN event ID against **only the scoreboard days actually fetched in the current archiver run**. If the provider reports the same ID with a different start, the derived index records `archiveHealth.observedScheduleChanges` for review. It never overwrites the original forecast, changes its scheduled date, or labels a postponed game as settled. If an event disappears from fetched scoreboards, the state is unknown—not automatically canceled.

The existing source-paired settlement rule requires an unequivocal NCAA result matching the original Eastern date/home-away and an independently confirmed ESPN completed final with identical score. Because a changed official game date fails that rule, the record appropriately remains unresolved pending explicit future policy, not silently scored. This constraint sacrifices recall to preserve prospective claim integrity.

The existing GitHub monitor checks age, audit files and source warnings and opens a de-duplicated recovery issue on missing/stale evidence. The public operations panel is a **static source receipt**, not an independent live probe of GitHub infrastructure or ESPN availability. Never infer perfect health from a successful website build.

### Operational response

Check [the archive workflow](https://github.com/dokeefe414/March-Madness-Forecasting/actions/workflows/archive-pregame.yml), [the monitor](https://github.com/dokeefe414/March-Madness-Forecasting/actions/workflows/monitor-archive.yml), the archived `index.json`, and the public Operations panel. For an unresolved over-48h row, examine ESPN event status, updated start time, NCAA score and team identity; postpone claims if they do not match. Run `PYTHONPATH=research python -m forecast.audit --dir web/public/forecasts` to verify original evidence. **Do not** retroactively record a probability, guess a score, force-push archive history, or silently substitute a postgame model probability for the original first forecast.

## 2. Two substantial research-only model implementations

`research/forecast/advanced_models.py` produces `web/public/current/advanced-models.json` from source-consistent `2027-games.json` and ratings generated in the same Pages run.

### Gradient-boosted CART ensemble

This is a *trained decision-tree ensemble*, distinct from v1.1's fixed two-leaf gradient stumps:

- Four frozen pregame signals: pre-date Elo difference / 400, exposure difference / 20, smoothed prior win-rate difference, and bounded combined prior game count
- Base probability is the Elo logit `log(p_Elo / (1-p_Elo))`, never fitted from a held-out outcome
- Train a 12-tree Newton-boosted ensemble of **depth-two CART trees** from previous-date saved features and results; each leaf estimates `sum(y-p) / (lambda + sum(p(1-p)))` with ridge `lambda=12`
- For each split, maximize second-order gain across numeric feature thresholds with minimum 12 samples per leaf
- Shrink each tree by a fixed learning rate 0.12
- Refit no more often than every **seven previous game days**, and only after at least 60 prior scored observations

Each current calendar day's predictions are computed from the pre-date Elo and previous-days-only ensemble; only **after that entire date is scored** do the outcomes update Elo and training history. A current-day final cannot change another prediction on that date. Tree depth, bin constraints, regularizer and refit schedule were chosen as research assumptions, not tuned for best observed tournament Brier. There is no production automatic promotion.

### Approximate Bayesian Bradley–Terry Gaussian skill filter

Each team starts with skill prior `N(1500,200²)`; home-court adds 65 Elo points and win probability comes from a logistic link. A Gaussian-logistic moment-matching approximation attenuates extreme predictions when either team's skill is uncertain. After a complete day's forecasts are scored, a **damped local Laplace/assumed-density update** changes the team's posterior mean and variance using the win/loss likelihood's gradient and curvature. Previous-date posterior means/variances alone drive the next date's predictions.

This is a genuine approximate Bayesian sequential rating method, but it is **not** an exact posterior, fully specified hierarchical model, posterior MCMC, a calibrated NCAA market estimate, or proof of improved predictive skill. Gaussian update order for multiple games on a date is also an approximation; the forecasts themselves remain date-frozen.

### Validation and promotion

The resulting JSON reports Elo, Bayesian Gaussian and fitted GBDT winner accuracy, Brier and log loss for **exactly the same games and date blocks**, as well as a per-date series and up to 80 frozen pre-update audit examples.

These are **retrospective chronological replay results**, even though models do not train on the evaluated day. They must never be labeled live publicly archived forecasts. Current operational Elo selection and the prior v0.9 promotion gates stay unchanged; promotion would require future new genuine archived shadow probabilities, robust confidence intervals, multiple dates and reproducibility without changing first-pick history.

## 3. Two-player historical bracket competition

The `BracketDuel` view appears alongside the existing historical play-in/Round-of-64-to-champion picker and simulator. Two users (A and B) can pick winners independently, navigate seven stages, and switch competitors. The duel saves both boards in device-local storage; the Share action encodes both sets of decisions into a link after size checks and source-team validation. No registration is required.

**Fair comparison** counts only matchups where both competitors reached the same pair of entrants and chose a winner. Upstream differences that produce different downstream games are **not** falsely counted as agreements or disagreements. The visible disagreement list makes the comparison transparent. Both players can also compare their picks with a deterministic **Elo chalk** baseline: always advance the higher-rated historical seeded entrant on the same source field. Elo chalk is not a sampled future result and is not a prediction accuracy claim.

The existing W–X / Y–Z semifinal crossover remains a **generic scenario assumption** unless official specific-year semifinal pairings are verified. New 2027 entrants, seeds, and winners are never invented before the official field exists. The duel does not claim a real-game leaderboard or an online multiplayer backend.

## 4. Scientific visualization center

The Model Lab now includes a separate, explicit research visualization module:

- Chronological **research-only** per-day Elo/GBDT/Bayesian Brier curves and identical-date aggregate metrics
- Genuine pre-tipoff earliest-pick 25-game rolling Brier trajectory, withheld until evidence is available
- Original favorite-probability confidence and actual independently settled favorite-win rates by confidence bucket
- A selectable source-linked current-team Elo history curve

Research retrospective samples and prospective pre-tipoff samples are never pooled to fabricate a live improvement. The browser renders its plots from published numeric JSON and uses meaningful `aria-label` descriptions. Missing or incomplete data shows an honest empty state.

## 5. Usability, mobile and navigation

The mobile app now provides thumb-sized shortcuts for Games, Teams, Accuracy and Brackets above the full scrollable navigation. Every main navigation click updates a shareable `?view=...` URL, and browser back/forward restores the correct workspace. Existing skip-to-content support and no-login PWA remain intact. Research and operations views use responsive cards and labels and should remain usable at narrow widths without horizontal page overflow.

## Validation

Run from the repository root:

```bash
PYTHONPATH=research python -m unittest discover -s research/tests -v
PYTHONPATH=research python -m forecast.audit --dir web/public/forecasts
PYTHONPATH=research python -m forecast.operations --ledger web/public/forecasts --out web/public/current/operations.json
PYTHONPATH=research python -m forecast.advanced_models --games web/public/current/2027-games.json --ratings web/public/current/2027.json --out web/public/current/advanced-models.json
cd web
npm install --no-audit --no-fund
npm run check:data
npm run test:bracket
npm run typecheck
npm run build
npm run test:e2e
```

The current-season `web/public/current` outputs are constructed by GitHub Pages deployment and are not independently committed as source files; to run the two dynamic modules locally, first generate current ratings and games from `forecast.live`, with its documented source dependencies. Tests use offline synthetic source fixtures and must not depend on external ESPN or NCAA availability. Production acceptance requires a successful merged-commit CI and Pages workflow **plus ongoing independent archive and final-score checks**.

Additional details: [v1.2 team/accuracy specification](v12-team-and-accuracy.md), [v1.1 operations](v11-season-intelligence.md), [immutable forecast audit](forecast-audit.md), [state-space experiment](state-space.md).
