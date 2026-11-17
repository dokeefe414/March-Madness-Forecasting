# v1.5 — Stronger Score Models, Possession-Aware Estimates and Causal Comparison

## What is changed, and what is deliberately not changed

The *visible score predictor* now prefers real, current NCAA-derived team box possession rates and opponent-adjusted points per 100 possessions, provided both teams have at least five independently linked box-score games. It uses the verified average observed pace and symmetric adjusted offense/defense strengths; games without sufficient data use the previous labeled scoring-mean fallback. This improves the basketball-specific structure of the score calculation, but **does not itself prove more accurate predicted scores**.

The public forecast's winning team probability is **unchanged**. Elo, Bayesian and gradient-boosted challengers remain independently research-only until first-published future-game evidence justifies a promotion. No archived pregame probability, earlier game record, official tournament field or immutable settlement is modified.

## Model 1: Possession-driven opponent-adjusted score estimate

This calculation uses `web/lib/scoreProjection.ts` and the existing `forecast.efficiency.attach_efficiency` pipeline, which validates source contest IDs, source team names and plausible possessions (`o_poss`, `d_poss`) before using per-100 offensive/defensive rates. The per-team opponent-adjusted strength fields `adjOff100` and `adjDef100` are already shrunk through 12 iterations of opponent-adjusted ridge regularization corresponding to approximately 600 pseudopossessions. Current-year schedule/rating provenance is checked before game projections.

For sufficiently observed home H and away A:

```text
projected possessions = (H.sourcePace + A.sourcePace) / 2
source rate anchor = (H.raw ORtg + H.raw DRtg + A.raw ORtg + A.raw DRtg) / 4

home points = H.adjusted ORtg × A.adjusted DRtg / source rate anchor × projected possessions / 100
away points = A.adjusted ORtg × H.adjusted DRtg / source rate anchor × projected possessions / 100
margin = home points − away points
total = home points + away points
```

These are *projected scoring rates*, not statistically independent random samples, and the normalizing anchor is a source-derived approximation of a league environment, not a full measured league-wide parameter. The pace is a simple arithmetic mean of the two source paces, not an experimentally calibrated possession forecast. Score forecasts remain descriptive and explicitly venue-neutral—even for scheduled non-neutral games; there is no fabricated home bonus.

**Eligibility:** at least five source-recorded total games and five verified team-box possession games for each team; finite adjusted and raw offensive and defensive efficiencies; observed pace between 50 and 95; source efficiency anchor between 50 and 150; adjusted efficiencies between 35 and 200. If any prerequisite fails, use the preexisting points-scored/allowed mean method only if those source fields are valid; otherwise return no estimate. Do not use or infer unknown possession values. The UI labels which model was used and the prior sample coverage.

**Do not call the spread a sportsbook line**, even if it is represented as `Favorite − X`; there is no odds-provider feed or validated margin error distribution.

## Model 2: Causal source-score replay and independent validation

`research/forecast/score_research.py` separately trains a regularized additive opponent-adjusted **scoring-margin research model** on real NCAA-sourced completed final game scores. Since these scheduled scores do not contain possession-level box rows, this is a *score-only fallback research experiment*, not a dishonest simulated possession backtest.

For each game date D, fit previous-date completed scores only. The additive model assumes:

```text
expected_home = prior_league_average_points + prior_offense_effect(home) + prior_defense_allowed_effect(away)
expected_away = prior_league_average_points + prior_offense_effect(away) + prior_defense_allowed_effect(home)
```

All team effects use 12 rounds of alternating ridge-regularized updates with nine-games-equivalent shrinkage. All games on D are predicted before any game from date D updates the dataset. Evaluation begins after at least 50 training games and requires at least three prior games by each participating team. The model is compared with the previous scoring-mean method on **the exact same chronological games** using absolute scoring margin error (MAE), combined-total MAE, and win-probability Brier. Elo is independently compared on the same game set for win-probability Brier, but is not given fictitious score projections.

For comparison only, the score model translates predicted margin into a hypothetical home-win probability with a normal CDF. The margin variance is approximated from residuals in previous games with 40 games of regularizing variance and a 15-point standard deviation prior. This is an explicit distributional assumption, **not** a proven calibrated predictive distribution. No algorithm is promoted because of retrospective backtest results alone.

The `Model Lab` publishes `current/score-research.json` and an interactive date-block benchmark table. It differentiates this historical-date replay from actual archived pre-tipoff forecast measurements. If the training sample is too small it reports zero eligible games and null error metrics rather than fictitious performance.

## Evaluation acceptance criteria

1. Only preceding UTC-embargoed calendar game dates may influence a prediction.
2. Multiple games on the same calendar date are evaluated from the same frozen previous-date state.
3. Identical games are used to compare score-model margins and scoring baseline; Elo Brier is paired on those same events.
4. Out-of-time chronological MAE/Brier determines whether the new score model appears useful; no claim of improvement until actual results demonstrate it.
5. A subsequent robust prospective study should archive score and margin predictions **before tipoff** and compare actual score MAE, interval coverage, Brier and log loss on independent final scores. Do not backfill or relabel this season's earlier archived Elo picks.

## Tests and reproducibility

```bash
PYTHONPATH=research python -m unittest discover -s research/tests -v
PYTHONPATH=research python -m forecast.score_research --games web/public/current/2027-games.json --ratings web/public/current/2027.json --out web/public/current/score-research.json
cd web
npm run test:score
npm run typecheck
npm run build
npm run test:e2e
```

CI tests no same-date leakage, future/current-day embargoes, missing source provenance, duplicate games, score-shrinkage bounds, no fictitious early-season metrics, source possession calculation, home/away symmetry and safe fallback. Data generated during actual GitHub Pages builds, not invented in repository source control.

Research next: time-indexed box-score features for a real **possession-based chronological backtest**, prior-year shrinkage calibrated on earlier seasons, probability calibration selected on disjoint time blocks, and fixed-pregame shadow score prediction archives. Only promote after paired prospective evidence shows a meaningful improvement.
