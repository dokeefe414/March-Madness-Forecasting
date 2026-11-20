# v0.7 — Nightly current-season retraining and chronological evaluation

## What runs automatically

The 2027 NCAA-derived dataset refresh already runs at **2:47 a.m. Eastern daily**, plus **6:47 a.m. Eastern** in season. v0.7 adds a **fitted outcome model**, not merely an updating team-rating curve. The 2:07, 6:07, 9:07 a.m. and 4:07 p.m. Eastern pretipoff archive/settlement workflow also regenerates the ratings and model before storing future forecasts. GitHub Actions times are best-effort. A source outage must fail rather than invent games.

**Source files:** `research/forecast/live.py` now optionally emits every accepted game under `web/public/current/2027-games.json`; this exact input is timestamp-linked to the 2027 Elo snapshot. `research/forecast/retrain.py` emits `web/public/current/2027-online-model.json`. Both are regenerated on deployment, not committed as stale data. The latter is publicly inspectable in the current-season dashboard.

## Model and features

A regularized logistic residual model learns from 2027 regular-season outcomes, keeping Elo as its base estimate:

```text
base_logit = ln(10) × (Elo_home + 65 − Elo_away)/400
x = [
  (Elo_home + 65 − Elo_away)/400,
  clip((bounded_recent_form_home − bounded_recent_form_away)/30, −1, +1),
  (wins_home+1)/(games_home+2) − (wins_away+1)/(games_away+2),
  1
]
P(home victory) = sigmoid(base_logit + coefficient_vector · x)
```

Form is computed from the team's existing *causal* Elo history; all features use **only earlier results**. The learner uses 100 full-batch gradient passes, learning rate 0.3, L2 coefficient penalty 0.08, and clips each coefficient to ±1. It does not assume that a more complicated model must beat Elo. No bookmakers, unsourced possessions, postseason results, coach or player data are inserted into the feature vector.

## Precise anti-leakage contract

1. Refuse the training run when accepted-game counts or retrieval timestamps disagree between the scored-game archive and Elo snapshot.
2. **Embargo all results dated on or after the current Eastern calendar date**. The schedule feed has dates but no universal trustworthy exact tipoff time or final-status flag. This excludes known current-day results even if their scores are already visible, for conservative as-of evaluation.
3. Group earlier games by date. Calculate **all** game-day features with the preceding day's Elo team states. Only **after** collecting their predictions and test scores update team ratings, form and records for that day. For the subsequent state's Elo updates use the existing baseline's deterministic winner/loser identity order as a disclosed proxy; it is not actual tipoff time.
4. After at least 160 preceding games across 10 preceding dates, refit on those earlier-date examples, predict the next full date's games, and record their baseline Elo and trained-model Brier scores. Move forward chronologically and repeat. No held-out date's outcomes are available to the coefficients scoring that date.
5. On each refresh, train final coefficients using all eligible previous-date games. Publish model weights, source retrieval timestamp, through-date, event sample sizes, last 20 individual evaluation receipts and a reproducible model fingerprint.

The new in-season Brier measurement is **retrospective rolling-date evaluation**, not a record of genuinely public pregame predictions. The timestamped pretipoff ledger is deliberately separate.

## Automated safety gate

The trained challenger is `shadow` until **all** of the following are true:

- At least **120** walk-forward evaluated games from **12** separate later test dates;
- Mean trained Brier beats baseline Elo on the same source fixtures by **at least 0.002**;
- A deterministic 500-draw bootstrap resampling *game-date blocks* has a lower 95% Brier-improvement endpoint above zero.

If evidence is insufficient or worse, the current active Elo stays operational. The job still retrains and publishes the candidate every run. **A passing gate permits manual review only:** the code deliberately never sets the logistic model to `active` during scheduled runs. Previously archived probabilities remain immutable. The 2027 logistic baseline-state replay uses the same capped score-margin game updates as the current source-aware Elo, including the prior-date embargo. No automatic use on neutral-site games (unvalidated venue shift). The report displays `evaluationGames`, `evaluationDays`, `modelBrierGain`, and `dayBlockGain95`; never claim a skill gain without its paired evaluation.

## Real pretipoff picks and preserved provenance

The archive workflow first rebuilds 2027 scores/ratings, then fits this model using the same retrieval snapshot. `forecast.snapshot` verifies the reported model source timestamp exactly matches the retrieved ratings and its training date is **strictly before** the ESPN-listed fixture's Eastern start date. Qualified picks store model name, model fingerprint and trained-through date. The [immutable prediction audit](forecast-audit.md) rejects model training on or after the game date and prevents later settlement from rewriting the original probability.

