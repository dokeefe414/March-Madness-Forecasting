"""2026–27 NCAA-source team/conference identity; no fuzzy cross-school joins.

The SportsDataverse ncaa_mbb_team_ids release supplies a team, season,
conference and NCAA ID. A normalized full-name equality match is required.
Ambiguities and unknown schools are NOT silently guessed to be Division I.
"""
from __future__ import annotations
import csv
import io
import re
import unicodedata
from collections import Counter
from typing import Mapping

SEASON = 2027
TEAM_URL = ("https://github.com/sportsdataverse/sportsdataverse-data/releases/download/"
            "ncaa_mbb_team_ids/ncaa_mbb_team_ids_2027.csv.gz")
INVALID = {"", "na", "n/a", "none", "null", "unknown", "-"}


def canonical(value: object) -> str:
    """Lossless-enough comparison for punctuation/spacing, never fuzzy similarity."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(c for c in text if not unicodedata.combining(c)).casefold()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def parse_directory(content: str) -> dict[str, dict]:
    reader = csv.DictReader(io.StringIO(content))
    needed = {"team", "conference", "id", "season"}
    if not needed.issubset(reader.fieldnames or []):
        raise ValueError(f"team directory missing columns: {sorted(needed - set(reader.fieldnames or []))}")
    candidates: dict[str, dict] = {}
    ambiguous = set()
    for row in reader:
        if str(row["season"]).strip() != str(SEASON):
            continue
        name = str(row["team"] or "").strip()
        conference = str(row["conference"] or "").strip()
        ncaa_id = str(row["id"] or "").strip()
        key = canonical(name)
        if not key or canonical(conference) in INVALID or not ncaa_id or not ncaa_id.isdigit():
            continue
        entry = {"sourceName": name, "conference": conference, "ncaaId": ncaa_id}
        if key in candidates and candidates[key] != entry:
            ambiguous.add(key)
        else:
            candidates[key] = entry
    for key in ambiguous:
        candidates.pop(key, None)
    if not candidates:
        raise ValueError("2027 team directory has no usable conference identities")
    return candidates


def annotate_teams(rows: list[dict], directory: Mapping[str, dict]) -> dict:
    """Mark source-conference membership without inventing NCAA D-I eligibility.

    The NCAA-derived team_id crosswalk is treated as evidence of *conference
    affiliation*, NOT an official tournament eligibility certification. A
    team can be rated against an unknown opponent and still be listed.
    """
    matched = 0
    unmatched = []
    confs = Counter()
    for team in rows:
        entry = directory.get(canonical(team["name"]))
        if entry:
            team["conference"] = entry["conference"]
            team["ncaaSourceTeamId"] = entry["ncaaId"]
            team["conferenceVerified"] = True
            matched += 1
            confs[entry["conference"]] += 1
        else:
            team["conference"] = None
            team["ncaaSourceTeamId"] = None
            team["conferenceVerified"] = False
            unmatched.append(team["name"])
    return {
        "source": TEAM_URL, "catalogEntries": len(directory),
        "matchedRatedTeams": matched, "ratedTeams": len(rows),
        "unmatchedRatedTeams": len(unmatched),
        "matchRate": round(matched / len(rows), 4) if rows else 0.0,
        "conferencesRepresented": len(confs),
        "conferenceCounts": dict(sorted(confs.items())),
        "unmatchedExample": sorted(unmatched)[:24],
        "policy": "Exact normalized full-name match only; unmapped != ineligible.",
    }
