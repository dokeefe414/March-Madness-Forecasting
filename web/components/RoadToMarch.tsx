"use client";
import {useState} from "react";
import {matchupProbability} from "../lib/models";
type Candidate={teamId:string;name:string;conference:string;projectedRating:number;wins:number;losses:number;games:number;category:string;powerRank:number|null;sampleBand:string};
export default function RoadToMarch({teams,asOf}:{teams:Candidate[];asOf:string}){
 const leaders=[...teams].filter(t=>Number.isFinite(t.projectedRating)).sort((a,b)=>b.projectedRating-a.projectedRating).slice(0,8);
 const [focus,setFocus]=useState(leaders[0]?.teamId||"");
 const active=leaders.find(t=>t.teamId===focus)||leaders[0];
 const closest=active&&leaders.filter(t=>t.teamId!==active.teamId).sort((a,b)=>Math.abs(a.projectedRating-active.projectedRating)-Math.abs(b.projectedRating-active.projectedRating))[0];
 const hypothetical=active&&closest?matchupProbability(active.projectedRating,closest.projectedRating):null;
 return <section className="road-march" aria-label="Unselected 2027 tournament strength outlook">
   <div className="road-heading"><div><span className="section-kicker">ROAD TO MARCH 2027 / SCENARIO ONLY</span>
      <h3>Eight teams to <em>watch.</em></h3>
      <p>Current source-verified D-I strength leaders from the power-only field scenario. These positions are not invitations, bracket seeds, or projected championship probabilities.</p></div>
      <span>SOURCE AS OF {asOf}</span>
   </div>
   <div className="road-grid">{leaders.map((t,i)=><button className={active?.teamId===t.teamId?"road-leader selected":"road-leader"}
      aria-pressed={active?.teamId===t.teamId} key={t.teamId} onClick={()=>setFocus(t.teamId)}>
      <small>POWER #{i+1} · {t.conference}</small><strong>{t.name}</strong><span>{t.wins}–{t.losses} / {t.games} games</span>
      <b>{t.projectedRating.toFixed(0)} <small>ELO</small></b>
   </button>)}</div>
   {active?<div className="road-focus" aria-live="polite"><div>
     <small>SELECTED PROGRAM / SOURCE-BASED OUTLOOK</small><h4>{active.name}</h4>
     <p>Current power rank: {active.powerRank??"Unavailable"} · Sample: {active.sampleBand}. Ranking and team strength can change as verified games are added.</p>
   </div><div><small>CLOSEST TOP-EIGHT PEER ON NEUTRAL COURT</small>
     <strong>{closest?.name||"No comparison available"}</strong>
     <b>{hypothetical==null?"—":(hypothetical*100).toFixed(1)+"%"}</b>
     <span>Hypothetical Elo matchup win chance for {active.name}, not a real scheduled game.</span>
   </div></div>:<p className="gc-empty">No verified current strength candidates available.</p>}
 </section>;
}
