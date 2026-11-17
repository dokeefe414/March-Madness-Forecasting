"""Offline integrity audit of committed immutable prediction/settlement evidence.

The archival workflow can only add a match to the public scoreboard when:
- a snapshot file proves a forecast was generated ahead of the scheduled start
- its current-season rating snapshot was retrieved by the claimed forecast time
- the settlement is unique and refers to a real original snapshot prediction
- the stored Brier/log loss/accuracy equals the deterministic result

This validation checks *internal evidence* only. It cannot independently certify
external API content or guarantee the event actually began at the listed time.
"""
from __future__ import annotations
import argparse
import json
import math
from datetime import timedelta
from pathlib import Path

from .snapshot import BUFFER_MINUTES, parse_time


def _read_all(folder: Path) -> list[tuple[Path, dict]]:
    output = []
    for path in sorted(folder.glob("*.json")):
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Unreadable ledger JSON: {path.name}") from exc
        if not isinstance(obj, dict):
            raise ValueError(f"Ledger entry must be a JSON object: {path.name}")
        output.append((path, obj))
    return output


def audit_ledger(folder: Path) -> dict:
    """Recompute derived metrics and verify append-only archive integrity."""
    folder = Path(folder)
    sources = _read_all(folder / "snapshots")
    settlements = _read_all(folder / "settlements")
    raw_index = folder / "index.json"
    if raw_index.exists():
        index = json.loads(raw_index.read_text(encoding="utf-8"))
    else:
        index = None
    original: dict[str, tuple[dict, dict]] = {}
    for path, snap in sources:
        if not isinstance(snap.get("predictions"), list):
            raise ValueError(f"Snapshot missing predictions: {path.name}")
        created = parse_time(snap["generatedAtUtc"])
        retrieved = parse_time(snap["ratingRetrievedAtUtc"])
        if retrieved > created:
            raise ValueError(f"Rating newer than forecast: {path.name}")
        buffer_minutes = int(snap.get("timeBufferMinutes", -1))
        if buffer_minutes < BUFFER_MINUTES or buffer_minutes > 360:
            raise ValueError(f"Invalid forecast time buffer: {path.name}")
        if snap.get("snapshotId") != path.stem:
            raise ValueError(f"Snapshot filename/id mismatch: {path.name}")
        for pred in snap["predictions"]:
            key = snap["snapshotId"] + ":" + str(pred["eventId"])
            if key in original:
                raise ValueError(f"Duplicate pregame snapshot prediction {key}")
            model_day = pred.get("modelTrainingThroughDate")
            if model_day is not None and model_day >= pred["scheduledEasternDate"]:
                raise ValueError(f"Online model training reaches forecast day: {key}")
            if pred.get("model") == "chronologically validated in-season logistic":
                if not model_day or not pred.get("modelId"):
                    raise ValueError(f"Trained forecast lacks as-of model provenance: {key}")
            start = parse_time(pred["scheduledStartUtc"])
            if created + timedelta(minutes=buffer_minutes) >= start:
                raise ValueError(f"Forecast not before tip-off buffer: {key}")
            p = float(pred["homeWinProbability"])
            q = float(pred["awayWinProbability"])
            if not (math.isfinite(p) and math.isfinite(q) and 0 < p < 1
                    and 0 < q < 1 and abs(p + q - 1) < 0.00001):
                raise ValueError(f"Invalid probability complement: {key}")
            original[key] = (snap, pred)
    scored: list[dict] = []
    seen: set[str] = set()
    for path, group in settlements:
        settled_at = parse_time(group["generatedAtUtc"])
        if not isinstance(group.get("results"), list):
            raise ValueError(f"Settlement missing results: {path.name}")
        for row in group["results"]:
            key = row["predictionKey"]
            if key in seen:
                raise ValueError(f"Duplicate settled forecast {key}")
            seen.add(key)
            if key not in original:
                raise ValueError(f"Settlement without original forecast {key}")
            snap, pred = original[key]
            start = parse_time(pred["scheduledStartUtc"])
            if settled_at <= start:
                raise ValueError(f"Settlement predates scheduled tip-off: {key}")
            if row["snapshotId"] != snap["snapshotId"] or row["eventId"] != pred["eventId"]:
                raise ValueError(f"Settlement identity mismatch: {key}")
            if parse_time(row["forecastAtUtc"]) != parse_time(snap["generatedAtUtc"]):
                raise ValueError(f"Settlement forecast timestamp mismatch: {key}")
            if parse_time(row["scheduledStartUtc"]) != start:
                raise ValueError(f"Settlement scheduled time mismatch: {key}")
            if str(row["home"]) != str(pred["home"]) or str(row["away"]) != str(pred["away"]):
                raise ValueError(f"Settlement team mismatch: {key}")
            p = float(pred["homeWinProbability"])
            if abs(float(row["predictedHome"]) - p) > 0.0000001:
                raise ValueError(f"Settlement probability changed: {key}")
            y = int(row["observedHome"])
            if y not in (0, 1):
                raise ValueError(f"Invalid observed outcome: {key}")
            if (int(row["homeScore"]) > int(row["awayScore"])) != bool(y) or int(row["homeScore"]) == int(row["awayScore"]):
                raise ValueError(f"Settlement contradicts final score: {key}")
            brier = (p-y)**2
            loss = -math.log(p if y else 1-p)
            accuracy = float(int((p > .5 and y == 1) or (p < .5 and y == 0))) if p != .5 else .5
            if (abs(float(row["brier"]) - brier) > .000001 or
                abs(float(row["logLoss"]) - loss) > .000001 or
                abs(float(row["winnerCorrect"]) - accuracy) > .000001):
                raise ValueError(f"Settlement probability scoring mismatch: {key}")
            scored.append(row)
    metrics = {
        "settledPredictions": len(scored),
        "brier": round(sum(float(r["brier"]) for r in scored)/len(scored),6) if scored else None,
        "logLoss": round(sum(float(r["logLoss"]) for r in scored)/len(scored),6) if scored else None,
        "winnerAccuracy": round(sum(float(r["winnerCorrect"]) for r in scored)/len(scored),6) if scored else None,
    }
    if index is not None:
        if index.get("scores") != metrics:
            raise ValueError("Public index metrics disagree with immutable settlement entries")
        snapshot_summary = index.get("snapshots", [])
        if any(item["id"] not in {s["snapshotId"] for _, s in sources} for item in snapshot_summary):
            raise ValueError("Public index references missing snapshot")
        for r in index.get("settlements", []):
            if r["predictionKey"] not in seen:
                raise ValueError("Public index contains non-archived settlement")
    return {"status": "verified", "snapshots": len(sources),
            "predictions": len(original), "settlements": len(settlements),
            "settledPredictions": len(scored), "scores": metrics,
            "warning": "Internal evidence validated; source and actual start time are not independently certified."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, default=Path("web/public/forecasts"))
    args = parser.parse_args()
    print(json.dumps(audit_ledger(args.dir), indent=2))


if __name__ == "__main__":
    main()
