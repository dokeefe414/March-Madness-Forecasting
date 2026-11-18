"use client";
import {useEffect,useState} from "react";
const base=process.env.NEXT_PUBLIC_BASE_PATH||"";
type RecordMetric={games:number;accuracy:number|null;brier:number|null;logLoss:number|null;upsets?:number};
type Comparison={model:string;pairedGames:number;pairedDays:number;eloBrier:number|null;
 candidateBrier:number|null;eloAccuracy:number|null;candidateAccuracy:number|null;
 brierGain:number|null;dateBlockGain95:number[]|null;reviewEligible:boolean;autoPromoted:false};
type Score={games:number;marginMAE:number|null;totalMAE:number|null;
 homeScoreMAE:number|null;awayScoreMAE:number|null;
 byMethod:Array<{method:string;games:number;marginMAE:number;totalMAE:number}>};
type Report={schemaVersion:number;mode:"first-pick-forward-research";
 generatedAtUtc:string;archiveGeneratedAtUtc:string|null;immutableFirstPicks:number;
 verifiedUniqueFinals:number;pendingUniqueGames:number;
 pendingByStatus:Record<"upcoming"|"recent-start"|"awaiting-final"|"delayed-review",number>;
 pendingReview:Array<{eventId:string;home:string;away:string;listedStartUtc:string;hoursSinceListedStart:number}>;
 verification:{independentESPNFinalRequired:boolean;matchingNCAAScoreRequired:boolean;
 esponFinalsInspectedInLastArchive:number|null;sourceWarnings:string[];
 observedScheduleChanges:Array<{eventId:string;home:string;away:string;originalListedStartUtc:string;revisedListedStartUtc:string}>};
 overall:RecordMetric;daily:Array<RecordMetric&{period:string}>;
 weekly:Array<RecordMetric&{period:string}>;pairedComparisons:Comparison[];
 frozenScoreResults:Score;reviewOnly:true;autoPromoted:false};
