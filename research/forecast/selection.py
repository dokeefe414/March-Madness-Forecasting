"""Provisional power-only watchlist, not an NCAA committee selection prediction."""
from __future__ import annotations
import math
from collections import defaultdict

FIELD_SIZE, AUTOMATIC, AT_LARGE = 76, 32, 44


def build_watchlist(teams: list[dict], as_of: str) -> dict:
    """Rank observed source-conference programs, separating 32 proxy AQs.

    An AQ proxy means the strongest *currently rated* team for a verified
    conference, NOT a tournament champion or conference standing. To avoid
    inventing missing leagues, publication is unavailable unless exactly
    32 unique verified conferences and >=76 mapped programs are represented.
    """
    eligible = [t for t in teams if t.get("conferenceVerified") and
                isinstance(t.get("conference"), str) and
                math.isfinite(float(t["projectedRating"]))]
    by_conference = defaultdict(list)
    for t in eligible:
        by_conference[t["conference"]].append(t)
    groups = sorted(by_conference)
    report = {
        "season": 2027, "asOfDate": as_of, "official": False,
        "method": "Current Elo power-only hypothetical field (NOT NCAA committee odds)",
        "fieldSize": FIELD_SIZE, "automaticSlotCount": AUTOMATIC,
        "atLargeSlotCount": AT_LARGE,
        "eligibleCandidateCount": len(eligible),
        "matchedConferences": len(groups),
        "limitations": [
            "Conference leader is projected Elo leader, NOT conference standings or tournament champion.",
            "Power-only strength is NOT NCAA NET, quadrants, official selection criteria or bid probability.",
            "Unknown/reclassifying member eligibility, conference tournament results, and bracket seed positions unavailable.",
            "No participant is officially in 2027 March Madness until Selection Sunday.",
        ],
    }
    if len(groups) != AUTOMATIC or len(eligible) < FIELD_SIZE:
        report.update({"status": "insufficient-coverage",
                       "reason": f"Need 32 source-verified conferences and 76 rated candidates; have {len(groups)} and {len(eligible)}",
                       "teams": [], "bubble": []})
        return report
    def order(t: dict):
        return (-float(t["projectedRating"]), -int(t["wins"])-int(t["losses"]), t["name"])
    leaders = [sorted(by_conference[c], key=order)[0] for c in groups]
    leader_ids = {t["teamId"] for t in leaders}
    remaining = sorted((t for t in eligible if t["teamId"] not in leader_ids), key=order)
    chosen = [(t, "conference-proxy") for t in leaders] + [
        (t, "power-only-at-large") for t in remaining[:AT_LARGE]
    ]
    if len(chosen) != FIELD_SIZE:
        raise ValueError("watchlist could not form 76 unique source-linked teams")
    chosen.sort(key=lambda pair: order(pair[0]))
    def public(t: dict, tag: str, rank: int | None = None):
        games = int(t["wins"]) + int(t["losses"])
        return {
            "teamId": t["teamId"], "name": t["name"],
            "conference": t["conference"], "projectedRating": t["projectedRating"],
            "wins": t["wins"], "losses": t["losses"], "games": games,
            "category": tag,
            "powerRank": rank,
            "sampleBand": "low (<5 games)" if games < 5 else
                          "medium (5–14)" if games < 15 else "higher (15+)",
        }
    report.update({
        "status": "ready",
        "teams": [public(t, label, i+1) for i, (t, label) in enumerate(chosen)],
        "bubble": [public(t, "near-power-cutline") for t in remaining[AT_LARGE:AT_LARGE+16]],
        "conferenceLeaders": len(leaders),
        "atLargeCandidates": AT_LARGE,
        "cutlineRating": round(chosen[-1][0]["projectedRating"], 1),
        "note": "An exploratory strength-based watchlist, not a credible Selection Sunday field or seeding forecast.",
    })
    return report
