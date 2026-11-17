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
    eligible = [t for t in teams if t.get("divisionIConfirmed") is True and t.get("conferenceVerified") and
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
        "divisionIConfirmedCandidateCount": sum(t.get("divisionIConfirmed") is True for t in teams),
        "matchedConferences": len(groups),
        "limitations": [
            "Conference leader is projected Elo leader, NOT conference standings or tournament champion.",
            "Power-only strength is NOT NCAA NET, quadrants, official selection criteria or bid probability.",
            "Division I group membership is independently source-linked when available; membership does not guarantee postseason eligibility.",
            "Unknown/reclassifying member eligibility, conference tournament results, and bracket seed positions unavailable.",
            "No participant is officially in 2027 March Madness until Selection Sunday.",
            "Seed ranges are hand-specified early-sample *strength tiers*, NOT statistically calibrated NCAA seed probabilities.",
        ],
    }
    if len(groups) != AUTOMATIC or len(eligible) < FIELD_SIZE:
        report.update({"status": "insufficient-coverage",
                       "reason": f"Need 32 2027 D-I group-linked and conference-matched leagues and 76 rated candidates; have {len(groups)} and {len(eligible)}",
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
        # Illustrative strength *range* only, not a committee seed forecast.
        # 64 direct slots plus 12 opening entrants make exact seeding
        # unknowable from rating rank alone. Early samples widen the band.
        nominal = min(16, max(1, math.ceil(rank / 4))) if rank else None
        spread = 5 if games < 5 else 3 if games < 15 else 2
        seed_range = ([max(1,nominal-spread), min(16,nominal+spread)]
                      if nominal is not None else None)
        return {
            "teamId": t["teamId"], "name": t["name"],
            "conference": t["conference"], "projectedRating": t["projectedRating"],
            "wins": t["wins"], "losses": t["losses"], "games": games,
            "category": tag,
            "powerRank": rank,
            "illustrativeSeedRange": seed_range,
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
