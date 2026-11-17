# v1.0 Prediction Intelligence — implementation and validation

This milestone extends **v0.9** rather than changing the underlying provenance, immutable forecasts, or model promotion criteria.

## 1. Game matchup intelligence

The real-game Game Center shows a paired descriptive analysis of team strength:
- **Elo**: team rating as of the published current-season dataset.
- **Recent form**: pre-existing `trend` indicator, not a separately fitted coefficient.
- **Opponent quality**: team-level average earlier opponent Elo when available.
- **Adjusted offense/defense**: source-linked possession metrics when present; lower adjusted defensive points allowed is better.
- **Tempo**: source-linked possessions per game when available.

The comparison is a descriptive view; bars have metric-local ranges so their lengths **cannot** be compared between metrics. No missing metrics are imputed. Home-court adjustment and actual publisher model selection remain in the original Game Center report. This avoids claiming that explanatory factors are additive Elo or learned coefficients.

## 2. Real archived prediction science

`research/forecast/performance.py` now outputs:
- `confidenceBands`: three exclusive groups for the original favorite confidence, [50%,60%), [60%,75%), [75%,100%].
- `coinFlipBrierSkill`: 1 - observed Brier / 0.25; **negative values are valid** and indicate worse-than-uniform probabilities.
- `rolling25`: chronological score of the most recent 25 genuine settled **first picks**, at each step after game 25.

These fields are absent or empty honestly when there are insufficient settled games. The display does not conflate training replay scores and first-archived game predictions. It does not change any model promotion rules; v0.9 remains strict: model comparisons must use genuinely archived same-game probabilities, date-frozen validation, and enough forward evidence. Never use outcomes to revise public pregame snapshots.

## 3. Controlled tournament scenario

The historical bracket laboratory now supports a *counterfactual* sensitivity experiment:
1. Run an original seeded bracket simulation on real historical entrants.
2. Choose exactly one team and shift its `projectedRating` by -150 to +150 Elo.
3. Construct a **new** field through `buildFieldFromSlots`, preserving every team ID, regional position, opening round and other team rating.
4. Re-run with the same simulation count and pseudorandom seed.
5. Display the largest differences in championship probability as percentage-point changes.

Both simulations use the same random seed, which reduces much of the noise of independent experiments but does not eliminate path-dependent Monte Carlo variation. The simulated national-semifinal pairings remain illustrative W–X / Y–Z unless an actual year's pairings are sourced. This **is not** the as-yet-unselected 2027 official field, a selection forecast, or a verified future game probability.

## 4. Operations and ongoing safeguards

Scheduled GitHub Actions remain the archive and data source of truth. The static website is not a streaming live feed. Operators should inspect:
- [Actions](https://github.com/dokeefe414/March-Madness-Forecasting/actions) for CI, publishing, pregame archive and archive-health workflows.
- [Archive health](https://dokeefe414.github.io/March-Madness-Forecasting/current/archive-health.json) for a published status that can be **missing**, **stale**, **source-partial** or **current**.
- [Public forward accuracy](https://dokeefe414.github.io/March-Madness-Forecasting/?view=predictions) for settled forecasts, not historical replay.

The scheduled archive-health check now has a de-duplicated GitHub Issues alert: if its evidence-age or audit check fails, it creates one open **Forecast archive health needs attention** issue containing a workflow link and recovery instructions (requires repository Actions issue-write permission). Existing open recovery issues are reused rather than spawning duplicates. An issue is a notification only: it does not assert that any public forecast was valid, nor automatically fabricate missing picks. A failed/silent archive cannot be repaired by backfilling a pregame percentage after tipoff. See [v0.9 forecast operations](v09-forecast-operations.md) for fail-safe source recovery and immutable archiving steps.

## 5. Regression and reproducibility

Run:
```bash
PYTHONPATH=research python -m unittest discover -s research/tests -v
cd web
npm ci
npm run typecheck
npm run test:bracket
npm run build
npm run test:e2e
```

The new Python tests assert that no-data means no score, a wrong 90%-confidence first pick produces negative Brier skill, and correct bins are assigned. Tournament tests assert that a rated-field perturbation does not modify the original data, maintains a valid 64-team structure, and has deterministic seeded Monte Carlo output.

**Acceptance standard:** CI green on the feature branch, responsive UI with no fake forecast outcomes, an honest empty-state when no real pregame archive exists, and source-backed bracket participants only.
