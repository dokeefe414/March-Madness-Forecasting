"""Research-only *frozen* source-backed scoring forecast (future events only).

Matches the descriptive live Game Center points and adjusted efficiency logic.
No bookmaker data, home-court adjustment, or trained probability distribution
is implied. The score/margin are frozen alongside future original predictions
so actual future first-pick score accuracy can be measured without backfill.
Missing or implausible fields always cause a disclosed fallback or abstention.
"""
from __future__ import annotations
import math

MIN_GAMES=5


def _valid(v:object)->bool:
    return type(v) in (int,float) and math.isfinite(v)


def score_shadow(home:dict,away:dict)->dict|None:
    if not home or not away or str(home.get("teamId"))==str(away.get("teamId")):
        return None
    try:
        hg=int(home["wins"])+int(home["losses"])
        ag=int(away["wins"])+int(away["losses"])
    except (ValueError,TypeError,KeyError):
        return None
    if hg<MIN_GAMES or ag<MIN_GAMES:return None
    adjusted=[home.get("adjOff100"),home.get("adjDef100"),away.get("adjOff100"),
              away.get("adjDef100"),home.get("pacePossessions"),away.get("pacePossessions")]
    raw=[home.get("offRating100"),home.get("defRating100"),
         away.get("offRating100"),away.get("defRating100")]
    n=min(int(home.get("possessionGames") or 0),int(away.get("possessionGames") or 0))
    have_box=n>=MIN_GAMES and all(_valid(x) for x in adjusted+raw)
    tempo=(adjusted[4]+adjusted[5])/2 if have_box else 0
    anchor=sum(raw)/4 if have_box else 0
    if (have_box and 50<=tempo<=95 and all(50<=x<=95 for x in adjusted[4:])
        and 50<=anchor<=150 and all(35<x<200 for x in adjusted[:4])):
        hp=adjusted[0]*adjusted[3]/anchor*tempo/100
        ap=adjusted[2]*adjusted[1]/anchor*tempo/100
        method="opponent-adjusted-possessions"
        evidence=n
    else:
        rates=[home.get("pointsForPerGame"),home.get("pointsAgainstPerGame"),
               away.get("pointsForPerGame"),away.get("pointsAgainstPerGame")]
        if not all(_valid(x) and 0<x<200 for x in rates):
            return None
        hp=(rates[0]+rates[3])/2
        ap=(rates[2]+rates[1])/2
        method="raw-scoring-means"
        evidence=None
    # Rounding only at the end avoids changing predictions if serialization
    # differs from the browser's decimal formatting.
    hp=round(hp,1)
    ap=round(ap,1)
    return {
        "schemaVersion":1,
        "modelVersion":"source-scoring-shadow-v1",
        "method":method,
        "projectedHomeScore":hp,
        "projectedAwayScore":ap,
        "projectedMargin":round(hp-ap,1),
        "projectedTotal":round(hp+ap,1),
        "sourceHomeGames":hg,
        "sourceAwayGames":ag,
        "verifiedPossessionGamesMinimum":evidence,
        "assumptions":"Neutral venue, no calibrated distribution, injuries or betting lines"
    }
