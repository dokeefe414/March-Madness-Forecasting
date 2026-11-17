# v0.6 — Provisional 2027 field watchlist and seed scenarios

The 2027 men's field format is **76 teams**, with **32 automatic berths** and **44 at-large** bids, followed by 12 Opening Round games into the ordinary 64-team draw. The NCAA's committee and conference results determine selections. The watchlist is an **unofficial power-only exploratory exercise**: it does not claim to know automatic champions, Selection Sunday entrants or real 2027 seed positions.

## Gating and selection algorithm

Code: `research/forecast/selection.py`, UI: `web/components/SelectionLab.tsx`.

Require at least 76 rated programs joined by full normalized name to the 2027 NCAA-source team directory **and** independently joined to the 2027 SportsDataverse Division I subdivision group membership, with exactly **32 distinct matched conference values**. If any are missing or extra due to source conventions, return `status="insufficient-coverage"`, list no invented field, and explain why. This is a strict double-source completeness gate, not individual tournament eligibility certification. Unknown division membership is not assumed D-I.

1. For each conference, pick its *highest projected Elo* from currently scored programs as an **AQ proxy**, not a championship pick or guaranteed autobid.
2. From remaining teams, pick **44 highest projected Elo** programs as hypothetical at-large proxies.
3. Rank the 76 total scenarios by current Elo strength and show 16 more near-cutline programs from the at-large pool.
4. If fewer than 76 unique teams remain, fail instead of fabricating entrants or seeds.
5. Display their games/wins/losses and small-sample indicator. With fewer than 5 games strength is highly provisional.

## Seed tier ranges

NCAA seed positions and play-in pairings depend on actual committee decisions, which are not available until March 14, 2027. The UI uses **illustrative, uncalibrated strength tiers**, not committee seed probabilities:

```text
nominal_tier = clamp(1,16, ceil(power_position / 4))
sample_spread = 5 if <5 games else 3 if <15 games else 2
strength_tier_range = [max(1,nominal-spread), min(16,nominal+spread)]
```

These are **not actual tournament seeds** and are not used to fill the verified 76-team bracket simulator. A hypothetical ranking of 76 teams must not be translated directly into seeded four-region matchups without real source slots.

## Limitations

- NCAA-source conference membership alone does not prove Division I membership; the second 2027 subdivision source must affirm D-I. Even both matches do not independently prove a team is eligible for the postseason.
- Elo conference leader is not an official regular-season/tournament conference champion.
- Power-only at-large ranking is not an NCAA NET ranking, quadrant resume, selection committee model or bid probability.
- First-half-November samples can be small and source incomplete. Actual 2027 bracket is not yet selected.
- No historical evaluation of watchlist selection/seed placement has been established. Accuracy claims are therefore prohibited.

The status card shows conference match coverage and permits users to inspect an unavailable field rather than hallucinate one. The title "Field Watch" is intentionally distinct from the source-derived historical Bracket Lab.

## Future scientifically valid upgrade

Build a validated NCAA eligibility/NET/team-ID source, retrieve past selection results and committee resume features **as-of Selection Sunday**, establish longitudinal crosswalks, and backtest which teams and seeds the model predicts out of time. Only then report candidate bid probabilities or predicted official seed placements.

## Independent subdivision source

Selection `eligible` now requires `divisionIConfirmed is True` from `forecast.division` as well as `conferenceVerified` from `forecast.reference`. SportsDataverse [2027 team group seasons](https://github.com/sportsdataverse/sportsdataverse-data/releases/tag/mbb_groups) identifies Division I with an explicit season-specific subdivision `group_id`. When source names do not match exactly or group data is unavailable, **the field gate remains closed**. See [identity and conferences](identity-and-conferences.md) for the three-way D-I/other/unknown semantics.
