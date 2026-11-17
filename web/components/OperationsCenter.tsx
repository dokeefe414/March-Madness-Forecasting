"use client";
import {useEffect,useState} from "react";
const base=process.env.NEXT_PUBLIC_BASE_PATH||"";
type Check={name:string;state:"pass"|"review"|"fail";detail:string};
type Report={state:"operational"|"review"|"degraded"|"off-season";checkedAtUtc:string;archiveStatus:string;
 lastSuccessfulCaptureUtc:string|null;captureAgeHours:number|null;checkedSourceEvents:number|null;unmatchedSourceEvents:number|null;
 uniqueArchivedEvents:number;repeatSnapshots:number;uniqueSettledEvents:number;delayedSnapshotEntries:number;
 sourceWarnings:string[];checks:Check[];delayedExamples:Array<{eventId:string;home:string;away:string;hoursSinceListedStart:number}>};
export default function OperationsCenter(){
 const [report,setReport]=useState<Report|null>(null);
 const [problem,setProblem]=useState("");
 useEffect(()=>{let alive=true;fetch(base+"/current/operations.json").then(r=>{if(!r.ok)throw Error("Operations artifact is not deployed.");return r.json()}).then(r=>{
   if(!r?.checks||!Array.isArray(r.checks))throw Error("Malformed archive operations status");
   if(alive)setReport(r);
 }).catch(e=>{if(alive)setProblem(e.message)});return()=>{alive=false}},[]);
 const pretty=(iso:string|null)=>iso?new Date(iso).toLocaleString("en-US",{timeZone:"America/New_York",month:"short",day:"numeric",hour:"numeric",minute:"2-digit"})+" ET":"not yet recorded";
 return <section className="v13-ops" aria-label="Public forecast operations and source quality">
   <div className="v13-feature-head"><span className="section-kicker">SOURCE PROVENANCE / PUBLIC OPERATIONS</span>
    <h3>Can we <em>trust the feed?</em></h3>
    <p>Evidence from the most recently published immutable Git ledger. This is a scheduled snapshot, not a real-time uptime monitor or a source of fictional game results.</p></div>
   {!report?<p className="v12-subtle" role="status">{problem||"Loading public source verification…"}</p>:<>
     <div className="v13-ops-head">
       <span className={"v13-state "+report.state}>ARCHIVE {report.state.toUpperCase()}</span>
       <div>Last committed capture: <strong>{pretty(report.lastSuccessfulCaptureUtc)}</strong></div>
       <div>Checked: <strong>{pretty(report.checkedAtUtc)}</strong></div>
     </div>
     <div className="v13-ops-metrics">
       {[
         ["SOURCE EVENTS CHECKED",report.checkedSourceEvents],
         ["UNAMBIGUOUSLY ARCHIVED",report.uniqueArchivedEvents],
         ["SETTLED UNIQUE GAMES",report.uniqueSettledEvents],
         ["DELAYED SNAPSHOT ENTRIES",report.delayedSnapshotEntries],
         ["DUPLICATE-TIME CAPTURES",report.repeatSnapshots]
       ].map(([name,value])=><div key={String(name)}><small>{name}</small><strong>{value==null?"—":value}</strong></div>)}
     </div>
     <div className="v13-check-grid">{report.checks.map(c=><article key={c.name} className={"v13-check "+c.state}>
        <div><strong>{c.name}</strong><span>{c.state==="pass"?"VERIFIED":c.state==="fail"?"ATTENTION":"REVIEW"}</span></div>
        <p>{c.detail}</p>
     </article>)}</div>
     {report.delayedExamples.length>0&&<details className="v13-ops-details"><summary>Review delayed source-final matches ({report.delayedSnapshotEntries} snapshot entries)</summary>
       {report.delayedExamples.map(x=><div key={x.eventId}><span>{x.away} @ {x.home}</span><small>Listed start {x.hoursSinceListedStart.toFixed(1)} hours ago; final remains unverified</small></div>)}
     </details>}
     <div className="v13-ops-actions">
       <a href="https://github.com/dokeefe414/March-Madness-Forecasting/actions/workflows/archive-pregame.yml" target="_blank" rel="noreferrer">SEE ARCHIVE RUNS ↗</a>
       <a href="https://github.com/dokeefe414/March-Madness-Forecasting/tree/main/web/public/forecasts" target="_blank" rel="noreferrer">INSPECT IMMUTABLE EVIDENCE ↗</a>
     </div>
   </>}
 </section>;
}
