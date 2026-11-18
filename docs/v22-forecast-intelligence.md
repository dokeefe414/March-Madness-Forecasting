# v2.2 — Forecast Intelligence: causal features, earlier-season learning, evidence and user experience

Release: 2026-11-18. Modules: `forecast.possession_research`,
`forecast.model_championship`, `forecast.forward_ensemble`,
`forecast.accuracy_research`; interface `ForecastIntelligence.tsx`.

## Executive technical contract

This release improves research depth and presentation **without silently
switching the active game predictor**. All metrics must distinguish:

1. Historical **pre-tournament** source-pinned held-out NCAA tournament seasons;
2. Current 2026–27 **prior-date** reconstructed regular-season experiments;
3. Genuine **first-published** pregame probabilities with independently
   verified ESPN final status and matching NCAA source scores.

Neither (1) nor (2) is relabeled as (3). Every current research artifact shares
`2027.json.retrievedAtUtc`, and the UI rejects a different source-capture
timestamp. Optional data unavailable? Publish an honest abstention, not an
invented possession or feature vector.

## A. Stronger historical training: conservative prior-year stack

The existing six-model tournament championship still independently trains every
season `Y` using seasons strictly `< Y`, as determined by pinned pre-tournament
team ratings and historical tournament matchup outcomes. A new **seventh
research output**, `priorYearStack`, is evaluated on the same later seasons;
the six original champion candidates and nested champion are not replaced.

For each season `Y`, first collect model probabilities that were evaluated in
historical years strictly earlier than `Y`; use only the most recent eight
previously held-out seasons. If fewer than five exist, use Elo alone. Otherwise
consider one convex combination per candidate:

```text
p_stack = (1 - w) * p_elo + w * p_candidate
w in {0, 0.15, 0.30, 0.45}
eligible nonzero weight requires prior out-of-time Brier gain >= 0.002
ranking penalty = historical mixture Brier + .001 * (w / .45)^2
```

Selection is determined **before** `Y` is evaluated. The output contains
`yearByYear[].stackChosenBeforeResults`,
`stackWeightChosenBeforeResults`, per-year metrics, cumulative Brier/accuracy,
and a **year-block bootstrap** difference vs Elo. If a candidate loses, the
negative gain remains visible. Repeated analysis of published historical
seasons can still cause researcher overfitting; external prospective testing
is necessary before deployment.

Why no transferred 2027 team rating priors? Source-normalized 2027 NCAA names
are not automatically equivalent to historical Kaggle team IDs and team
composition changes. Do **not** join them by guessed school names or claim
historical strength as a justified early-season Elo seed.

## B. Real basketball efficiency: exact paired source boxes

`forecast.live` already fetches the NCAA-derived `ncaa_mbb_team_box_2027`
source when available. It now emits `web/public/current/2027-box-games.json`
from the SAME accepted-score snapshot with:

- Exact `contest_id` join to accepted source games;
- Exact canonical full-team-name match for BOTH sides;
- Strict finite and plausible checks for ORTG, DRTG and offensive/defensive
  possession counts; duplicate team-event lines are withheld;
- `pairedGameBoxes`, `acceptedScoreGames`,
  `completeFourFactorGames`, and incomplete-source diagnostics;
- Optional source columns `fga,fgm,fg3m,fta,tov,orb,drb` are used only
  when actually supplied and numerically valid. Offensive rebound opportunity
  uses **opponent defensive rebounds**, never own defensive rebounds.
  If those columns do not exist, no Four Factors are claimed.

This is a **source-backfilled** date-frozen research study, not a guarantee
that the exact box was available in real time before an earlier game's tipoff.
If source/team matching is partial, only matched games contribute.

## C. Learned efficiency challenger (out-of-date replay, research-only)

`forecast.possession_research` constructs each team's previous-date
possession-weighted offensive/defensive performance, last five *prior game*
net efficiencies, mean opponent pregame Elo, verified rest-day interval, and
optional prior Four Factors composite. The opponent's date-frozen Elo drives
the expected score-only probability; each matched team needs at least **three
previous** paired source boxes before its advanced feature vector qualifies.

Current date `D`:

1. Start with the Elo rating and team stats from **earlier days only**.
2. On each fixture, compute the strictly pre-date Elo probability and advanced
   feature vector. Games without sufficient paired prior boxes abstain from
   advanced comparison. Score-only Elo still updates on every accepted game.
3. If at least 80 earlier qualifying games spanning eight earlier dates exist,
   fit a **fixed-hyperparameter, L2-regularized logistic residual** (70
   gradient steps, learning rate 0.2, L2 0.15) on older games. Predict today's
   advanced probability with logit-offset `logit(p_elo) + w·features`.
4. Freeze **all** date-D predictions and features, then update both teams'
   zero-sum Elo via the v2.1 bounded margin multiplier. Only then ingest
   date-D source box data for future dates.
5. Compare Elo vs challenger on the **identical qualifying test fixtures**,
   publishing Brier, log loss, winner accuracy, per-date scorecards, a
   date-block bootstrap Brier interval, coverage and last fitted weights.

The feature vector is:

```text
[intercept,
 clipped difference in possession-shrunken net offensive/defensive rating,
 clipped recent last-5 net-efficiency gap,
 clipped game-time opponent Elo / strength of schedule gap,
 clipped rest-days gap,
 clipped Four Factors gap if BOTH have actual previous rows, else 0 signal]
```

