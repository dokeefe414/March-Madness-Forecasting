"""Nightly 2027 in-season retraining with strictly earlier-date walk-forward tests.

This model predicts outcomes for game day D using ONLY sourced results from
days < D. We freeze all same-day feature vectors before updating any Elo
strengths, because the source provides dates but not verifiable tipoff times.

The model is a regularized logistic residual correction to ordinary Elo:
  P(home) = sigmoid(log(10) * (Elo_home + 65 - Elo_away)/400 + w · x)
  x = (Elo gap /400, bounded projected-form gap /30,
       Laplace-smoothed win-percentage gap, home-intercept=1).
No NCAA seed, same-day final or historical tournament outcome enters training.
Its held-out test days are evaluated with a model fitted only on earlier days.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from .performance import summarize_forward

from .advanced import sigmoid
from .core import TeamState, forecast_rating, matchup_probability

EASTERN = ZoneInfo("America/New_York")
MIN_TRAIN_GAMES = 160
MIN_TRAIN_DAYS = 10
MIN_EVAL_GAMES = 120
MIN_EVAL_DAYS = 12
MIN_BRIER_GAIN = 0.002
LN10 = math.log(10.0)
SCHEMA = 1


def _feature(home: TeamState, away: TeamState) -> tuple[float, float, float, float]:
    form_h = forecast_rating(home) - home.rating
    form_a = forecast_rating(away) - away.rating
    return ((home.rating + 65 - away.rating) / 400,
            max(-1.0, min(1.0, (form_h - form_a) / 30)),
            (home.wins + 1)/(home.games + 2) - (away.wins + 1)/(away.games + 2),
            1.0)


def probability(x: tuple[float, float, float, float], weights: list[float] | tuple[float, ...]) -> float:
    if len(x) != 4 or len(weights) != 4 or not all(math.isfinite(v) for v in (*x, *weights)):
        raise ValueError("expected four finite in-season feature/coefficient values")
    return sigmoid(LN10*x[0] + sum(a*b for a,b in zip(weights,x)))


def train(examples: list[tuple[tuple[float, float, float, float], int]],
          passes: int = 100, lr: float = .3, ridge: float = .08) -> list[float]:
    if not examples:
        raise ValueError("cannot retrain an empty game history")
    weights = [0.0]*4
    for _ in range(passes):
        grad = [0.0]*4
        for x,y in examples:
            err = probability(x, weights) - y
            for i in range(4):
                grad[i] += err*x[i]
        for i in range(4):
            weights[i] -= lr*(grad[i]/len(examples) + ridge*weights[i])
            weights[i] = max(-1.0, min(1.0, weights[i]))
    return weights


def _update(states: dict[str, TeamState], game: dict) -> None:
    home, away = states[game["home"]], states[game["away"]]
    y = int(game["homeScore"] > game["awayScore"])
    p = matchup_probability(home.rating, away.rating, 65)
    change = 24*(y-p)
    home.rating += change
    away.rating -= change
    home.wins += y
    home.losses += 1-y
    away.wins += 1-y
    away.losses += y
    home.history.append(home.rating)
    away.history.append(away.rating)


def _bootstrap(days: list[tuple[str, list[float]]], samples: int = 500) -> list[float] | None:
    if len(days) < 2:
        return None
    rng = random.Random(2027)
    measures = []
    for _ in range(samples):
        picked = [days[rng.randrange(len(days))][1] for _ in days]
        values = [v for daily in picked for v in daily]
        measures.append(sum(values)/len(values))
    measures.sort()
    return [round(measures[int(.025*samples)],6), round(measures[int(.975*samples)-1],6)]


def score_archived_forward(root: Path | None) -> dict:
    """Check already frozen earliest actual predictions; do not tune from misses.

    Shadow candidate and baseline must be probabilities frozen for the same
    fixture in the original *before-tipoff* Git artifact. Each game is counted
    once. The training gate is conservative until 40 genuine settled pairs.
    """
    if root is None:
        return {"status":"not-requested","pairedGames":0,"promote":False,
                "reason":"No immutable live-game archive was provided"}
    snapshots=[]
    settlements=[]
    for file in sorted((root/"snapshots").glob("*.json")):
        snapshots.append(json.loads(file.read_text(encoding="utf-8")))
    for file in sorted((root/"settlements").glob("*.json")):
        settlements.extend(json.loads(file.read_text(encoding="utf-8"))["results"])
    summary=summarize_forward(snapshots,settlements)
    compare=summary["shadowComparison"]
    paired=compare["pairedGames"]
    gain=compare["challengerBrierGain"]
    # Never train/adjust coefficients by the result of the one game we missed.
    allowed=paired>=40 and gain is not None and gain>=.002
    return {"status":"eligible" if allowed else "insufficient-evidence",
            "pairedGames":paired,"minPairedGames":40,
            "eloBrier":compare["eloBrier"],
            "challengerBrier":compare["challengerBrier"],
            "challengerBrierGain":gain,"promote":allowed,
            "reason":("Earlier live predictions and true source finals justify continued evaluation"
                      if allowed else "Keep Elo for actual picks until >=40 unique settled, paired pretipoff comparisons show Brier gain >=0.002"),
            "note":"Each ESPN event uses its earliest source-archived forecast. This is forward monitoring, not immediate adjustment after a single miss."}


def build_report(games: list[dict], ratings: dict, now: datetime | None = None,
                 forward_evidence: dict | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("training clock requires timezone")
    now = now.astimezone(timezone.utc)
    eastern_date = now.astimezone(EASTERN).date()
    if ratings.get("mode") != "current" or ratings.get("season") != 2027:
        raise ValueError("online model requires current 2027 Elo snapshot")
    if not isinstance(games,list) or len(games) != ratings.get("regularSeasonGames"):
        raise ValueError("game archive and current rating source counts differ")
    if not ratings.get("retrievedAtUtc"):
        raise ValueError("missing retrieval timestamp")
    # Provider dates are Eastern game dates, not trustworthy tipoff timestamps.
    # Exclude the ENTIRE current Eastern date from model fitting/evaluation.
    grouped = defaultdict(list)
    ids = set()
    for game in games:
        if game["id"] in ids:
            raise ValueError("duplicate source contest ID")
        ids.add(game["id"])
        day = date.fromisoformat(game["date"])
        if day >= eastern_date:
            continue
        if day > date.fromisoformat(ratings["lastGameDate"]):
            raise ValueError("future game beyond current ratings snapshot")
        if game["home"] == game["away"] or not all(isinstance(game[k],int) and game[k]>0 for k in ("homeScore","awayScore")) or game["homeScore"]==game["awayScore"]:
            raise ValueError("invalid game in training set")
        grouped[day.isoformat()].append(game)
    if not grouped:
        return {
            "schemaVersion": SCHEMA, "type":"current-season-chronological-logistic",
            "season":2027,"mode":"baseline","reason":"No completed previous-day games to fit",
            "ratingRetrievedAtUtc":ratings["retrievedAtUtc"],"trainedThroughDate":None,
            "trainingGames":0,"evaluationGames":0,"evaluationDays":0,
            "modelWeights":None,"walkForward":None,
        }
    states: dict[str,TeamState] = {}
    examples: list[tuple[tuple[float,float,float,float],int]] = []
    played_days = 0
    validation: list[dict] = []
    differences: list[tuple[str,list[float]]] = []
    for day in sorted(grouped):
        batch = sorted(grouped[day], key=lambda g: g["id"])
        day_examples = []
        for g in batch:
            for name in (g["home"], g["away"]):
                states.setdefault(name, TeamState(team_id=len(states)+1, name=name))
            x = _feature(states[g["home"]], states[g["away"]])
            y = int(g["homeScore"] > g["awayScore"])
            baseline = matchup_probability(states[g["home"]].rating, states[g["away"]].rating,65)
            day_examples.append((x,y,baseline,g["id"]))
        if len(examples) >= MIN_TRAIN_GAMES and played_days >= MIN_TRAIN_DAYS:
            weights = train(examples)
            diffs = []
            for x,y,p,gid in day_examples:
                candidate = probability(x, weights)
                diffs.append((p-y)**2-(candidate-y)**2)
                validation.append({"date":day,"eventId":gid,
                                   "priorTrainingGames":len(examples),"priorTrainingDays":played_days,
                                   "baselineBrier":round((p-y)**2,8),
                                   "trainedBrier":round((candidate-y)**2,8)})
            differences.append((day,diffs))
        examples.extend((x,y) for x,y,_,_ in day_examples)
        # AFTER all pre-day predictions. Match EloEngine's deterministic
        # same-day ordering by winner/loser team identity, not contest ID.
        # Either ordering is only an approximation without tipoff timestamps.
        def elo_order(g: dict) -> tuple[str, str, str]:
            winner = g["home"] if g["homeScore"] > g["awayScore"] else g["away"]
            loser = g["away"] if winner == g["home"] else g["home"]
            return (winner.casefold(), loser.casefold(), g["id"])
        for g in sorted(batch, key=elo_order):
            _update(states,g)
        played_days+=1
    weights = train(examples)
    baseline_brier = sum(v["baselineBrier"] for v in validation)/len(validation) if validation else None
    trained_brier = sum(v["trainedBrier"] for v in validation)/len(validation) if validation else None
    ci = _bootstrap(differences)
    gain = baseline_brier-trained_brier if validation else None
    chronological_pass = (len(validation)>=MIN_EVAL_GAMES and len(differences)>=MIN_EVAL_DAYS
                and gain is not None and gain >= MIN_BRIER_GAIN
                and ci is not None and ci[0]>0)
    # The candidate cannot become an operational public pick solely because
    # retrospective replay looks attractive. Require first real publication.
    forward_evidence = forward_evidence or score_archived_forward(None)
    promoted = chronological_pass and forward_evidence.get("promote") is True
    model_id = hashlib.sha256(json.dumps({
        "through":max(grouped), "weights":weights, "count":len(examples),
        "sourceRetrieved": ratings["retrievedAtUtc"]
    },sort_keys=True).encode()).hexdigest()[:16]
    return {
        "schemaVersion":SCHEMA,"type":"current-season-chronological-logistic",
        "season":2027,"mode":"active" if promoted else "shadow",
        "reason":("Chronological and independent real pregame Brier gates passed"
                  if promoted else "Elo remains operational until retrospective AND real first-pick forward evidence passes both gates"),
        "chronologicalGatePassed":chronological_pass,
        "forwardValidation":forward_evidence,
        "modelId":model_id,"modelWeights":[round(x,9) for x in weights],
        "ratingRetrievedAtUtc":ratings["retrievedAtUtc"],
        "lastIncludedResultDate":ratings["lastGameDate"],
        "trainedThroughDate":max(grouped),
        "trainingCutoffExclusive":eastern_date.isoformat(),
        "generatedAtUtc":now.isoformat().replace("+00:00","Z"),
        "source":ratings.get("sourceUrl"),
        "trainingGames":len(examples),"trainingDays":played_days,
        "excludedCurrentDateGames":len(games)-len(examples),
        "evaluationGames":len(validation),"evaluationDays":len(differences),
        "walkForward":{
            "eloBrier":round(baseline_brier,6) if validation else None,
            "onlineLogisticBrier":round(trained_brier,6) if validation else None,
            "modelBrierGain":round(gain,6) if gain is not None else None,
            "dayBlockGain95":ci,
            "minTrainingGames":MIN_TRAIN_GAMES,"minTrainingDays":MIN_TRAIN_DAYS,
            "minEvaluationGamesToPromote":MIN_EVAL_GAMES,
            "minEvaluationDaysToPromote":MIN_EVAL_DAYS,
            "minBrierGainToPromote":MIN_BRIER_GAIN,
            "sampleEvaluation":validation[-20:],
            "method":"Strict rolling date-origin; each tested date uses weights from earlier dates only",
        },
        "features":["home_advantaged_elo_gap","causal_recent_form_gap","smoothed_win_percentage_gap","home_intercept"],
        "caveats":[
            "Source game dates have no independently verified tipoff time. Every game on a given date is evaluated before same-day Elo updates.",
            "Retrospective rolling-day scores are not proof of public pregame predictions. Only the separate immutable prediction ledger provides that evidence.",
            "No current-date result is used in training; incomplete or provisional upstream scoreboards can still require correction.",
            "Promoted weight parameters are a 2027 regular-season model, not an NCAA tournament seeding or bracket model.",
        ],
    }


def validate_for_pick(report: dict | None, ratings: dict, scheduled_date: str) -> dict | None:
    """Safely choose trained weights only for genuinely future fixture dates."""
    if not report or report.get("mode")!="active":
        return None
    if report.get("type")!="current-season-chronological-logistic" or report.get("season")!=2027:
        raise ValueError("wrong online model contract")
    if report.get("ratingRetrievedAtUtc")!=ratings.get("retrievedAtUtc"):
        raise ValueError("online model and ratings source do not share an as-of retrieval")
    through = report.get("trainedThroughDate")
    if not isinstance(through,str) or through>=scheduled_date:
        raise ValueError("model trained using same-date or future fixture results")
    weights=report.get("modelWeights")
    if not isinstance(weights,list) or len(weights)!=4 or not all(isinstance(v,(float,int)) and math.isfinite(v) and abs(v)<=1.00001 for v in weights):
        raise ValueError("invalid online model coefficients")
    return report


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games",type=Path,default=Path("web/public/current/2027-games.json"))
    parser.add_argument("--ratings",type=Path,default=Path("web/public/current/2027.json"))
    parser.add_argument("--out",type=Path,default=Path("web/public/current/2027-online-model.json"))
    parser.add_argument("--ledger",type=Path,help="Read-only frozen public forecast archive for independent forward activation gate")
    args=parser.parse_args()
    gamefile=json.loads(args.games.read_text(encoding="utf-8"))
    ratings=json.loads(args.ratings.read_text(encoding="utf-8"))
    if gamefile.get("season")!=2027 or gamefile.get("retrievedAtUtc")!=ratings.get("retrievedAtUtc"):
        raise ValueError("training source does not match the published ratings snapshot")
    report=build_report(gamefile["games"],ratings,
                        forward_evidence=score_archived_forward(args.ledger))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(f"Chronologically retrained on {report['trainingGames']} prior-day games, "
          f"{report['evaluationGames']} rolling-origin tests; mode {report['mode']}. "
          f"Report: {args.out}")


if __name__=="__main__":
    main()
