"""Strict NCAA Division I membership from 2027 SportsDataverse season lineages.

Cross-provider team names are joined EXACTLY after punctuation normalization.
The source's subdivision group for season 2027 is first resolved from
mbb_group_seasons.csv; the team's season row must explicitly reference it.
We do not guess D-I from a conference name, ESPN numeric ID, or likely school.
"""
from __future__ import annotations
import csv
import io
from collections import Counter
from .reference import canonical

GROUP_SEASONS_URL = (
    "https://github.com/sportsdataverse/sportsdataverse-data/releases/download/"
    "mbb_groups/mbb_group_seasons.csv"
)
TEAM_MEMBERSHIP_URL = (
    "https://github.com/sportsdataverse/sportsdataverse-data/releases/download/"
    "mbb_groups/mbb_team_group_seasons_2027.csv"
)


ALIASES_URL = (
    "https://github.com/sportsdataverse/sportsdataverse-data/releases/download/"
    "mbb_groups/mbb_team_aliases.csv"
)


def parse_ncaa_aliases(csv_text: str, season: int = 2027) -> dict[str, str]:
    """Build exact NCAA-name → ESPN team-id links from source-provided aliases.

    Crucially, alias id values are explicitly sourced from the vendor's
    ESPN-keyed lineage table, not inferred from matching team names to ESPN
    mascot names. Only named NCAA aliases valid for the requested season
    are accepted, and ambiguous names never resolve.
    """
    reader = csv.DictReader(io.StringIO(csv_text))
    required = {"league", "team_id", "team_id_source", "source",
                "name_kind", "value", "valid_from", "valid_to"}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError(f"team aliases missing fields: {sorted(required-set(reader.fieldnames or []))}")
    answers: dict[str, str] = {}
    ambiguous: set[str] = set()
    for row in reader:
        if (str(row["league"]).strip() != "mbb" or
            str(row["source"]).strip().casefold() != "ncaa" or
            str(row["team_id_source"]).strip().casefold() != "espn" or
            str(row["name_kind"]).strip().casefold() != "name"):
            continue
        label = canonical(row["value"])
        espn_id = str(row["team_id"] or "").strip()
        if not label or not espn_id:
            continue
        try:
            first = int(row["valid_from"]) if str(row["valid_from"] or "").strip() else None
            last = int(row["valid_to"]) if str(row["valid_to"] or "").strip() else None
        except ValueError:
            continue
        if (first is not None and first > season) or (last is not None and last < season):
            continue
        if label in answers and answers[label] != espn_id:
            ambiguous.add(label)
        else:
            answers[label] = espn_id
    for label in ambiguous:
        answers.pop(label, None)
    return answers


CROSSWALK_URL = (
    "https://github.com/sportsdataverse/sportsdataverse-data/releases/download/"
    "mbb_crosswalk/ncaa_espn_team_crosswalk.csv"
)


def parse_ncaa_espn_ids(csv_text: str) -> dict[str, str]:
    """Return explicit *same-season* NCAA team ID -> ESPN team ID mappings.

    stats.ncaa.org team IDs are *reissued each season*. The ESPN team ID can
    never be inferred by integer equality. Accept only source-authored 2026-27
    mappings whose match_method is not unmatched. Any same-season conflicting
    NCAA ID is omitted, rather than randomly choosing a candidate.
    """
    reader = csv.DictReader(io.StringIO(csv_text))
    needed = {"season", "ncaa_team_id", "espn_team_id", "match_method"}
    if not needed.issubset(reader.fieldnames or []):
        raise ValueError(f"NCAA-ESPN crosswalk missing fields: {sorted(needed-set(reader.fieldnames or []))}")
    matches: dict[str, str] = {}
    ambiguous: set[str] = set()
    for row in reader:
        season = str(row.get("season", "") or "").strip().replace("–", "-")
        if season not in {"2026-27", "2027"}:
            continue
        ncaa_id = str(row.get("ncaa_team_id", "") or "").strip()
        espn_id = str(row.get("espn_team_id", "") or "").strip()
        method = str(row.get("match_method", "") or "").strip().casefold()
        if (not ncaa_id.isdecimal() or not espn_id.isdecimal()
            or method in {"", "unmatched", "null", "none", "na"}):
            continue
        if ncaa_id in matches and matches[ncaa_id] != espn_id:
            ambiguous.add(ncaa_id)
        else:
            matches[ncaa_id] = espn_id
    for key in ambiguous:
        matches.pop(key, None)
    return matches


