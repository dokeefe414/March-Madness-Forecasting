"use client";
import {useMemo} from "react";
type Fixture={eventId:string;scheduledEasternDate:string;scheduledStartUtc:string;home:string;away:string;status:"ready"|"unmatched";homeWinProbability:number|null};
type Health={status:string;message:string}|null;
const percentage=(v:number)=>(100*v).toFixed(1)+"%";
export default function DailyDesk({games,today,health,generatedAt,settled,onChoose,onToday}:{games:Fixture[];today:string;health:Health;generatedAt:string;settled:number;onChoose:(id:string)=>void;onToday:()=>void}){
 const ordered=useMemo(()=>games.filter(g=>g.status==="ready"&&g.homeWinProbability!=null),[games]);
 const todays=ordered.filter(g=>g.scheduledEasternDate===today);
 const favorites=[...ordered].sort((a,b)=>Math.abs((b.homeWinProbability??.5)-.5)-Math.abs((a.homeWinProbability??.5)-.5));
 const upsets=[...ordered].filter(g=>Math.max(g.homeWinProbability??.5,1-(g.homeWinProbability??.5))<=.65)
   .sort((a,b)=>Math.abs((a.homeWinProbability??.5)-.5)-Math.abs((b.homeWinProbability??.5)-.5));
 const time=(iso:string)=>new Date(iso).toLocaleString("en-US",{timeZone:"America/New_York",month:"short",day:"numeric",hour:"numeric",minute:"2-digit"})+" ET";
 const card=(g:Fixture|undefined,kind:string)=><div className="daily-card" key={kind}>
   <small>{kind}</small>
   {g?<><strong>{g.away} at {g.home}</strong><span>{time(g.scheduledStartUtc)}</span>
     <b>{percentage(Math.max(g.homeWinProbability!,1-g.homeWinProbability!))} modeled favorite</b>
     <button type="button" onClick={()=>onChoose(g.eventId)}>ANALYZE THIS GAME ↗</button></>:
     <p>No source-verified qualifying fixture in the published upcoming schedule.</p>}
 </div>;
 const stale=Number.isFinite(Date.parse(generatedAt))&&Date.now()-Date.parse(generatedAt)>36*60*60*1000;
 return <section className="daily-desk" aria-label="Today's basketball forecast desk">
    <div className="daily-heading"><div><span className="section-kicker">DAILY COURTSIDE DESK / EASTERN TIME</span>
      <h2>Today & <em>what's next.</em></h2>
      <p>Only sourced future fixtures. Probabilities are pregame model estimates, not live in-game odds.</p></div>
      <button type="button" className="daily-today" onClick={onToday}>VIEW TODAY'S FIXTURES ↓</button>
    </div>
    <div className="daily-kpis">
      <div><small>TODAY'S FUTURE GAMES</small><strong>{games.filter(g=>g.scheduledEasternDate===today).length}</strong><span>At published snapshot</span></div>
      <div><small>SOURCE-MATCHED FUTURE</small><strong>{ordered.length}</strong><span>Model estimates available</span></div>
      <div><small>SETTLED FIRST PICKS</small><strong>{settled}</strong><span>Independent final verification</span></div>
      <div><small>ARCHIVE STATUS</small><strong className="daily-health">{health?.status?.replaceAll("-"," ")||"unverified"}</strong><span>{health?.message||"Archive status unavailable"}</span></div>
    </div>
    {stale&&<p className="gc-warning" role="status">Published schedule is more than 36 hours old; do not treat its future odds as current.</p>}
    <div className="daily-highlights">
       {card(todays[0],"NEXT VERIFIED GAME TODAY")}
       {card(favorites[0],"STRONGEST MODELED FAVORITE")}
       {card(upsets[0],"CLOSEST MODELED MATCHUP")}
    </div>
    <p className="daily-capture">Snapshot: {time(generatedAt)}. Cards describe the currently published future schedule, not all NCAA games. Missing source matches remain unpredicted.</p>
 </section>;
}
