"use client";
import {useEffect,useState} from "react";
const base=process.env.NEXT_PUBLIC_BASE_PATH||"";
type Evidence={
 schemaVersion:number;mode:"shadow";pairedSettledGames:number;pairedSettledDates:number;
 trainingGames:number;trainingDates:number;untouchedHoldoutGames:number;untouchedHoldoutDates:number;
 weight:number;eloHoldoutBrier:number|null;ensembleHoldoutBrier:number|null;holdoutBrierGain:number|null;
 dateBlockBrierGain95:number[]|null;scientificReviewEligible:boolean;promoteAutomatically:false;
 sourceRetrievedAtUtc:string;policy:string;
};
const num=(n:number|null|undefined)=>n==null?"—":n.toFixed(4);
export default function EnsembleEvidence(){
 const [evidence,setEvidence]=useState<Evidence|null>(null);
 const [notice,setNotice]=useState("");
 useEffect(()=>{let active=true;
  fetch(base+"/current/forward-ensemble.json",{cache:"no-store"}).then(r=>{
   if(!r.ok)throw Error("Prospective ensemble evidence is not published yet.");
   return r.json();
  }).then((data:Evidence)=>{
   if(!active)return;
   if(data.schemaVersion!==1||data.mode!=="shadow"||data.promoteAutomatically!==false)
    throw Error("Unexpected ensemble release policy.");
   setEvidence(data);
  }).catch((error:Error)=>{if(active)setNotice(error.message)});
  return()=>{active=false};
 },[]);
 return <section className="v16-evidence" aria-label="Prospective ensemble holdout and promotion evidence">
  <div className="v13-feature-head">
    <span className="section-kicker">FORWARD-FIRST / NO LEAKAGE / NO AUTOMATIC PROMOTION</span>
    <h3>DOES THE <em>ENSEMBLE WIN?</em></h3>
    <p>Combines only previously frozen shadow signals with Elo. Weights may be learned from earlier independently settled first picks, and evaluated on later untouched date blocks. The final decision still requires prospective evidence and human review.</p>
  </div>
  {!evidence?<p className="v12-subtle" role="status">{notice||"Loading source-verified ensemble comparison…"}</p>:
   <>
    <div className="v16-ensemble-metrics">
      <div><small>VERIFIED PAIRED PICKS</small><strong>{evidence.pairedSettledGames}</strong></div>
      <div><small>WEIGHT ON RESEARCH</small><strong>{(evidence.weight*100).toFixed(0)}%</strong></div>
      <div><small>HOLDOUT ELO BRIER ↓</small><strong>{num(evidence.eloHoldoutBrier)}</strong></div>
      <div><small>HOLDOUT ENSEMBLE BRIER ↓</small><strong>{num(evidence.ensembleHoldoutBrier)}</strong></div>
    </div>
    <div className="v16-comparison">
      <p><strong>Chronological train:</strong> {evidence.trainingGames} games / {evidence.trainingDates} dates</p>
      <p><strong>Later untouched holdout:</strong> {evidence.untouchedHoldoutGames} games / {evidence.untouchedHoldoutDates} dates</p>
      <p><strong>Holdout Brier gain vs Elo:</strong> {evidence.holdoutBrierGain==null?"Not measured":(evidence.holdoutBrierGain>=0?"+":"")+num(evidence.holdoutBrierGain)}</p>
      <p><strong>95% date-block interval:</strong> {evidence.dateBlockBrierGain95?.map(n=>num(n)).join(" to ")||"Insufficient independent dates"}</p>
    </div>
    <p className="v16-evidence-status"><strong>{evidence.scientificReviewEligible?"REVIEW ELIGIBLE — NOT PROMOTED":"SHADOW RESEARCH — ELO REMAINS ACTIVE"}</strong>
     {" "}The site does not automatically switch models based on a backtest or a small set of results.</p>
    <p className="v12-subtle">Confidence is withheld when source-verified first-pick observations are unavailable. A fixed exploratory 25% research weight does not imply statistical superiority. This portfolio only appears when at least two supported pregame research signals are present.</p>
   </>}
 </section>;
}
