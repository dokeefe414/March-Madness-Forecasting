"""Opponent-adjusted offensive/defensive pace-based estimates from NCAA team box.

Unlike raw margin this reads actual offensive/defensive possession counts
(o_poss, d_poss) and efficiency ratings (ortg, drtg). Only game IDs present
in the confirmed schedule-finals snapshot are accepted. The iterative
opponent adjustment is a regularized descriptive model, not fitted tournament
win probabilities.
"""
from __future__ import annotations
import csv
import io
import math
from collections import defaultdict
from .reference import canonical

BOX_URL = ("https://github.com/sportsdataverse/sportsdataverse-data/releases/download/"
           "ncaa_mbb_team_box/ncaa_mbb_team_box_2027.csv.gz")
NEEDED = {"contest_id", "team", "o_poss", "d_poss", "ortg", "drtg", "season"}


def attach_efficiency(teams: list[dict], games: list[dict],
                      csv_text: str, min_possessions: float = 30.0) -> dict:
    reader = csv.DictReader(io.StringIO(csv_text))
    missing = NEEDED - set(reader.fieldnames or ())
    if missing:
        raise ValueError(f"team-box source missing fields: {sorted(missing)}")
    lookup = {canonical(t["name"]): t for t in teams}
    finals = {str(g["id"]): g for g in games}
    records: list[dict] = []
    seen = set()
    skipped = 0
    for row in reader:
        if str(row["season"]).strip() != "2027":
            continue
        game = finals.get(str(row["contest_id"] or "").strip())
        if not game:
            continue  # only score-confirmed regular-season contests
        team_name = canonical(row["team"])
        home, away = canonical(game["home"]), canonical(game["away"])
        if team_name not in {home, away} or team_name not in lookup:
            skipped += 1
            continue
        try:
            op, dp = float(row["o_poss"]), float(row["d_poss"])
            off, defence = float(row["ortg"]), float(row["drtg"])
        except (TypeError, ValueError):
            skipped += 1
            continue
        if not (all(map(math.isfinite, (op, dp, off, defence)))
                and min_possessions <= op <= 180 and min_possessions <= dp <= 180
                and 25 <= off <= 250 and 25 <= defence <= 250):
            skipped += 1
            continue
        key = (str(game["id"]), team_name)
        if key in seen:
            skipped += 1
            continue
        seen.add(key)
        opponent = away if team_name == home else home
        records.append({
            "team": team_name, "opponent": opponent,
            "off": off, "def": defence, "op": op, "dp": dp,
            "contestId": str(game["id"]),
        })
    if not records:
        return {"source": BOX_URL, "matchedTeamGames": 0, "teamsWithMetrics": 0,
                "skippedRows": skipped, "policy": "No verified possession rows; no estimates published."}
    baseline = sum(g["off"] * g["op"] for g in records) / sum(g["op"] for g in records)
    by_team = defaultdict(list)
    for g in records:
        by_team[g["team"]].append(g)
    offense = defaultdict(float)
    defense = defaultdict(float)
    # Ridge regularization of ~600 pseudopossessions minimizes early-season
    # runaway strength estimates. Both effects are expressed per 100 possessions.
    for _ in range(12):
        new_off = {}
        for name, rows in by_team.items():
            weight = sum(g["op"] for g in rows)
            new_off[name] = sum(g["op"] * (g["off"] - baseline -
                defense[g["opponent"]]) for g in rows) / (weight + 600.0)
        new_def = {}
        for name, rows in by_team.items():
            weight = sum(g["dp"] for g in rows)
            new_def[name] = sum(g["dp"] * (g["def"] - baseline -
                new_off.get(g["opponent"], 0.0)) for g in rows) / (weight + 600.0)
        offense.update(new_off)
        defense.update(new_def)
    for name, rows in by_team.items():
        team = lookup[name]
        op_total = sum(g["op"] for g in rows)
        dp_total = sum(g["dp"] for g in rows)
        team["offRating100"] = round(sum(g["off"] * g["op"] for g in rows) / op_total, 2)
        team["defRating100"] = round(sum(g["def"] * g["dp"] for g in rows) / dp_total, 2)
        team["pacePossessions"] = round((op_total + dp_total) / (2 * len(rows)), 2)
        team["adjOff100"] = round(baseline + offense[name], 2)
        team["adjDef100"] = round(baseline + defense[name], 2)
        team["adjNet100"] = round(offense[name] - defense[name], 2)
        team["possessionGames"] = len(rows)
    return {
        "source": BOX_URL,
        "matchedTeamGames": len(records), "teamsWithMetrics": len(by_team),
        "scheduledFinalGames": len(games), "skippedRows": skipped,
        "leagueBaseEfficiency": round(baseline, 2),
        "method": "Possession-weighted per-100 rates; 12-step opponent adjustment with 600-pseudopossession ridge",
        "caveat": "Small sample, partial source coverage, descriptive not independently calibrated for March.",
    }
