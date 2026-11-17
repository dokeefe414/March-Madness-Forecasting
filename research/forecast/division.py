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


def parse_division_members(groups_text: str, members_text: str) -> dict[str, dict]:
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
    for row in groups:
        if (str(row.get("league", "")).strip() == "mbb" and
            str(row.get("season", "")).strip() == "2027" and
            str(row.get("level", "")).strip().casefold() == "subdivision" and
            canonical(row.get("name")) in {"division i", "ncaa division i"}):
            division_ids.add(str(row["group_id"]).strip())
    if not division_ids:
        raise ValueError("2027 Division I subdivision missing from source group seasons")
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
    return candidates


def annotate_division(teams: list[dict], membership: dict[str, dict]) -> dict:
    matched = 0
    divi = 0
    non_divi = 0
    source_groups: set[str] = set()
    for team in teams:
        match = membership.get(canonical(team["name"]))
        team["divisionIConfirmed"] = bool(match["divisionIConfirmed"]) if match else None
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
        "catalogEntries": len(membership),
        "policy": "Season-2027 exact-name join to documented subdivision; absence != not D-I; not postseason eligibility certification.",
    }
