"use client";
import { useMemo,useState } from "react";

export default function TeamTrend({ratings, team}:{ratings:number[];team:string}){
  const [focused,setFocused]=useState<number|null>(null);
  const values=useMemo(()=>ratings.filter(x=>Number.isFinite(x)),[ratings]);
  if(values.length<2) return <div className="trend-empty">Not enough sequential results to draw a real Elo trajectory.</div>;
  const width=740,height=208,padX=26,padY=24;
  const min=Math.floor(Math.min(...values)/25)*25-10;
  const max=Math.ceil(Math.max(...values)/25)*25+10;
  const span=Math.max(max-min,1);
  const coords=values.map((v,i)=>({
    x:padX+(width-2*padX)*i/(values.length-1),
    y:height-padY-(v-min)/span*(height-2*padY),
  }));
  const line=coords.map((p,i)=>(i===0?"M":"L")+p.x.toFixed(2)+","+p.y.toFixed(2)).join(" ");
  const area=line+" L"+coords[coords.length-1].x.toFixed(2)+","+(height-padY)+" L"+coords[0].x.toFixed(2)+","+(height-padY)+" Z";
  const selected=focused==null ? values.length-1 : Math.min(focused,values.length-1);
  const delta=values[selected]-values[0];
  return <section className="trend-panel" aria-label={"Actual season Elo rating trajectory for "+team}>
    <div className="trend-header"><div><span className="feature-kicker">GAME-BY-GAME MODEL TIMELINE</span><h4>Rating trajectory</h4></div>
      <div className="trend-current"><strong>{values[selected].toFixed(0)}</strong><small>{selected===0?"PRE-SEASON":"AFTER GAME "+selected} · {delta>=0?"+":""}{delta.toFixed(1)} SINCE START</small></div></div>
    <svg viewBox="0 0 740 208" role="img" aria-label={"Elo evolved from "+values[0].toFixed(0)+" to "+values[values.length-1].toFixed(0)+" in "+(values.length-1)+" recorded games"}>
      <defs><linearGradient id="seasonCurveFill" x1="0" x2="0" y1="0" y2="1"><stop stopColor="#a0ffcb" stopOpacity=".32"/><stop offset="1" stopColor="#a0ffcb" stopOpacity="0"/></linearGradient></defs>
      {Array.from({length:5},(_,i)=>{const y=padY+(height-2*padY)*i/4;return <g key={i}><line x1={padX} x2={width-padX} y1={y} y2={y} stroke="#32555d" strokeDasharray="3 7"/><text x={width-padX} y={y-5} fill="#93abb2" textAnchor="end" fontSize="11">{(max-(max-min)*i/4).toFixed(0)}</text></g>})}
      <path d={area} fill="url(#seasonCurveFill)"/>
      <path d={line} fill="none" stroke="#9bffcb" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round"/>
      {coords.map((p,i)=><circle key={i} cx={p.x} cy={p.y} r={selected===i?5.5:3.5}
        fill={selected===i?"#dffff0":"#83cfa8"} stroke="#0e2d29" strokeWidth="1.5"
        tabIndex={0} role="button"
        aria-label={"After game "+i+", Elo "+values[i].toFixed(1)}
        onMouseEnter={()=>setFocused(i)} onFocus={()=>setFocused(i)}
        onMouseLeave={()=>setFocused(null)} onBlur={()=>setFocused(null)}
        onKeyDown={e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();setFocused(i);}}}>
          <title>{"Game "+i+": "+values[i].toFixed(1)}</title>
        </circle>)}
    </svg>
    <div className="trend-footer"><span>PRESEASON 1500</span><span>{values.length-1} GAMES RECORDED</span></div>
  </section>;
}
