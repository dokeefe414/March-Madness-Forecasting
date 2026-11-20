"use client";

import {useEffect,useMemo,useState} from "react";

const base=process.env.NEXT_PUBLIC_BASE_PATH||"";
type TeamComparison={apRank:number;apName:string;espnTeamId:string;
  eloRank:number|null;elo:number|null;eloTeamName:string|null;
  eloGames:number|null;rankGap:number|null;eloTop25:boolean};
type Week={pollKey:string;sourceWeekStart:string;sourceWeekNumber?:number|null;
  capturedAtUtc:string;eloGameCutoffDate:string;eloModelVersion:string;
  status:"ready"|"incomplete-source-coverage";matchedApTeams:number;
  missingApTeams:number;top25Overlap:number|null;top10Overlap:number|null;
  meanAbsoluteRankGap:number|null;spearmanWithinMatched:number|null;
  divisionIRatedProgramsAtCutoff:number;ncaaPlusEspnRatedGamesThroughCutoff:number;
  teams:TeamComparison[];
  eloTop25:Array<{eloRank:number;team:string;espnTeamId:string;elo:number}>};
type History={schemaVersion:number;season:number;mode:string;pollSourceUrl:string;
  sourceLandingUrl:string;weeks:Week[]};
const labelDate=(v:string)=>new Date(v+"T12:00:00Z").toLocaleDateString("en-US",{
  month:"short",day:"numeric",year:"numeric",timeZone:"UTC"});
const display=(v:number|null|undefined,n=2)=>v==null?"—":v.toFixed(n);

