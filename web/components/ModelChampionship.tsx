"use client";
import {useEffect,useState} from "react";
const base=process.env.NEXT_PUBLIC_BASE_PATH||"";
type Stat={games:number;brier:number|null;logLoss:number|null;accuracy:number|null};
type Model="elo"|"logistic"|"boosted"|"calibratedTrendElo"|"scoreDistribution"|"priorShrinkage";
const models:[Model,string][]=[
 ["elo","Original Elo"],["logistic","Regularized logistic"],
 ["boosted","Gradient-boosted stumps"],["calibratedTrendElo","Prior-year trend Elo"],
 ["scoreDistribution","Scoring-margin probability"],["priorShrinkage","Prior-shrunk Elo"]
];
type Competition={schemaVersion:number;mode:"historical-only";sourceCommit:string;indexSha256:string;
 evaluatedSeasons:number;heldOutGames:number;models:Record<Model,Stat>;
 nestedChampion:Stat;nestedGainVsElo:number;nestedGainYearBlock95:number[]|null;
 modelGainYearBlock95:Partial<Record<Model,number[]|null>>;
 matchupTiers:Array<{label:string;elo:Stat;candidate:Stat}>;
 yearByYear:Array<{season:number;trainedThroughSeason:number;championSelectedBeforeResults:Model;
 modelScores:Record<Model,Stat>;nestedChampion:Stat}>;
 modelSelection:{noAutomaticProductionPromotion:boolean};
 safety:{livePredictionsModified:boolean}};
type Coverage={sourceCommit:string;available:boolean;sourceGames:number;teamSeasons:number;
 missingBoxSeasons:number[];limitations:string[];sourceSha256:string|null};
