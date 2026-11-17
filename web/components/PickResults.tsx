"use client";
import {useEffect,useMemo,useState} from "react";
const base=process.env.NEXT_PUBLIC_BASE_PATH||"";
type Outcome={eventId:string;date:string;scheduledStartUtc:string;forecastAtUtc:string;
  home:string;away:string;homeScore:number;awayScore:number;predictedHome:number;
  observedHome:number;predictedWinner:string|null;actualWinner:string;correct:boolean|null;
  brier:number;model:string};
type Unique={forecastedUniqueGames:number;settledUniqueGames:number;verifiedOutcomes?:Outcome[]};
type Report={schemaVersion:number;generatedAtUtc:string;uniqueGames?:Unique};
type Filter="all"|"correct"|"missed"|"even";
const pct=(p:number)=>(p*100).toFixed(1)+"%";
const eastern=(s:string)=>new Date(s).toLocaleString("en-US",{timeZone:"America/New_York",month:"short",day:"numeric",hour:"numeric",minute:"2-digit"})+" ET";
export default function PickResults(){
 const [data,setData]=useState<Report|null>(null);
 const [error,setError]=useState("");
 const [filter,setFilter]=useState<Filter>("all");
 const [search,setSearch]=useState("");
 const [limit,setLimit]=useState(24);
 useEffect(()=>{let active=true;fetch(base+"/forecasts/index.json",{cache:"no-store"}).then(r=>{
    if(!r.ok)throw new Error("The source-verified ledger is not yet published.");
    return r.json();
  }).then(report=>{if(!active)return;if(report.schemaVersion!==1||!report.uniqueGames)throw new Error("Unknown archive schema");
   setData(report);}).catch(e=>{if(active)setError(e.message)});return()=>{active=false}},[]);
 const original=data?.uniqueGames;
 const outcomes=useMemo(()=>original?.verifiedOutcomes||[],[original]);
 const correct=outcomes.filter(x=>x.correct===true).length;
 const missed=outcomes.filter(x=>x.correct===false).length;
 const tossups=outcomes.filter(x=>x.correct===null).length;
 const visible=outcomes.filter(x=>(filter==="all"||filter==="correct"&&x.correct===true||filter==="missed"&&x.correct===false||filter==="even"&&x.correct===null)
  &&(x.home+" "+x.away).toLowerCase().includes(search.toLowerCase()));
 return <section className="v14-results" aria-label="Correct and missed original before-tipoff predictions">
  <div className="v13-feature-head"><span className="section-kicker">REAL RESULTS / PUBLIC FIRST-PICK RECEIPTS</span>
   <h3>RIGHT. <em>WRONG.</em> VERIFIED.</h3>
   <p>See exactly which original pregame favorite won and which was upset. Every result is the earliest archived prediction for a unique ESPN game, scored only after matching independent final-score evidence.</p></div>
  {!data?<p role={error?"alert":"status"} className="v12-subtle">{error||"Loading independently verified game results…"}</p>:<>
   <div className="v14-result-metrics">
    <div><small>ORIGINAL FIRST PICKS</small><strong>{original?.forecastedUniqueGames??0}</strong></div>
    <div><small>VERIFIED FINALS</small><strong>{original?.settledUniqueGames??0}</strong></div>
    <div><small>CORRECT FAVORITES</small><strong>{correct}</strong></div>
    <div><small>MISSED FAVORITES</small><strong>{missed}</strong></div>
   </div>
   {tossups>0&&<p className="v12-subtle">{tossups} original 50/50 predictions have no chosen winner, and do not count as correct or missed.</p>}
   <div className="v14-results-controls">
    <div role="group" aria-label="Filter verified pick outcomes">
     {([["all","ALL FINALS"],["correct","CORRECT"],["missed","MISSED"],["even","EVEN ODDS"]] as [Filter,string][]).map(([k,label])=>
      <button type="button" key={k} aria-pressed={filter===k} className={filter===k?"active":""} onClick={()=>{setFilter(k);setLimit(24)}}>{label}</button>)}
    </div>
    <label>FIND A GAME<input type="search" value={search} onChange={e=>{setSearch(e.target.value);setLimit(24)}} placeholder="Search team…" aria-label="Search verified results by team"/></label>
   </div>
   {outcomes.length===0?<div className="v14-empty-result">
     <strong>NO VERIFIED FINALS YET</strong>
     <p>The archive has not recorded independently confirmed outcomes for its original first picks. Once source-matched scores settle, correct and missed games will appear here automatically after the website republishes.</p>
     <p>Unarchived past games will not be invented or shown as successful predictions.</p>
   </div>:<>
    <div className="v14-outcome-grid">{visible.slice(0,limit).map(g=><article key={g.eventId} className={"v14-outcome "+(g.correct===true?"is-right":g.correct===false?"is-wrong":"is-even")}>
      <div className="v14-outcome-head"><strong>{g.correct===true?"✓ CORRECT PICK":g.correct===false?"× MISSED PICK":"◊ NO FAVORITE"}</strong><span>{g.date} · EVENT {g.eventId}</span></div>
      <div className="v14-score-row"><span>{g.away}<b>{g.awayScore}</b></span><span>{g.home}<b>{g.homeScore}</b></span></div>
      <div className="v14-result-answer"><span>Predicted: <b>{g.predictedWinner||"50/50 tie"} · {pct(Math.max(g.predictedHome,1-g.predictedHome))}</b></span><span>Winner: <b>{g.actualWinner}</b></span></div>
      <div className="v14-outcome-footer"><span>Brier {g.brier.toFixed(4)}</span><span>Frozen {eastern(g.forecastAtUtc)}</span></div>
     </article>)}</div>
     {!visible.length&&<p className="v12-subtle" role="status">No verified results match that filter. No game result has been inferred.</p>}
     {visible.length>limit&&<button className="v14-load-more" onClick={()=>setLimit(v=>v+24)}>SHOW MORE VERIFIED GAMES ({visible.length-limit} remaining)</button>}
    </>}
   <p className="v12-subtle">Latest published archive: {eastern(data.generatedAtUtc)}. This is not a live scoreboard. A missed pick is an original favorite losing—not simply a probability below 50%. Duplicate captures never increase the unique-game correctness totals.</p>
  </>}
 </section>;
}
