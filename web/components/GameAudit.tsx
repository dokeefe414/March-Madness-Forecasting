"use client";
import {useMemo} from "react";

type Pick={eventId:string;homeWinProbability:number;model:string;
  baselineHomeWinProbability?:number|null;modelId?:string|null};
export type ArchivedSnapshot={id:string;generatedAtUtc:string;count:number;predictions:Pick[]};
export type ArchivedSettlement={eventId:string;predictionKey:string;home:string;away:string;
  actualResultDate:string;homeScore:number;awayScore:number;predictedHome:number;
  observedHome:number;brier:number;winnerCorrect:number;forecastAtUtc:string;
  scheduledStartUtc:string;espnFinalVerified?:boolean;ncaaContestId?:string};

type TimedPick={id:string;captured:string;probability:number;model:string};
const pct=(v:number)=>(100*v).toFixed(1)+"%";
const when=(iso:string)=>new Date(iso).toLocaleString("en-US",{
  timeZone:"America/New_York",month:"short",day:"numeric",hour:"numeric",minute:"2-digit"})+" ET";
function ProbabilityTimeline({data}:{data:TimedPick[]}){
  if(data.length<2)return <p className="ga-empty">One or no genuine archived pregame captures so far. A probability time-series requires multiple real, frozen forecasts of this same game.</p>;
  const values=data.map(d=>d.probability);
  const min=Math.max(0,Math.min(...values)-.08),max=Math.min(1,Math.max(...values)+.08);
  const scale=Math.max(.02,max-min);
  const nodes=data.map((d,i)=>({x:28+(i/Math.max(1,data.length-1))*680,
      y:155-(d.probability-min)/scale*110}));
  const d=nodes.map((p,i)=>(i?"L":"M")+p.x.toFixed(1)+" "+p.y.toFixed(1)).join(" ");
  return <div className="ga-probability"><svg role="img" viewBox="0 0 740 190"
    aria-label={"Actual archived pregame probability timeline from "+pct(values[0])+" to "+pct(values[values.length-1])}>
    <line x1="28" x2="711" y1="155" y2="155" stroke="#416c66"/>
    <line x1="28" x2="711" y1="45" y2="45" stroke="#416c66" strokeDasharray="5 7"/>
    <path d={d} stroke="#b7ffd2" strokeWidth="3.5" strokeLinejoin="round" strokeLinecap="round" fill="none"/>
    {nodes.map((p,i)=><circle key={data[i].id} cx={p.x} cy={p.y} r="4" fill="#deffdc"><title>{when(data[i].captured)+" · home "+pct(data[i].probability)+" · "+data[i].model}</title></circle>)}
    <text x="30" y="22" fontSize="12" fill="#bde2d0">{pct(max)}</text>
    <text x="30" y="175" fontSize="12" fill="#bde2d0">{pct(min)}</text>
  </svg>
  <div className="ga-capture-list">{data.slice(-5).map(p=><div key={p.id}>
    <span>{when(p.captured)}</span><strong>{pct(p.probability)} home</strong><small>{p.model}</small></div>)}</div></div>;
}

export default function GameAudit({eventId,snapshots,settlements,closed=false}:{
  eventId:string;snapshots:ArchivedSnapshot[];settlements:ArchivedSettlement[];
  closed?:boolean
}){
 const captures=useMemo(()=>{
   const all:TimedPick[]=[];
   for(const snap of snapshots||[]){
     for(const p of snap.predictions||[]){
       if(p.eventId===eventId){
         all.push({id:snap.id,captured:snap.generatedAtUtc,
                   probability:p.homeWinProbability,model:p.model});
       }
     }
   }
   return all.sort((a,b)=>a.captured.localeCompare(b.captured)||a.id.localeCompare(b.id));
 },[snapshots,eventId]);
 const results=(settlements||[]).filter(s=>s.eventId===eventId);
 const first=captures[0];
 const actual=first?results.find(s=>s.predictionKey===first.id+":"+eventId):null;
 const latest=results[0]||null;
 const receipt=actual||latest;
 const miss=receipt?.winnerCorrect===0;
 return <section className="ga" aria-label="Before-tipoff prediction receipts and postgame result">
   <div className="ga-heading"><span className="section-kicker">{closed?"FINISHED GAME / GRADED RESULTS":"ARCHIVED PREGAME EVIDENCE"}</span>
     <h3>{closed?"The final. The original call.":"How the probability changed."}</h3>
     <p>Only real Git-archived predictions appear below. Each capture was originally recorded before the source-listed tipoff. Later outcomes never rewrite the earlier win percentage.</p>
   </div>
   {receipt&&<div className="ga-postgame">
     <div><small>{receipt.espnFinalVerified?"INDEPENDENTLY VERIFIED FINAL":"ARCHIVED SOURCE RESULT — FINAL NOT INDEPENDENTLY CONFIRMED"}</small><h4>{receipt.away} {receipt.awayScore} · {receipt.home} {receipt.homeScore}</h4>
       <p>{receipt.actualResultDate} · ESPN final-status confirmation: {receipt.espnFinalVerified?"YES":"not independently reported in this record"}</p></div>
     <div><small>ARCHIVED FORECAST OF HOME WIN</small><strong>{pct(receipt.predictedHome)}</strong><span>{when(receipt.forecastAtUtc)}</span></div>
     <div><small>WINNER SELECTION</small><strong>{receipt.winnerCorrect===1?"CORRECT":receipt.winnerCorrect===0?"MISSED":"50/50"}</strong><span>Brier: {receipt.brier.toFixed(4)}</span></div>
     {miss?<p className="ga-loss">This prediction missed. The prior probability stays frozen. Future training can incorporate the confirmed outcome after the game-date embargo; one upset alone does not justify inventing a cause or reversing the earlier pick.</p>:
       <p className="ga-win">The original forecast has been scored without hindsight. A correct pick is a sample, not a guarantee that the model is reliably calibrated.</p>}
   </div>}
   <div className="ga-history">
     <span className="section-kicker">PUBLIC PROBABILITY HISTORY</span>
     <h4>{captures.length} originally published capture{captures.length===1?"":"s"}</h4>
     <ProbabilityTimeline data={captures}/>
     {!captures.length&&<p className="ga-empty">No source-verified public-before-tipoff forecast is archived for this event yet. The website's current odds are an indicative snapshot, not retroactive proof of an earlier public pick.</p>}
   </div>
   {receipt&&first&&!actual?<p className="ga-disclaimer">A more recent archived prediction settled, but the earliest visible capture has no verified settlement. This displayed receipt is not counted as an extra first-pick outcome.</p>:null}
 </section>;
}
