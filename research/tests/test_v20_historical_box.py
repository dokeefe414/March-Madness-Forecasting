"""v2.0 source-integrity and basketball Four Factors tests (synthetic fixtures only)."""
from __future__ import annotations
import csv
import json
import tempfile
import unittest
from pathlib import Path
from forecast.historical_box_store import load,NUMERIC_FIELDS
WEB=Path(__file__).resolve().parents[2]/"web"

def synthetic(web:Path):
    (web/"data").mkdir(parents=True)
    (web/"public/seasons").mkdir(parents=True)
    (web/"data/history-index.json").write_text(json.dumps({
        "sourceCommit":"pinned-ncaa-source-hash-123","seasons":[{"season":2019,"isComplete":True,
           "throughDay":132,"teams":2,"tournamentGames":1}]}))
    (web/"public/seasons/2019.json").write_text(json.dumps({
      "season":2019,"sourceCommit":"pinned-ncaa-source-hash-123","throughDay":132,
      "teams":[{"teamId":"1","rating":1600},{"teamId":"2","rating":1400}]}))

def rows():
    games=[]
    for i in range(5):
        games.append({"season":2019,"day":80+i,"eventId":f"NCAA-TEST-{i}",
          "homeTeamId":"1","awayTeamId":"2",
          "sourceUri":f"https://stats.ncaa.org/contests/test-{i}",
          "homePoints":75+i,"awayPoints":68+i,
          "homePossessions":70,"awayPossessions":70,
          "homeFga":62,"awayFga":60,"homeFgm":28,"awayFgm":25,
          "homeFg3m":8,"awayFg3m":7,"homeFta":19,"awayFta":17,
          "homeTov":12,"awayTov":11,"homeOrb":8,"awayOrb":9,
          "homeDrb":27,"awayDrb":26})
    return games

def write(path:Path,values):
    with path.open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["season","day","eventId","homeTeamId","awayTeamId",
                  "sourceUri",*NUMERIC_FIELDS])
        w.writeheader();w.writerows(values)

class BoxStoreTests(unittest.TestCase):
 def test_missing_data_is_reported_not_fabricated(self):
    result=load(WEB,None)
    self.assertFalse(result["available"])
    self.assertEqual(result["teamSeasons"],0)
    self.assertEqual(result["sourceGames"],0)
    self.assertFalse(result["teamFeatures"])
    self.assertTrue(result["missingBoxSeasons"])

 def test_verified_schema_four_factors_and_source_hash(self):
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder);synthetic(root)
        file=root/"boxes.csv";write(file,rows())
        result=load(root,file)
        self.assertTrue(result["available"])
        self.assertEqual(result["sourceGames"],5)
        self.assertEqual(result["teamSeasons"],2)
        self.assertEqual(len(result["sourceSha256"]),64)
        home=next(x for x in result["teamFeatures"] if x["teamId"]=="1")
        self.assertEqual(home["sourceGames"],5)
        self.assertEqual(home["efgPct"],round((28+.5*8)/62,6))
        self.assertEqual(home["turnoverRate"],round(12/70,6))
        self.assertEqual(home["offensiveReboundPct"],round(8/(8+26),6))
        self.assertEqual(home["freeThrowRate"],round(19/62,6))
        self.assertEqual(home["pacePossessions"],70)
        self.assertEqual(home["opponentRatingMean"],1400)
        self.assertGreater(home["offensePer100"],100)
        self.assertEqual(result["missingBoxSeasons"],[])

 def test_fails_on_future_box_data_identity_and_claimed_source(self):
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder);synthetic(root)
        file=root/"boxes.csv"
        for field,value,expected in [
          ("day",133,"Post-tournament"),
          ("homeTeamId","not-a-team","identity"),
          ("sourceUri","https://example.com/fake","official NCAA"),
          ("homePossessions",140,"possession"),
          ("homeFgm",80,"shooting"),
          ("homeTov",82,"turnover"),
          ("homePoints",1,"box points"),
        ]:
            data=rows();data[0][field]=value;write(file,data)
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,expected):
                load(root,file)
        repeated=rows();repeated[1]["eventId"]=repeated[0]["eventId"]
        write(file,repeated)
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            load(root,file)

 def test_partial_source_must_not_impute_missing_team_season(self):
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder);synthetic(root)
        file=root/"boxes.csv"
        write(file,rows()[:4])
        report=load(root,file)
        self.assertTrue(report["available"])
        self.assertEqual(report["teamSeasons"],0)
        self.assertFalse(report["teamFeatures"])
if __name__=="__main__":unittest.main()
