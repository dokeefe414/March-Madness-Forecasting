"use client";
import {useEffect,useMemo,useState} from "react";
import type {BracketField,BracketTeam} from "../lib/fullBracket";
const rounds=["PLAY-IN","ROUND OF 64","ROUND OF 32","SWEET 16","ELITE 8","FINAL FOUR","TITLE"] as const;
type Match={key:string;a:BracketTeam|null;b:BracketTeam|null};
type Picks=Record<string,string>;
function pair(items:(BracketTeam|null)[],prefix:string):Match[]{
 const results:Match[]=[];for(let i=0;i<items.length;i+=2)results.push({key:prefix+"-"+i/2,a:items[i],b:items[i+1]});
 return results;
}
function buildRounds(field:BracketField,picks:Picks):Match[][]{
 const play:Match[]=[];const regionFirst:(BracketTeam|null)[][]=[];
 for(const region of field.regions){
   regionFirst.push(region.slots.map(slot=>{
     if(slot.teams.length===1)return slot.teams[0];
     const key="play-"+region.code+"-"+slot.seed;
     play.push({key,a:slot.teams[0],b:slot.teams[1]});
     return slot.teams.find(t=>t.teamId===picks[key])||null;
   }));
 }
 const all:Match[][]=[play];
 let current=regionFirst;
 for(let round=0;round<4;round++){
   const matches:Match[]=[],next:(BracketTeam|null)[][]=[];
   for(let region=0;region<4;region++){
     const segment=pair(current[region],"region-"+field.regions[region].code+"-r"+round);
     matches.push(...segment);
     next.push(segment.map(m=>m.a&&m.b?(m.a.teamId===picks[m.key]?m.a:m.b.teamId===picks[m.key]?m.b:null):null));
   }
   all.push(matches);current=next;
 }
 // W/X and Y/Z crossover is a scenario assumption from the existing engine.
 let entrants=[current[0][0],current[1][0],current[2][0],current[3][0]];
 const semifinal=pair(entrants,"semi");
 all.push(semifinal);
 entrants=semifinal.map(m=>m.a&&m.b?(m.a.teamId===picks[m.key]?m.a:m.b.teamId===picks[m.key]?m.b:null):null);
 all.push(pair(entrants,"final"));
 return all;
}
export default function BracketBuilder({field}:{field:BracketField}){
 const [picks,setPicks]=useState<Picks>({});
 const [stage,setStage]=useState(1);
 const [notice,setNotice]=useState("");
 const [loaded,setLoaded]=useState(false);
 const storageKey="marchforecast-bracket-"+field.season;
 useEffect(()=>{
   let result:Picks={};
   try{const params=new URLSearchParams(window.location.search);const encoded=params.get("picks");
      if(encoded){const parsed=JSON.parse(decodeURIComponent(atob(encoded)));if(parsed&&typeof parsed==="object"&&!Array.isArray(parsed))result=parsed}
      else {const saved=localStorage.getItem(storageKey);if(saved)result=JSON.parse(saved)}}
   catch{result={};}
   setPicks(result);setStage(1);setLoaded(true);
 },[storageKey]);
 const roundsData=useMemo(()=>buildRounds(field,picks),[field,picks]);
 const current=roundsData[stage]||[];
 const winners=roundsData[6][0];
 const champion=winners?.a&&winners?.b?(winners.a.teamId===picks[winners.key]?winners.a:winners.b.teamId===picks[winners.key]?winners.b:null):null;
 const decided=roundsData.flat().filter(m=>m.a&&m.b&&[m.a.teamId,m.b.teamId].includes(picks[m.key])).length;
 const playable=roundsData.flat().filter(m=>m.a&&m.b).length;
 function pick(key:string,id:string){setNotice("");setPicks(old=>{const next={...old,[key]:id};try{localStorage.setItem(storageKey,JSON.stringify(next))}catch{}return next})}
 function reset(){setPicks({});try{localStorage.removeItem(storageKey)}catch{}setNotice("Bracket picks reset.")}
 async function share(){
    const valid:Record<string,string>={};
    for(const m of roundsData.flat())if(m.a&&m.b&&[m.a.teamId,m.b.teamId].includes(picks[m.key]))valid[m.key]=picks[m.key];
    const url=new URL(window.location.href);url.searchParams.set("view","bracket");
    url.searchParams.set("picks",btoa(encodeURIComponent(JSON.stringify(valid))));
    try{await navigator.clipboard.writeText(url.toString());setNotice("Shareable bracket link copied.")}catch{setNotice("Copy link unavailable in this browser.")}
 }
 return <section className="v12-builder" aria-label="Build a historical tournament bracket">
  <div className="v12-head"><div><span className="section-kicker">INTERACTIVE PICK'EM / HISTORICAL SOURCE FIELD {field.season}</span><h3>Build your own <em>bracket.</em></h3><p>Pick opening games and advance winners through each round. Your choices save in this browser; share a link with your scenario. The game outcomes are not treated as predictions by the forecasting model.</p></div></div>
  <div className="v12-builder-actions"><strong>{decided} / {playable} available games picked</strong><button onClick={share}>COPY SCENARIO LINK ↗</button><button onClick={reset}>RESET PICKS</button></div>
  <div className="v12-round-tabs" role="group" aria-label="Tournament round">{rounds.map((round,i)=><button key={round} aria-pressed={i===stage} className={i===stage?"active":""} onClick={()=>setStage(i)}>{round}</button>)}</div>
  {stage===1&&field.openingRoundGames>0&&<p className="v12-subtle">Complete the Play-in round first for any two-team seed slots. Unresolved games will wait for a winner.</p>}
  <div className="v12-match-grid">{current.map(m=><article className="v12-match" key={m.key}>
    <small>{m.key.replaceAll("-"," ").toUpperCase()}</small>
    {[m.a,m.b].map((team,i)=><button key={i} disabled={!team} onClick={()=>team&&pick(m.key,team.teamId)} className={team&&picks[m.key]===team.teamId?"selected":""} aria-pressed={!!team&&picks[m.key]===team.teamId}>
      {team?<><span>#{team.seed} {team.name}</span><b>{team.projectedRating.toFixed(0)} ELO</b></>:<span>WINNER PENDING</span>}
    </button>)}
   </article>)}</div>
  {stage===6&&<div className="v12-builder-champion"><small>YOUR CHAMPION</small><strong>{champion?.name||"Choose a winner to crown the champion"}</strong></div>}
  <p className="v12-subtle" role="status">{notice||(!loaded?"Loading saved picks…":"Scenario only. Historical seeded entrants are real; the generic Final Four region crossover may differ from the official year-specific semifinal pairing.")}</p>
 </section>;
}
