"use client";
import {useEffect,useState} from "react";
const base=process.env.NEXT_PUBLIC_BASE_PATH||"";
type Report={checkedAtUtc:string;sourceVerifiedUniqueGames:number;settledUniqueGames:number;pendingUniqueEvents:number;counters:{future:number;recentlyStarted:number;awaitingVerifiedFinal:number;delayedOver48h:number;settledSnapshots:number};oldestDelayed:Array<{eventId:string;home:string;away:string;scheduledStartUtc:string;hoursSinceListedStart:number}>};
export default function SettlementHealth(){
 const [report,setReport]=useState<Report|null>(null);
 const [error,setError]=useState(false);
 useEffect(()=>{let active=true;fetch(base+"/current/settlement-health.json").then(r=>{if(!r.ok)throw Error("unpublished");return r.json()}).then(v=>{if(active)setReport(v)}).catch(()=>{if(active)setError(true)});return()=>{active=false}},[]);
 return <section className="v12-card" aria-label="Verified prediction settlement diagnostics">
   <div className="v12-head"><div><span className="section-kicker">EVIDENCE WATCH / FINAL SCORE RECONCILIATION</span><h3>What happened <em>after the pick?</em></h3>
     <p>Pending does not mean incorrect. Settlements need matching NCAA scores and independent ESPN completed-game verification; listed start time is not proof that play occurred.</p></div></div>
   {report?<><div className="v12-stats">
     <div><small>ORIGINAL UNIQUE GAMES</small><strong>{report.sourceVerifiedUniqueGames}</strong></div>
     <div><small>SETTLED UNIQUE GAMES</small><strong>{report.settledUniqueGames}</strong></div>
     <div><small>FUTURE SNAPSHOT ENTRIES</small><strong>{report.counters.future}</strong></div>
     <div><small>OLDER THAN 48 HOURS</small><strong>{report.counters.delayedOver48h}</strong></div>
   </div><p className="v12-subtle">{report.counters.recentlyStarted} entries started less than five hours ago; {report.counters.awaitingVerifiedFinal} are awaiting independently matched finals (5–48 hours). Counts are snapshot entries unless marked unique.</p>
     {report.oldestDelayed.length>0?<div className="v12-delays"><h4>REVIEW DELAYED SOURCE MATCHES</h4>{report.oldestDelayed.map(x=><div key={x.eventId}><span>{x.away} at {x.home}</span><strong>{x.hoursSinceListedStart.toFixed(0)}h since listed start</strong></div>)}</div>:<p className="v12-subtle">No unverified entries currently exceed the 48-hour review threshold.</p>}
     <p className="v12-subtle">Status calculated {new Date(report.checkedAtUtc).toLocaleString("en-US",{timeZone:"America/New_York"})} ET. Does not rewrite saved picks or results.</p>
   </>:<p className="v12-subtle" role="status">{error?"Settlement diagnostics have not been published yet. Original archived picks remain available above.":"Loading source audit status…"}</p>}
 </section>;
}