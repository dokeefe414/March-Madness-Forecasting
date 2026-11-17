# v0.8 — Genuine forward accuracy, immutable misses and adaptive learning

## Accuracy must mean real games that were picked before they started

The public `Accuracy & Picks` view counts only source-verified, Git-archived forecasts created before the ESPN *scheduled* start with a 15-minute buffer, then settled later against NCAA-derived scored results. This is categorically different from the platform's retrospective 2027 replay or the 35-year historical tournament experiment.

A scheduled event may appear in more than one archived snapshot. To avoid duplicate counting or cherry-picking the best late model update, v0.8 chooses the **earliest archived pretipoff snapshot of each ESPN event ID before looking at the outcome**. Only a settlement for that frozen first snapshot contributes to headline winner accuracy. If a later forecast settled but the first did not, the event remains unscored in that unique-game measure. No sample is padded with guesses, retrospective predictions or fixtures without source verification.

```text
winner accuracy = (number of correctly picked winners + 0.5 × exact-even-odds picks) / settled unique games
Brier = mean((predicted home win probability − observed home win indicator)^2)
log loss = −mean(log(probability assigned to observed outcome))
```

If no genuine predictions have settled, the UI shows **—**, not 0%, 50%, or 100%. Model-specific accuracy is calculated only for games actually picked with that model. The older `scores` aggregate remains accessible for *all* archived snapshots and is explicitly distinct from the first-pick, one-game-one-vote score.

## Audit and code

`research/forecast/performance.py` derives `uniqueGames` from immutable `snapshots/*.json` and `settlements/*.json` during `forecast.snapshot.write_ledger`. `research/forecast/audit.py` independently rebuilds the new aggregate and rejects any mismatch with the published `forecasts/index.json`, as well as existing score/timestamp and original probability checks. This is a public calculation, not secret back-office grading.

The derived report includes `forecastedUniqueGames`, `settledUniqueGames`, `score`, `byModel`, an earliest-pick cumulative `trajectory`, confidence/`calibration` bins, last twelve `recentMisses`, and **paired models evaluated against the exact same observed game**. Confidence bins compare the favorite probability with realized favorite win frequency. Small samples, especially buckets with few games, are unstable.

## Learning from wrong calls without cheating

A correct prediction never guarantees the next game; misses are not bugs that can be automatically erased.

Every settled miss stays in the public history with its original model, probability, date and actual result. The site highlights high-confidence upsets and moderate/toss-up losses, but **does not invent a causal explanation** (e.g., undocumented injuries or fatigue) simply because a team lost.

At subsequent scheduled refreshes:
1. Newly accepted results enter the current-season game sequence.
2. The date-ordered logistic retraining runs from **previous Eastern game dates only**, with the current day embargoed.
3. Retrospective rolling-origin performance is evaluated on future calendar dates relative to each training cutoff.
4. The pregame archive separately records **both** the actual headline pick and Elo vs learned-model shadow probabilities while the game is still in the future.
5. The learned model may become operational for future non-neutral picks only if its historical-date Brier/date-block gate **and** genuine first-pretipoff paired comparison gate pass. The latter requires **at least 40 distinct settled paired games** and a prospective Brier improvement of **at least 0.002** on those same games.

This is **adaptive**, but not "patch every miss to win in hindsight." The original forecast remains unchanged. A model may be demoted when updated evidence weakens its case; current-day results never enter that day's model features. This method does not promise accuracy gains. It is a bounded regular-season model, not automatically a tournament calibration.

## Frozen research challengers

Each new pick may include:

- `homeWinProbability`: the single operational model's actual selected probability.
- `baselineHomeWinProbability`: independently frozen Elo for the exact same game.
- `challengerHomeWinProbability`: source-matched future-only logistic candidate, even while it is in **shadow** mode. Never claim shadow predictions were the operational choice.
- `stateSpaceHomeWinProbability`: a **research-only** uncertainty-aware state-space experiment, on the same sourced matchup if the prior-date state is available.

The earliest archived predictions and their source timestamps permit later comparison without looking ahead. A historical re-run can evaluate a model class but **cannot** retrospectively publish credible pretipoff picks.

## Practical limits

- The NCAA-derived schedule publisher does not authenticate an actual final-status flag for every nonzero, unequal score. Live status is not independently confirmed by the latest site refresh, and corrections may arrive later.
- ESPN's scheduled tipoff may change due to postponement. The previously committed schedule is proof of what was reported at prediction capture, not incontrovertible proof of actual start.
- The settlement joins on exact canonical home/away and Eastern calendar date; a renamed/rescheduled game may remain unsettled rather than being attached to the wrong result.
- The minimum 40 paired games is only an operational threshold. It does not guarantee statistical significance or future superiority.
- The published static site is eventually consistent with daily GitHub Actions and source availability; do not advertise as an instant live API.
- At next year's season boundary, models need an explicit sourced 2028 migration.

Use `PYTHONPATH=research python -m unittest discover -s research/tests -v` and `PYTHONPATH=research python -m forecast.audit --dir web/public/forecasts` to verify the implementation.

Code: `research/forecast/performance.py`, `research/forecast/audit.py`, `research/forecast/retrain.py`, `research/forecast/snapshot.py`; UI: `web/components/ForwardScorecard.tsx`, `ForecastTracker.tsx`, `OnlineLearning.tsx`.
