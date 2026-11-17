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

## v0.6 independently verified Division I source status (additional gate)

The project also uses the **SportsDataverse season-2027 basketball conference/division lineage release**: [mbb_groups](https://github.com/sportsdataverse/sportsdataverse-data/releases/tag/mbb_groups), specifically `mbb_group_seasons.csv` and `mbb_team_group_seasons_2027.csv`. Its schema is described by [SportsDataverse team group season docs](https://py.sportsdataverse.org/docs/mbb/reference/loaders/team).

`forecast.division.parse_division_members` first identifies a season-2027 `level=subdivision` record explicitly named `Division I` or `NCAA Division I`. It then checks each season-2027 team membership row's **exact `subdivision_id` reference**. Teams are matched back to scored-program names by the same conservative normalized full-name equality; no cross-provider numeric-ID assumptions. Conflicting duplicate team names are dropped.

Three explicit states are exposed for each rated program:
- `divisionIConfirmed=true`: matched source membership row that explicitly belongs to the 2027 Division I subdivision.
- `divisionIConfirmed=false`: matched source record explicitly belongs to another subdivision.
- `divisionIConfirmed=null`: no unambiguous 2027 membership row can be joined. **Unknown is not ineligible.**

`divisionCoverage` reports how many scored teams matched the division source, confirmed D-I, explicitly outside D-I and unknown, alongside the number of unique D-I source conference groups represented. If either supplementary group source cannot be fetched/validated, this status is unavailable and all team division flags remain unknown. The Field Watch algorithm now **requires BOTH** `divisionIConfirmed=true` and `conferenceVerified=true` to create any of its 76 hypothetical entrants, then still requires 32 conferences and 76 candidates. The earlier NCAA team-name crosswalk alone can no longer put a school in the hypothetical field.

**Caveat:** The source's season-end group membership indicates subdivision affiliation; it is NOT the NCAA’s own official postseason eligibility determination for probation, transitions, disciplinary sanctions or other restrictions. The 2027 watchlist is still hypothetical until Selection Sunday.

Offline source-specific tests: `research/tests/test_division.py` (confirmed D-I, explicitly other division, unmatched, duplicate source conflict, missing subdivision reference, and refusing unsourced field scenarios).

## Dated NCAA-to-ESPN school aliases (2027 correction)

The first deployed v0.6 production report revealed a provider-identity mismatch: **365 scored schools linked to the NCAA team/conference directory, but zero matched the ESPN-keyed subdivision table by their display names**. SportsDataverse's reference dataset includes a genuine [`mbb_team_aliases.csv` source](https://github.com/sportsdataverse/sportsdataverse-data/releases/tag/mbb_groups) precisely for such identity-space differences. Its [schema documentation](https://py.sportsdataverse.org/docs/mbb/reference/loaders/team) describes rows with `source="ncaa"`, a source-native NCAA school-name `value`, the validated ESPN `team_id`, the `team_id_source` and the season-specific `valid_from` / `valid_to` bounds.

The revised `forecast.division.parse_ncaa_aliases` **only** accepts provider-authored NCAA school **name** aliases keyed to an ESPN team, scoped to a 2027-valid season window. It rejects ambiguous aliases, provider IDs from other leagues, name abbreviations, and expired/future-only entries. The mapping uses the published ESPN `team_id` to reach the separate, independently sourced **2027 Division I subdivision** membership; it never assumes that NCAA numerical IDs and ESPN numerical IDs are interchangeable and never infers a school from mascot similarity. Exact matching remains the first choice; source-provided aliases add an evidence-backed second route.

A missing/invalid alias file cannot erase verified 2027 scores or possession data: it causes only source-alias coverage to be unavailable, and the original exact-name join remains conservative. The watchlist still needs 32 source-linked D-I conferences and 76 candidates to display even a hypothetical power field.

This can materially improve verified D-I coverage **after a successful new deployment**. No numerical improvement is claimed until the new production logs and `divisionCoverage` actually show it.

## Primary same-season numeric NCAA→ESPN crosswalk

An even stronger source than historical name aliases is SportsDataverse's published [`ncaa_espn_team_crosswalk.csv` under `mbb_crosswalk`](https://github.com/sportsdataverse/sportsdataverse-data/releases/tag/mbb_crosswalk), documented in the [sdv-py IDs/crosswalk guide](https://py.sportsdataverse.org/docs/mbb/reference/additional/ids-and-crosswalks). It associates the **2026–27 NCAA season-specific `ncaa_team_id`** directly with the provider's own **`espn_team_id`**. The NCAA side comes from the *same 2027 season* `ncaa_mbb_team_ids_2027.csv.gz` source that already matched 365 schools in the first v0.6 production run.

`forecast.division.parse_ncaa_espn_ids` requires the explicitly matching season `2026-27` (or year 2027) and a non-unmatched `match_method`; it drops blank/ambiguous/repeated conflicting mappings and wrong-year links. A stats.ncaa.org team ID **must never be equated to an ESPN team ID**: the actual provider crosswalk states both numbers. The ESPN ID then finds the team in the independently sourced 2027 season subdivision membership table, where the team's `subdivision_id` must explicitly reference the published 2027 Division I group.

The per-team lookup prefers a verified NCAA-ID mapping to name-only matching, but if the two source paths disagree on the **ESPN group team ID**, it refuses to assert division membership. Production `divisionCoverage` now reports `seasonNCAAIdMatchedTeams`, `ncaaAliasMatchedTeams` and `crosswalkSource` so improvement can be demonstrated with real counts. Again, source-verified subdivision is **not individual postseason eligibility**. If the upstream crosswalk lacks rows for the 2026–27 season, the importer must *not* borrow prior-year NCAA numeric IDs — stats.ncaa.org IDs are regenerated each season.

This correction follows the initial 0-match NCAA-name/ESPN-name join and still enforces **32 D-I conference groups and 76 rated candidates** before any hypothetical selection field appears. It should never silently lower that gate to force a table of teams.

## Conference GROUP identity versus a display name

The 2027 live build with genuine source inputs reported **32 independently verified D-I source conference group IDs** but only **31 different human-readable conference labels** in the NCAA team directory. This is a provider-label inconsistency; inferring that the tournament has 31 leagues would be wrong. A display name is presentation metadata, *not a primary key*.

The `division.py` output now sets `divisionConferenceGroupId` only when the team is affirmatively linked to a season-2027 Division I membership record with a non-empty `conferenceGroupId`. Unknown or non-D-I teams receive `null`. The provisional field groups by this ID, not the NCAA `conference` string, and requires **32 distinct D-I group IDs**, **76 unique rated programs** and independent team-directory name identity before it can display 76 conditional strength candidates.

The report includes `matchedConferences` (source group ID count), `distinctConferenceDisplayNames`, and `groupingKey`. This lets reviewers reproduce the 32/31 distinction and prevents teams in two verified conferences with the same provider display label from sharing one automatic-bid proxy. As always, the result is *not* the committee's chosen field.