def parse_division_members(groups_text: str, members_text: str,
                           alias_csv: str | None = None,
                           crosswalk_csv: str | None = None) -> dict[str, dict]:
    """Return unambiguous 2027 team-name evidence of source D-I membership.

    The SportsDataverse reference uses a 2027 ENDING year and league='mbb'.
    Accept only the group name 'Division I' in a season-specific subdivision
    record; no guessed slug ID. A non-D-I record is explicit counterevidence,
    not ignored, and duplicate contradictory names are excluded.
    """
    groups = csv.DictReader(io.StringIO(groups_text))
    needed_g = {"league", "season", "group_id", "level", "name"}
    if not needed_g.issubset(groups.fieldnames or []):
        raise ValueError(f"group seasons missing {sorted(needed_g-set(groups.fieldnames or []))}")
    division_ids: set[str] = set()
    group_rows = list(groups)
    for row in group_rows:
        if (str(row.get("league", "")).strip() == "mbb" and
            str(row.get("season", "")).strip() == "2027" and
            str(row.get("level", "")).strip().casefold() == "subdivision" and
            canonical(row.get("name")) in {"division i", "ncaa division i"}):
            division_ids.add(str(row["group_id"]).strip())
    if not division_ids:
        raise ValueError("2027 Division I subdivision missing from source group seasons")
    # The group source's own conference label is authoritative for its
    # source conference ID; another NCAA team directory may carry names
    # from before a conference realignment.
    source_conference_names = {
        str(row.get("group_id", "")).strip(): str(row.get("name", "")).strip()
        for row in group_rows
        if str(row.get("league", "")).strip() == "mbb"
        and str(row.get("season", "")).strip() == "2027"
        and str(row.get("level", "")).strip().casefold() == "conference"
        and str(row.get("group_id", "")).strip()
        and str(row.get("name", "")).strip()
    }
    members = csv.DictReader(io.StringIO(members_text))
    needed = {"league", "season", "team_name", "team_id", "subdivision_id", "conference_id"}
    if not needed.issubset(members.fieldnames or []):
        raise ValueError(f"group membership missing {sorted(needed-set(members.fieldnames or []))}")
    candidates: dict[str, dict] = {}
    ambiguous: set[str] = set()
    for row in members:
        if str(row["league"]).strip() != "mbb" or str(row["season"]).strip() != "2027":
            continue
        name = str(row["team_name"] or "").strip()
        key = canonical(name)
        if not key:
            continue
        subdivision = str(row["subdivision_id"] or "").strip()
        info = {
            "groupTeamName": name,
            "divisionIConfirmed": subdivision in division_ids,
            "groupTeamId": str(row["team_id"] or "").strip(),
            "conferenceGroupId": str(row["conference_id"] or "").strip() or None,
            "conferenceGroupName": source_conference_names.get(str(row["conference_id"] or "").strip()),
            "subdivisionId": subdivision,
        }
        if key in candidates and candidates[key] != info:
            ambiguous.add(key)
        else:
            candidates[key] = info
    for key in ambiguous:
        candidates.pop(key, None)
    if not candidates:
        raise ValueError("group source did not provide 2027 membership rows")
    if alias_csv is not None or crosswalk_csv is not None:
        # ESPN season-2027 group names and NCAA season-2027 schedule names
        # are not necessarily spelled alike. The provider's own NCAA↔ESPN
        # alias rows create *verified* additional exact NCAA-name keys.
        indexed: dict[str, dict] = {}
        duplicate_ids = set()
        for entry in candidates.values():
            espn_id = entry["groupTeamId"]
            if espn_id in indexed and indexed[espn_id] != entry:
                duplicate_ids.add(espn_id)
            indexed[espn_id] = entry
        for espn_id in duplicate_ids:
            indexed.pop(espn_id, None)
        for ncaa_label, espn_id in (parse_ncaa_aliases(alias_csv).items()
                                    if alias_csv is not None else []):
            member = indexed.get(espn_id)
            if not member:
                continue
            joined = {**member, "joinedBy": "source NCAA-name alias to ESPN member ID"}
            if ncaa_label in candidates and candidates[ncaa_label]["groupTeamId"] != espn_id:
                ambiguous.add(ncaa_label)
                continue
            if ncaa_label not in candidates:
                candidates[ncaa_label] = joined
        for label in ambiguous:
            candidates.pop(label, None)
        if crosswalk_csv is not None:
            for ncaa_id, espn_id in parse_ncaa_espn_ids(crosswalk_csv).items():
                member = indexed.get(espn_id)
                if not member:
                    continue
                candidates["ncaa-id:" + ncaa_id] = {
                    **member, "joinedBy": "same-season published NCAA team ID to ESPN team ID",
                }
    return candidates


