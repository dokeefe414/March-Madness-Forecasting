"""Validate published source-derived team records and write refresh provenance.

The schedule comes from GitHub Actions' America/New_York timezone-aware cron.
This gate only checks internal source and model arithmetic; it CANNOT certify
that every latest game has been completed or published by the provider.
Conservatively fail a new static build if malformed/nonfresh source snapshots
or incoherent game/record totals would replace a healthy site.

CLI: PYTHONPATH=research python -m forecast.freshness
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


def check_snapshot(data: dict, now: datetime | None = None) -> dict:
    """Validate 2027 current-season snapshot; return transparent status."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("audit clock must carry timezone")
    now = now.astimezone(timezone.utc)
    if data.get("mode") != "current" or data.get("season") != 2027:
        raise ValueError("expected current 2027 NCAA-source ratings")
    if not data.get("sourceUrl") or not str(data["sourceUrl"]).startswith("https://"):
        raise ValueError("missing HTTPS source provenance")
    try:
        retrieved = datetime.fromisoformat(data["retrievedAtUtc"].replace("Z", "+00:00"))
        included = date.fromisoformat(data["lastGameDate"])
    except (KeyError, AttributeError, ValueError) as exc:
        raise ValueError("missing or invalid retrieval/result timestamps") from exc
    if retrieved.tzinfo is None:
        raise ValueError("retrieval time must have a timezone")
    retrieved = retrieved.astimezone(timezone.utc)
    age = now - retrieved
    if age < timedelta(minutes=-5) or age > timedelta(hours=2):
        raise ValueError("new site build refused stale or future-dated source snapshot")
    if included > now.date():
        raise ValueError("included result date lies in the future")
    total = data.get("regularSeasonGames")
    teams = data.get("teams")
    if not isinstance(total, int) or total < 1 or not isinstance(teams, list) or not teams:
        raise ValueError("cannot publish an empty/current-season score feed")
    ids: set[str] = set()
    wins = losses = 0
    for team in teams:
        ident = team.get("teamId") if isinstance(team, dict) else None
        if not isinstance(ident, str) or not ident.startswith("ncaa-") or ident in ids:
            raise ValueError("duplicate or invalid NCAA-source team identity")
        ids.add(ident)
        for key in ("rating", "projectedRating"):
            value = team.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"team has invalid {key}")
        w, l = team.get("wins"), team.get("losses")
        if (isinstance(w, bool) or isinstance(l, bool) or
            not isinstance(w, int) or not isinstance(l, int) or w < 0 or l < 0):
            raise ValueError("team has invalid win/loss record")
        wins += w
        losses += l
    if wins != total or losses != total:
        raise ValueError(f"record totals do not match source games: {wins} wins, {losses} losses, {total} games")
    games = data.get("recentGames")
    if not isinstance(games, list) or not games:
        raise ValueError("source must contain last accepted completed-score records")
    if games[0].get("date") != included.isoformat():
        raise ValueError("source latest date disagrees with most recent result")
    source_lag_days = (now.date() - included).days
    diagnostics = data.get("pregameDiagnostics")
    if isinstance(diagnostics, dict):
        if diagnostics.get("evaluatedGames") != total:
            raise ValueError("online Elo evaluation count disagrees with accepted games")
        for key in ("brier", "accuracy"):
            val = diagnostics.get(key)
            if not isinstance(val, (float, int)) or not math.isfinite(val) or not 0 <= val <= 1:
                raise ValueError(f"invalid online {key} diagnostic")
    return {
        "schemaVersion": 1,
        "mode": "nightly-source-validation",
        "auditTimeUtc": now.isoformat().replace("+00:00", "Z"),
        "retrievedAtUtc": retrieved.isoformat().replace("+00:00", "Z"),
        "lastIncludedGameDate": included.isoformat(),
        "lastNcaaScoredGameDate":(data.get("sourceReconciliation") or {}).get("ncaaLastGameDate",included.isoformat()),
        "espnOnlyRatedGames":(data.get("sourceReconciliation") or {}).get("ratedEspnOnlyFinals",0),
        "ratedGameProvenance":(data.get("sourceReconciliation") or {}).get("mode","NCAA-only"),
        "acceptedGameCount": total,
        "ratedTeamCount": len(teams),
        "confirmedDivisionIPrograms": sum(t.get("divisionIConfirmed") is True for t in teams),
        "sourceLagCalendarDaysUtc": source_lag_days,
        "status": "source-recent" if source_lag_days <= 2 else "source-may-be-delayed",
        "primaryRefresh": "1:00 a.m. America/New_York, daily",
        "lateResultCatchUp": "5:17 a.m. America/New_York, November-April",
        "preTipoffArchive": "9:07 a.m. America/New_York, November-April",
        "source": data["sourceUrl"],
        "notice": "Ratings include accepted NCAA scores plus independently ESPN-final and same-season-ID-verified supplemental games when available, with deduplication. This is not live streaming.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("web/public/current/2027.json"))
    parser.add_argument("--out", type=Path, default=Path("web/public/current/refresh-status.json"))
    args = parser.parse_args()
    result = check_snapshot(json.loads(args.input.read_text(encoding="utf-8")))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        f"Nightly data checked: {result['acceptedGameCount']} sourced games, "
        f"{result['ratedTeamCount']} rated programs, last score date "
        f"{result['lastIncludedGameDate']} ({result['espnOnlyRatedGames']} ESPN-only finals; "
        f"NCAA file through {result['lastNcaaScoredGameDate']}; "
        f"source lag {result['sourceLagCalendarDaysUtc']} UTC calendar days)"
    )


if __name__ == "__main__":
    main()