export default function ApPollComparison(){
  const [history,setHistory]=useState<History|null>(null);
  const [state,setState]=useState<"loading"|"ready"|"unavailable">("loading");
  const [selected,setSelected]=useState("");
  const [differences,setDifferences]=useState(false);
  const [revision,setRevision]=useState(0);

  useEffect(()=>{
    const refresh=()=>setRevision(r=>r+1);
    const timer=window.setInterval(refresh,10*60_000);
    const visible=()=>{if(document.visibilityState==="visible")refresh()};
    document.addEventListener("visibilitychange",visible);
    return()=>{window.clearInterval(timer);document.removeEventListener("visibilitychange",visible)};
  },[]);
  useEffect(()=>{
    let active=true;
    fetch(base+"/research/ap-poll-history.json",{cache:"no-store"})
      .then(async r=>{if(!r.ok)throw Error("No archived AP poll data");
        const data=await r.json() as History;
        if(data.schemaVersion!==1||data.season!==2027||
           data.mode!=="weekly-AP-vs-Elo-independent-research"||
           !Array.isArray(data.weeks))throw Error("Invalid AP comparison source");
        return data;
      }).then(data=>{if(!active)return;setHistory(data);setState("ready")})
      .catch(()=>{if(active)setState("unavailable")});
    return()=>{active=false};
  },[revision]);

  const editions=useMemo(()=>[...(history?.weeks||[])].reverse(),[history]);
  const week=editions.find(w=>w.pollKey===selected)||editions[0];
  const rows=week?.teams||[];
  const shown=rows.filter(r=>!differences||r.eloRank==null||
                 Math.abs(r.rankGap||0)>=5||!r.eloTop25);
  const pollIds=new Set(rows.map(r=>r.espnTeamId));
  const outsiders=(week?.eloTop25||[]).filter(r=>!pollIds.has(r.espnTeamId));
  const latest=editions[0];

  return <section className="ap-lab" id="ap-elo-comparison" aria-label="Weekly AP Top 25 versus Elo rankings">
    <div className="ap-lab-head">
      <div className="ap-lab-eyebrow"><span className="ap-lab-dot"/> INDEPENDENT WEEKLY BENCHMARK / 2026–27</div>
      <div className="ap-lab-head-grid">
        <div>
          <h2>THE POLL <span>vs.</span> THE MODEL.</h2>
          <p>See where the voters' AP Top 25 and our game-aware Elo rankings agree—and where they disagree. Each captured comparison is preserved, so you can follow the relationship week by week.</p>
        </div>
        <div className="ap-lab-summary">
          <small>AP TOP 25 OVERLAP</small>
          <strong>{week?.top25Overlap==null?"—":String(week.top25Overlap).padStart(2,"0")}<em>/25</em></strong>
          <span>{week?.status==="ready"?"Identical ranked teams in both Top 25s":"Waiting for a complete comparable poll"}</span>
        </div>
      </div>
    </div>
    {state==="loading"?<p className="ap-empty" role="status">Loading frozen weekly AP comparisons…</p>:
     state==="unavailable"?<p className="ap-empty" role="alert">The weekly AP comparison archive isn't available. Elo rankings and game forecasts remain independent.</p>:
     !week?<div className="ap-empty"><strong>First weekly comparison pending.</strong><p>After ESPN publishes the men's AP Top 25 and the scheduled GitHub archiver captures it, this panel will display the poll against Elo through the previous Sunday. The archive is checked Monday evening, with subsequent scheduled retries if the provider is delayed.</p></div>:
     <>
       <div className="ap-lab-controls">
         <label>SELECT AP POLL WEEK
           <select aria-label="Select AP poll comparison week" value={week.pollKey}
             onChange={e=>setSelected(e.target.value)}>
             {editions.map(w=><option key={w.pollKey} value={w.pollKey}>
               Week of {labelDate(w.sourceWeekStart)} · {w.status==="ready"?"Compared":"Partial coverage"}
             </option>)}
           </select>
         </label>
         <div className="ap-lab-source">
           <span>AP SOURCE WEEK <b>{labelDate(week.sourceWeekStart)}</b></span>
           <span>ELO GAME CUTOFF <b>{labelDate(week.eloGameCutoffDate)}</b></span>
           <span>COLLECTED <b>{new Date(week.capturedAtUtc).toLocaleDateString("en-US",{month:"short",day:"numeric",year:"numeric"})}</b></span>
         </div>
       </div>
       {week.status!=="ready"&&<p className="ap-lab-warning" role="status">This edition has only {week.matchedApTeams} of 25 AP teams matched to played-game, 2027 source-verified Division I Elo programs. Agreement metrics are withheld until the evidence is sufficient; missing schools never receive an invented rank.</p>}
       <div className="ap-lab-metrics">
         <div><small>TOP 25 OVERLAP</small><strong>{week.top25Overlap??"—"} <span>/ 25</span></strong><p>Shared members of the two Top 25 lists</p></div>
         <div><small>TOP 10 OVERLAP</small><strong>{week.top10Overlap??"—"} <span>/ 10</span></strong><p>Same teams inside each Top 10</p></div>
         <div><small>AVG. RANK DIFFERENCE</small><strong>{display(week.meanAbsoluteRankGap,1)}</strong><p>Mean |AP rank − Elo D-I rank| for matched teams</p></div>
         <div><small>RANK CORRELATION</small><strong>{display(week.spearmanWithinMatched)}</strong><p>Spearman across the shared AP-ranked programs</p></div>
       </div>
       <div className="ap-lab-main">
         <div className="ap-lab-table-panel">
           <div className="ap-lab-panel-head">
             <div><small>POWER RANKING DIFFERENCES</small><h3>Side by side.</h3></div>
             <label className="ap-lab-toggle">
               <input type="checkbox" checked={differences} onChange={e=>setDifferences(e.target.checked)}/>
               BIG GAPS ONLY
             </label>
           </div>
           <div className="ap-lab-table-scroll">
             <table className="ap-lab-table">
               <thead><tr><th>AP #</th><th>PROGRAM</th><th>ELO D-I #</th><th>GAP</th></tr></thead>
               <tbody>{shown.map(team=><tr key={team.espnTeamId}>
                 <td><b className="ap-lab-ap-rank">{team.apRank}</b></td>
                 <td><strong>{team.apName}</strong>
                   <small>{team.eloGames==null?"NO PRE-WEEK ELO MATCH":
                        team.eloGames+" games · Elo "+display(team.elo,1)}</small></td>
                 <td>{team.eloRank==null?<span className="ap-lab-missing">—</span>:
                   <b className={team.eloTop25?"ap-lab-elo-in":"ap-lab-elo-out"}>#{team.eloRank}</b>}</td>
                 <td>{team.rankGap==null?"—":<span className={Math.abs(team.rankGap)>=10?"ap-lab-large-gap":""}>
                   {team.rankGap>0?"+":""}{team.rankGap}</span>}</td>
               </tr>)}</tbody>
             </table>
           </div>
           {shown.length===0&&<p className="ap-lab-empty-results">No large gaps in this week's matched teams.</p>}
           <p className="ap-lab-legend">A positive gap means Elo ranks the team <strong>lower</strong> than the AP poll. Elo ranks include source-matched D-I schools with recorded games, not every opponent in the national data feed.</p>
         </div>
         <div className="ap-lab-side">
           <div className="ap-lab-trend">
             <small>WEEK-TO-WEEK / TOP 25 AGREEMENT</small>
             <h3>Watch it evolve.</h3>
             {editions.slice(0,8).reverse().map(w=><button
               type="button" key={w.pollKey}
               className={"ap-lab-history-line"+(w.pollKey===week.pollKey?" selected":"")}
               onClick={()=>setSelected(w.pollKey)} aria-label={"Select AP week of "+labelDate(w.sourceWeekStart)}>
               <span>{labelDate(w.sourceWeekStart)}</span>
               <i><b style={{width:((w.top25Overlap??0)/25*100)+"%"}}/></i>
               <strong>{w.top25Overlap==null?"—":w.top25Overlap+"/25"}</strong>
             </button>)}
             {!latest?.top25Overlap&&latest?.top25Overlap!==0?<p>Waiting for enough matched schools to compare.</p>:null}
           </div>
           <div className="ap-lab-outsiders">
             <small>MODEL TOP 25 · NOT VOTED INTO AP</small>
             <h3>Outside the poll.</h3>
             {outsiders.length?outsiders.slice(0,8).map(x=>
               <div key={x.espnTeamId}><span>#{x.eloRank} <strong>{x.team}</strong></span><b>{x.elo.toFixed(0)} Elo</b></div>):
               <p>{week.status!=="ready"?"Source matching is incomplete.":"Both Top 25 lists contain the same schools, or Elo has no unmatched rated schools in its Top 25."}</p>}
           </div>
         </div>
       </div>
       <p className="ap-lab-footnote">Poll edition <strong>{labelDate(week.sourceWeekStart)}</strong> · Elo replay includes {week.ncaaPlusEspnRatedGamesThroughCutoff?.toLocaleString()??0} results dated through the previous Sunday. Source: <a href={history?.sourceLandingUrl||"https://www.espn.com/mens-college-basketball/rankings"} target="_blank" rel="noreferrer">ESPN's AP poll feed ↗</a>. Poll positions are opinions, not verified game outcomes. Matching the AP poll is <strong>not</strong> evidence of higher win-prediction accuracy, and poll comparisons never train or automatically promote any model. Earlier weekly captures remain frozen even if historical source rows arrive later.</p>
     </>}
  </section>;
}