def annotate_division(teams: list[dict], membership: dict[str, dict]) -> dict:
    matched = 0
    divi = 0
    non_divi = 0
    source_groups: set[str] = set()
    id_matched = 0
    alias_matched = 0
    for team in teams:
        source_id = str(team.get("ncaaSourceTeamId") or "").strip()
        matched_id = membership.get("ncaa-id:" + source_id) if source_id else None
        matched_name = membership.get(canonical(team["name"]))
        # Two source-defined paths must agree on the ESPN group team ID.
        # If they disagree, refuse a division claim rather than trusting one.
        if (matched_id and matched_name and
            matched_id["groupTeamId"] != matched_name["groupTeamId"]):
            match = None
        else:
            match = matched_id or matched_name
        team["divisionIConfirmed"] = bool(match["divisionIConfirmed"]) if match else None
        # The provider's season-2027 conference *group ID* is the authority
        # for identity and AQ grouping. NCAA display labels may collapse
        # multiple distinct source leagues (31 names vs 32 source groups).
        team["divisionConferenceGroupId"] = (
            match["conferenceGroupId"]
            if match and match["divisionIConfirmed"] and match["conferenceGroupId"]
            else None
        )
        team["divisionConferenceGroupName"] = (
            match.get("conferenceGroupName")
            if match and match["divisionIConfirmed"]
            else None
        )
        if matched_id and match:
            id_matched += 1
        elif matched_name and match and matched_name.get("joinedBy"):
            alias_matched += 1
        if match:
            matched += 1
            if match["divisionIConfirmed"]:
                divi += 1
                if match["conferenceGroupId"]:
                    source_groups.add(match["conferenceGroupId"])
            else:
                non_divi += 1
    return {
        "status": "ready", "groupSeasonsSource": GROUP_SEASONS_URL,
        "teamMembershipSource": TEAM_MEMBERSHIP_URL,
        "matchedRatedTeams": matched, "divisionIConfirmed": divi,
        "explicitlyNonDI": non_divi, "unmatchedRatedTeams": len(teams)-matched,
        "sourceDivisionIConferenceGroups": len(source_groups),
        "conferenceGroupingMethod": "season-2027 independent source conference_group_id",
        "seasonNCAAIdMatchedTeams": id_matched,
        "ncaaAliasMatchedTeams": alias_matched,
        "crosswalkSource": CROSSWALK_URL,
        "catalogEntries": len(membership),
        "policy": "Season-2027 exact-name join to documented subdivision; absence != not D-I; not postseason eligibility certification.",
    }
