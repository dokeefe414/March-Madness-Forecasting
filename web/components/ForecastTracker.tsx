"use client";
import { useEffect,useMemo,useState } from "react";
import ForwardScorecard from "./ForwardScorecard";
import SettlementHealth from "./SettlementHealth";
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || "";
type Pick = {eventId:string;scheduledStartUtc:string;scheduledEasternDate:string;home:string;away:string;homeTeamId:string;awayTeamId:string;homeWinProbability:number;neutralSite:boolean;model:string;modelId?:string|null;modelTrainingThroughDate?:string|null};
type Snapshot = {id:string;generatedAtUtc:string;count:number;predictions:Pick[]};
type Settled = {predictionKey:string;snapshotId:string;eventId:string;forecastAtUtc:string;scheduledStartUtc:string;home:string;away:string;homeScore:number;awayScore:number;predictedHome:number;observedHome:number;brier:number;winnerCorrect:number;logLoss:number};
type Ledger = {schemaVersion:number;generatedAtUtc:string;snapshots:Snapshot[];settlements:Settled[];scores:{settledPredictions:number;brier:number|null;logLoss:number|null;winnerAccuracy:number|null};uniqueGames?:React.ComponentProps<typeof ForwardScorecard>["report"];warning:string};
type Mode = "all"|"scheduled"|"settled";
const pct = (n:number)=>(100*n).toFixed(1)+"%";
function DateDisplay({iso}:{iso:string}){return <time dateTime={iso}>{new Date(iso).toLocaleString("en-US",{month:"short",day:"numeric",hour:"numeric",minute:"2-digit",timeZone:"America/New_York"})} ET</time>}
export default function ForecastTracker(){
  const [ledger,setLedger] = useState<Ledger|null>(null);
  const [missing,setMissing] = useState("");
  const [mode,setMode] = useState<Mode>("all");
  const [search,setSearch] = useState("");
  useEffect(()=>{
    let alive = true;
    fetch(basePath+"/forecasts/index.json").then(r=>{
      if(!r.ok) throw new Error("No independently archived, pre-tipoff predictions have been published yet.");
      return r.json();
    }).then((r:Ledger)=>{
      if(!alive)return;
      if(r.schemaVersion!==1||!Array.isArray(r.snapshots)||!Array.isArray(r.settlements)) throw new Error("Ledger integrity checks failed.");
      setLedger(r);
    }).catch((e:Error)=>{if(alive)setMissing(e.message)});
    return()=>{alive=false};
  },[]);
  const all = useMemo(()=>{
    const settled = new Map(ledger?.settlements.map(s=>[s.predictionKey,s])||[]);
    return (ledger?.snapshots||[]).flatMap(s=>s.predictions.map(p=>({
      ...p,snapshotId:s.id,generatedAtUtc:s.generatedAtUtc,
      result:settled.get(s.id+":"+p.eventId) as Settled|undefined,
    }))).sort((a,b)=>b.generatedAtUtc.localeCompare(a.generatedAtUtc)).slice(0,180);
  },[ledger]);
  const visible = useMemo(()=>all.filter(p=>(mode==="all" || (mode==="settled" ? Boolean(p.result) : !p.result)) &&
      (p.home+" "+p.away).toLowerCase().includes(search.toLowerCase())),[all,mode,search]);
  const scores=ledger?.scores;
  return <section className="content-section picks-exp" id="predictions">
    <div className="section-heading"><div><span className="section-kicker">03 / PROOF BEFORE TIP-OFF</span>
      <h2>Prediction <span>ledger</span></h2><p>Timestamped, sourced probabilities archived before the listed game start. Results are settled later — without rewriting the original picks.</p>
    </div><span className="research-pill">IMMUTABLE FORECAST ARCHIVE</span></div>
    <div className="feature-banner picks-banner"><div className="banner-copy"><span className="feature-kicker">MAKE THE CALL BEFORE THE GAME.</span>
      <h3>NO BACKFILL.<br/><em>NO HINDSIGHT.</em></h3><p>Actual future fixtures, exact team matching, 15-minute pre-tipoff buffer, independent NCAA result settlement and an open Git history. If no verified matchups exist, we show no picks.</p></div>
      <div className="picks-watermark" aria-hidden="true">PRE<br/>GAME<span>●</span></div></div>
    {!ledger ? <div className="premium-empty" role={missing?"alert":"status"}><span className="empty-spark">◎</span>
      <h3>{missing?"NO AUDITED FORECAST ARCHIVE YET":"LOADING SOURCE-TIMESTAMPED PICKS"}</h3>
      <p>{missing||"Reading the committed pre-tipoff prediction ledger…"}</p>
      <p>The scheduled GitHub workflow will populate it once future fixtures can be matched unambiguously. No retroactively generated historical forecasts count as forward predictions.</p>
      <a className="button-outline" href="https://github.com/dokeefe414/March-Madness-Forecasting/actions/workflows/archive-pregame.yml" target="_blank" rel="noreferrer">VIEW FORECAST ARCHIVER ↗</a></div>:
      <>
        <div className="source-status"><span className="status-bullet"/><div><strong>PUBLIC GITHUB AUDIT TRAIL</strong><span>Latest index <DateDisplay iso={ledger.generatedAtUtc}/> · {ledger.snapshots.length} saved capture runs · exact-time provenance</span></div><a href="https://github.com/dokeefe414/March-Madness-Forecasting/tree/main/web/public/forecasts" target="_blank" rel="noreferrer">VERIFY SOURCE FILES ↗</a></div>
        <ForwardScorecard report={ledger.uniqueGames}/>
        <SettlementHealth/>
        <div className="mini-metrics"><div><small>PRE-TIPOFF PICKS</small><strong>{all.length}</strong><span>Latest archived runs shown</span></div>
          <div><small>SETTLED PICKS</small><strong>{scores?.settledPredictions||0}</strong><span>Against NCAA final scores</span></div>
          <div><small>OUT-OF-SAMPLE BRIER</small><strong>{scores?.brier!=null?scores.brier.toFixed(4):"—"}</strong><span>50/50 reference 0.2500</span></div>
          <div><small>WINNER ACCURACY</small><strong>{scores?.winnerAccuracy!=null?pct(scores.winnerAccuracy):"—"}</strong><span>Only settled pregame picks</span></div></div>
        <div className="picks-insights"><div><span className="feature-kicker">HOW OUR PRE-TIPOFF CLAIMS ARE PROTECTED</span><h3>Every probability has a receipt.</h3>
          <p>Scores are not computed retroactively and called predictions. We store the source-schedule time, model snapshot time, forecast creation time, and the first subsequent matching NCAA final separately.</p></div>
          <div className="picks-proof"><span>01 / SOURCE MATCHED</span><span>02 / BEFORE TIPOFF</span><span>03 / ARCHIVED</span><span>04 / SETTLED LATER</span></div></div>
        <div className="watch-filters"><div className="watch-segments" role="group" aria-label="Forecast status">
          {([["all","ALL PICKS"],["scheduled","AWAITING FINALS"],["settled","SETTLED"]] as [Mode,string][]).map(([value,label])=><button className={mode===value?"active":""} key={value} onClick={()=>setMode(value)}>{label}</button>)}
          </div><label className="watch-search">FIND MATCHUP<input value={search} placeholder="Search teams..." aria-label="Search audited matchups" onChange={e=>setSearch(e.target.value)}/></label></div>
        <div className="picks-board">{visible.map(p=><article className="pick-card" key={p.snapshotId+":"+p.eventId}>
          <div className="pick-top"><span>{p.result?"SETTLED / NCAA SOURCE":"AWAITING NCAA FINAL"}</span><span>ESPN EVENT {p.eventId}</span></div>
          <div className="pick-versus"><div><small>ROAD</small><strong>{p.away}</strong></div><span>AT</span><div><small>HOME</small><strong>{p.home}</strong></div></div>
          <div className="pick-prob-row"><div><strong>{pct(1-p.homeWinProbability)}</strong><span>{pct(p.homeWinProbability)}</span></div><div className="pick-probbar"><div style={{width:pct(1-p.homeWinProbability)}}/></div></div>
          <p className="online-pick-model">{p.model}{p.modelTrainingThroughDate?" · trained through "+p.modelTrainingThroughDate:""}</p>
          <div className="pick-details"><span>Listed start: <DateDisplay iso={p.scheduledStartUtc}/></span><span>Forecast frozen: <DateDisplay iso={p.generatedAtUtc}/></span></div>
          {p.result && <div className="pick-result"><strong>FINAL {p.result.awayScore}–{p.result.homeScore}</strong><span>Forecast Brier {p.result.brier.toFixed(4)} · {p.result.winnerCorrect===1?"CORRECT PICK":p.result.winnerCorrect===.5?"EVEN-ODDS PICK":"MISSED PICK"}</span></div>}
        </article>)}
        {!visible.length&&<div className="premium-empty"><h3>NO QUALIFYING MATCHUPS</h3><p>There are no source-matched predictions for this filter. We will not backfill them after games start.</p></div>}</div>
        <p className="source-note">Scheduled fixture source: ESPN public scoreboard; results: SportsDataverse NCAA-source finals; identity join: exact normalized NCAA name only. An ESPN scheduled start is not proof of actual tip-off if a game was rescheduled. Settlements require same Eastern date, same home/away names, and a single confirmed result. Multiple pregame snapshots of a game count as distinct forecasts and are not independent games. <a href="https://github.com/dokeefe414/March-Madness-Forecasting/blob/main/docs/forecast-audit.md" target="_blank" rel="noreferrer">Read audit policy ↗</a></p>
      </>}
  </section>;
}
