"use client";
import {useEffect,useState} from "react";
const base=process.env.NEXT_PUBLIC_BASE_PATH||"";
type Metrics={games:number;brier:number|null;logLoss:number|null;accuracy:number|null};
type Score={games:number;marginMAE:number|null;totalMAE:number|null;marginRMSE:number|null;totalRMSE:number|null;
 margin80Coverage:number|null;total80Coverage:number|null;margin80MeanWidth:number|null;total80MeanWidth:number|null};
type Calibration={ece:number|null;bins:Array<{lower:number;upper:number;games:number;averageProbability:number|null;realizedFrequency:number|null}>};
type Year={season:number;trainingThrough:number;modelWeight:number;scoreProbabilityScale:number;
  elo:Metrics;scoreProbability:Metrics;ensemble:Metrics;scoreIntervals:Score};
type Report={schemaVersion:number;mode:"historical-research-only";sourceCommit:string;datasetIndexSha256:string;
 evaluatedYears:number;heldOutGames:number;trainingData:string;metrics:{elo:Metrics;calibratedElo:Metrics;
 scoringProbability:Metrics;nestedEnsemble:Metrics;projectedScores:Score};
 calibration:{elo:Calibration;scoring:Calibration;ensemble:Calibration};
 ensembleBrierGainVsElo:number;seasonBlockGain95:number[]|null;yearByYear:Year[];
 policy:{liveForecastsChanged:boolean;noAutomaticPromotion:boolean};limitations:string[]};
