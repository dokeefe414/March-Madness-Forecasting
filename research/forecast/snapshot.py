"""Immutable *pre-tipoff* prediction ledger with source timestamps and settlement.

Sources:
  - Current NCAA-source Elo snapshot generated **before** each event
  - ESPN public men's college basketball site scoreboard (scheduled event time,
    event ID, participant names; independent from the result feed)
  - NCAA-source completed final results used *later*, only for settlement

No browser-side writes: GitHub Actions appends snapshots and separate settlement
artifacts to the public repository. If a future schedule cannot be verified,
nothing is published (rather than manufacturing "predictions").
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from .core import matchup_probability
from .reference import canonical
from .live import SOURCE_URL, final_games, fetch_csv
from .retrain import validate_for_pick, probability as online_probability
from .performance import summarize_forward

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard"
LOCAL = ZoneInfo("America/New_York")
BUFFER_MINUTES = 15


def parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Invalid event UTC datetime {value!r}") from exc
    if parsed.tzinfo is None:
        raise ValueError("Event start requires explicit timezone")
    return parsed.astimezone(timezone.utc)


def fixture_source(day: date) -> str:
    return ESPN_BASE + "?" + urlencode({
        "groups": "50", "limit": "500", "dates": day.strftime("%Y%m%d"),
    })


def retrieve_fixture(day: date) -> dict:
    request = Request(fixture_source(day),
                      headers={"User-Agent": "MarchForecastResearch/0.6",
                               "Accept": "application/json"})
    with urlopen(request, timeout=30) as response:
        raw = response.read(3_000_001)
    if len(raw) > 3_000_000:
        raise ValueError("ESPN fixture JSON exceeded 3 MB bounded size")
    result = json.loads(raw)
    if not isinstance(result, dict) or not isinstance(result.get("events"), list):
        raise ValueError("ESPN fixture response missing events")
    return result


def _one_team(side: dict, name_index: dict[str, list[dict]],
              id_index: dict[str, list[dict]] | None = None) -> dict | None:
    team = side.get("team") or {}
    if not isinstance(team, dict):
        return None
    # Prefer a season-2027 NCAA↔ESPN verified team-ID join when present.
    # ESPN display names may contain mascots or inconsistent abbreviations.
    provider_id = str(team.get("id") or "").strip()
    linked = (id_index or {}).get(provider_id,[]) if provider_id else []
    if len(linked) == 1:
        return linked[0]
    if len(linked)>1:
        return None
    matched: dict[str, dict] = {}
    for label in ("location", "shortDisplayName", "displayName"):
        name = canonical(team.get(label))
        if not name:
            continue
        entries = name_index.get(name, [])
        if len(entries) == 1:
            # Do not override a contradictory verified provider ID based
            # solely on similar school names from another ESPN program.
            if not provider_id or not entries[0].get("espnSourceTeamId") or (
                str(entries[0]["espnSourceTeamId"]) == provider_id):
                matched[entries[0]["teamId"]] = entries[0]
    # ESPN's location and display names occasionally refer to different
    # programs: do not pick whichever name appears first.
    return next(iter(matched.values())) if len(matched) == 1 else None


def forecast_scheduled(scoreboards: list[dict], ratings: dict,
                       generated_at: datetime, online_model: dict | None = None,
                       state_space: dict | None = None) -> dict:
    """Strict as-of future-start verification and source identity matching."""
    generated_at = generated_at.astimezone(timezone.utc)
    retrieved = parse_time(ratings["retrievedAtUtc"])
    if retrieved > generated_at:
        raise ValueError("rating source snapshot cannot be retrieved in the future")
    if ratings.get("mode") != "current" or ratings.get("season") != 2027:
        raise ValueError("wrong season or model mode")
    name_index: dict[str, list[dict]] = {}
    for team in ratings["teams"]:
        name_index.setdefault(canonical(team["name"]), []).append(team)
    id_index: dict[str,list[dict]] = {}
    for row in ratings["teams"]:
        if row.get("espnSourceTeamId"):
            id_index.setdefault(str(row["espnSourceTeamId"]), []).append(row)
    if state_space is not None and (state_space.get("season") != 2027 or
           state_space.get("ratingRetrievedAtUtc") != ratings["retrievedAtUtc"]):
        raise ValueError("state-space and ratings do not share source provenance")
    unique: dict[str, dict] = {}
    counters = {"eventsSeen": 0, "notScheduled": 0, "startedOrTooClose": 0,
                "unmatchedOrAmbiguous": 0, "duplicateIds": 0}
    cutoff = generated_at + timedelta(minutes=BUFFER_MINUTES)
    for scoreboard in scoreboards:
        if not isinstance(scoreboard, dict) or not isinstance(scoreboard.get("events"), list):
            raise ValueError("fixture input must include events list")
        for event in scoreboard["events"]:
            counters["eventsSeen"] += 1
            event_id = str(event.get("id", "")).strip()
            status = ((event.get("status") or {}).get("type") or {})
            if not event_id or str(status.get("name", "")).upper() != "STATUS_SCHEDULED":
                counters["notScheduled"] += 1
                continue
            if status.get("completed"):
                counters["notScheduled"] += 1
                continue
            starts = parse_time(event["date"])
            if starts <= cutoff:
                counters["startedOrTooClose"] += 1
                continue
            competitions = event.get("competitions") or []
            sides = (competitions[0].get("competitors") or []) if competitions else []
            home_sides = [s for s in sides if s.get("homeAway") == "home"]
            away_sides = [s for s in sides if s.get("homeAway") == "away"]
            if len(home_sides) != 1 or len(away_sides) != 1:
                counters["unmatchedOrAmbiguous"] += 1
                continue
            home = _one_team(home_sides[0], name_index, id_index)
            away = _one_team(away_sides[0], name_index, id_index)
            if not home or not away or home["teamId"] == away["teamId"]:
                counters["unmatchedOrAmbiguous"] += 1
                continue
            if event_id in unique:
                counters["duplicateIds"] += 1
                continue
            neutral = bool(competitions[0].get("neutralSite", False))
            # The trained home/away correction is not evaluated for neutral
            # venues. Such games keep the baseline without an extrapolation.
            future_eastern_day = starts.astimezone(LOCAL).date().isoformat()
            candidate = None
            if (not neutral and online_model and
                online_model.get("mode") in ("active","shadow")):
                # Compute the shadow candidate before outcome; the original
                # mode still controls whether it may become the actual pick.
                candidate = validate_for_pick({**online_model,"mode":"active"},
                                              ratings,future_eastern_day)
            selected = candidate if online_model and online_model.get("mode")=="active" else None
            baseline = matchup_probability(home["rating"], away["rating"], 0 if neutral else 65)
            challenger = None
            if candidate:
                form_gap=(home.get("trend",0)-away.get("trend",0))/30.0
                home_rate=(home["wins"]+1)/(home["wins"]+home["losses"]+2)
                away_rate=(away["wins"]+1)/(away["wins"]+away["losses"]+2)
                challenger=online_probability(((home["rating"]+65-away["rating"])/400,
                       max(-1.,min(1.,form_gap)),home_rate-away_rate,1.),candidate["modelWeights"])
            state_probability=None
            if state_space is not None and not neutral and (
                    not state_space.get("trainedThroughDate") or
                    state_space["trainedThroughDate"] < future_eastern_day):
                strengths=state_space.get("strengths",{})
                if home["name"] in strengths and away["name"] in strengths:
                    state_probability=matchup_probability(strengths[home["name"]]["mean"],
                                      strengths[away["name"]]["mean"],65)
            p=challenger if selected else baseline
            model_name=("chronologically validated in-season logistic"
                        if selected else "as-of regular-season Elo")
            unique[event_id] = {
                "eventId": event_id, "scheduledStartUtc": starts.isoformat().replace("+00:00", "Z"),
                "scheduledEasternDate": starts.astimezone(LOCAL).date().isoformat(),
                "home": home["name"], "away": away["name"],
                "homeTeamId": home["teamId"], "awayTeamId": away["teamId"],
                "homeWinProbability": round(p, 7),
                "awayWinProbability": round(1-p, 7),
                "neutralSite": neutral, "model": model_name,
                "baselineHomeWinProbability":round(baseline,7),
                "challengerHomeWinProbability":round(challenger,7) if challenger is not None else None,
                "stateSpaceHomeWinProbability":round(state_probability,7) if state_probability is not None else None,
                "modelId": selected.get("modelId") if selected else None,
                "modelTrainingThroughDate": selected.get("trainedThroughDate") if selected else None,
                "match": "exact canonical NCAA name to ESPN team location/display",
            }
    result = sorted(unique.values(), key=lambda p: (p["scheduledStartUtc"], p["eventId"]))
    return {
        "schemaVersion": 1, "type": "immutable-pre-tipoff-probability-snapshot",
        "generatedAtUtc": generated_at.isoformat().replace("+00:00", "Z"),
        "ratingRetrievedAtUtc": ratings["retrievedAtUtc"],
        "lastIncludedResultDate": ratings.get("lastGameDate"),
        "scheduleSource": ESPN_BASE,
        "ratingSource": ratings.get("sourceUrl", SOURCE_URL),
        "timeBufferMinutes": BUFFER_MINUTES,
        "predictions": result, "coverage": {**counters, "published": len(result)},
        "limitations": [
            "Missing/ambiguous ESPN ↔ NCAA name matches are excluded, never guessed.",
            "ESPN scheduled start may change; this records its as-of state, not proof of the actual tip-off.",
            "Every actual and experimental probability is frozen before the listed start; challenger and state-space scenarios are not automatically promoted.",
            "Only forecasts generated before reported start (with 15-minute buffer) are stored.",
        ],
    }


def independently_verified_finals(scoreboards: list[dict]) -> dict[str, dict]:
    """Only ESPN's completed final, exact source scores, and date qualify."""
    verified: dict[str, dict] = {}
    for scoreboard in scoreboards:
        if not isinstance(scoreboard, dict) or not isinstance(scoreboard.get("events"), list):
            raise ValueError("ESPN finals source missing events")
        for event in scoreboard["events"]:
            status = ((event.get("status") or {}).get("type") or {})
            if str(status.get("name") or "").upper() != "STATUS_FINAL" or status.get("completed") is not True:
                continue
            event_id = str(event.get("id") or "").strip()
            if not event_id:
                raise ValueError("Completed ESPN final missing event ID")
            try:
                final_day = parse_time(event["date"]).astimezone(LOCAL).date().isoformat()
                comps = event.get("competitions") or []
                if len(comps) != 1:
                    continue
                sides = comps[0].get("competitors") or []
                home = [x for x in sides if x.get("homeAway") == "home"]
                away = [x for x in sides if x.get("homeAway") == "away"]
                if len(home) != 1 or len(away) != 1:
                    continue
                h, a = int(home[0]["score"]), int(away[0]["score"])
            except (KeyError, ValueError, TypeError):
                continue
            if h <= 0 or a <= 0 or h == a:
                continue
            row = {"date":final_day, "homeScore":h, "awayScore":a,
                   "verification":"independent ESPN completed STATUS_FINAL"}
            if event_id in verified and verified[event_id] != row:
                raise ValueError(f"Conflicting ESPN final for {event_id}")
            verified[event_id] = row
    return verified


