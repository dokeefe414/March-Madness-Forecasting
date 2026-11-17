# v0.7 — Nightly current-season retraining and chronological evaluation

## What runs automatically

The 2027 NCAA-derived dataset refresh already runs at **1:00 a.m. Eastern daily**, plus **5:17 a.m. Eastern** in season. v0.7 adds a **fitted outcome model**, not merely an updating team-rating curve. The 9:07 a.m. Eastern pretipoff archival workflow also regenerates the ratings and model before storing future forecasts. GitHub Actions times are best-effort. A source outage must fail rather than invent games.

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

If insufficient evidence or worse performance, Elo stays operational. The job still retrains and publishes the candidate every run. If the gate later passes, `mode: active` permits the candidate for new **non-neutral future** picks. If it no longer passes, the next pretipoff snapshot returns to Elo; already archived probabilities remain immutable. No automatic use on neutral-site games (unvalidated venue shift). The report displays `evaluationGames`, `evaluationDays`, `modelBrierGain`, and `dayBlockGain95`; never claim a skill gain without its paired evaluation.

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

The earlier chronological 160/10 minimum training and 120 games/12 days Brier bootstrap comparison remains necessary, but now **cannot alone promote a trained model**. The scheduled `forecast.retrain --ledger web/public/forecasts` command reads the public immutable snapshot/settlement archive, counts the earliest first-published forecast of each ESPN event, and requires **at least 40 unique actually settled games** that had both Elo and the shadow logistic probabilities frozen before listed tipoff. Their paired forward Brier must improve by >=0.002 for the learned model to become operational.

The `forwardValidation` public report has status, paired game count, Elo and challenger Brier, comparison gain and reason. It may remain `shadow` for an extended time. A wrong pick is never manually corrected in the archive or used for today's features; only new previous-day source results enter the next fitted model. This is *not* guaranteed improved accuracy. Full distinctions between historical-date scores and publicly archived forward picks: [forward performance](forward-performance.md).
