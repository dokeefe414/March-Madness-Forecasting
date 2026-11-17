# v0.6 — NCAA identities, Division I inference, and conference coverage

## Why this matters

The 2026–27 NCAA-source schedule includes roughly 548 rated opponents early in the season, including programs that are not necessarily Division I. **The count of teams with scores is not the number of Division I members.** Forecasting March selection requires a sourced program/conference universe and separate NCAA eligibility evidence; fuzzy string matching can silently create wrong school identities.

## The 2027 conference crosswalk

Upstream: [SportsDataverse 2027 NCAA men's team-ID asset](https://github.com/sportsdataverse/sportsdataverse-data/releases/tag/ncaa_mbb_team_ids), `ncaa_mbb_team_ids_2027.csv.gz`.

Pipeline `research/forecast/reference.py` validates `team, conference, id, season`, accepts only `season=2027`, numeric NCAA ID and a non-empty conference, and builds a per-season exact name→ID lookup. Comparison normalization includes Unicode diacritics, case folding, punctuation and spacing. **This is not fuzzy school matching**: two similarly named schools remain unmatched.

Ambiguous duplicates with different source IDs/conferences are dropped from lookup rather than picking an arbitrary winner. Unmatched score-only opponents are displayed as unverified, not declared ineligible or automatically excluded from Elo updates. This distinction matters because non-D-I games can still affect observed scoring and baseline Elo.

Public metadata:
- `identityCoverage.ratedTeams`, `matchedRatedTeams`, `unmatchedRatedTeams`, `matchRate`.
- `conferencesRepresented` and `conferenceCounts`.
- `source`, `status`, and a short alphabetically sorted unmatched-name sample for diagnostics.
- Per-team `conference`, `conferenceVerified`, `ncaaSourceTeamId`.

This crosswalk is **not an official Division I eligibility certification**. It is a verified NCAA-source team/conference identity, not evidence of the conference tournament champion, reclassification status or postseason eligibility. The 2027 project keeps the historical Kaggle ID namespace separate; names alone do not establish a safe cross-era ID join.

## Coverage policy and fail-safe behavior

The live schedule is the essential feed. If the team crosswalk fails fetching or validation, the website continues to display real game scores and Elo, but all program conference identity is marked unavailable. If the box-score supplement fails, possession metrics are not fabricated. An outage must never be papered over by an apparently "full Division I" team count.

If exactly 32 conference groups are not source matched at the current cutoff, the hypothetical 76-team field watchlist remains **insufficient coverage** (with reason). This is stricter than letting a missing conference silently disappear. A 32-conference crosswalk still does not certify eligibility; all watchlist entrants are explicitly illustrative.

## Offline test

```powershell
$env:PYTHONPATH="research"
py -m unittest research.tests.test_v06_data -v
```

Fixture tests cover Unicode/punctuation normalization, exact matches, missing/ambiguous crosswalk records, unknown opponents and the conservative 32-conference watchlist gate.

## Decisions and next steps

A certified Division I eligible-program universe with conference realignment and postseason restrictions should be obtained from an official up-to-date NCAA roster/directory, and joined using verified NCAA numeric team IDs — not solely by scraped display names. Until that source and join are verified, the project says **conference linked**, not **Division I verified**.