def settle_snapshots(snapshots: list[dict], final_games: list[dict],
                     previously_settled: set[str], now: datetime,
                     verified_finals: dict[str,dict] | None = None) -> list[dict]:
    """Settle by exact matchup and Eastern scheduled date; never alter snapshot."""
    by_key: dict[tuple[str, str, str], list[dict]] = {}
    for g in final_games:
        by_key.setdefault((g["date"], canonical(g["home"]), canonical(g["away"])), []).append(g)
    records = []
    for snap in snapshots:
        created = parse_time(snap["generatedAtUtc"])
        if created >= now:
            continue
        # Do not settle an artifact even if manually inserted unless it
        # proves the ratings existed at capture time. Older archives may have
        # missing metadata; these cannot qualify as verified live forecasts.
        try:
            rated_at = parse_time(snap["ratingRetrievedAtUtc"])
        except (KeyError, TypeError, ValueError):
            continue
        if rated_at > created:
            continue
        for f in snap.get("predictions", []):
            key = snap["snapshotId"] + ":" + f["eventId"]
            scheduled = parse_time(f["scheduledStartUtc"])
            buffer = timedelta(minutes=int(snap.get("timeBufferMinutes", BUFFER_MINUTES)))
            if buffer < timedelta(minutes=BUFFER_MINUTES):
                continue
            if key in previously_settled or scheduled >= now or created + buffer >= scheduled:
                continue
            candidates = by_key.get((f["scheduledEasternDate"],
                                     canonical(f["home"]), canonical(f["away"])), [])
            if len(candidates) != 1:
                continue
            game = candidates[0]
            if verified_finals is not None:
                check = verified_finals.get(str(f["eventId"]))
                if (check is None or check["date"] != f["scheduledEasternDate"] or
                    check["homeScore"] != game["homeScore"] or
                    check["awayScore"] != game["awayScore"]):
                    # No independent final, unexpected score, or changed date.
                    # Refuse settlement instead of counting provisional scores.
                    continue
            outcome = int(game["homeScore"] > game["awayScore"])
            p = float(f["homeWinProbability"])
            if not (0 < p < 1):
                continue
            records.append({
                "predictionKey": key, "snapshotId": snap["snapshotId"],
                "eventId": f["eventId"], "forecastAtUtc": snap["generatedAtUtc"],
                "scheduledStartUtc": f["scheduledStartUtc"],
                "actualResultDate": game["date"], "ncaaContestId": game["id"],
                "home": game["home"], "away": game["away"],
                "homeScore": game["homeScore"], "awayScore": game["awayScore"],
                "predictedHome": p, "observedHome": outcome,
                "brier": round((p-outcome)**2, 7),
                "logLoss": round(-math.log(p if outcome else 1-p), 7),
                "winnerCorrect": int((p>.5 and outcome==1) or (p<.5 and outcome==0))
                                 if p != .5 else .5,
                "settlementPolicy": "exact canonical team pair + Eastern scheduled date",
                "espnFinalVerified": verified_finals is not None,
                "independentVerification": ("ESPN STATUS_FINAL / matching NCAA score"
                                             if verified_finals is not None else
                                             "offline legacy source match only"),
            })
    return records


