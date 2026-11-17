"use client";

import { useEffect, useMemo, useState } from "react";
import type { RatingsDataset, Team } from "../lib/models";

type WatchTeam = {teamId:string; name:string; conference:string; projectedRating:number; wins:number;
 losses:number; games:number; category:string; powerRank:number|null; sampleBand:string;illustrativeSeedRange?:number[]|null};
type Watchlist = {season:number; asOfDate:string; official:false; status:string; method:string;fieldSize:number;
 automaticSlotCount:number;atLargeSlotCount:number;eligibleCandidateCount:number;matchedConferences:number;
 reason?:string; teams:WatchTeam[];bubble:WatchTeam[];cutlineRating?:number;limitations:string[]};

const basePath = process.env.NEXT_PUBLIC_BASE_PATH || "";
type Filter = "all" | "conference-proxy" | "power-only-at-large" | "bubble";

export default function SelectionLab(){
  const [data,setData] = useState<RatingsDataset|null>(null);
  const [error,setError] = useState("");
  const [filter,setFilter] = useState<Filter>("all");
  const [search,setSearch] = useState("");
  const [conference,setConference] = useState("all");
  const [detailId,setDetailId] = useState("");
  useEffect(()=>{
    let alive = true;
    fetch(basePath+"/current/2027.json").then(r=>{
      if(!r.ok) throw new Error("No verified 2027 source snapshot has been deployed yet.");
      return r.json();
    }).then((r:RatingsDataset)=>{
      if(!alive)return;
      if(r.mode!=="current" || !r.selectionWatchlist) throw new Error("Current-season projection schema unavailable.");
      setData(r);
    }).catch((e:Error)=>{if(alive)setError(e.message)});
    return()=>{alive=false};
  },[]);
  const watch = data?.selectionWatchlist as Watchlist|undefined;
  const options = useMemo(()=>{
    const names = watch?.teams?.map(t=>t.conference)||[];
    return [...new Set(names)].sort();
  },[watch]);
  const candidates = useMemo(()=>{
    const base = watch?.status==="ready" ?
      filter==="bubble" ? (watch.bubble||[]) :
      filter==="all" ? (watch.teams||[]) :
      (watch.teams||[]).filter(t=>t.category===filter)
      : [];
    return base.filter(t=>t.name.toLowerCase().includes(search.toLowerCase()) &&
        (conference==="all" || t.conference===conference));
  },[watch,filter,search,conference]);
  const selected = (watch?.teams||[]).concat(watch?.bubble||[]).find(t=>t.teamId===detailId)||candidates[0];
  const confMatched = data?.identityCoverage?.matchedRatedTeams || 0;
  const confCount = data?.identityCoverage?.conferencesRepresented || 0;
  const preview = useMemo(()=>{
    return (data?.teams||[]).filter(t=>t.conferenceVerified)
      .sort((a,b)=>b.projectedRating-a.projectedRating).slice(0,16);
  },[data]);

  return <section className="content-section selection-exp" id="selection">
    <div className="section-heading"><div><span className="section-kicker">02 / ROAD TO SELECTION SUNDAY</span>
      <h2>Field <span>watchlist</span></h2>
      <p>Conference-by-conference strength signals, a transparent 76-team power scenario, and bubble context — without fake tournament bids.</p>
    </div><span className="research-pill">2027 · MARCH 14 SELECTION</span></div>
    <div className="feature-banner selection-banner"><div className="banner-copy"><span className="feature-kicker">MORE TEAMS. MORE MADNESS.</span>
      <h3>76 SPOTS.<br/><em>ZERO LOCKS YET.</em></h3><p>The 2027 men's tournament has 32 automatic and 44 at-large berths. Our power-only watchlist is an exploratory scenario; conference championships, eligibility and the committee decide the real field.</p>
      </div><div className="selection-watermark" aria-hidden="true"><strong>76</strong><span>THE EXPANDED FIELD</span></div></div>
    {!data ? <div className="premium-empty" role={error?"alert":"status"}><span className="empty-spark">◎</span><h3>{error?"SOURCE UNAVAILABLE":"VERIFYING CONFERENCE DATA"}</h3><p>{error||"Loading the sourced 2026–27 season…"}</p></div> :
    <>
      <div className="mini-metrics">
        <div><small>2027 FIELD SIZE</small><strong>76</strong><span>NCAA confirmed</span></div>
        <div><small>AUTO / AT-LARGE</small><strong>32 / 44</strong><span>NCAA-defined slots</span></div>
        <div><small>VERIFIED CONFERENCES</small><strong>{confCount} / 32</strong><span>In scored results directory</span></div>
        <div><small>LINKED PROGRAMS</small><strong>{confMatched}</strong><span>Exact NCAA-source name matches</span></div>
      </div>
      {watch?.status!=="ready" ? <div className="selection-pending">
        <div><span className="feature-kicker">DATA COVERAGE GATE</span><h3>A responsible bracket starts with the right teams.</h3>
        <p>{watch?.reason || "Verified conference membership is still unavailable."}</p>
        <p>We do not invent missing conferences or treat unverified opponents as officially tournament-eligible. The scoreboard still contains real results; the field scenario activates only with full 32-conference coverage.</p>
        <a href="https://github.com/sportsdataverse/sportsdataverse-data/releases/tag/ncaa_mbb_team_ids" target="_blank" rel="noreferrer">CHECK CONFERENCE SOURCE ↗</a></div>
        <div className="coverage-ring"><strong>{confCount}<small>/32</small></strong><span>CONFERENCES</span></div>
      </div> : <>
        <div className="watchlist-disclaimer"><span className="status-bullet"/><strong>UNOFFICIAL · POWER-ONLY SCENARIO</strong><span>All 76 entrants below are hypothetical. AQ proxies are Elo leaders, not conference champions; at-large candidates are strength-ranked, not committee selections. Ranking ≠ NCAA seed. Strength-tier ranges are illustrative and uncalibrated.</span></div>
        <div className="watch-filters">
          <div className="watch-segments" role="group" aria-label="Watchlist segment">
            {([["all","FULL WATCHLIST"],["conference-proxy","CONFERENCE PROXIES"],["power-only-at-large","AT-LARGE PROXIES"],["bubble","NEAR CUTLINE"]] as [Filter,string][]).map(([id,label])=>
              <button className={filter===id?"active":""} key={id} onClick={()=>{setFilter(id);setDetailId("");}}>{label}</button>)}
          </div>
          <label className="watch-search">FIND TEAM<input aria-label="Search projected watchlist" value={search} placeholder="School name..." onChange={e=>setSearch(e.target.value)}/></label>
          <label className="watch-search">CONFERENCE<select value={conference} onChange={e=>setConference(e.target.value)}><option value="all">All conferences</option>{options.map(c=><option value={c} key={c}>{c}</option>)}</select></label>
        </div>
        <div className="watch-layout">
          <div className="watch-table">
            <div className="watch-table-head"><span>POWER</span><span>PROGRAM</span><span>RECORD</span><span>MODEL RATING</span></div>
            <div className="watch-table-scroll">{candidates.map((t,i)=><button key={t.teamId} onClick={()=>setDetailId(t.teamId)}
              className={selected?.teamId===t.teamId?"watch-row active":"watch-row"}><span className="watch-rank">{t.powerRank?String(t.powerRank).padStart(2,"0"):"↗"}</span>
              <span className="watch-name"><strong>{t.name}</strong><small>{t.conference} · {t.category==="conference-proxy"?"AQ PROXY":t.category==="power-only-at-large"?"AT-LARGE PROXY":"NEAR CUTLINE"}</small></span>
              <span>{t.wins}–{t.losses}</span><b>{t.projectedRating.toFixed(0)}</b></button>)}
              {!candidates.length&&<div className="empty-state">No sourced programs match these filters.</div>}
            </div>
          </div>
          <aside className="watch-spotlight">
            {selected ? <><span className="feature-kicker">PROGRAM WATCH / POWER RATING</span><h3>{selected.name}</h3><p className="watch-conference">{selected.conference}</p>
              <div className="watch-rating">{selected.projectedRating.toFixed(0)}<span>MODEL ELO</span></div>
              <div className="watch-facts"><div><small>POWER POSITION</small><strong>{selected.powerRank||"Outside 76"}</strong></div><div><small>SEASON SAMPLE</small><strong>{selected.games} games</strong></div><div><small>ILLUSTRATIVE SEED TIER</small><strong>{selected.illustrativeSeedRange?selected.illustrativeSeedRange.join("–"):"N/A"}</strong></div><div><small>DATA CONFIDENCE</small><strong>{selected.sampleBand}</strong></div></div>
              <div className="watch-tag">{selected.category.replaceAll("-"," ").toUpperCase()}</div>
              <p>The seed-tier range above is a wide, rule-based strength scenario, not a statistically calibrated NCAA seed forecast or chance of a bid. A team's conference tournament result and committee criteria may change selection dramatically.</p>
            </> : <div className="premium-empty">Select a program to inspect its model inputs.</div>}
          </aside>
        </div>
      </>}
      <div className="selection-foot"><span className="feature-kicker">CONFERENCE-LINKED SOURCE LEADERS</span>
        <p>These are the highest-rated programs that could be joined exactly to the NCAA 2027 team directory. They are not officially qualified.</p>
        <div className="selection-preview">{preview.map((t,i)=><div key={t.teamId}><span>{String(i+1).padStart(2,"0")}</span><strong>{t.name}</strong><small>{t.conference||"—"}</small><b>{t.projectedRating.toFixed(0)}</b></div>)}</div>
      </div>
      <p className="source-note">Conference source: <a href="https://github.com/sportsdataverse/sportsdataverse-data/releases/tag/ncaa_mbb_team_ids" target="_blank" rel="noreferrer">NCAA team-ID crosswalk ↗</a>. Official field rules: <a href="https://www.ncaa.org/championships/march-madness/expansion-what-to-know/" target="_blank" rel="noreferrer">NCAA 2027 expansion ↗</a>. Matching conference membership is not a standalone official eligibility certification. Provisional power-based candidates will evolve with results; no historical backtest of committee selection accuracy has been established.</p>
    </>}
  </section>;
}
