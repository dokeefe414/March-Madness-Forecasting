"use client";
import type {Team} from "../lib/models";
type Datum={label:string;home:number|null;away:number|null;unit:string;note:string;better:"high"|"low"};
const number=(x:number|null,unit:string)=>x==null?"—":x.toFixed(1)+unit;
export default function MatchupIntelligence({home,away}:{home:Team|undefined;away:Team|undefined}){
  if(!home||!away)return <p className="gc-empty">No source-verified team metrics available for comparison.</p>;
  const has=(a:unknown)=>typeof a==="number"&&Number.isFinite(a)?a as number:null;
  const metrics:Datum[]=[
    {label:"Elo strength",home:has(home.rating),away:has(away.rating),unit:"",note:"Current causal team rating",better:"high"},
    {label:"Recent form",home:has(home.trend),away:has(away.trend),unit:"",note:"Rating trend, not a stand-alone win coefficient",better:"high"},
    {label:"Opponent strength",home:has(home.opponentAverageElo),away:has(away.opponentAverageElo),unit:"",note:"Average earlier opponent Elo",better:"high"},
    {label:"Adjusted offense",home:has(home.adjOff100),away:has(away.adjOff100),unit:"",note:"Source-linked opponent-adjusted points / 100 possessions",better:"high"},
    {label:"Adjusted defense",home:has(home.adjDef100),away:has(away.adjDef100),unit:"",note:"Lower points allowed / 100 possessions is preferable",better:"low"},
    {label:"Tempo",home:has(home.pacePossessions),away:has(away.pacePossessions),unit:"",note:"Possessions per game, descriptive only",better:"high"},
  ];
  return <section className="gc-intelligence" aria-label="Verified team matchup intelligence">
    <div className="gc-intelligence-header"><span className="section-kicker">SOURCE-BASED STRENGTH COMPARISON</span>
      <h3>The matchup under the microscope.</h3>
      <p>These are descriptive source-linked inputs, not invented contributions to the forecast. Missing possession evidence is displayed as unavailable.</p></div>
    <div className="gc-intelligence-teams"><b>{away.name} · AWAY</b><b>{home.name} · HOME</b></div>
    {metrics.map(metric=>{
      const both=metric.home!=null&&metric.away!=null;
      const lo=both?Math.min(metric.home!,metric.away!)-Math.max(2,Math.abs(metric.home!-metric.away!)*.5):0;
      const hi=both?Math.max(metric.home!,metric.away!)+Math.max(2,Math.abs(metric.home!-metric.away!)*.5):1;
      const width=(v:number|null)=>!both||v==null?0:Math.max(4,Math.min(100,(v-lo)/(hi-lo)*100));
      return <div className="gc-intelligence-metric" key={metric.label}>
        <div className="gc-intelligence-title"><strong>{metric.label}</strong><small>{metric.note}</small></div>
        <div className="gc-intelligence-values"><span>{number(metric.away,metric.unit)}</span><span>{number(metric.home,metric.unit)}</span></div>
        <div className="gc-intelligence-bars"><div><i style={{width:width(metric.away)+"%"}}/></div><div><i style={{width:width(metric.home)+"%"}}/></div></div>
      </div>;
    })}
    <p className="gc-intelligence-caveat">Bar scales are local to each metric and show relative magnitude only; do not compare bar lengths between metrics. Defensive efficiency favors lower values. The published win probability uses its own explicitly named model.</p>
  </section>;
}