def _existing(path: Path) -> list[dict]:
    return [json.loads(f.read_text(encoding="utf-8")) for f in sorted(path.glob("*.json"))]


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation ensures an immutable snapshot/settlement stays intact.
    with path.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2, sort_keys=True)
        stream.write("\n")


def write_ledger(out_dir: Path, snapshot: dict, finals: list[dict], now: datetime,
                 verified_finals: dict[str,dict] | None = None,
                 source_warnings: list[str] | None = None) -> dict:
    """Append-only source-based archives; index is a replaceable derived view."""
    folder = Path(out_dir)
    snapshot_dir, settlement_dir = folder / "snapshots", folder / "settlements"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    settlement_dir.mkdir(parents=True, exist_ok=True)
    stamp = now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if snapshot["predictions"]:
        snapshot["snapshotId"] = stamp
        _write_json(snapshot_dir / (stamp + ".json"), snapshot)
    all_snapshots = _existing(snapshot_dir)
    all_settlements = _existing(settlement_dir)
    done = {r["predictionKey"] for s in all_settlements for r in s["results"]}
    newly_done = settle_snapshots(all_snapshots, finals, done, now, verified_finals=verified_finals)
    if newly_done:
        _write_json(settlement_dir / (stamp + ".json"), {
            "generatedAtUtc": now.isoformat().replace("+00:00","Z"),
            "results": newly_done,
            "note": "Settlements are separate from immutable timestamped prediction artifacts.",
        })
    all_settlements += [{
        "results": newly_done,
    }]
    combined = [r for group in all_settlements for r in group["results"]]
    scores = {
        "settledPredictions": len(combined),
        "brier": round(sum(r["brier"] for r in combined) / len(combined), 6) if combined else None,
        "logLoss": round(sum(r["logLoss"] for r in combined) / len(combined), 6) if combined else None,
        "winnerAccuracy": round(sum(r["winnerCorrect"] for r in combined) / len(combined), 6) if combined else None,
    }
    forward = summarize_forward(all_snapshots,combined)
    index = {
        "schemaVersion": 1, "generatedAtUtc": now.isoformat().replace("+00:00", "Z"),
        "uniqueGames": forward,
        "archiveHealth": {
            "generatedAtUtc": now.isoformat().replace("+00:00", "Z"),
            "newPredictions": len(snapshot.get("predictions", [])),
            "verifiedNewSettlements": len(newly_done),
            "everArchivedPredictions": sum(len(x["predictions"]) for x in all_snapshots),
            "independentFinalVerification": verified_finals is not None,
            "completedEspnEventsChecked": len(verified_finals or {}),
            "sourceWarnings": source_warnings or [],
            "status": ("source-partial" if source_warnings else
                       "no-pregame-forecasts" if not all_snapshots else "recording"),
            "policy": "No final settlement without completed ESPN and same-score NCAA evidence",
        },
        "snapshots": [{
            "id": s["snapshotId"],
            "generatedAtUtc": s["generatedAtUtc"],
            "count": len(s["predictions"]),
            "predictions": s["predictions"],
        } for s in all_snapshots[-60:]],
        "settlements": combined[-600:],
        "scores": scores,
        "warning": "Real pre-tipoff, timestamped scheduled-game forecasts only; no backfilled historical predictions.",
    }
    _write_index = folder / "index.json"
    _write_index.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return index


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ratings", type=Path, default=Path("web/public/current/2027.json"))
    parser.add_argument("--online-model", type=Path, help="Current-source 2027 chronologically retrained model JSON")
    parser.add_argument("--state-space", type=Path, help="Optional same-source causal experimental team-state report")
    parser.add_argument("--out-dir", type=Path, default=Path("web/public/forecasts"))
    parser.add_argument("--scoreboard-json", type=Path, help="Offline fixture JSON for hermetic runs")
    parser.add_argument("--finals-csv", type=Path, help="Offline results CSV")
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    ratings = json.loads(args.ratings.read_text(encoding="utf-8"))
    online_model = json.loads(args.online_model.read_text(encoding="utf-8")) if args.online_model else None
    state_space = json.loads(args.state_space.read_text(encoding="utf-8")) if args.state_space else None
    if online_model and online_model.get("generatedAtUtc"):
        if parse_time(online_model["generatedAtUtc"]) > now:
            raise ValueError("online training artifact is newer than archived forecast")

    today = now.astimezone(LOCAL).date()
    source_warnings: list[str] = []
    if args.scoreboard_json:
        fixture_data = json.loads(args.scoreboard_json.read_text(encoding="utf-8"))
        scoreboards = fixture_data if isinstance(fixture_data, list) else [fixture_data]
        finals_scoreboards = scoreboards
    else:
        # Verify up to ten days of still-relevant finals without downloading an
        # unbounded season. Fetch future fixtures independently of old results.
        dates = [today + timedelta(days=i) for i in range(3)]
        all_old = _existing(args.out_dir / "snapshots")
        past_days = {
            date.fromisoformat(pred["scheduledEasternDate"])
            for snap in all_old for pred in snap.get("predictions", [])
            if today - timedelta(days=10) <=
               date.fromisoformat(pred["scheduledEasternDate"]) <= today
        }
        completed_dates = sorted(past_days | {
            today - timedelta(days=i) for i in range(1,4)
        })
        by_date = {}
        for day in sorted(set(dates + completed_dates)):
            try:
                by_date[day] = retrieve_fixture(day)
            except (OSError, TimeoutError, ValueError, KeyError) as exc:
                source_warnings.append(f"{day.isoformat()}: {type(exc).__name__}")
        scoreboards = [by_date[day] for day in dates if day in by_date]
        finals_scoreboards = [by_date[day] for day in completed_dates if day in by_date]
        if not scoreboards:
            raise RuntimeError("All scheduled ESPN fixture checks failed; no false archive created")
    forecast = forecast_scheduled(scoreboards, ratings, now, online_model=online_model,
                                  state_space=state_space)
    if args.finals_csv:
        finals_text = args.finals_csv.read_text(encoding="utf-8-sig")
    else:
        finals_text = fetch_csv()
    finals = final_games(finals_text, now.date())
    confirmations = independently_verified_finals(finals_scoreboards)
    index = write_ledger(args.out_dir, forecast, finals, now,
                         verified_finals=confirmations, source_warnings=source_warnings)
    print(f"Pregame futures: {len(forecast['predictions'])} "
          f"(unmatched {forecast['coverage']['unmatchedOrAmbiguous']}). "
          f"Settled archive predictions: {index['scores']['settledPredictions']}. "
          f"Archive: {args.out_dir}")


if __name__ == "__main__":
    main()
