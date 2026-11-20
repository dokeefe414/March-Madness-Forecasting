# v2.6 — Weekly AP Top 25 versus source-audited Elo

## Purpose

This is a **supplementary diagnostic**: compare the voting-based Associated
Press men's Top 25 to the site's actual 2026–27 game-aware Elo strength model.
It does **not** treat AP as the ground truth for basketball outcomes. AP agreement
is not probability calibration, Brier score, prospective winning accuracy or
a reason to train an AP-dependent forecaster. The first-published frozen picks
and their independent ESPN + NCAA score settlement remain untouched.

Visible in the existing **Model Lab** below Forecast Intelligence:
[Open weekly AP comparison](https://dokeefe414.github.io/March-Madness-Forecasting26-27/?view=models#ap-elo-comparison).

## Primary source and edition selection

The source is the publicly accessible ESPN rankings API for
**men's NCAA Division I basketball**, specifically the section marked
`AP Top 25` / `type=ap`:

```
https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/rankings?groups=50
```

ESPN **transmits** AP poll rankings; it is not an independent official
result or a new game-score provider. The adapter requires exactly
25 distinct source ESPN IDs, numbered 1–25, and an explicit
`latestWeek.startDate` or poll-date field provided by ESPN. If there
is no authoritative poll edition, the previous frozen weeks remain
visible and a missing poll is *not invented*. Other rankings (Coaches,
BPI, NET) are not silently mislabeled as the AP poll.

The capture is **source-week keyed**, not run-timestamp keyed:
`AP-2027-YYYY-MM-DD` from ESPN's source week. A returning archive
whose source edition was already captured does **not** rewrite it.
A midweek ESPN update or later NCAA backfill cannot silently overwrite
the original stored rank comparison. No more than one distinct AP poll
is selected in a single fetch.

## Fair before-week Elo comparison

When a source edition begins Monday `W`, the model builds a **separate
Elo replay using only game results dated before W** (through Sunday
`W-1`). It calls the same date-embargoed `GameAwareEloEngine` used by
current-season live Elo, including the opponent/venue/bounded scoring
margin rules. It may consume the game's already source-accepted NCAA
score or the previously source-verified and deduplicated ESPN final
receipt. This is not the current Thursday/Friday Elo leaderboard compared
against Monday's older AP ballot.

Elo school identities are joined by the vendor's **same-season
ESPN school ID** present in the NCAA/ESPN membership crosswalk
(`espnSourceTeamId`). Name similarity is not sufficient. The ranked
model pool contains only 2027 D-I group-verified teams with games
through the cutoff; other recorded opponents cannot displace a
verified D-I team in the Top 25.

This is an as-of-**game-date** historical replay rather than a guarantee
that all of the underlying score feed was published before the poll's
exact timestamp. A source may backfill a previously played game
after the poll comes out. We expose the **first capture timestamp**
and permanently freeze that comparison so a later backfill does not
create fake improvements in prior weeks.

## Methods and exact metrics

For every AP-ranked team (25 rows) show:

- AP rank, poll team, matched 2027 D-I Elo rank, pre-week Elo score and
  number of prior games; missing ID/played-game evidence shows **—**
  rather than an invented placement.
- **Rank gap = Elo D-I rank − AP rank**: positive = model ranks this
  team lower (worse); negative = model ranks it higher (better).
- **Top-25 overlap:** number of schools appearing in BOTH Top-25 lists
  out of 25.
- **Top-10 overlap:** number appearing in BOTH Top-10 lists out of 10.
- **Mean absolute rank gap:** average |AP − Elo overall D-I rank|
  among the matched AP poll teams.
- **Spearman rank correlation:** Spearman for the same matched AP
  team cohort, re-ranked *within* that cohort; never pretend the Elo
  rank values 1..N are a 25-team Spearman reference distribution.
- Highest-ranked 2027 Elo schools outside the AP Top 25.
- Historical week-over-week agreement bars, selectable week archive
  and a large-gap filter.

No agreement metrics are published if fewer than 20 AP schools can be
matched to a source-verified D-I team with earlier recorded games, or
if fewer than 25 comparable D-I Elo teams have played. We still show
the raw source ranks and explicit missing coverage. A preseason
AP poll with no earlier game data is deliberately marked incomplete.

There is **no automatic AP-conditioned Elo update**, model weight
promotion, postgame confidence correction or retrospective modification
of already released win probabilities.

## Weekly automation / preserving history

The existing archival workflow now checks AP rankings after its
source-backed current 2027 ratings are assembled. The first valid new
source poll edition produces a frozen comparison in:

```
web/public/research/ap-poll-history.json
```

The file is committed **with the same safe non-force Git workflow** as
the immutable original forecast and result receipts. New weeks append,
and previous weeks remain intact. Existing archiver scheduling (02:07,
06:07, 09:07, 16:07 and 22:07 Eastern) also provides retries if the
source poll has not updated yet.

**New weekly Monday Eastern jobs:**

| Task | Scheduled Monday |
|---|---|
| Archive new AP poll and Sunday-cutoff Elo comparison | **6:07 PM** |
| Republish AP dashboard with the newly archived comparison | **6:47 PM** |

If the AP source is delayed, unreachable or malformed, it does **not**
cause the core game scores, Elo, first picks, or website build to fail.
It reports that the source is unavailable and leaves past poll weeks
untouched. The next scheduled archive run can try again.

GitHub schedules are best-effort; these are target start times, not
guaranteed completion deadlines. The actual AP poll may be published
later than expected. No extra top-level website tabs are added.

## Quality controls and recovery

```powershell
$env:PYTHONPATH="research"
py -m unittest discover -s research/tests -p "test_ap_poll.py" -v
py -m unittest discover -s research/tests -p "test_nightly_automation.py" -v
py -m unittest discover -s research/tests -v
cd web
npm install
npm run typecheck
npm run build
npm run test:e2e
```

The AP poll tests cover 25 distinct exact provider IDs, AP-vs-Coaches
selection, season/version rejection, chronological Elo pre-week cutoff,
rank metrics, missing coverage, immutable weekly history, and historical
game backfill immunity. The E2E tests exercise week selection, the
25-team comparison, large-gap filtering, history bars and the
no-AP-data fallback on desktop/mobile.

After deployment, inspect the archived file for `weeks[].pollKey`,
`sourceWeekStart`, `eloGameCutoffDate`, `matchedApTeams`,
`top25Overlap`, `eloModelVersion`, `capturedAtUtc`.
The weekly dashboard refuses to pass a missing/malformed poll off as a
comparison. A new source week's original data should appear **after**
a completed archive and subsequent Pages deploy, never at an invented
scheduled minute.

**Interpretation:** disagreement is potentially interesting—perhaps
the voters reward schedule, injuries, roster quality or expectations
that an early-season Elo has not learned. It is **not automatically a
model mistake**, and closely tracking AP is **not automatically better**
for predicting the March tournament. To answer the latter, compare
prospectively frozen probabilities to actual independently settled games.