const metric=(n:number|null|undefined,d=4)=>n==null?"—":n.toFixed(d);
const pct=(n:number|null|undefined)=>n==null?"—":(100*n).toFixed(1)+"%";
export default function AccuracyDashboard(){
 const [report,setReport]=useState<Report|null>(null);
 const [error,setError]=useState("");
 const [period,setPeriod]=useState<"daily"|"weekly">("daily");
 useEffect(()=>{
  let alive=true;
  fetch(base+"/current/accuracy-research.json",{cache:"no-store"}).then(r=>{
    if(!r.ok)throw new Error("Verified accuracy diagnostics have not been published.");
    return r.json();
  }).then((x:Report)=>{
    if(!alive)return;
    if(x.schemaVersion!==1||x.mode!=="first-pick-forward-research"||x.reviewOnly!==true||
       x.autoPromoted!==false||!x.verification.independentESPNFinalRequired||
       !x.verification.matchingNCAAScoreRequired)
      throw new Error("Accuracy evidence did not pass publication-policy checks");
    setReport(x);
  }).catch((e:Error)=>{if(alive)setError(e.message)});
  return()=>{alive=false};
 },[]);
 const rows=report?.[period]||[];
 return <section className="v19-accuracy" aria-label="Verified real-game prediction performance center">
  <div className="v13-feature-head"><span className="section-kicker">v1.9 / ORIGINAL FIRST-PICK PROOF</span>
   <h3>HOW WELL DID <em>WE REALLY PICK?</em></h3>
   <p>Only the earliest archived forecast for each ESPN event is eligible. Correct picks and missed favorites are scored after independent ESPN completed-game and matching NCAA final-score verification. No historical hindsight is mixed into these numbers.</p></div>
  {!report?<p role={error?"alert":"status"} className="v12-subtle">{error||"Checking independently verified first-pick outcomes…"}</p>:<>
    <div className="v19-metrics">
     <div><small>ORIGINAL UNIQUE PICKS</small><strong>{report.immutableFirstPicks}</strong></div>
     <div><small>VERIFIED FINAL SCORES</small><strong>{report.verifiedUniqueFinals}</strong></div>
     <div><small>CORRECT WINNER RATE</small><strong>{pct(report.overall.accuracy)}</strong></div>
     <div><small>ACTUAL BRIER ↓</small><strong>{metric(report.overall.brier)}</strong></div>
    </div>
    <div className="v19-status">
     <div><strong>{report.pendingByStatus.upcoming}</strong><span>Upcoming</span></div>
     <div><strong>{report.pendingByStatus["recent-start"]}</strong><span>Recently started</span></div>
     <div><strong>{report.pendingByStatus["awaiting-final"]}</strong><span>Awaiting verified final</span></div>
     <div><strong>{report.pendingByStatus["delayed-review"]}</strong><span>Older than 48h — review</span></div>
    </div>
    {report.verifiedUniqueFinals===0&&<p className="v19-empty">No source-verified finals have settled yet. Pending fixtures are not incorrect picks. This is a verification status—not 0% accuracy.</p>}
    {(report.verification.sourceWarnings?.length||0)>0&&<p className="v19-warning" role="status">Some ESPN source checks were incomplete: {report.verification.sourceWarnings.slice(0,5).join("; ")}. No unverifiable final was counted.</p>}
    {(report.verification.observedScheduleChanges?.length||0)>0&&<p className="v12-subtle">{report.verification.observedScheduleChanges.length} source-observed start-time changes have been flagged for review. Original archived times are preserved.</p>}
    <div className="v19-group-head">
     <h4>Accuracy over time</h4>
     <div role="group" aria-label="Real-game performance aggregation">
      <button type="button" aria-pressed={period==="daily"} onClick={()=>setPeriod("daily")}>Daily</button>
      <button type="button" aria-pressed={period==="weekly"} onClick={()=>setPeriod("weekly")}>Weekly</button>
     </div>
    </div>
    {rows.length>0?<div className="v15-score-table-wrap"><table className="v15-score-table">
     <thead><tr><th scope="col">PERIOD (ET)</th><th scope="col">GAMES</th><th scope="col">WINNER RATE ↑</th><th scope="col">BRIER ↓</th><th scope="col">UPSETS OF OUR FAVORITE</th></tr></thead>
     <tbody>{[...rows].reverse().slice(0,35).map(x=><tr key={x.period}><th scope="row">{x.period}</th><td>{x.games}</td><td>{pct(x.accuracy)}</td><td>{metric(x.brier)}</td><td>{x.upsets||0}</td></tr>)}</tbody></table></div>:
     <p className="v12-subtle">Daily and weekly performance begins once real first-picked games have independently verified finals.</p>}
    <div className="v19-group-head"><h4>Model versus Elo: identical settled games</h4></div>
    <div className="v15-score-table-wrap"><table className="v15-score-table">
     <thead><tr><th scope="col">FROZEN RESEARCH MODEL</th><th scope="col">PAIRED GAMES</th><th scope="col">ELO BRIER ↓</th><th scope="col">CHALLENGER BRIER ↓</th><th scope="col">DIFFERENCE (+ IS BETTER)</th></tr></thead>
     <tbody>{report.pairedComparisons.map(x=><tr key={x.model}><th scope="row">{x.model}{x.reviewEligible?" · Review threshold met":""}</th>
      <td>{x.pairedGames}</td><td>{metric(x.eloBrier)}</td><td>{metric(x.candidateBrier)}</td>
      <td>{x.brierGain==null?"—":(x.brierGain>0?"+":"")+metric(x.brierGain,5)}
       {x.dateBlockGain95&&<small className="v19-interval">95% date-block interval: {x.dateBlockGain95.map(v=>metric(v,5)).join(" to ")}</small>}</td>
     </tr>)}</tbody></table></div>
    <p className="v12-subtle">All candidate comparisons use their original frozen probabilities against original Elo on the same independently verified events. A smaller sample, or an interval spanning zero, does not justify promotion; model updates require explicit review.</p>
    <div className="v19-group-head"><h4>Actual experimental score prediction error</h4></div>
    <div className="v19-score">
      <div><small>FROZEN PREGAME SCORE FORECASTS SCORED</small><strong>{report.frozenScoreResults.games}</strong></div>
      <div><small>SCORING MARGIN MAE</small><strong>{metric(report.frozenScoreResults.marginMAE,2)}</strong></div>
      <div><small>COMBINED TOTAL MAE</small><strong>{metric(report.frozenScoreResults.totalMAE,2)}</strong></div>
    </div>
    {report.frozenScoreResults.games===0?<p className="v12-subtle">No original pregame-frozen score projection has a matched verified final yet. Older projected scores will never be backfilled to manufacture a result.</p>:
      <p className="v12-subtle">Point errors are calculated using the original pregame projected final score, not a model refitted after the game. This score forecast is experimental and separate from the active Elo win probability.</p>}
    <details className="v19-review"><summary>Source verification and delayed-game review</summary>
      <p>Last report: {new Date(report.generatedAtUtc).toLocaleString("en-US",{timeZone:"America/New_York"})} ET. Last archived ledger: {report.archiveGeneratedAtUtc?new Date(report.archiveGeneratedAtUtc).toLocaleString("en-US",{timeZone:"America/New_York"}):"Unknown"}.</p>
      {report.pendingReview.length>0?report.pendingReview.map(x=><p key={x.eventId}>{x.away} at {x.home} · ESPN {x.eventId} · {x.hoursSinceListedStart.toFixed(0)}h since listed start · Needs independent source matching; not scored.</p>):
       <p>No original unmatched games currently exceed the 48-hour review threshold.</p>}
    </details>
   </>}
 </section>;
}
