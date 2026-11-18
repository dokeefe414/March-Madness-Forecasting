"""Causal source-linked 2026-27 basketball efficiency research.

Use only matched NCAA-derived game/season identity, date, and paired team-box
records. Actual team box ratings (ORTG, DRTG, possessions) are not claims of
Four Factors if the provider does not supply shooting/rebound/turnover fields.

The first-pick public prediction and real-game Elo remain unchanged. This
module evaluates a regularized, prior-date feature residual in research mode.
Incomplete source coverage leads to abstention, not invented statistics.
"""
from __future__ import annotations
import argparse
import csv
import io
import json
import math
import random
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from .core import matchup_probability
from .game_aware_elo import margin_multiplier
from .reference import canonical
from .efficiency import BOX_URL, NEEDED

EASTERN=ZoneInfo("America/New_York")
MIN_TEAM_BOX=3
MIN_TRAIN=80
MIN_DAYS=8
MIN_COMPARE_DAYS=6
SHRINK_POSSESSIONS=450.
FEATURES=("intercept","opponent_adjusted_net_gap","recent_net_gap",
          "schedule_strength_gap","rest_days_gap","four_factor_gap")
FACTOR_COLS=("fga","fgm","fg3m","fta","tov","orb","drb")
# All hyperparameters are fixed; no in-sample tuning or automatic promotion.
L2=.15
STEPS=70
LEARNING_RATE=.2

def _finite(x:object,lo:float,hi:float)->float|None:
    try:z=float(x)
    except (TypeError,ValueError):return None
    return z if math.isfinite(z) and lo<=z<=hi else None

def _optional_factors(row:dict)->dict|None:
    if not set(FACTOR_COLS).issubset(row):return None
    vals={name:_finite(row[name],0,300) for name in FACTOR_COLS}
    if any(x is None for x in vals.values()):return None
    if vals["fga"]<30 or vals["fgm"]>vals["fga"] or vals["fg3m"]>vals["fgm"]:
        return None
    return vals

def source_game_boxes(games:list[dict],box_csv:str|None,
                      retrieved:str)->dict:
    """Join both team rows to SOURCE contest IDs and exact full school names.

    The published JSON contains only rows from the already accepted scored
    schedule; records with missing/ambiguous pairings are entirely withheld.
    """
    manifest={"schemaVersion":1,"season":2027,"retrievedAtUtc":retrieved,
        "sourceUrl":BOX_URL,"status":"unavailable" if box_csv is None else "partial",
        "acceptedScoreGames":len(games),"pairedGameBoxes":0,
        "completeFourFactorGames":0,"droppedRows":0,"games":[],
        "limitations":["Only previous-date stats are used to predict later dates.",
           "The NCAA-derived scored-game list does not independently confirm ESPN STATUS_FINAL.",
           "Source ORTG, DRTG, and possessions do not imply shooting and rebounding columns exist.",
           "No unverified team-name aliases or unmatched one-sided boxes are imputed."]}
    if box_csv is None:return manifest
    reader=csv.DictReader(io.StringIO(box_csv))
    if not NEEDED.issubset(set(reader.fieldnames or ())):
        raise ValueError("Source team-box schema lacks required columns")
    by_id={str(g["id"]):g for g in games}
    by_pair={}
    for row in reader:
        if str(row.get("season","")).strip()!="2027":continue
        game=by_id.get(str(row.get("contest_id","")).strip())
        if game is None:continue
        school=canonical(row.get("team"))
        names=(canonical(game["home"]),canonical(game["away"]))
        if not school or names[0]==names[1] or school not in names:
            manifest["droppedRows"]+=1;continue
        off=_finite(row.get("ortg"),25,250)
        defence=_finite(row.get("drtg"),25,250)
        op=_finite(row.get("o_poss"),30,180)
        dp=_finite(row.get("d_poss"),30,180)
        if any(z is None for z in (off,defence,op,dp)):
            manifest["droppedRows"]+=1;continue
        key=(str(game["id"]),school)
        if key in by_pair:
            # Competing duplicate rows make an event unusable, even if they
            # agree. Never choose a convenient version of a stat line.
            by_pair[key]=None;manifest["droppedRows"]+=1;continue
        by_pair[key]={"off":off,"def":defence,"poss":(op+dp)/2,
                      "factors":_optional_factors(row)}
    clean=[]
    factors=0
    for g in sorted(games,key=lambda x:(x["date"],str(x["id"]))):
        h=by_pair.get((str(g["id"]),canonical(g["home"])))
        a=by_pair.get((str(g["id"]),canonical(g["away"])))
        if h is None or a is None:continue
        if h["factors"] is not None and a["factors"] is not None:factors+=1
        clean.append({"id":str(g["id"]),"date":g["date"],
                      "home":g["home"],"away":g["away"],
                      "homeBox":h,"awayBox":a})
    return {**manifest,"status":"matched" if clean else "no-matched-pairs",
            "pairedGameBoxes":len(clean),"completeFourFactorGames":factors,
            "games":clean}

