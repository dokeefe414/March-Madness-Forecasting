"use client";
import {useEffect,useState} from "react";
const base=process.env.NEXT_PUBLIC_BASE_PATH||"";
type ScoreMetrics={games:number;marginMAE?:number|null;totalMAE?:number|null;winnerAccuracy?:number|null;brier?:number|null;logLoss?:number|null};
type Report={schemaVersion:number;season:number;mode:"research-only";sourceGames:number;
 evaluatedGames:number;evaluatedDays:number;retrievedAtUtc:string;excluded:Record<string,number>;
 methods:{opponentAdjusted:ScoreMetrics;rawScoringMeans:ScoreMetrics;elo:{games:number;brier:number|null}};
 policy:string;modelVersion:string;perDate:Array<{date:string;games:number;adjustedMarginMAE:number;rawMarginMAE:number;adjustedBrier:number;rawBrier:number;eloBrier:number}>};
function num(n:number|null|undefined,d=3){return n==null?"—":n.toFixed(d)}
export default function ScoreResearchEvidence(){
 const [report,setReport]=useState<Report|null>(null);
 const [status,setStatus]=useState("Loading date-frozen scoring research…");
 useEffect(()=>{let active=true;fetch(base+"/current/score-research.json").then(r=>{
   if(!r.ok)throw Error("New scoring benchmark has not been published.");
   return r.json();
 }).then((r:Report)=>{if(!active)return;
   if(r.mode!=="research-only"||r.season!==2027||!r.methods?.opponentAdjusted||!r.methods?.rawScoringMeans)
     throw Error("Unexpected scoring research dataset.");
   setReport(r);
 }).catch((e:Error)=>{if(active)setStatus(e.message)});return()=>{active=false}},[]);
 const rows=report?.perDate||[];
 const vals=rows.slice(-24);
 const maxErr=Math.max(1,...vals.map(v=>Math.max(v.adjustedMarginMAE,v.rawMarginMAE)));
 return <section className="v15-score-research" aria-label="Chronological score and margin forecasting benchmark">
  <div className="v13-feature-head"><span className="section-kicker">NEW / INDEPENDENT DATE-FROZEN SCORING RESEARCH</span>
   <h3>PROVE THE <em>SCORING EDGE.</em></h3>
   <p>A regularized opponent-adjusted scoring model is compared on the same earlier-date-only games as the previous scoring-average baseline and Elo. Better predictions must reduce measured errors; algorithm complexity is not proof.</p></div>
  {!report?<p role="status" className="v12-subtle">{status}</p>:
   <><div className="v15-score-head">
       <div><small>HELD-OUT CHRONOLOGICAL GAMES</small><strong>{report.evaluatedGames}</strong></div>
       <div><small>INDEPENDENT GAME DATES</small><strong>{report.evaluatedDays}</strong></div>
       <div><small>RESEARCH MODEL</small><strong className="v15-small">Adjusted offense + defense</strong></div>
     </div>
     <div className="v15-score-table-wrap"><table className="v15-score-table">
       <thead><tr><th scope="col">MODEL</th><th scope="col">MARGIN MAE ↓</th><th scope="col">TOTAL MAE ↓</th><th scope="col">WIN PROBABILITY BRIER ↓</th></tr></thead>
       <tbody>
        <tr><th scope="row">Opponent-adjusted scoring</th><td>{num(report.methods.opponentAdjusted.marginMAE,2)}</td><td>{num(report.methods.opponentAdjusted.totalMAE,2)}</td><td>{num(report.methods.opponentAdjusted.brier,4)}</td></tr>
        <tr><th scope="row">Raw scoring means</th><td>{num(report.methods.rawScoringMeans.marginMAE,2)}</td><td>{num(report.methods.rawScoringMeans.totalMAE,2)}</td><td>{num(report.methods.rawScoringMeans.brier,4)}</td></tr>
        <tr><th scope="row">Elo win probability</th><td>—</td><td>—</td><td>{num(report.methods.elo.brier,4)}</td></tr>
       </tbody>
     </table></div>
     {vals.length>0&&<div className="v15-error-trend"><h4>RECENT DATE-BLOCK ERROR COMPARISON</h4>
       {vals.map(day=><div key={day.date} className="v15-error-row">
        <span>{day.date} · {day.games} games</span>
        <div><i style={{width:(day.adjustedMarginMAE/maxErr*100).toFixed(2)+"%"}}/></div>
        <div><i style={{width:(day.rawMarginMAE/maxErr*100).toFixed(2)+"%"}}/></div></div>)}
       <p className="v12-subtle">Mint: opponent adjusted; blue: unadjusted scoring means. Bars compare absolute margin error within each date, not favorite probability or confidence.</p>
     </div>}
     <p className="v12-subtle">All predictions on a day are frozen before that day's scores are used. {report.evaluatedGames===0?"No qualified future-of-training games exist yet; no performance claim is possible.":"The research run evaluated "+report.evaluatedGames+" sourced games on "+report.evaluatedDays+" dates."} This historical replay is not timestamped prospective first-pick evidence, and these models have not been promoted to the public Elo system.</p>
   </>}
 </section>;
}
