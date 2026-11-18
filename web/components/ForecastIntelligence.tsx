"use client";
import {useEffect,useState} from "react";

const base=process.env.NEXT_PUBLIC_BASE_PATH||"";
type Score={games:number;brier:number|null;accuracy?:number|null};
type Efficiency={
  mode:string;season:number;retrievedAtUtc:string;boxStatus:string;
  acceptedPriorDateGames:number;pairedPriorDateBoxGames:number;
  fourFactorSourceGames:number;eligibleWithPriorStats:number;
  evaluatedGames:number;evaluatedDates:number;
  metrics:{elo:Score;efficiencyResidual:Score;brierGainVsElo:number|null;
           dateBlockGain95:number[]|null};featureNames:string[];
  auditPerDate:Array<{date:string;games:number;eloBrier:number;efficiencyBrier:number}>;
};
type Forward={
  mode:string;sourceRetrievedAtUtc:string;pairedSettledGames:number;
  archivedPortfolioGames:number;archivedPortfolioBrierGain:number|null;
  prequentialAdaptive:{evaluatedGames:number;evaluatedDates:number;
    eloBrier:number|null;adaptiveBrier:number|null;brierGain:number|null;
    gainDateBlock95:number[]|null;latestPastWeight:number|null;
    weightChanges:Array<{asOfDate:string;weight:number;trainedFromPriorGames:number}>};
};
type Historical={
  mode:string;evaluatedSeasons:number;heldOutGames:number;
  models:{elo:Score};nestedChampion:Score;
  priorYearStack:Score;priorYearStackGainVsElo:number;
  priorYearStackGain95:number[]|null;
  yearByYear:Array<{season:number;stackChosenBeforeResults:string;
                     stackWeightChosenBeforeResults:number}>;
};
type Accuracy={
  verifiedUniqueFinals:number;immutableFirstPicks:number;
  overall:Score;calibrationDiagnostics:{status:string;games:number;
    expectedCalibrationError:number|null;bins:Array<{
      confidenceRange:string;games:number;meanPredicted:number|null;
      realizedCorrect:number|null;gap:number|null}>};
  byRatingVersion:Array<{version:string;games:number;brier:number|null;
    accuracy:number|null;latestGameDate:string}>;
};
type Current={season:number;mode:string;retrievedAtUtc:string;
  lastGameDate:string;regularSeasonGames:number;eloComparison?:{
    enhancedBrier:number|null;classicBrier:number|null;enhancedBrierGain:number|null}};
type Tab="efficiency"|"weighting"|"history";
const number=(value:number|null|undefined,places=4)=>value==null?"—":value.toFixed(places);
const count=(value:number|null|undefined)=>value==null?"—":value.toLocaleString();
const pct=(value:number|null|undefined)=>value==null?"—":(value*100).toFixed(1)+"%";
const gain=(value:number|null|undefined)=>value==null?"Pending evidence":(value>0?"+":"")+value.toFixed(4);
const checks=(a:number,b:number)=>b>0?Math.max(0,Math.min(100,100*a/b)):0;

function ScoreComparison({baseline,candidate,baselineLabel,candidateLabel}:{
  baseline:number|null|undefined;candidate:number|null|undefined;
  baselineLabel:string;candidateLabel:string;
}){
  const max=Math.max(.04,baseline??0,candidate??0)*1.1;
  return <div className="fi-comparison" aria-label="Matched Brier comparison, lower is better">
    {([{label:baselineLabel,value:baseline,kind:"baseline"},
       {label:candidateLabel,value:candidate,kind:"candidate"}] as const).map(row=>
     <div className="fi-bar-row" key={row.kind}>
       <span>{row.label}</span><div className="fi-bar-track"><i className={row.kind}
        style={{width:row.value==null?"0%":Math.max(1,100*row.value/max).toFixed(2)+"%"}}/></div>
       <strong>{number(row.value)}</strong>
     </div>)}
  </div>;
}

