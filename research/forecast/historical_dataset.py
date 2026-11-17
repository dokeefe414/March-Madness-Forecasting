"""Audited historical pre-tournament feature dataset and nested walk-forward evidence.

Reads only pinned, committed historical season snapshots and verified tournament
outcomes. Source snapshot features describe each season through day 132; they
are NOT per-game historical tipoff snapshots. The winner is a label only and
never enters the feature construction. No current season, pre-tipoff ledger,
model-selection policy, or scheduled archive is modified.

Design: deterministic team-ID orientation, every sourced matchup exactly once,
source SHA-256 manifest, chronological training + nested previous-OOS selection,
season-block uncertainty, explicit incomplete/omitted seasons and honest
provenance. Standard library only; no network access.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from .benchmark import Outcome, choose_temperature, probability_of_winner

FIRST_HISTORICAL_SEASON=1985
REGULAR_SEASON_END=132
MIN_TRAIN_SEASONS=5
MIN_META_SEASONS=3
BOOTSTRAP_DRAWS=1000
SEED=17027


@dataclass(frozen=True)
class HistoricalGame:
    season:int
    day:int
    side_a_id:str
    side_b_id:str
    side_a_won:int
    winner_score:int
    loser_score:int
    elo_difference:float
    projected_difference:float
    win_pct_difference:float

    def feature_dict(self)->dict:
        return {
            "season":self.season,"day":self.day,
            "sideAId":self.side_a_id,"sideBId":self.side_b_id,
            "sideAWon":self.side_a_won,
            "winnerScore":self.winner_score,"loserScore":self.loser_score,
            "sideAEloMinusB":round(self.elo_difference,8),
            "sideAProjectedEloMinusB":round(self.projected_difference,8),
            "sideAWinPctMinusB":round(self.win_pct_difference,8)
        }


def _read(path:Path)->tuple[dict,str]:
    content=path.read_bytes()
    digest=hashlib.sha256(content).hexdigest()
    return json.loads(content),digest


def _finite_team(team:dict,season:int)->tuple[float,float,float]:
    rating=float(team["rating"])
    projected=float(team["projectedRating"])
    wins,losses=int(team.get("wins",0)),int(team.get("losses",0))
    if not(all(map(math.isfinite,(rating,projected))) and
           wins>=0 and losses>=0 and wins+losses>0):
        raise ValueError(f"Invalid pre-tournament team history in {season}")
    return rating,projected,wins/(wins+losses)


def load_dataset(web:Path)->tuple[list[HistoricalGame],dict]:
    web=Path(web)
    index,index_sha=_read(web/"data/history-index.json")
    pinned=index.get("sourceCommit")
    if not isinstance(pinned,str) or len(pinned)<12:
        raise ValueError("Historical source provenance pin missing")
    entries=index.get("seasons")
    if not isinstance(entries,list) or not entries:
        raise ValueError("Historical index is empty")
    rows=[]
    manifest=[]
    seen_seasons=set()
    for entry in sorted(entries,key=lambda x:x["season"]):
        season=int(entry["season"])
        if season in seen_seasons:raise ValueError(f"Duplicate historical season {season}")
        seen_seasons.add(season)
        status={"season":season,"indexedGames":int(entry.get("tournamentGames") or 0)}
        if (not entry.get("isComplete") or entry.get("throughDay")!=REGULAR_SEASON_END
            or not entry.get("tournamentGames")):
            manifest.append({**status,"status":"excluded-incomplete-or-no-tournament",
                            "retainedGames":0,"omittedMissingRatedTeams":0})
            continue
        rated_path=web/f"public/seasons/{season}.json"
        games_path=web/f"public/tournaments/{season}.json"
        rated,rated_sha=_read(rated_path)
        tour,tour_sha=_read(games_path)
        if rated.get("season")!=season or tour.get("season")!=season:
            raise ValueError(f"Historical season mismatch for {season}")
        if (rated.get("sourceCommit")!=pinned or tour.get("sourceCommit")!=pinned
            or rated.get("isComplete") is not True or rated.get("throughDay")!=REGULAR_SEASON_END):
            raise ValueError(f"Historical source pin or pre-tournament cutoff mismatch in {season}")
        if tour.get("mainDrawOnly"):
            manifest.append({**status,"status":"excluded-incomplete-playin-field",
                             "seasonSha256":rated_sha,"tournamentSha256":tour_sha,
                             "retainedGames":0,"omittedMissingRatedTeams":0})
            continue
        games=tour.get("games")
        if not isinstance(games,list) or len(games)!=status["indexedGames"]:
            raise ValueError(f"Historical tournament count differs from index for {season}")
        team_rows=rated.get("teams")
        if not isinstance(team_rows,list) or len(team_rows)!=int(entry["teams"]):
            raise ValueError(f"Historical rating team count differs from index for {season}")
        team_map={}
        for team in team_rows:
            key=str(team["teamId"])
            if key in team_map:raise ValueError(f"Duplicate rated team identity {season}:{key}")
            team_map[key]=team
        omitted=0
        seen_events=set()
        season_rows=[]
        for game in games:
            day=int(game["day"])
            w,l=str(game["winnerId"]),str(game["loserId"])
            ws,ls=int(game["winnerScore"]),int(game["loserScore"])
            if (day<=REGULAR_SEASON_END or day>175 or w==l
                or ws<=ls or ls<=0 or ws>200):
                raise ValueError(f"Invalid postseason outcome in {season}")
            key=(day,tuple(sorted((w,l))))
            if key in seen_events:raise ValueError(f"Duplicate tournament matchup {season}:{key}")
            seen_events.add(key)
            if w not in team_map or l not in team_map:
                omitted+=1
                continue
            a,b=sorted((w,l))
            ar,apr,apct=_finite_team(team_map[a],season)
            br,bpr,bpct=_finite_team(team_map[b],season)
            season_rows.append(HistoricalGame(
                season,day,a,b,int(a==w),ws,ls,ar-br,apr-bpr,apct-bpct))
        rows.extend(sorted(season_rows,key=lambda g:(g.day,g.side_a_id,g.side_b_id)))
        manifest.append({**status,"status":"usable","seasonSha256":rated_sha,
                         "tournamentSha256":tour_sha,"ratedTeams":len(team_map),
                         "retainedGames":len(season_rows),
                         "omittedMissingRatedTeams":omitted,
                         "featureCutoffDay":REGULAR_SEASON_END})
    if len({r.season for r in rows})<MIN_TRAIN_SEASONS+2:
        raise ValueError("Insufficient complete source-pinned seasons for out-of-time evaluation")
    report={"schemaVersion":1,"sourceCommit":pinned,
            "historicalIndexSha256":index_sha,
            "featureAsOf":"season-specific frozen pre-tournament day 132",
            "labelSource":"pinned historical NCAA tournament results, after cutoff",
            "firstSeason":min(seen_seasons),"lastSeason":max(seen_seasons),
            "includedSeasons":len({r.season for r in rows}),
            "includedGames":len(rows),
            "omittedMissingRatedTeams":sum(x["omittedMissingRatedTeams"] for x in manifest),
            "excludedSeasons":[x["season"] for x in manifest if x["status"]!="usable"],
            "perSeason":manifest,
            "caveat":"These regular-season day-132 features precede historical tournament games; they are NOT per-game pre-tipoff data, and the games are observed tournament matchups rather than hypothetical bracket paths."}
    return rows,report


def _scores(rows:list[tuple[float,int]])->dict:
    if not rows:return {"games":0,"brier":None,"logLoss":None,"accuracy":None}
    n=len(rows)
    return {"games":n,
            "brier":round(sum((p-y)**2 for p,y in rows)/n,6),
            "logLoss":round(-sum(math.log(max(1e-12,p if y else 1-p)) for p,y in rows)/n,6),
            "accuracy":round(sum(.5 if p==.5 else float((p>.5)==bool(y)) for p,y in rows)/n,6)}


def _confidence_bins(rows:list[tuple[float,int]])->list[dict]:
    bins=[[] for _ in range(5)]
    for p,y in rows:
        conf=max(p,1-p)
        favorite_win=(y==1) if p>.5 else (y==0) if p<.5 else .5
        i=min(4,int((conf-.5)*10))
        bins[i].append((conf,float(favorite_win)))
    return [
        {"range":f"{50+i*10}–{60+i*10}%",
         "count":len(group),
         "predictedConfidence":round(sum(x for x,_ in group)/len(group),6) if group else None,
         "favoriteAccuracy":round(sum(y for _,y in group)/len(group),6) if group else None}
        for i,group in enumerate(bins)
    ]


def _season_block_interval(by_season:list[list[tuple[float,int,float]]],
                           draws:int=BOOTSTRAP_DRAWS)->list[float]|None:
    if len(by_season)<5:return None
    rng=random.Random(SEED)
    sampled=[]
    for _ in range(draws):
        group=[by_season[rng.randrange(len(by_season))] for _ in by_season]
        values=[(b-y)**2-(p-y)**2 for season in group for p,y,b in season]
        sampled.append(sum(values)/len(values))
    sampled.sort()
    return [round(sampled[int(.025*draws)],6),round(sampled[int(.975*draws)-1],6)]


def evaluate(rows:list[HistoricalGame],manifest:dict,min_training_seasons:int=MIN_TRAIN_SEASONS)->dict:
    years=sorted({r.season for r in rows})
    if min_training_seasons<1 or len(years)<min_training_seasons+2:
        raise ValueError("Not enough earlier training seasons")
    by_year=defaultdict(list)
    for row in rows:
        by_year[row.season].append(row)
    if len(by_year)!=len(years):raise ValueError("Invalid year partition")
    previous_oos=[]
    results=[]
    observed=[]
    by_season_delta=[]
    for i in range(min_training_seasons,len(years)):
        season=years[i]
        history=[r for year in years[:i] for r in by_year[year]]
        # Winner orientation is used solely to train the original calibrated
        # Elo temperature; side A remains sorted by numeric/text team ID
        # before the labels are even read.
        past=[Outcome((2*r.side_a_won-1)*r.elo_difference,
                      (2*r.side_a_won-1)*r.projected_difference)
              for r in history]
        temperature=choose_temperature(past)
        # Nested selection: only prior held-out years may choose calibrated
        # over Elo. Holdout seasons are never used to tune themselves.
        previous_eligible=len(previous_oos)>=MIN_META_SEASONS
        prev_elo=sum(x["eloBrier"]*x["games"] for x in previous_oos)/sum(x["games"] for x in previous_oos) if previous_eligible else None
        prev_cal=sum(x["calibratedBrier"]*x["games"] for x in previous_oos)/sum(x["games"] for x in previous_oos) if previous_eligible else None
        selected="calibrated" if previous_eligible and prev_cal+0.001<prev_elo else "elo"
        one=[]
        for row in by_year[season]:
            base=probability_of_winner(row.elo_difference)
            calibrated=probability_of_winner(row.projected_difference,temperature)
            choice=calibrated if selected=="calibrated" else base
            one.append((base,calibrated,choice,row.side_a_won))
        baseline=_scores([(a,y) for a,_,_,y in one])
        calibrated=_scores([(b,y) for _,b,_,y in one])
        chosen=_scores([(c,y) for _,_,c,y in one])
        previous_oos.append({"season":season,"games":len(one),"eloBrier":baseline["brier"],
                             "calibratedBrier":calibrated["brier"]})
        results.append({"season":season,"trainingThrough":years[i-1],
                        "trainingSeasons":i,"evaluatedGames":len(one),
                        "temperatureFromPriorYears":temperature,
                        "selectionPriorOosSeasons":i-min_training_seasons,
                        "selectedByEarlierOos":selected,
                        "elo":baseline,"calibrated":calibrated,"nestedSelected":chosen})
        observed.extend(one)
        by_season_delta.append([(c,y,a) for a,_,c,y in one])
    active=_scores([(c,y) for _,_,c,y in observed])
    elo=_scores([(a,y) for a,_,_,y in observed])
    calibrated=_scores([(b,y) for _,b,_,y in observed])
    return {"schemaVersion":1,
            "evaluationType":"historical-pre-tournament-day132-nested-walk-forward",
            "sourceCommit":manifest["sourceCommit"],
            "datasetIndexSha256":manifest["historicalIndexSha256"],
            "evaluatedSeasons":len(results),"testedGames":len(observed),
            "firstTestSeason":results[0]["season"],"lastTestSeason":results[-1]["season"],
            "selectionPolicy":"For each season, train temperature exclusively on earlier tournament years. Choose between Elo and calibrated trend Elo only from at least three earlier out-of-time tournament seasons, with a 0.001 Brier gain required. Then score the untouched next year.",
            "metrics":{"elo":elo,"calibratedTrendElo":calibrated,"nestedSelected":active},
            "nestedBrierGainVsElo":round(elo["brier"]-active["brier"],6),
            "nestedGainSeasonBlock95":_season_block_interval(by_season_delta),
            "calibration":{"elo":_confidence_bins([(a,y) for a,_,_,y in observed]),
                           "nestedSelected":_confidence_bins([(c,y) for _,_,c,y in observed])},
            "yearByYear":results,
            "activePublicModelChanged":False,
            "limitations":[manifest["caveat"],
                          "Same season frozen pre-tournament ratings may not contain possession-level historical snapshots.",
                          "Nested selection is historical prospective simulation, not immutable genuinely published game predictions.",
                          "Repeated model development against these years can bias generalization claims even with chronological splits.",
                          "Season-block confidence interval is descriptive; no candidate is automatically promoted."]}


def build(web:Path)->tuple[list[HistoricalGame],dict,dict]:
    rows,manifest=load_dataset(web)
    return rows,manifest,evaluate(rows,manifest)


def main()->None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--web-dir",type=Path,default=Path("web"))
    p.add_argument("--manifest",type=Path,default=Path("research/outputs/historical-data-manifest.json"))
    p.add_argument("--evaluation",type=Path,default=Path("research/outputs/historical-evaluation.json"))
    p.add_argument("--rows",type=Path,default=None,help="Optional deterministic offline training rows JSONL")
    args=p.parse_args()
    rows,manifest,report=build(args.web_dir)
    for path,content in [(args.manifest,manifest),(args.evaluation,report)]:
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(content,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    if args.rows:
        args.rows.parent.mkdir(parents=True,exist_ok=True)
        args.rows.write_text("".join(json.dumps(r.feature_dict(),sort_keys=True)+"\n" for r in rows),encoding="utf-8")
    print(json.dumps({"completeSeasons":manifest["includedSeasons"],
                      "sourceGames":manifest["includedGames"],
                      "heldOutGames":report["testedGames"],
                      "nestedBrier":report["metrics"]["nestedSelected"]["brier"],
                      "eloBrier":report["metrics"]["elo"]["brier"],
                      "gain":report["nestedBrierGainVsElo"]}))
if __name__=="__main__":main()