Displayed probabilities use the JSON snapshot's rounded Elo and trend fields, so they can differ negligibly from calculations using unrounded internal state. The separate historical tournament models remain trained only on earlier tournament years; 2027 regular-season retraining is not an NCAA selection or national-title predictor.

## Offline reproduction

```powershell
$env:PYTHONPATH="research"
py -m unittest discover -s research/tests -p "test_retrain.py" -v

# Following generation of the exact scored-game and Elo snapshot:
py -m forecast.retrain --games web/public/current/2027-games.json --ratings web/public/current/2027.json --out web/public/current/2027-online-model.json
```

CI tests date-order exclusions, same-day leakage, before-date training counts, probability bounds, promotion eligibility, model source-match checks, and whether immutable picks identify the actual model used.

## Limitations and ongoing research

- The NCAA-derived source publishes scored games, not a fully authenticated final-state stream. Positive in-progress results can be mistaken upstream; the same-day training embargo and next-morning catch-up reduce risk but cannot provide source authenticity.
- Tournament and regular-season Brier scores belong to different populations, so they should not be compared as if measured on identical games.
- Bootstrap intervals are descriptive and within-season. They cannot guarantee future performance, and the candidate may be demoted.
- A schedule timestamp is not a certified actual tipoff time; missing or ambiguous cross-provider program identity still prevents a pick.
- Automatically fitting a new learner is not evidence that it is active. Verify `mode` in the published JSON. Do not describe a shadow model as the operational predictor.
- This is one bounded model class with fixed hyperparameters. Genuinely new ML methods and cross-season learning need separate leakage-safe research and validation.


## v0.8 independent forward-pick activation gate

The earlier chronological 160/10 minimum training and 120 games/12 days Brier bootstrap comparison remains necessary, but now **cannot alone promote a trained model**. The scheduled `forecast.retrain --ledger web/public/forecasts` command reads the public immutable snapshot/settlement archive, counts the earliest first-published forecast of each ESPN event, and requires **at least 100 unique actually settled games** that had both Elo and the shadow logistic probabilities frozen before listed tipoff. Their paired forward Brier must improve by >=0.002, span at least 12 independent dates, and have a positive date-block lower 95% confidence bound for the model to become **eligible for review only**; it will not auto-replace Elo.

The `forwardValidation` public report has status, paired game count, Elo and challenger Brier, comparison gain and reason. It may remain `shadow` for an extended time. A wrong pick is never manually corrected in the archive or used for today's features; only new previous-day source results enter the next fitted model. This is *not* guaranteed improved accuracy. Full distinctions between historical-date scores and publicly archived forward picks: [forward performance](forward-performance.md).


## v0.9 normal overnight adaptation and no miss-specific overfitting

The operational Elo/logistic switch still requires the prior-date chronological gate **AND** actual, independently settled, earliest-publication pregame paired evidence. A wrong favorite cannot make the next prediction artificially perfect; only sourced outcomes dated **strictly before** the prediction's Eastern game date influence its training. The archive's new completed-status and exact-score final verification are required before a published miss enters prospective grading. A separate opponent margin-residual model and adaptive Kalman-style state-space challenger have been added as strictly **research-only** candidates with their own retrospective and genuinely forward paired Brier reports. See [new model mathematics](v09-model-validation.md) and [archive operations](v09-forecast-operations.md).


## Source-aware Elo update parity (Nov 2026)

The `forecast.retrain` replay calculates its daily score-margin-adjusted team-Elo changes from the exact same formula as `forecast.live`: baseline K=24, recorded home=65 Elo, and a capped logarithmic score margin factor. Every source date is evaluated before that date's changes are applied, and the date's updates are accumulated without leaking earlier-listed same-day results. This prevents training the logistic residual correction against a different classic Elo state than the one used for published current-season probabilities. See [game-aware Elo mathematics and limitations](game-aware-elo.md).


## v2.5: More timely source-verified training, same conservative model gate

The daily `2027-games.json` training corpus is now reconciled from
original NCAA results plus ESPN `STATUS_FINAL` records only where both
teams have explicit source-authored, same-season ESPN IDs. The previous
NCAA one-to-two-day release lag no longer necessarily blocks all rated
results from the preceding night. ESPN-only scores are recorded in
`espn-final-receipts.json` and are deduplicated against NCAA catch-up;
`sourceReconciliation` documents quarantined disagreements.

All challenger model recomputation uses the newly accepted game corpus.
A retrospective replay of newly imported older games cannot prove the
game was known on the timestamp of an old archived forecast. Independent
**actual prospective** scoring and the non-automatic promotion gate stay
unchanged: original first-published snapshots are immutable, and their
correctness still requires separately matching ESPN and NCAA finals.
See [daily Elo v2.5](daily-elo-2026-11-19.md).
