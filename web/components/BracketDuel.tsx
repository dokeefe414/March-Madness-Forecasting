"use client";
import {useEffect,useMemo,useState} from "react";
import type {BracketField} from "../lib/fullBracket";
import {buildRounds,type Picks,type Match} from "./BracketBuilder";
const roundNames=["PLAY IN","ROUND OF 64","ROUND OF 32","SWEET 16","ELITE 8","FINAL FOUR","TITLE"];
type Player="A"|"B";
function validDecision(match:Match,picks:Picks):string|null{
 if(!match.a||!match.b)return null;
 return [match.a.teamId,match.b.teamId].includes(picks[match.key])?picks[match.key]:null;
}
export function modelPicks(field:BracketField):Picks{
 let picks:Picks={};
 // Each round is fully resolved from the *previous* round's source-backed
 // seeds and independent fixed Elo strength. No tournament result is used.
 for(let round=0;round<7;round++)
   for(const m of buildRounds(field,picks)[round])
     if(m.a&&m.b)picks[m.key]=(m.a.projectedRating>=m.b.projectedRating?m.a:m.b).teamId;
 return picks;
}
export function comparePicks(field:BracketField,a:Picks,b:Picks):{
 comparable:number;agreements:number;disagreements:Array<{round:number;key:string;a:string;b:string}>
}{
 const ar=buildRounds(field,a),br=buildRounds(field,b);
 let comparable=0,agreements=0;
 const disagreements=[];
 for(let round=0;round<7;round++){
   for(let i=0;i<ar[round].length;i++){
      const left=ar[round][i],right=br[round][i];
      const aa=validDecision(left,a),bb=validDecision(right,b);
      // Different reachable participants indicate a disagreement already
      // captured in an earlier round, not a comparable match here.
      if(!aa||!bb||!left.a||!left.b||!right.a||!right.b)continue;
      if([left.a.teamId,left.b.teamId].sort().join(",")!==[right.a.teamId,right.b.teamId].sort().join(","))continue;
      comparable++;
      if(aa===bb)agreements++;
      else disagreements.push({round,key:left.key,a:aa,b:bb});
   }
 }
 return {comparable,agreements,disagreements};
}
export default function BracketDuel({field}:{field:BracketField}){
 const [players,setPlayers]=useState<{A:Picks;B:Picks}>({A:{},B:{}});
 const [who,setWho]=useState<Player>("A");
 const [round,setRound]=useState(1);
 const [notice,setNotice]=useState("");
 const storageKey="marchforecast-duel-"+field.season;
 useEffect(()=>{
  try{const saved=localStorage.getItem(storageKey);
    if(saved){const parsed=JSON.parse(saved);if(parsed&&typeof parsed==="object"&&parsed.A&&parsed.B)setPlayers(parsed);}}
  catch{/* Disabled storage: in-memory play still works. */}
 },[storageKey]);
 const matches=useMemo(()=>buildRounds(field,players[who]),[field,players,who]);
 const comparison=useMemo(()=>comparePicks(field,players.A,players.B),[field,players]);
 const chalk=useMemo(()=>modelPicks(field),[field]);
 const versusModel=useMemo(()=>comparePicks(field,players[who],chalk),[field,players,who,chalk]);
 function choose(key:string,id:string){
  setPlayers(prev=>{
   const next={A:{...prev.A},B:{...prev.B}};
   next[who][key]=id;
   try{localStorage.setItem(storageKey,JSON.stringify(next))}catch{}
   return next;
  });
  setNotice("");
 }
 function reset(){
  const next={A:{},B:{}};setPlayers(next);
  try{localStorage.removeItem(storageKey)}catch{}
  setNotice("Both brackets reset.");
 }
 async function share(){
  const urls=new URL(window.location.href);
  urls.searchParams.set("view","bracket");
  const encoded=btoa(encodeURIComponent(JSON.stringify(players)));
  urls.searchParams.set("duel",encoded);
  if(urls.toString().length>7500){setNotice("This duel has too many picks for a reliably shareable URL; both players can continue in this browser.");return}
  try{await navigator.clipboard.writeText(urls.toString());setNotice("Two-player competition link copied.");}
  catch{setNotice("Clipboard is unavailable; your local two-player brackets are still saved.")}
 }
 useEffect(()=>{
  const code=new URLSearchParams(window.location.search).get("duel");
  if(!code||code.length>12000)return;
  try{
   const p=JSON.parse(decodeURIComponent(atob(code)));
   if(!p||typeof p!=="object"||!p.A||!p.B)return;
   // Retain only actual existing round keys and valid entrant IDs. Later
   // round reachability is revalidated by the normal resolver.
   const sanitize=(val:unknown)=>{
     const clean:Picks={};
     if(!val||typeof val!=="object"||Array.isArray(val))return clean;
     const allowed=new Set(field.entrants.map(t=>t.teamId));
     for(const [key,id] of Object.entries(val))
       if(key.length<=80&&typeof id==="string"&&allowed.has(id)&&Object.keys(clean).length<90)clean[key]=id;
     return clean;
   };
   setPlayers({A:sanitize(p.A),B:sanitize(p.B)});
  }catch{/* No trusted decoder shortcut; ignore malformed URL. */}
 },[field]);
 const pending=matches[round]||[];
 const name=(id:string)=>field.entrants.find(t=>t.teamId===id)?.name||"Unverified team";
 return <section className="v13-duel" aria-label="Two-player bracket competition">
   <div className="v13-feature-head"><span className="section-kicker">BRACKET VERSUS / SAME VERIFIED HISTORICAL FIELD</span>
    <h3>TWO PLAYERS. <em>ONE TITLE.</em></h3>
    <p>Pass the device or share a comparison link. Each person's picks are independent and only comparable matches count toward agreement. A separate all-Elo-favorites bracket provides a transparent reference—not an official result or proven optimal strategy.</p></div>
   <div className="v13-duel-score">
    <div><small>COMPARABLE DECISIONS</small><strong>{comparison.comparable}</strong></div>
    <div><small>DIFFERENT PICKS</small><strong>{comparison.disagreements.length}</strong></div>
    <div><small>AGREEMENTS</small><strong>{comparison.agreements}</strong></div>
    <div><small>{who==="A"?"PLAYER A":"PLAYER B"} VS ELO FAVORITES</small><strong>{versusModel.agreements}/{versusModel.comparable}</strong></div>
   </div>
   <div className="v13-duel-actions">
     <div role="group" aria-label="Active bracket competitor">
      {(["A","B"] as Player[]).map(p=><button key={p} aria-pressed={who===p} className={who===p?"active":""} onClick={()=>setWho(p)}>PLAYER {p}</button>)}
     </div>
     <button type="button" onClick={share}>COPY DUEL LINK ↗</button>
     <button type="button" onClick={reset}>RESET BOTH</button>
   </div>
   <div className="v12-round-tabs" role="group" aria-label="Duel round">
    {roundNames.map((r,i)=><button type="button" key={r} aria-pressed={round===i} className={round===i?"active":""} onClick={()=>setRound(i)}>{r}</button>)}
   </div>
   <div className="v13-duel-matches">
     {pending.map(m=><div key={m.key} className="v13-duel-match">
       <small>{m.key.replaceAll("-"," ").toUpperCase()}</small>
       {[m.a,m.b].map((team,index)=><button type="button" key={index} disabled={!team}
         onClick={()=>team&&choose(m.key,team.teamId)}
         className={team&&validDecision(m,players[who])===team.teamId?"active":""}
         aria-pressed={!!team&&validDecision(m,players[who])===team.teamId}>
         <span>{team?team.name:"Winner pending"}</span><b>{team?team.projectedRating.toFixed(0)+" Elo":"—"}</b>
       </button>)}
     </div>)}
     {!pending.length&&<p className="v12-subtle">No play-in games in this historical field. Continue to Round of 64.</p>}
   </div>
   {comparison.disagreements.length>0&&<div className="v13-disagreements">
      <h4>HEAD-TO-HEAD DIFFERENCES</h4>
      {comparison.disagreements.slice(0,10).map(d=><p key={d.key}><b>{roundNames[d.round]}</b> · A: {name(d.a)} · B: {name(d.b)}</p>)}
   </div>}
   <p className="v12-subtle" role="status">{notice||"These are hypothetical bracket choices. Match comparison excludes games with different prior-round entrants; no game score, reward, account or future prediction is implied."}</p>
 </section>;
}