def sigmoid(v:float)->float:
    return 1/(1+math.exp(-max(-24.,min(24.,v))))

def _predict(elo:float,x:tuple[float,...],weights:list[float])->float:
    if len(x)!=len(FEATURES) or len(weights)!=len(FEATURES):
        raise ValueError("Invalid fitted efficiency feature vector")
    elo=min(.999999,max(.000001,elo))
    offset=math.log(elo/(1-elo))
    return sigmoid(offset+sum(v*w for v,w in zip(x,weights)))

def _fit(rows:list[dict])->list[float]:
    w=[0.]*len(FEATURES)
    for _ in range(STEPS):
        grad=[0.]*len(w)
        for r in rows:
            err=_predict(r["elo"],r["x"],w)-r["y"]
            for j,v in enumerate(r["x"]):grad[j]+=err*v
        for j in range(len(w)):
            w[j]-=LEARNING_RATE*(grad[j]/len(rows)+L2*w[j])
            w[j]=max(-1.,min(1.,w[j]))
    return w

class TeamStats:
    def __init__(self):
        self.poss=0.
        self.off=0.
        self.defence=0.
        self.games=0
        self.recent=[]
        self.opp_elo=0.
        self.factors=[]
        self.last_date=None

    def net(self)->float:
        # Observed adjusted offense and defense are pulled toward league
        # baseline when there is limited source possession coverage.
        return (self.off-self.defence)/(self.poss+SHRINK_POSSESSIONS)*100

    def recent_net(self)->float:
        return sum(self.recent[-5:])/len(self.recent[-5:]) if self.recent else 0.

    def sos(self)->float:
        return self.opp_elo/self.games if self.games else 1500.

    def factor(self)->float|None:
        if not self.factors:return None
        return sum(self.factors[-8:])/len(self.factors[-8:])

    def update(self,box:dict,opponent_elo:float,day:str)->None:
        self.poss+=box["poss"]
        self.off+=box["off"]*box["poss"]/100
        self.defence+=box["def"]*box["poss"]/100
        self.games+=1
        self.recent.append(box["off"]-box["def"])
        self.opp_elo+=opponent_elo
        self.last_date=day
        facts=box["factors"]
        if facts:
            # Dimensionless four-factor attack quality; descriptive only.
            fga=facts["fga"]
            efg=(facts["fgm"]+.5*facts["fg3m"])/fga
            tov=facts["tov"]/max(30.,box["poss"])
            orb=facts["orb"]/max(1.,facts["orb"]+facts["drb"])
            ftr=facts["fta"]/fga
            self.factors.append(efg-tov+.2*orb+.1*ftr)

def _features(h:TeamStats,a:TeamStats,game_date:str)->tuple[float,...]:
    d=datetime.fromisoformat(game_date).date()
    rh=(min(10,(d-datetime.fromisoformat(h.last_date).date()).days)
        if h.last_date else 7)
    ra=(min(10,(d-datetime.fromisoformat(a.last_date).date()).days)
        if a.last_date else 7)
    f_h=h.factor();f_a=a.factor()
    return (1.,
            max(-2.,min(2.,(h.net()-a.net())/24)),
            max(-2.,min(2.,(h.recent_net()-a.recent_net())/28)),
            max(-1.5,min(1.5,(h.sos()-a.sos())/200)),
            max(-1.,min(1.,(rh-ra)/7)),
            max(-1.,min(1.,(f_h-f_a)/.2)) if f_h is not None and f_a is not None else 0.)

def _summary(rows:list[dict],key:str)->dict:
    if not rows:return {"games":0,"brier":None,"accuracy":None,"logLoss":None}
    n=len(rows)
    return {"games":n,
        "brier":round(sum((r[key]-r["y"])**2 for r in rows)/n,6),
        "accuracy":round(sum(float((r[key]>.5)==bool(r["y"])) if r[key]!=.5 else .5 for r in rows)/n,6),
        "logLoss":round(-sum(math.log(max(1e-8,r[key] if r["y"] else 1-r[key])) for r in rows)/n,6)}