export default function ForecastIntelligence(){
 const [efficiency,setEfficiency]=useState<Efficiency|null>(null);
 const [forward,setForward]=useState<Forward|null>(null);
 const [historical,setHistorical]=useState<Historical|null>(null);
 const [accuracy,setAccuracy]=useState<Accuracy|null>(null);
 const [current,setCurrent]=useState<Current|null>(null);
 const [tab,setTab]=useState<Tab>("efficiency");
 const [status,setStatus]=useState<"loading"|"ready"|"unavailable">("loading");

 useEffect(()=>{
   let live=true;
   const get=async<T,>(path:string):Promise<T|null>=>{
     try{const r=await fetch(base+path,{cache:"no-store"});return r.ok?await r.json() as T:null;}
     catch{return null;}
   };
   Promise.all([
     get<Efficiency>("/current/efficiency-research.json"),
     get<Forward>("/current/forward-ensemble.json"),
     get<Historical>("/research/model-championship.json"),
     get<Accuracy>("/current/accuracy-research.json"),
     get<Current>("/current/2027.json")
   ]).then(([e,f,h,a,c])=>{
     if(!live)return;
     const valid=Boolean(c?.mode==="current"&&c.season===2027);
     setCurrent(valid?c:null);
     setEfficiency(valid&&e?.mode==="research-only"&&e.season===2027&&
       e.retrievedAtUtc===c?.retrievedAtUtc?e:null);
     setForward(valid&&f?.mode==="shadow"&&
       f.sourceRetrievedAtUtc===c?.retrievedAtUtc?f:null);
     setHistorical(h?.mode==="historical-only"?h:null);
     setAccuracy(a);setStatus(valid?"ready":"unavailable");
   }).catch(()=>{if(live)setStatus("unavailable")});
   return()=>{live=false};
 },[]);

 const adaptive=forward?.prequentialAdaptive;
 const calibration=accuracy?.calibrationDiagnostics;
 const latestVersion=accuracy?.byRatingVersion?.find(v=>v.version==="source-aware-game-elo-v1");
 const track=[
   {label:"Historical source-tested games",metric:count(historical?.heldOutGames),
    detail:(historical?.evaluatedSeasons??0)+" unseen tournament years",ready:!!historical},
   {label:"Paired game boxes",metric:count(efficiency?.pairedPriorDateBoxGames),
    detail:efficiency?.acceptedPriorDateGames?
      pct(efficiency.pairedPriorDateBoxGames/efficiency.acceptedPriorDateGames)+" of prior-date scores":"Coverage not confirmed",ready:!!efficiency?.pairedPriorDateBoxGames},
   {label:"Adaptive ensemble tests",metric:count(adaptive?.evaluatedGames),
    detail:"Verified original components; prequential research",ready:!!adaptive?.evaluatedGames},
   {label:"Genuine settled first picks",metric:count(accuracy?.verifiedUniqueFinals),
    detail:"Independent ESPN + matching NCAA finals",ready:!!accuracy?.verifiedUniqueFinals}
 ];
 const notes={
   efficiency:"Opponent-adjusted strengths, prior possession efficiency, recent efficiency, schedule strength, rest intervals and verified Four Factors when sourced. No same-day feature leakage.",
   weighting:"Weights are chosen from only earlier, independently settled forecasts. Current-day results never choose their own weight. These research probabilities were not the originally published adaptive picks.",
   history:"Tournament challengers train only on earlier seasons. A shrinkage stack blends one prior-year-selected model with Elo, and is tested on a later unseen season. This does not automatically change 2027 predictions."
 };
 return <section className="fi" aria-label="Forecast intelligence and training evidence">
   <div className="fi-hero">
     <div className="fi-hero-copy">
       <span className="fi-kicker"><i aria-hidden="true"/> LIVE RESEARCH SYSTEM · 2026–27</span>
       <h2>BETTER SIGNALS.<br/><em>BETTER QUESTIONS.</em></h2>
       <p>Scores move Elo. Verified basketball stats enrich the research. Every challenger must earn its place on games it has not already seen.</p>
       <div className="fi-meta">
         <span><b>01</b> LEARN</span><span><b>02</b> TEST</span>
         <span><b>03</b> VERIFY</span><span><b>04</b> IMPROVE</span>
       </div>
     </div>
     <div className="fi-orbit" aria-label="Verified outcomes measured against available first picks">
       <div className="fi-orbit-ring"><div className="fi-orbit-center">
         <span>VERIFIED FIRST PICKS</span>
         <strong>{accuracy?count(accuracy.verifiedUniqueFinals):"—"}</strong>
         <small>{accuracy?.overall.accuracy==null?"Accuracy pending":pct(accuracy.overall.accuracy)+" winners correct"}</small>
       </div></div>
       <p>{current?.lastGameDate?"SOURCE RESULTS THROUGH "+current.lastGameDate:"AWAITING SOURCE STATE"} · PERIODIC REFRESH</p>
     </div>
   </div>

   {status==="loading"?<p className="fi-placeholder" role="status">Checking source-aligned model artifacts and prospective scorecards…</p>:
    status==="unavailable"?<p className="fi-placeholder" role="alert">Current-season source snapshot is unavailable or does not match 2027. We will not show invented performance.</p>:<>
     <div className="fi-signal-grid" aria-label="Evidence coverage">
       {track.map((card,i)=><div className="fi-signal" key={card.label}>
         <div className="fi-signal-top"><span>0{i+1}</span><span>{card.ready?"DATA AVAILABLE":"COLLECTING"}</span></div>
         <strong>{card.metric}</strong><h3>{card.label}</h3><p>{card.detail}</p>
       </div>)}
     </div>
     <div className="fi-workbench">
       <div className="fi-workbench-head">
         <div><span className="fi-eyebrow">MODEL ENGINEERING / EVIDENCE BEFORE ADOPTION</span>
           <h3>The forecast <em>workbench.</em></h3></div>
         <span className="fi-research-tag">NO AUTOMATIC PROMOTION</span>
       </div>
       <div className="fi-switches" role="group" aria-label="Choose model experiment">
         {([["efficiency","Efficiency signals"],["weighting","Adaptive ensemble"],["history","Historical stack"]] as const).map(([key,label])=>
          <button type="button" key={key} onClick={()=>setTab(key)} aria-pressed={tab===key}
           className={tab===key?"active":""}>{label}</button>)}
       </div>
       <div className="fi-workbench-body" aria-live="polite">
         <div className="fi-explainer">
           <span className="fi-eyebrow">{tab==="efficiency"?"01 / VERIFIED TEAM BOX DATA":tab==="weighting"?"02 / BEFORE-EACH-DATE WEIGHTING":"03 / PREVIOUS-SEASON LEARNING"}</span>
           <h4>{tab==="efficiency"?"Does efficiency beat score-only Elo?":tab==="weighting"?"Can the ensemble adapt without hindsight?":"Does a historical stack generalize?"}</h4>
           <p>{notes[tab]}</p>
           <div className="fi-progress-box">
             {tab==="efficiency"?<>
               <div><span>BOX-SCORE COVERAGE</span><b>{efficiency?.pairedPriorDateBoxGames??0}/{efficiency?.acceptedPriorDateGames??0} games</b></div>
               <div className="fi-progress"><i style={{width:checks(efficiency?.pairedPriorDateBoxGames??0,efficiency?.acceptedPriorDateGames??0)+"%"}}/></div>
               <small>{efficiency?.fourFactorSourceGames??0} games have complete optional Four Factors source fields. Missing is not zero.</small>
             </>:tab==="weighting"?<>
               <div><span>DATE-ORDERED EVALUATION</span><b>{adaptive?.evaluatedDates??0} dates</b></div>
               <div className="fi-progress"><i style={{width:checks(adaptive?.evaluatedGames??0,100)+"%"}}/></div>
               <small>Latest fitted research weight: {adaptive?.latestPastWeight==null?"insufficient data":pct(adaptive.latestPastWeight)}. This is not an active production allocation.</small>
             </>:<>
               <div><span>HISTORICAL TOURNAMENT YEARS</span><b>{historical?.evaluatedSeasons??0} tested</b></div>
               <div className="fi-progress"><i style={{width:checks(historical?.evaluatedSeasons??0,40)+"%"}}/></div>
               <small>Source-linked pre-tournament rating/record history; missing historical box data is not manufactured.</small>
             </>}
           </div>
         </div>
         <div className="fi-score-panel">
           <span className="fi-eyebrow">PAIRED BRIER SCORE · LOWER IS BETTER</span>
           {tab==="efficiency"?<>
             <ScoreComparison baseline={efficiency?.metrics.elo.brier} candidate={efficiency?.metrics.efficiencyResidual.brier}
               baselineLabel="Matched Elo" candidateLabel="Efficiency learner"/>
             <div className="fi-delta"><span>MEASURED BRIER GAIN</span><strong>{gain(efficiency?.metrics.brierGainVsElo)}</strong></div>
             <small>{efficiency?.evaluatedGames??0} identical prior-date test games. Confidence interval: {efficiency?.metrics.dateBlockGain95?.map(x=>number(x,5)).join(" to ")??"not yet available"}.</small>
           </>:tab==="weighting"?<>
             <ScoreComparison baseline={adaptive?.eloBrier} candidate={adaptive?.adaptiveBrier}
               baselineLabel="Matched Elo" candidateLabel="Adaptive research mix"/>
             <div className="fi-delta"><span>MEASURED BRIER GAIN</span><strong>{gain(adaptive?.brierGain)}</strong></div>
             <small>{adaptive?.evaluatedGames??0} date-frozen reconstructed predictions; original published ensemble results are scored separately.</small>
           </>:<>
             <ScoreComparison baseline={historical?.models.elo.brier} candidate={historical?.priorYearStack.brier}
               baselineLabel="Prior-year Elo" candidateLabel="Historical stack"/>
             <div className="fi-delta"><span>MEASURED BRIER GAIN</span><strong>{gain(historical?.priorYearStackGainVsElo)}</strong></div>
             <small>{count(historical?.heldOutGames)} unseen historical tournament games. Season-block interval: {historical?.priorYearStackGain95?.map(x=>number(x,5)).join(" to ")??"not enough years"}.</small>
           </>}
           <p className="fi-proof-warning">A negative gain means the new approach performed worse. No gain is guaranteed. Earlier-date replay is not actual archived pregame success.</p>
         </div>
       </div>
     </div>
     <div className="fi-monitor">
       <div className="fi-monitor-heading"><span className="fi-eyebrow">PROSPECTIVE MODEL RELIABILITY / ORIGINAL FIRST PICKS</span>
         <h3>Confidence needs <em>receipts.</em></h3>
         <p>How often did a predicted favorite actually win at each confidence level? These bins use independently verified first-published forecasts, not historical simulations.</p>
       </div>
       <div className="fi-monitor-body">
         <div className="fi-calibration" aria-label="Prediction reliability by confidence bin">
           {(calibration?.bins||[]).map(bin=><div className="fi-calibration-row" key={bin.confidenceRange}>
             <span>{bin.confidenceRange}</span>
             <div className="fi-calibration-tracks">
               <i className="expectation" style={{width:bin.meanPredicted==null?"0%":100*bin.meanPredicted+"%"}}/>
               <b className="reality" style={{width:bin.realizedCorrect==null?"0%":100*bin.realizedCorrect+"%"}}/>
             </div>
             <strong>{bin.games?pct(bin.realizedCorrect):"—"}</strong>
             <small>{bin.games} games</small>
           </div>)}
           {!calibration?.bins?.length&&<p>Reliability bins will appear when source-confirmed first picks are available.</p>}
           <div className="fi-legend"><span><i/> Predicted confidence</span><span><b/> Realized win rate</span></div>
         </div>
         <div className="fi-monitor-stats">
           <div><small>CALIBRATION ERROR · LOWER IS BETTER</small><strong>{number(calibration?.expectedCalibrationError)}</strong>
             <span>{calibration?.status==="observing"?"DESCRIPTIVE MONITORING":"MORE VERIFIED PICKS REQUIRED"}</span></div>
           <div><small>UPDATED ELO / VERIFIED FIRST PICKS</small><strong>{count(latestVersion?.games)}</strong>
             <span>{latestVersion?.accuracy==null?"Awaiting updated-model outcomes":pct(latestVersion.accuracy)+" correct · "+number(latestVersion.brier)+" Brier"}</span></div>
           <p>Model versions are separated instead of silently combining old and new ratings. Calibration is descriptive, not a promise about the next game.</p>
         </div>
       </div>
     </div>
   </>}
 </section>;
}
