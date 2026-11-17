"use client";
import {useMemo,useState} from "react";
import {buildFieldFromSlots,simulateFullBracket,type BracketField,type BracketResult} from "../lib/fullBracket";
const pct=(p:number)=>(p*100).toFixed(2)+"%";
/** Counterfactual: change one team's pre-tournament Elo and hold every other input fixed.
 * Both simulations use identical random seed and run count (common random numbers).
 * This is a sensitivity experiment, never a claimed official bracket forecast.
 */
export default function BracketScenario({field,runs,seed,baseline}:{field:BracketField;runs:number;seed:number;baseline:BracketResult[]}) {
  const [teamId,setTeamId]=useState(field.entrants[0]?.teamId??"");
  const [shift,setShift]=useState(50);
  const [scenario,setScenario]=useState<{teamId:string;shift:number;rows:BracketResult[];runs:number;seed:number}|null>(null);
  const ranking=useMemo(()=>[...field.entrants].sort((a,b)=>b.projectedRating-a.projectedRating),[field]);
  function evaluate(){
    const adjusted=field.regions.map(region=>({
      code:region.code,
      slots:region.slots.map(slot=>({
        region:slot.region,seed:slot.seed,
        teams:slot.teams.map(t=>t.teamId===teamId?{...t,projectedRating:t.projectedRating+shift}:t)
      }))
    }));
    const candidate=buildFieldFromSlots(field.season,adjusted);
    setScenario({teamId,shift,rows:simulateFullBracket(candidate,runs,seed),runs,seed});
  }
  const active=scenario&&scenario.teamId===teamId&&scenario.shift===shift&&scenario.runs===runs&&scenario.seed===seed?scenario:null;
  const compared=active?ranking.map(t=>{
    const a=baseline.find(r=>r.teamId===t.teamId);
    const b=active.rows.find(r=>r.teamId===t.teamId);
    return {team:t.name,teamId:t.teamId,base:a?.champion??0,changed:b?.champion??0,delta:(b?.champion??0)-(a?.champion??0)};
  }).sort((a,b)=>Math.abs(b.delta)-Math.abs(a.delta)).slice(0,8):[];
  return <section className="scenario-studio" aria-label="Tournament sensitivity scenario">
    <div className="scenario-intro"><span className="feature-kicker">TOURNAMENT INTELLIGENCE / CONTROLLED EXPERIMENT</span>
      <h3>What changes the <em>champion?</em></h3>
      <p>Raise or lower one team's pre-tournament Elo. Compare championship probabilities against the original field using the same seeded Monte Carlo draws. Every other team's input remains unchanged.</p></div>
    <div className="scenario-controls">
      <label>TEAM<select aria-label="Sensitivity experiment team" value={teamId} onChange={e=>{setTeamId(e.target.value);setScenario(null)}}>
        {ranking.map(t=><option key={t.teamId} value={t.teamId}>{t.name} ({t.region} {t.seed})</option>)}</select></label>
      <label>ELO ADJUSTMENT<select value={shift} aria-label="Elo rating adjustment" onChange={e=>{setShift(Number(e.target.value));setScenario(null)}}>
        {[-150,-100,-50,0,50,100,150].map(n=><option key={n} value={n}>{n>0?"+":""}{n} Elo</option>)}</select></label>
      <button type="button" className="button-primary" onClick={evaluate}>COMPARE SCENARIOS</button>
    </div>
    {active?<div className="scenario-comparison" aria-live="polite"><div className="scenario-legend">
      <strong>Largest championship probability changes</strong><span>{runs.toLocaleString()} paired simulations · same random seed</span></div>
      {compared.map(x=><div key={x.teamId} className="scenario-row">
        <strong>{x.team}</strong><span>{pct(x.base)} → {pct(x.changed)}</span>
        <b className={x.delta>=0?"scenario-positive":"scenario-negative"}>{x.delta>0?"+":""}{(x.delta*100).toFixed(2)} pp</b>
      </div>)}
      <p>Monte Carlo variability remains; differences are not statistically validated causal effects on real games. This experiment does not alter public predictions or archived original picks.</p>
    </div>:<p className="scenario-help">Run the sensitivity comparison to inspect how a single rating assumption changes tournament outcomes. Results are intentionally not precomputed.</p>}
  </section>;
}