type Manifest={sourceCommit:string;historicalIndexSha256:string};
const n=(v:number|null|undefined,d=4)=>v==null?"—":v.toFixed(d);
export default function ModelChampionship(){
 const [contest,setContest]=useState<Competition|null>(null);
 const [coverage,setCoverage]=useState<Coverage|null>(null);
 const [error,setError]=useState("");
 const [selection,setSelection]=useState<Model>("boosted");
 useEffect(()=>{
  let alive=true;
  const get=(p:string)=>fetch(base+p,{cache:"no-store"}).then(r=>{
    if(!r.ok)throw new Error("Historical model benchmark not published");
    return r.json();
  });
  Promise.all([get("/research/model-championship.json"),
   get("/research/historical-box-coverage.json"),
   get("/research/historical-data-manifest.json")])
   .then(([c,d,m]:[Competition,Coverage,Manifest])=>{
    if(!alive)return;
    if(c.schemaVersion!==1||c.mode!=="historical-only"||
     c.sourceCommit!==m.sourceCommit||c.indexSha256!==m.historicalIndexSha256||
     d.sourceCommit!==m.sourceCommit||
     c.modelSelection.noAutomaticProductionPromotion!==true||
     c.safety.livePredictionsModified!==false)
       throw new Error("Model championship source pins or research-only policy did not validate");
    setContest(c);setCoverage(d);
   }).catch((e:Error)=>{if(alive)setError(e.message)});
  return()=>{alive=false};
 },[]);
 return <section className="v20-championship" aria-label="Multi-model historical tournament championship">
  <div className="v13-feature-head">
   <span className="section-kicker">v2.0 / HISTORICAL MODEL CHAMPIONSHIP</span>
   <h3>THE MODELS <em>HAVE TO EARN IT.</em></h3>
   <p>Six approaches, identical source-verified tournament matchups. All contenders train on earlier seasons; a nested policy chooses a challenger using only previously held-out tournament years. Active 2026–27 picks never change based on this backtest.</p>
  </div>
  {!contest||!coverage?<p role={error?"alert":"status"}>{error||"Checking matched source hashes and historical model scores…"}</p>:<>
    <div className="v20-scorecards">
     <div><small>UNSEEN TOURNAMENT GAMES</small><strong>{contest.heldOutGames.toLocaleString()}</strong></div>
     <div><small>HISTORICAL TEST YEARS</small><strong>{contest.evaluatedSeasons}</strong></div>
     <div><small>ELO BRIER ↓</small><strong>{n(contest.models.elo.brier)}</strong></div>
     <div><small>NESTED CHAMPION BRIER ↓</small><strong>{n(contest.nestedChampion.brier)}</strong></div>
    </div>
    <div className="v15-score-table-wrap"><table className="v15-score-table">
     <thead><tr><th>HISTORICAL MODEL</th><th>PAIRED GAMES</th><th>BRIER ↓</th><th>LOG LOSS ↓</th><th>WINNER ACCURACY</th></tr></thead>
     <tbody>{models.map(([key,label])=><tr key={key}>
      <th scope="row">{label}</th><td>{contest.models[key].games}</td>
      <td>{n(contest.models[key].brier)}</td><td>{n(contest.models[key].logLoss)}</td>
      <td>{contest.models[key].accuracy==null?"—":(100*contest.models[key].accuracy!).toFixed(1)+"%"}</td>
     </tr>)}
     <tr><th scope="row">Nested prior-year champion</th>
      <td>{contest.nestedChampion.games}</td><td>{n(contest.nestedChampion.brier)}</td>
      <td>{n(contest.nestedChampion.logLoss)}</td>
      <td>{contest.nestedChampion.accuracy==null?"—":(100*contest.nestedChampion.accuracy!).toFixed(1)+"%"}</td></tr></tbody>
    </table></div>
    <p className="v20-interval"><strong>Nested improvement over Elo:</strong> {contest.nestedGainVsElo>=0?"+":""}{n(contest.nestedGainVsElo,5)} Brier points.
      {" "}Year-block 95% descriptive interval: {contest.nestedGainYearBlock95?.map(v=>n(v,5)).join(" to ")||"Not enough seasons"}. If the range includes zero, the observed advantage is inconclusive.
    </p>
    <div className="v20-compare">
      <h4>Study individual challengers</h4>
      <div className="v20-choices" role="group" aria-label="Choose historical model to inspect">
       {models.filter(x=>x[0]!=="elo").map(([key,label])=>
        <button key={key} type="button" aria-pressed={selection===key}
         onClick={()=>setSelection(key)}>{label}</button>)}
      </div>
      <p>95% season-block paired Brier improvement interval for {models.find(x=>x[0]===selection)?.[1]}:
       {" "}<strong>{contest.modelGainYearBlock95[selection]?.map(v=>n(v,5)).join(" to ")||"Insufficient seasons"}</strong>. Intervals compare each model with Elo on identical held-out fixtures.
      </p>
    </div>
    <div className="v20-data-audit">
     <h4>Actual possession and Four Factors source coverage</h4>
     {coverage.available?
       <p><strong>{coverage.sourceGames}</strong> audited NCAA event box scores and <strong>{coverage.teamSeasons}</strong> eligible team-season records. Raw source SHA-256: <code>{coverage.sourceSha256?.slice(0,16)}…</code>. Tournament models still require separate forward validation before using these features.</p>:
       <p><strong>Not supplied.</strong> The historical archive currently provides pre-tournament Elo and win-loss features, but no validated game-by-game shooting, rebounds or possessions file. We do not infer those missing statistics. An NCAA event-level ingestion pipeline now checks them whenever a genuine source file is supplied.</p>}
     <p>Missing source seasons: {coverage.missingBoxSeasons.length}. Historical prediction tests remain based on the same available rating features for every model.</p>
    </div>
    <details className="v17-details"><summary>Year-by-year champion selection and test results</summary>
      <div className="v15-score-table-wrap"><table className="v15-score-table">
       <thead><tr><th>TEST YEAR</th><th>TRAINED THROUGH</th><th>PRIOR-YEAR SELECTED</th><th>ELO BRIER</th><th>SELECTED BRIER</th></tr></thead>
       <tbody>{contest.yearByYear.map(y=><tr key={y.season}><th>{y.season}</th><td>{y.trainedThroughSeason}</td>
         <td>{models.find(m=>m[0]===y.championSelectedBeforeResults)?.[1]||y.championSelectedBeforeResults}</td>
         <td>{n(y.modelScores.elo.brier)}</td><td>{n(y.nestedChampion.brier)}</td></tr>)}</tbody>
      </table></div>
    </details>
    <p className="v12-subtle">This is a tournament historical replay, not a 2026–27 real first-pick accuracy score. No retroactive change to Elo, the live shadow models, or the immutable forecast archive. No unverified box-score values were synthesized.</p>
  </>}
 </section>;
}
