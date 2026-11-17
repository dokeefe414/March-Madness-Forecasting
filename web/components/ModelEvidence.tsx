"use client";
import {useEffect,useState} from "react";
const base=process.env.NEXT_PUBLIC_BASE_PATH||"";
type Paired={pairedGames:number;pairedDates:number;baselineEloBrier:number|null;candidateBrier:number|null;candidateAccuracy:number|null;baselineEloAccuracy:number|null;candidateBrierGain:number|null;dateBlockGain95:number[]|null};
type Ledger={uniqueGames:{pairedModelComparisons?:Record<string,Paired>;settledUniqueGames:number;calibration?:Array<{bin:string;count:number;predictedConfidence:number|null;realizedAccuracy:number|null}>}};
const num=(n:number|null|undefined)=>n==null?"—":n.toFixed(4);
export default function ModelEvidence(){
 const [ledger,setLedger]=useState<Ledger|null>(null);
 useEffect(()=>{let alive=true;fetch(base+"/forecasts/index.json").then(r=>r.ok?r.json():null).then(d=>{if(alive)setLedger(d)}).catch(()=>{});return()=>{alive=false}},[]);
 const pairs=ledger?.uniqueGames?.pairedModelComparisons||{};
 const rows=Object.entries(pairs).sort((a,b)=>(b[1].pairedGames||0)-(a[1].pairedGames||0));
 return <section className="v12-card" aria-label="Independent head to head model research evidence">
  <div className="v12-head"><span className="section-kicker">FAIR COMPARISONS / SAME BEFORE-TIPOFF GAMES</span><h3>Did a challenger <em>actually win?</em></h3>
  <p>Only first archived, independently settled source games count toward forward evidence. Each row compares the challenger to frozen Elo probabilities on identical events, and uncertainty is withheld for small samples.</p></div>
  <div className="v12-model-table-wrap"><table className="v12-model-table"><thead><tr><th scope="col">CHALLENGER</th><th scope="col">PAIRED GAMES</th><th scope="col">ELO BRIER ↓</th><th scope="col">CHALLENGER BRIER ↓</th><th scope="col">BRIER GAIN</th><th scope="col">DATE-BLOCK 95% INTERVAL</th></tr></thead><tbody>
   {rows.map(([name,x])=><tr key={name}><th scope="row">{name}</th><td>{x.pairedGames}</td><td>{num(x.baselineEloBrier)}</td><td>{num(x.candidateBrier)}</td><td>{num(x.candidateBrierGain)}</td><td>{x.dateBlockGain95?.map(num).join(" to ")||"Insufficient sample"}</td></tr>)}
  </tbody></table></div>
  {!rows.length&&<p className="v12-subtle">No independently settled, same-game paired samples exist. This is not evidence that any model beats Elo.</p>}
  <p className="v12-subtle">Positive Brier gain favors the challenger. Date-block intervals resample entire game dates, not individual contests. Neither retrospective research scores nor this table automatically promote a model.</p>
  <div className="v12-calibration">{ledger?.uniqueGames.calibration?.map(b=><div key={b.bin}><small>{b.bin} CONFIDENCE · {b.count} GAMES</small><div className="v12-calibration-track"><span style={{width:(b.predictedConfidence??0)*100+"%"}}/><i style={{width:(b.realizedAccuracy??0)*100+"%"}}/></div></div>)}</div>
 </section>;
}
