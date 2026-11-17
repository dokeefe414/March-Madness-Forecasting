# v0.6 — Possession-based adjusted team efficiency

## Source

The source is SportsDataverse's [NCAA-derived team box 2027 release](https://github.com/sportsdataverse/sportsdataverse-data/releases/tag/ncaa_mbb_team_box), `ncaa_mbb_team_box_2027.csv.gz`. This is a *separate* source from the schedule, with game IDs and team rows containing `o_poss`, `d_poss`, `ortg`, `drtg`, `season`. Rows are used only when the `contest_id` is in the accepted, completed NCAA-source **regular-season** schedule and the named team matches one of that game's recorded home/away teams.

## Data constraints

- Season exactly 2027; an unrelated source-season record is discarded.
- Game ID must match a validated schedule final; future and postseason games cannot train current pre-tournament efficiency.
- School must be the known home or away side of the same confirmed match; unknown opponents never acquire synthetic box scores.
- Offensive and defensive possessions must each be finite and between 30 and 180 per game; reported offensive/defensive efficiency per 100 possessions between 25 and 250. Suspect rows are skipped and counted, never silently inserted.
- A game-team duplicate is accepted once; row coverage counts and exclusions are available in `efficiencyCoverage`.

## Formulas

Observed offense and defense are possessions-weighted:

```text
OffRtg(team) = Σ(offensive possessions * offensive rating) / Σ(offensive possessions)
DefRtg(team) = Σ(defensive possessions * defensive rating) / Σ(defensive possessions)
Pace ≈ [Σ(o_poss)+Σ(d_poss)] / [2 * team game count]
```

These are legitimate possession-based metrics, unlike raw point differential.

### Shrunk opponent adjustment

Set global possession-weighted average offense `μ`. Initialize each team's offense/defense effects `O_i,D_i = 0`; repeat **12 coordinate iterations** with 600 pseudo-possessions of regularization:

```text
O_i := Σ_games poss_off * (game_ORtg_i - μ - D_opponent) / (Σ poss_off + 600)
D_i := Σ_games poss_def * (game_DRtg_i - μ - O_opponent) / (Σ poss_def + 600)
AdjOff_i = μ + O_i
AdjDef_i = μ + D_i
AdjNet_i = O_i - D_i
```

Defensive effects `D_i` are coded as excess points **allowed** per 100 possessions, so smaller is better; `AdjNet` is strength differential per 100 possessions. This is a deliberately simple opponent-informed regularized iterative model and requires statistical validation before being used as a probability predictor. No arbitrary performance label is given to programs without verified box rows.

## Display contract

Each linked team may have `offRating100`, `defRating100`, `pacePossessions`, `adjOff100`, `adjDef100`, `adjNet100`, and `possessionGames`. Teams missing a verified row show an em dash. The 2027 Pulse includes an explicit box-score coverage count and an independent conference-match coverage count.

**Important:** 2027 possession-adjusted statistics are not part of the Kaggle-based historic benchmark or the currently published 2027 matchup odds. Presenting them as predictive enhancements without cross-season evaluation would be misleading.

## Source failures

The schedule is mandatory and fails closed on invalid main inputs. The box and conference datasets are optional and each publishes a typed `status=unavailable` or `status=empty` rather than manufactured values when missing. Invalid supplemental rows are skipped/count-tracked; invalid required headers abort supplemental attachment, leaving source-score Elo unaffected. Exact source coverage is an output of each run, not a hard-coded number.

## Tests and reproducibility

```powershell
$env:PYTHONPATH="research"
py -m unittest research.tests.test_v06_data -v
py -m forecast.live --out web/public/current/2027.json
```

The offline fixture tests inspect the accepted 4 box rows, reject a non-schedule contest, and assert possession estimates exist only for genuinely matched source games. For a complete accuracy study, acquire **historically versioned** possession data and pre-tournament team IDs, then re-run the full rolling-year test with features available before each year's selection.