type Manifest={sourceCommit:string;historicalIndexSha256:string};
const fmt=(n:number|null|undefined,places=4)=>n==null?"—":n.toFixed(places);
const percent=(n:number|null|undefined)=>n==null?"—":(100*n).toFixed(1)+"%";
export default function ProbabilisticResearch(){
 const [report,setReport]=useState<Report|null>(null);
 const [error,setError]=useState("");
 const [calibration,setCalibration]=useState<"elo"|"scoring"|"ensemble">("ensemble");
 useEffect(()=>{
   let active=true;
   const load=(p:string)=>fetch(base+p,{cache:"no-store"}).then(x=>{
    if(!x.ok)throw new Error("Historical probability study unavailable.");
    return x.json();
   });
   Promise.all([load("/research/historical-data-manifest.json"),load("/research/historical-probabilistic.json")])
    .then(([m,data]:[Manifest,Report])=>{
     if(!active)return;
     if(data.schemaVersion!==1||data.mode!=="historical-research-only"||
       data.sourceCommit!==m.sourceCommit||data.datasetIndexSha256!==m.historicalIndexSha256||
       data.policy?.liveForecastsChanged!==false||data.policy?.noAutomaticPromotion!==true)
       throw new Error("Historical model evaluation source or release-policy validation failed.");
     setReport(data);
    }).catch((e:Error)=>{if(active)setError(e.message)});
   return()=>{active=false};
 },[]);
 const models=report?.metrics;
 const score=models?.projectedScores;
 const intervals=report?.calibration[calibration];
 return <section className="v18-study" aria-label="Historical probabilistic scoring and calibration research">
   <div className="v13-feature-head">
    <span className="section-kicker">v1.8 / PROBABILITY, SCORE & UNCERTAINTY SCIENCE</span>
    <h3>MORE THAN <em>A FINAL SCORE.</em></h3>
    <p>A regularized model predicts score margin and total with uncertainty, converts the margin into a probability, and tests a conservative historical ensemble against Elo on unseen tournament seasons. Every model uses the same original pre-tournament-only matchup evidence.</p>
   </div>
   {!report?<p role={error?"alert":"status"} className="v12-subtle">{error||"Loading source-verified historical scoring research…"}</p>:<>
    <div className="v18-stat-bar">
      <div><small>HELD-OUT TOURNAMENT GAMES</small><strong>{report.heldOutGames.toLocaleString()}</strong></div>
      <div><small>SCORING MARGIN MAE</small><strong>{fmt(score?.marginMAE,2)}</strong></div>
      <div><small>TOTAL POINTS MAE</small><strong>{fmt(score?.totalMAE,2)}</strong></div>
      <div><small>80% MARGIN INTERVAL COVERAGE</small><strong>{percent(score?.margin80Coverage)}</strong></div>
    </div>
    <p className="v12-subtle">The 80% interval is a Gaussian modeling assumption, tested on unseen historical years. Actual coverage is shown above; 80% is the nominal target, not a guarantee. The scoring model has not been trained from complete historical per-possession game data.</p>
    <div className="v15-score-table-wrap"><table className="v15-score-table">
     <thead><tr><th scope="col">HISTORICAL WIN PROBABILITY</th><th scope="col">BRIER ↓</th><th scope="col">LOG LOSS ↓</th><th scope="col">ACCURACY ↑</th></tr></thead>
     <tbody>
       {([["elo","Elo baseline"],["calibratedElo","Earlier-year calibrated Elo"],["scoringProbability","Regularized score distribution"],["nestedEnsemble","Previously held-out-selected ensemble"]] as const)
        .map(([name,label])=><tr key={name}><th scope="row">{label}</th><td>{fmt(models![name].brier)}</td>
         <td>{fmt(models![name].logLoss)}</td><td>{percent(models![name].accuracy)}</td></tr>)}
     </tbody></table></div>
    <p className="v18-gain"><strong>Nested ensemble Brier gain vs Elo:</strong> {report.ensembleBrierGainVsElo>=0?"+":""}{fmt(report.ensembleBrierGainVsElo,5)}
    {" "}· Year-block descriptive 95% interval: {report.seasonBlockGain95?.map(v=>fmt(v,5)).join(" to ")||"Not enough independent years"}.
    A negative gain means the ensemble lost to Elo; a confidence interval spanning zero is inconclusive.</p>
    <div className="v18-calibration">
      <div><h4>ARE THE PROBABILITIES BELIEVABLE?</h4><p>Compare average predicted home-side win probability with actual wins in independent historical tournament games. Sparse groups should not be overinterpreted.</p></div>
      <div className="v18-switches" role="group" aria-label="Historical probability calibration model">
       {([["elo","Elo"],["scoring","Score model"],["ensemble","Ensemble"]] as const)
        .map(([key,label])=><button type="button" key={key} aria-pressed={calibration===key}
         className={calibration===key?"active":""} onClick={()=>setCalibration(key)}>{label}</button>)}
      </div>
      <p><strong>Expected calibration error:</strong> {fmt(intervals?.ece,4)} (lower is better; descriptive ten-bin metric)</p>
      <div className="v18-calibration-bars">
       {intervals?.bins.map((bin,i)=><div key={i} className="v18-calibration-row">
         <span>{Math.round(bin.lower*100)}–{Math.round(bin.upper*100)}%</span>
         <div className="v18-calibration-track" title={"Average predicted "+percent(bin.averageProbability)}>
           <i style={{width:percent(bin.averageProbability??0)}}/>
         </div>
         <div className="v18-calibration-track actual" title={"Actual wins "+percent(bin.realizedFrequency)}>
           <i style={{width:percent(bin.realizedFrequency??0)}}/>
         </div>
         <span>{bin.games} games</span>
       </div>)}
      </div>
      <p className="v12-subtle">Mint = average predicted probability; blue = actual fraction of wins. Zero-sample bins have no estimated frequency and are displayed without claiming calibration.</p>
    </div>
    <details className="v17-details">
      <summary>See yearly forecasts, learned weights, and scoring error</summary>
      <div className="v15-score-table-wrap"><table className="v15-score-table">
        <thead><tr><th scope="col">YEAR</th><th scope="col">TRAIN THROUGH</th><th scope="col">ENSEMBLE WEIGHT</th><th scope="col">MARGIN MAE</th><th scope="col">TOTAL MAE</th><th scope="col">ENSEMBLE BRIER</th></tr></thead>
        <tbody>{report.yearByYear.map(y=><tr key={y.season}><th scope="row">{y.season}</th>
        <td>{y.trainingThrough}</td><td>{Math.round(y.modelWeight*100)}%</td>
        <td>{fmt(y.scoreIntervals.marginMAE,2)}</td><td>{fmt(y.scoreIntervals.totalMAE,2)}</td>
        <td>{fmt(y.ensemble.brier)}</td></tr>)}</tbody>
      </table></div>
    </details>
    <p className="v12-subtle">Research-only. Models, ensemble weights, score uncertainties and probability calibration are fitted using previous tournaments only. Live 2026–27 predictions, original archive files and the active Elo policy are unchanged. No betting market spread, per-game injury data or synthetic possession history was invented.</p>
   </>}
 </section>;
}
