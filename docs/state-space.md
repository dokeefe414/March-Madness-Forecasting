# v0.8 — Causal Gaussian team-strength filter (experimental)

## Motivation

Elo updates a single point estimate of team strength. Under a season with changes in players, opponents and performance, we also want a model that tracks uncertainty and responds to unusual observed margins. `research/forecast/state_space.py` supplies a small, deterministic **Kalman-style** two-team latent skill filter as a research challenger — not an unverified claim to beat Elo.

For team i, before game n, the latent state is `N(mean_i, variance_i)`; initially, mean 1500 and variance 150². Every observed game adds a fixed process variance `Q=18²` to both participants.

For a game with home-score margin `m`, the noisy observed team-skill difference is assumed:

```text
z = clamp(18 × m, −400, +400) − 65
e = z − (mean_home − mean_away)
S = var_home+Q + var_away+Q + 250²
K_home = (var_home+Q) / S
K_away = (var_away+Q) / S
mean_home(new) = mean_home + K_home × e
mean_away(new) = mean_away − K_away × e
var_home(new) = max(250, (var_home+Q) × (1−K_home))
var_away(new) = max(250, (var_away+Q) × (1−K_away))
```

These are **explicit modeling assumptions** about points-to-Elo conversion, observation noise and home advantage. They are not parameters estimated from actual NCAA possession data. The filter is a genuine Gaussian uncertainty recursion under those assumptions, but the distribution of scores is not guaranteed Gaussian and the win probabilities remain a logistic strength heuristic.

A large normalized observation innovation `abs(e) > 2.5 × sqrt(S)` adds a **shock flag** to both affected teams; this is an interpretable sensitivity indicator, **not** a statistically confirmed independent injury/roster change point. The report includes `shockFlags`, latent mean, standard deviation, last dozen skill states and latest mean change.

## Strict chronological validation

All source games dated on or after the **current Eastern calendar date** are excluded. For each earlier date, **all pregame skill estimates and probabilities are evaluated before any score on that date updates the filter**. Identical dated games are used for both the state-space and Elo baseline's date-frozen comparison. Reported `brier` and `eloSameDayBrier` are retrospective and are explicitly NOT real archived-before-tipoff evidence.

This is a separate `mode: research-only` JSON artifact at `/current/2027-state-space.json`, regenerated each nightly deployment from the exact same `retrievedAtUtc` source. No state-space forecast becomes the website's operational choice solely by existing: if the paired before-tipoff evidence is unavailable, the system continues to use Elo or its chronologically approved logistic model.

## Integration and reproduction

```powershell
$env:PYTHONPATH="research"
py -m forecast.state_space --games web/public/current/2027-games.json --ratings web/public/current/2027.json --out web/public/current/2027-state-space.json
py -m unittest discover -s research/tests -p "test_state_space.py" -v
```

The Game Center research comparison shows a state-space hypothetical probability only if both teams have source-built latent states and the training date is earlier than the scheduled match. The pretipoff ledger also freezes it as an experimental comparison for later independent evaluation — **not** as the selected forecast.

Compare prospective reliability, drift and delayed-release sensitivity before considering a subsequent model promotion experiment. Do not conflate a big latent mean movement with a certified change point or explain a miss using an injury never verified in the source.


## v0.9 innovation-driven adaptive candidate

The original **fixed** Kalman-style model is retained as a control. A *second, independently evaluated* adaptive state filter starts from the same baseline assumptions and source date. Both predictions are frozen before any game-day result is incorporated. The adaptive candidate tracks each prior game's standardized innovation `e/sqrt(S)`.

A watch opens only when **two of the last three innovations** have the same sign and magnitude at least **0.8**; the team's *next* process-noise contribution multiplies by **2.5** (baseline `18²`). The watch clears after persistent evidence stops. An isolated spectacular loss never causes an instant permanent skill or probability edit. Per-team `recentStandardizedInnovations`, `driftWatch`, `driftWatchEpisodes`, latent mean/uncertainty, and `adaptiveStrengths` appear in the public source report. `adaptiveBrier` versus `eloSameDayBrier` are evaluated on the **same date-frozen cases**, and `recentSevenDatesBrier` reports the newest matching cohort.

This remains a **heuristic watch**, not a tested statistical change-point detector or proof that a player's injury, coaching or roster change occurred. Neither fixed nor adaptive model is automatically the real headline probability. Both may be frozen before tipoff as research alternatives so actual forward comparisons can begin. [Detailed equations and validation](v09-model-validation.md).
