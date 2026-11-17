"use client";
import { useEffect, useState } from "react";
type Model = {
  mode:"active"|"shadow"|"baseline";reason:string;trainedThroughDate:string|null;
  forwardValidation?:{pairedGames:number;minPairedGames:number;promote:boolean;status:string;reason:string};
  trainingGames:number;evaluationGames:number;evaluationDays:number;
  walkForward:{eloBrier:number|null;onlineLogisticBrier:number|null;
               modelBrierGain:number|null;dayBlockGain95:number[]|null}|null;
};
const url=(process.env.NEXT_PUBLIC_BASE_PATH||"")+"/current/2027-online-model.json";
export default function OnlineLearning(){
  const [report,setReport]=useState<Model|null>(null);
  const [error,setError]=useState("");
  useEffect(()=>{
    let alive=true;
    fetch(url).then(r=>{if(!r.ok)throw new Error("No current-season model audit is published.");return r.json()})
      .then((r:Model)=>{if(!alive)return;
        if(!["active","shadow","baseline"].includes(r.mode)||typeof r.trainingGames!=="number")
          throw new Error("Model report failed validation.");
        setReport(r);
      }).catch((e:Error)=>{if(alive)setError(e.message)});
    return()=>{alive=false};
  },[]);
  return <section className="online-learning" aria-label="Chronologically retrained current-season model">
    <div className="online-learning-head">
      <div><span className="feature-kicker">AUTOMATED 2027 MODEL LAB / CHRONOLOGICAL VALIDATION</span>
        <h3>Learn with every game day.</h3>
        <p>Nightly training uses prior completed game days; later dates evaluate it. Today's results never train tonight's model.</p>
      </div>
      <span className={"online-learning-state "+(report?.mode==="active"?"state-active":"")}>
        {!report?"SOURCE CHECK":report.mode==="active"?"VALIDATED / ACTIVE":report.mode==="shadow"?"TRAINED / SHADOW":"ELO FALLBACK"}
      </span>
    </div>
    {report?<><div className="online-learning-metrics">
      <div><small>PREVIOUS-DAY GAMES LEARNED</small><strong>{report.trainingGames.toLocaleString()}</strong><span>Through {report.trainedThroughDate||"not available"}</span></div>
      <div><small>CHRONOLOGICAL TEST GAMES</small><strong>{report.evaluationGames.toLocaleString()}</strong><span>{report.evaluationDays} tested game days</span></div>
      <div><small>HELD-OUT ELO BRIER ↓</small><strong>{report.walkForward?.eloBrier?.toFixed(4)??"—"}</strong><span>Identical evaluated fixtures</span></div>
      <div><small>TRAINED MODEL BRIER ↓</small><strong>{report.walkForward?.onlineLogisticBrier?.toFixed(4)??"—"}</strong><span>Fitted only to preceding days</span></div>
    </div>
    {report.forwardValidation&&<div className="fp-online-gate"><strong>ACTIVATION REQUIRES LIVE FORWARD VALIDATION</strong>
      <span>{report.forwardValidation.pairedGames}/{report.forwardValidation.minPairedGames||40} paired settled pretipoff game forecasts</span>
      <small>{report.forwardValidation.promote?"Forward evidence passed.":"Retrospective improvement alone cannot promote the model."}</small></div>}
    <div className="online-learning-bottom"><p><strong>{report.mode==="active"?"Validated candidate can serve eligible future picks.":"Elo remains the operating forecast."}</strong> {report.reason}. {report.walkForward?.dayBlockGain95?
      "95% date-block Brier gain interval: "+report.walkForward.dayBlockGain95.map(v=>v.toFixed(4)).join(" to ")+".":"Independent day-block interval not yet available."}</p>
      <a href={url} target="_blank" rel="noreferrer">MODEL REPORT ↗</a></div>
    <p className="online-learning-foot">Rolling historical-date evaluation is distinct from genuinely posted before-tipoff forecasts. The public Prediction Ledger audits actual archived picks. This model does not automatically predict committee selections or tournament outcomes.</p>
    </>:<p className="online-learning-unavailable">{error||"Reading the nightly retraining artifact…"}</p>}
  </section>;
}
