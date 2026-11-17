"use client";
import {useEffect,useState} from "react";
const base=process.env.NEXT_PUBLIC_BASE_PATH||"";
type Metric={games:number;brier:number|null;logLoss:number|null;accuracy:number|null};
type Year={season:number;trainingThrough:number;selectedByEarlierOos:string;elo:Metric;calibrated:Metric;nestedSelected:Metric;evaluatedGames:number};
type Evaluation={schemaVersion:number;sourceCommit:string;datasetIndexSha256:string;testedGames:number;firstTestSeason:number;lastTestSeason:number;
  evaluatedSeasons:number;nestedBrierGainVsElo:number;nestedGainSeasonBlock95:number[]|null;activePublicModelChanged:boolean;
  metrics:{elo:Metric;calibratedTrendElo:Metric;nestedSelected:Metric};yearByYear:Year[];limitations:string[]};
type Manifest={sourceCommit:string;historicalIndexSha256:string;includedSeasons:number;includedGames:number;
 omittedMissingRatedTeams:number;excludedSeasons:number[];perSeason:Array<{season:number;status:string;retainedGames:number}>;featureAsOf:string};
const display=(value:number|null|undefined,d=4)=>value==null?"—":value.toFixed(d);
export default function HistoricalEvidence(){
 const [evaluation,setEvaluation]=useState<Evaluation|null>(null);
 const [manifest,setManifest]=useState<Manifest|null>(null);
 const [error,setError]=useState("");
 useEffect(()=>{
   let live=true;
   const load=(url:string)=>fetch(base+url,{cache:"no-store"}).then(r=>{if(!r.ok)throw new Error("Historical research artifact unavailable");return r.json()});
   Promise.all([load("/research/historical-data-manifest.json"),load("/research/historical-evaluation.json")])
    .then(([m,e]:[Manifest,Evaluation])=>{
      if(!live)return;
      if(m.sourceCommit!==e.sourceCommit||m.historicalIndexSha256!==e.datasetIndexSha256||
          e.schemaVersion!==1||e.activePublicModelChanged!==false)
        throw new Error("Historical training data and evaluation source pins do not match");
      setManifest(m);setEvaluation(e);
    }).catch((cause:Error)=>{if(live)setError(cause.message)});
   return()=>{live=false};
 },[]);
 return <section className="v17-history" aria-label="Audited historical training and out-of-time model evaluation">
  <div className="v13-feature-head">
   <span className="section-kicker">v1.7 / REPRODUCIBLE HISTORICAL DATA LAB</span>
   <h3>PROVE IT <em>ON UNSEEN SEASONS.</em></h3>
   <p>Source-pinned, pre-tournament-only features; strictly earlier-season calibration; a separate previous-out-of-time model-selection layer. These are historical observed tournament matchups, not actual prospectively archived predictions.</p>
  </div>
  {!manifest||!evaluation?<p role={error?"alert":"status"} className="v12-subtle">{error||"Checking historical data provenance and evaluation…"}</p>:
   <>
    <div className="v17-stats">
     <div><small>COMPLETE HISTORICAL SEASONS</small><strong>{manifest.includedSeasons}</strong></div>
     <div><small>HISTORICAL SOURCE GAMES</small><strong>{manifest.includedGames.toLocaleString()}</strong></div>
     <div><small>OUT-OF-TIME TEST GAMES</small><strong>{evaluation.testedGames.toLocaleString()}</strong></div>
     <div><small>TESTED YEARS</small><strong>{evaluation.firstTestSeason}–{evaluation.lastTestSeason}</strong></div>
    </div>
    <div className="v15-score-table-wrap"><table className="v15-score-table">
      <thead><tr><th scope="col">HISTORICAL MODEL</th><th scope="col">BRIER ↓</th><th scope="col">LOG LOSS ↓</th><th scope="col">WINNER ACCURACY</th></tr></thead>
      <tbody>
       {([["elo","Unchanged Elo"],["calibratedTrendElo","Prior-year calibrated Elo"],["nestedSelected","Nested prior-OOS selection"]] as const).map(([key,label])=><tr key={key}>
        <th scope="row">{label}</th><td>{display(evaluation.metrics[key].brier)}</td>
        <td>{display(evaluation.metrics[key].logLoss)}</td>
        <td>{evaluation.metrics[key].accuracy==null?"—":(evaluation.metrics[key].accuracy!*100).toFixed(1)+"%"}</td>
       </tr>)}
      </tbody></table></div>
    <p className="v17-gain"><strong>Nested Brier gain over Elo:</strong> {evaluation.nestedBrierGainVsElo>=0?"+":""}{display(evaluation.nestedBrierGainVsElo,5)} · 95% season-block descriptive interval: {evaluation.nestedGainSeasonBlock95?.map(n=>display(n,5)).join(" to ")||"Insufficient independent seasons"}</p>
    <details className="v17-details"><summary>View year-by-year held-out results and audit exclusions</summary>
      <div className="v15-score-table-wrap"><table className="v15-score-table">
       <thead><tr><th scope="col">TEST YEAR</th><th scope="col">TRAINED THROUGH</th><th scope="col">SELECTED</th><th scope="col">ELO BRIER</th><th scope="col">SELECTED BRIER</th></tr></thead>
       <tbody>{evaluation.yearByYear.map(y=><tr key={y.season}><th scope="row">{y.season}</th><td>{y.trainingThrough}</td><td>{y.selectedByEarlierOos}</td><td>{display(y.elo.brier)}</td><td>{display(y.nestedSelected.brier)}</td></tr>)}</tbody>
      </table></div>
      <p className="v12-subtle">Excluded unavailable/incomplete seasons: {manifest.excludedSeasons.join(", ")||"none"}. Missing rated-team matchup exclusions: {manifest.omittedMissingRatedTeams}.</p>
    </details>
    <p className="v12-subtle">Pinned source commit: <code>{manifest.sourceCommit.slice(0,12)}</code> · Source manifest: SHA-256 verified · Feature cutoff: pre-tournament day 132. Neither the live 2026–27 forecasts nor the v1.6 ensemble has been retrained or promoted using this research. <a href="https://github.com/dokeefe414/March-Madness-Forecasting26-27/blob/main/docs/v17-historical-evaluation.md" target="_blank" rel="noreferrer">Full source and evaluation methods</a>.</p>
   </>}
 </section>;
}