Missing optional Four Factors yield no composite signal, not synthetic
box scores. Team-box data can be missing in some NCAA fixtures; no selective
"improved accuracy" claim is allowed. The source schedule may publish scores
before explicit final-status confirmation, which is why genuine archived
forward grading independently verifies ESPN finals. The additional model is
always research-only and may perform worse than Elo.

## D. Adaptive ensemble weighting, without hindsight

The existing prospective ensemble keeps its original frozen first-pick
probabilities and **never auto-promotes**. New
`forward-ensemble.json.prequentialAdaptive` adds a chronological **research
reconstruction** that blends prior frozen Elo and shadow component probabilities.

For each game date `D`, choose a small weight from
`{0, .1, .2, .3, .4}` minimizing Brier on at least 80 previously graded
source-verified unique-event games over at least six **earlier** dates. A
nonzero weight needs previous Brier improvement >= .002 and incurs a small
complexity penalty. A crucial new **settlement publication embargo** only
allows prior results whose **settlement file timestamp is earlier than the
target forecast creation**. A previous-date score that was verified *later*
cannot be used earlier merely because its game date was earlier.

Evaluate the chosen weight on date D without fitting to date D and retain
per-date changes, matched prequential Brier and date-block uncertainty.
These reconstructed research probabilities were **not** necessarily frozen
as the original adaptive output at pretipoff. Only the separate
`archivedPortfolio*` fields score originally frozen real public ensemble
probabilities. Publication of a favorable retrospective weight is not
authorization to change active forecasts.

## E. Real model health, model versions and calibration

`forecast.accuracy_research` uses the **earliest** originally published
forecast for each event, only after ESPN STATUS_FINAL and matching NCAA final
score settlement. It adds:

- Five favorite-confidence intervals (50–60%, etc.) containing raw game
  counts, predicted confidence, actual win rate and absolute mismatch;
- A descriptive count-weighted expected calibration error (ECE) and
  `insufficient-evidence` status before 50 settled games;
- Per-rated-Elo model-version performance (`pre-v2.1-unversioned` vs
  `source-aware-game-elo-v1`) without mixing previous formulas or
  claiming a nonrandom comparison is a causal improvement;
- Existing per-day/per-week Brier/accuracy, missed picks, delayed settlement
  warnings, paired prospectively frozen model evidence, and drift safeguards.

ECE is descriptive, not a formal hypothesis test or promise about tomorrow.
Pending/unverified games are never incorrect picks. The active Elo vs shadow
promotion gate remains an explicitly separate manual code/release decision.

## F. Design system and UX

The existing **five main destinations** remain; no extra tab clutter.
The Model Lab adds a responsive, high-contrast **Forecast Intelligence**
workbench with four evidence counters, an accessible interactive switch
(Efficiency / Adaptive Ensemble / Historical Stack), paired Brier bars with
negative gains visible, actual verified first-pick confidence reliability
bins and independent model version tracking.

- Visually consistent dark court grid, mint/cyan palette, large condensed
  numerical typography and source-aware status.
- No fake "improved" badges, implied live score metrics, decorative
  successful-model claims, or chart heights derived from missing values.
- Source refresh date and game date remain distinct.
- Accessible button roles, `aria-pressed`, `aria-live`, visible numeric
  chart labels, focus outlines, reduced motion, desktop and 490px breakpoints.
- If a source artifact is absent or retrieval timestamps mismatch, withhold
  the mismatched experiment rather than blending report dates.

## Scheduling and operating procedure

The existing GitHub Actions refresh continues the separate 2:07/6:07 a.m.
Eastern archival/score settlement and 2:47/6:47 a.m. in-season website
rebuilds with subsequent daytime backup checks. GitHub scheduling and the
provider can lag; this is not tick-by-tick real-time coverage.

New deploy sequence:
```powershell
$env:PYTHONPATH="research"
py -m forecast.live --games-out web/public/current/2027-games.json --box-out web/public/current/2027-box-games.json --out web/public/current/2027.json
py -m forecast.possession_research --games web/public/current/2027-games.json --ratings web/public/current/2027.json --boxes web/public/current/2027-box-games.json --out web/public/current/efficiency-research.json
py -m forecast.model_championship --web-dir web --out web/public/research/model-championship.json
py -m forecast.forward_ensemble --ratings web/public/current/2027.json --ledger web/public/forecasts --out web/public/current/forward-ensemble.json
py -m forecast.accuracy_research --ledger web/public/forecasts --out web/public/current/accuracy-research.json
```

Offline testing and build:
```powershell
$env:PYTHONPATH="research"
py -m unittest discover -s research/tests -p "test_v22_forecasting.py" -v
py -m unittest discover -s research/tests -v
cd web
npm install
npm run typecheck
npm run build
npm run test:e2e
```

If the optional team-box source fails to download or validate, the deployment
still publishes an explicit `status=unavailable` efficiency artifact and
does not invent box scores. If the **mandatory accepted-score source** fails
or existing validation fails, the workflow fails closed and leaves the last
correctly published website. No changes were made to existing immutable
snapshot or settlement records.

## Next evidence thresholds

- Accumulate original future predictions and independently verified finals.
- Inspect actual original first-pick Brier, calibration and opponent/venue
  strata, not only percent correct.
- Require statistically defensible prospective paired improvement over
  multiple dates (with positive date-block interval) before even *reviewing*
  an alternative production model.
- For expanded player/lineup, neutral-court and Four Factors signals, first
  acquire a source that proves coverage and as-of availability. Test them
  chronologically before allowing them into live picks.

**No claim:** Neither training on more historical data nor adding extra
basketball statistics automatically guarantees a more accurate predictor.
Negative measured gains are a useful reason to keep Elo.