def _date_interval(rows:list[dict],draws:int=500)->list[float]|None:
    by=defaultdict(list)
    for r in rows:by[r["date"]].append((r["elo"]-r["y"])**2-(r["learner"]-r["y"])**2)
    if len(by)<MIN_COMPARE_DAYS:return None
    rng=random.Random(22027)
    days=sorted(by)
    vals=[]
    for _ in range(draws):
        sample=[by[days[rng.randrange(len(days))]] for _ in days]
        pieces=[v for block in sample for v in block]
        vals.append(sum(pieces)/len(pieces))
    vals.sort()
    return [round(vals[int(.025*draws)],6),round(vals[int(.975*draws)-1],6)]

def evaluate(games:list[dict],ratings:dict,boxes:dict,now:datetime|None=None)->dict:
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:raise ValueError("Research clock must be timezone aware")
    if ratings.get("mode")!="current" or ratings.get("season")!=2027:
        raise ValueError("Only current 2027 games are supported")
    if len(games)!=ratings.get("regularSeasonGames") or (
       ratings.get("retrievedAtUtc")!=boxes.get("retrievedAtUtc")):
        raise ValueError("Source, score and box retrieval timestamps/counts differ")
    if boxes.get("schemaVersion")!=1 or boxes.get("season")!=2027:
        raise ValueError("Incorrect source box artifact")
    known={str(g["id"]):g for g in games}
    if len(known)!=len(games):raise ValueError("Duplicate source game ID")
    keyed={}
    for row in boxes.get("games",[]):
        g=known.get(str(row["id"]))
        if g is None or str(row["id"]) in keyed or (
            row["date"],row["home"],row["away"]) != (
            g["date"],g["home"],g["away"]):
            raise ValueError("Box-game identity/date disagrees with accepted source score")
        for side in ("homeBox","awayBox"):
            b=row[side]
            if not all(type(b[k]) in (int,float) and math.isfinite(b[k]) and
                       (25<=b[k]<=250 if k in ("off","def") else 30<=b[k]<=180)
                       for k in ("off","def","poss")):
                raise ValueError("Box-game contains invalid possessions or efficiency")
        keyed[str(row["id"])]=row
    if len(keyed)!=boxes.get("pairedGameBoxes"):
        raise ValueError("Paired source-game box counts differ")
    cutoff=now.astimezone(EASTERN).date().isoformat()
    eligible=[g for g in games if g["date"]<cutoff]
    groups=defaultdict(list)
    for g in eligible:
        if g["date"]>ratings.get("lastGameDate",""):
            raise ValueError("Game later than reported source cutoff")
        groups[g["date"]].append(g)
    ratings_state=defaultdict(lambda:1500.)
    stats=defaultdict(TeamStats)
    training=[]
    tested=[]
    cold=0
    daily=[]
    last_weights=None
    for day in sorted(groups):
        rows=[]
        for g in sorted(groups[day],key=lambda x:str(x["id"])):
            h,a=g["home"],g["away"]
            p=matchup_probability(ratings_state[h],ratings_state[a],65)
            y=int(g["homeScore"]>g["awayScore"])
            box=keyed.get(str(g["id"]))
            available=(box is not None and stats[h].games>=MIN_TEAM_BOX
                       and stats[a].games>=MIN_TEAM_BOX)
            record={"date":day,"id":str(g["id"]),"home":h,"away":a,
                    "elo":p,"y":y,"x":_features(stats[h],stats[a],day)
                    if available else None,"pairedBox":box is not None,
                    "ready":available,"box":box,
                    "preHomeElo":ratings_state[h],"preAwayElo":ratings_state[a]}
            if available and len(training)>=MIN_TRAIN and len({t["date"] for t in training})>=MIN_DAYS:
                if last_weights is None:last_weights=_fit(training)
                record["learner"]=_predict(p,record["x"],last_weights)
                tested.append(record)
            elif available:cold+=1
            rows.append(record)
        # all game probabilities and all current-day features have been frozen.
        day_ready=[r for r in rows if r["ready"]]
        training.extend(day_ready)
        day_tested=[r for r in rows if "learner" in r]
        if day_tested:
            daily.append({"date":day,"games":len(day_tested),
              "eloBrier":_summary(day_tested,"elo")["brier"],
              "efficiencyBrier":_summary(day_tested,"learner")["brier"]})
        # Calculate zero-sum movements using pre-date ratings, not a same-day
        # chain where a game's result accidentally influences another.
        for r in rows:
            g=known[r["id"]]
            margin=abs(g["homeScore"]-g["awayScore"])
            delta=24*margin_multiplier(margin)*(r["y"]-r["elo"])
            ratings_state[r["home"]]+=delta
            ratings_state[r["away"]]-=delta
            if r["box"] is not None:
                stats[r["home"]].update(r["box"]["homeBox"],r["preAwayElo"],day)
                stats[r["away"]].update(r["box"]["awayBox"],r["preHomeElo"],day)
        # Training changes can only affect a future date, never today's fit.
        last_weights=None
    baseline=_summary(tested,"elo")
    candidate=_summary(tested,"learner")
    ci=_date_interval(tested) if len(tested)>=40 else None
    gain=(round(baseline["brier"]-candidate["brier"],6) if tested else None)
    source_box_count=sum(str(g["id"]) in keyed for g in eligible)
    return {"schemaVersion":1,"mode":"research-only","season":2027,
        "retrievedAtUtc":ratings["retrievedAtUtc"],
        "boxSourceUrl":boxes.get("sourceUrl"),"boxStatus":boxes.get("status"),
        "acceptedPriorDateGames":len(eligible),
        "pairedPriorDateBoxGames":source_box_count,
        "fourFactorSourceGames":boxes.get("completeFourFactorGames",0),
        "eligibleWithPriorStats":len(tested)+cold,
        "coldStartEligible":cold,"evaluatedGames":len(tested),
        "evaluatedDates":len({r["date"] for r in tested}),
        "trainedThroughDate":max(groups) if groups else None,
        "metrics":{"elo":baseline,"efficiencyResidual":candidate,
                   "brierGainVsElo":gain,"dateBlockGain95":ci},
        "featureNames":list(FEATURES),
        "training":{"minPerTeamPreviousBoxes":MIN_TEAM_BOX,
            "minimumEarlierEligibleGames":MIN_TRAIN,
            "minimumEarlierDates":MIN_DAYS,"ridge":L2,
            "gradientSteps":STEPS,"learningRate":LEARNING_RATE,
            "shrinkPseudoPossessions":SHRINK_POSSESSIONS},
        "auditPerDate":daily[-35:],
        "currentWeights":_fit(training) if len(training)>=MIN_TRAIN else None,
        "automaticPromotion":False,
        "policy":"Fit a score-margin opponent-aware Elo OFFSET logistic residual using genuinely earlier-date paired team boxes; test on later games with exactly the same Elo baseline. Research-only: no active forecasts or archived predictions are overwritten.",
        "limitations":[
            "Source team-game ORTG, DRTG and possessions are used only when BOTH opponents have >=3 previous matched boxes; no missing stats are fabricated.",
            "Box score date D is added AFTER predictions for all date-D games; never predict a game using its own box line.",
            "Four Factors enter only for prior complete verified source rows; no assumed factors when columns are missing.",
            "Source's home designation is not a guarantee of neutral-site classification.",
            "Retrospective date-frozen backtest is NOT prospective archived accuracy; repeated review can overfit.",
            "Only separately verified ESPN final plus matching NCAA score can settle real archived predictions."
        ]}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--games",type=Path,default=Path("web/public/current/2027-games.json"))
    p.add_argument("--ratings",type=Path,default=Path("web/public/current/2027.json"))
    p.add_argument("--boxes",type=Path,default=Path("web/public/current/2027-box-games.json"))
    p.add_argument("--out",type=Path,default=Path("web/public/current/efficiency-research.json"))
    args=p.parse_args()
    g=json.loads(args.games.read_text(encoding="utf-8"))
    r=json.loads(args.ratings.read_text(encoding="utf-8"))
    b=json.loads(args.boxes.read_text(encoding="utf-8"))
    if g.get("retrievedAtUtc")!=r.get("retrievedAtUtc"):
        raise ValueError("Score archive and rating source timestamp mismatch")
    report=evaluate(g["games"],r,b)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"boxCoverage":report["pairedPriorDateBoxGames"],
       "tested":report["evaluatedGames"],"brierGain":report["metrics"]["brierGainVsElo"]}))

if __name__=="__main__":main()
