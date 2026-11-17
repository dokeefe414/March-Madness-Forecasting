"use client";
import {useEffect,useMemo,useState} from "react";
const base=process.env.NEXT_PUBLIC_BASE_PATH||"";
type Daily={date:string;games:number;eloBrier:number|null;bayesianBrier:number|null;gradientBoostedBrier:number|null};
type Metrics={games:number;accuracy:number|null;brier:number|null;logLoss:number|null};
type Research={mode:"research-only";retrievedAtUtc:string;evaluatedGames:number;methods:{elo:Metrics;bayesianGaussian:Metrics;gradientBoostedTrees:Metrics};perDate:Daily[];policy:string};
type Timeline={date:string;games:number;brier:number|null;accuracy:number|null};
type Bin={bin:string;count:number;predictedConfidence:number|null;realizedAccuracy:number|null};
type Ledger={uniqueGames?:{settledUniqueGames:number;trajectory:Timeline[];calibration:Bin[];rolling25?:Timeline[]}};
type Team={teamId:string;name:string;history:number[];rating:number};
type Ratings={mode:string;teams:Team[];retrievedAtUtc:string};
function fmt(v:number|null|undefined,d=3){return v==null?"—":v.toFixed(d)}
function Series({rows,keys}:{rows:Array<Record<string,number|string|null>>;keys:{key:string;name:string;color:string}[]}){
 const meaningful=rows.filter(r=>keys.some(k=>typeof r[k.key]==="number"));
 if(meaningful.length<2)return <p className="v12-subtle">Not enough confirmed chronological observations to draw a trend.</p>;
 const vals=meaningful.flatMap(r=>keys.map(k=>r[k.key]).filter((v):v is number=>typeof v==="number"));
 const low=Math.max(0,Math.min(...vals)-.025),high=Math.max(...vals)+.025,range=Math.max(.001,high-low);
 return <div className="v13-plot"><svg viewBox="0 0 600 185" preserveAspectRatio="none" role="img" aria-label={keys.map(k=>k.name).join(" versus ")+" chronological observed Brier trend"}>
   {[0,1,2,3,4].map(i=><line key={i} x1="5" x2="595" y1={15+i*35} y2={15+i*35} stroke="#416459" strokeDasharray="3 7"/>)}
   {keys.map(k=>{
      const points=meaningful.map((r,i)=>{
        const v=r[k.key];return typeof v==="number"?[(8+i*584/Math.max(1,meaningful.length-1)),(160-(v-low)/range*145)]:null;
      });
      const path=points.map((p,i)=>p?(points.slice(0,i).reverse().some(x=>x)? "L":"M")+p[0].toFixed(1)+" "+p[1].toFixed(1):"").filter(Boolean).join(" ");
      return <path key={k.key} d={path} stroke={k.color} strokeWidth="3" strokeLinecap="round" fill="none"/>;
   })}
 </svg><div className="v13-plot-legend">{keys.map(k=><span key={k.key}><i style={{background:k.color}}/>{k.name}</span>)}</div>
 <p className="v12-subtle">Chronological source dates · lower Brier is better · vertical scale adapts to observed values.</p></div>;
}
export default function ResearchVisualization(){
 const [advanced,setAdvanced]=useState<Research|null>(null);
 const [ledger,setLedger]=useState<Ledger|null>(null);
 const [ratings,setRatings]=useState<Ratings|null>(null);
 const [teamId,setTeamId]=useState("");
 useEffect(()=>{let alive=true;const get=(path:string)=>fetch(base+path).then(r=>r.ok?r.json():null).catch(()=>null);
   Promise.all([get("/current/advanced-models.json"),get("/forecasts/index.json"),get("/current/2027.json")]).then(([a,l,r])=>{
     if(!alive)return;setAdvanced(a?.mode==="research-only"?a:null);setLedger(l);setRatings(r);
     setTeamId(r?.teams?.[0]?.teamId||"");
   });return()=>{alive=false};
 },[]);
 const top=useMemo(()=>[...(ratings?.teams||[])].sort((a,b)=>b.rating-a.rating).slice(0,30),[ratings]);
 const chosen=top.find(t=>t.teamId===teamId)||top[0];
 const trend=advanced?.perDate||[];
 const forward=ledger?.uniqueGames;
 const trajectory=forward?.rolling25||[];
 const calibration=forward?.calibration||[];
 const level=chosen?.history?.length||0;
 const minRating=Math.min(...(chosen?.history?.length?chosen.history:[1500]))-10,maxRating=Math.max(...(chosen?.history?.length?chosen.history:[1500]))+10;
 const ratingPath=(chosen?.history||[]).map((value,i)=>`${i?"L":"M"}${10+i*580/Math.max(1,level-1)} ${155-(value-minRating)/Math.max(1,maxRating-minRating)*130}`).join(" ");
 return <section className="v13-research" aria-label="Interactive prediction research visualizations">
   <div className="v13-feature-head"><span className="section-kicker">MODEL SCIENCE / TWO SEPARATE EVIDENCE TYPES</span>
     <h3>Explore the <em>evidence.</em></h3>
     <p>Compare newly fitted date-frozen research experiments with independently archived public predictions. The two samples are intentionally separate and cannot be treated as the same forecast evaluation.</p></div>
   <div className="v13-research-grid">
    <article className="v13-viz">
      <div className="v13-viz-head"><span>01 / CAUSAL HISTORICAL REPLAY</span><strong>{advanced?.evaluatedGames??"—"} scored games</strong></div>
      <h4>Three research forecasters</h4>
      <div className="v13-research-metrics">
        {([["Elo","elo"],["Gaussian Bayesian","bayesianGaussian"],["Gradient-boosted CART","gradientBoostedTrees"]] as const).map(([label,key])=><div key={key}>
         <small>{label}</small><strong>{fmt(advanced?.methods[key].brier,4)}</strong><span>Brier ↓ · {advanced?.methods[key].games??0} games</span>
        </div>)}
      </div>
      <Series rows={trend} keys={[
       {key:"eloBrier",name:"Elo",color:"#9bcafe"},
       {key:"bayesianBrier",name:"Gaussian Bayesian",color:"#c5ffd4"},
       {key:"gradientBoostedBrier",name:"Boosted CART",color:"#ffd68e"}
      ]}/>
      <p className="v12-subtle">Fixed hyperparameters. Depth-two fitted trees retrain every seven previous game dates, never on the day being scored. This is NOT a public pregame track record.</p>
    </article>
    <article className="v13-viz">
      <div className="v13-viz-head"><span>02 / REAL FROZEN PICKS</span><strong>{forward?.settledUniqueGames??0} unique finals</strong></div>
      <h4>25-game forward error</h4>
      <Series rows={trajectory} keys={[{key:"brier",name:"Rolling 25-game Brier",color:"#acffd4"}]}/>
      <p className="v12-subtle">{forward?.settledUniqueGames? "Only earliest archived pregame predictions and independently verified finals are included. Rolling windows overlap and are descriptive.":"No truly settled first picks have been recorded yet. This chart cannot claim accuracy from research replay."}</p>
    </article>
    <article className="v13-viz">
      <div className="v13-viz-head"><span>03 / REAL PROBABILITY CALIBRATION</span><strong>{forward?.settledUniqueGames??0} unique finals</strong></div>
      <h4>Confidence vs actual wins</h4>
      <div className="v13-calibration">
        {calibration.map(bin=><div className="v13-bin" key={bin.bin}>
          <span>{bin.bin}</span>
          <div className="v13-bin-tracks"><i style={{width:((bin.predictedConfidence??0)*100)+"%"}}/><b style={{width:((bin.realizedAccuracy??0)*100)+"%"}}/></div>
          <small>{bin.count} games · predicted {bin.predictedConfidence==null?"—":(bin.predictedConfidence*100).toFixed(0)+"%"} / actual {bin.realizedAccuracy==null?"—":(bin.realizedAccuracy*100).toFixed(0)+"%"}</small>
        </div>)}
        {!calibration.length&&<p className="v12-subtle">No qualifying archived predictions have settled. Calibration is unavailable.</p>}
      </div>
      <p className="v12-subtle">Blue: original favorite confidence; mint: settled favorite win rate. Empty bins are not treated as 0% wins.</p>
    </article>
    <article className="v13-viz">
      <div className="v13-viz-head"><span>04 / DATED STRENGTH EVOLUTION</span><strong>Source-linked teams only</strong></div>
      <h4>Team Elo trajectory</h4>
      <label className="v13-team-pick">COMPARE A TEAM<select aria-label="Choose team strength trend" value={chosen?.teamId||""} onChange={e=>setTeamId(e.target.value)}>
        {top.map(t=><option key={t.teamId} value={t.teamId}>{t.name}</option>)}
      </select></label>
      {level>1?<svg className="v13-rating-plot" viewBox="0 0 600 170" preserveAspectRatio="none" role="img" aria-label={chosen?.name+" recorded Elo rating trajectory"}>
        <line x1="10" x2="595" y1="155" y2="155" stroke="#4e8171"/>
        <path d={ratingPath} stroke="#b8ffd8" strokeWidth="3" strokeLinejoin="round" fill="none"/>
      </svg>:<p className="v12-subtle">Not enough sourced games for this rating curve.</p>}
      <p className="v12-subtle">Most recent source Elo {chosen?.rating?.toFixed(1)??"—"}. The sequence describes existing game evidence, not actual betting odds or predicted injuries.</p>
    </article>
   </div>
 </section>;
}
