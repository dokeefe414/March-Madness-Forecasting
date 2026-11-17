# Verified picks, winner grading, and experimental score/spread estimation

## Automatic update schedule

The before-tipoff GitHub Actions archive runs at **9:07 a.m. and 4:07 p.m. Eastern** during configured basketball months. It fetches source NCAA results, generates a timestamped pregame Elo snapshot, and independently matches finished ESPN events against the NCAA final feed. It writes strictly append-only original prediction snapshots and separate settlement records, then regenerates `forecasts/index.json` from those artifacts. Successful archive workflow completions trigger a Pages publication run. Scheduling and upstream source availability are **best effort**; a final buzzer does not immediately or unconditionally imply that public archive results exist. The archive monitor checks receipt freshness.

If a fixture was not captured before tipoff with the required time buffer, it **cannot** be counted retrospectively as a genuine pregame forecast. If independent source finals don't agree on event identity, home/away, date and score, that result stays **pending**, not incorrect. A postponed game does not automatically settle because its listed start time has passed.

## Which games were correct?

`research/forecast/performance.py` now publishes `uniqueGames.verifiedOutcomes` in the source-derived index. The results are ordered newest first and include exactly **one earliest archived and independently settled snapshot for each ESPN event ID**. Columns are canonical event ID, listed scheduled start, original pretipoff UTC, actual final date, team names, actual final scores, original home-win probability, original chosen favorite or null at exactly 50%, actual winner, correct/missed/null at 50%, frozen model identity and individual Brier.

The new `PickResults` panel in the Accuracy & Picks tab displays first-pick counts and filters **ALL FINALS / CORRECT / MISSED / EVEN ODDS**. It includes actual final scores, original favorite probability, original forecast freeze time, and each game's Brier. Duplicate snapshots for a single event never inflate these unique-game counts. Even-odds forecasts are neither marked right nor wrong and continue to receive 0.5 accuracy credit as in the existing science conventions. Real game records are never fabricated from scheduled fixtures.

**Important:** this is different from `scores.settledPredictions`, the count of all settled snapshot entries. For independent accuracy, use `uniqueGames.settledUniqueGames` and `uniqueGames.score`.

## Experimental score and projected spread

The real Game Center's detailed source-matched matchup view now includes `ScoreProjection`. This estimates a **neutral-court descriptive** projected score from the currently retrieved, source-derived points-for and points-against per game:

```text
projected_home = (home_points_for_per_game + away_points_against_per_game) / 2
projected_away = (away_points_for_per_game + home_points_against_per_game) / 2
projected_margin = projected_home - projected_away
projected_spread = favorite - abs(projected_margin)
projected_total = projected_home + projected_away
```

Display is rounded to one decimal. Each team needs **at least five source-recorded contests** and finite scoring averages in a sane scoring domain; otherwise the UI declines to provide a figure. This method estimates *points* from observed means; it is not a fitted statistical margin model, an odds-market point spread, a betting line, a confidence interval, or a complete probability distribution. It does not incorporate opponent-adjusted efficiency, injuries, rest, travel, possession-level effects, or venue scoring bonus. It can disagree with the main published Elo favorite; a visible warning explicitly explains that they are independent approaches. Non-neutral scheduled matchups retain a descriptive neutral-court scoring baseline and are labeled accordingly.

This is a **new illustrative and testable scoring model**, not a replacement for the trained Elo probability forecasts, and it does not contribute to the archived pregame scorecard or a claimed score-prediction backtest. A scientifically defensible next step is to train and evaluate point-total/margin distributions using a strictly chronological prior-date training process, out-of-sample MAE and calibration/coverage, before adding confidence intervals or automated shadow-score archiving.

## Validation

```bash
PYTHONPATH=research python -m unittest discover -s research/tests -v
cd web
npm install --no-audit --no-fund
npm run test:score
npm run typecheck
npm run build
npm run test:e2e
```

Unit checks cover strict absence on unverified finals, no duplicate first-pick inflation, correct/missed event and actual score integrity, arithmetic consistency for projected total and spread, missing-data gating, and exact pick'em. Browser checks exercise correctly classified settled outcomes, filters, score projection with current verified records, and unavailable evidence. The existing repository audit and production-path historical tournament tests are preserved.

## Website links

- [Game Center](https://dokeefe414.github.io/March-Madness-Forecasting26-27/?view=games)
- [Verified Accuracy & Picks](https://dokeefe414.github.io/March-Madness-Forecasting26-27/?view=predictions)
- [Forecast archive runs](https://github.com/dokeefe414/March-Madness-Forecasting26-27/actions/workflows/archive-pregame.yml)
