"use client";
import { useEffect, useMemo, useState } from "react";
import type { RatingsDataset, Team } from "../lib/models";
import { matchupProbability } from "../lib/models";
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || "";
const pct = (n: number) => (n * 100).toFixed(1) + "%";

export default function LiveSeason() {
  const [data, setData] = useState<RatingsDataset | null>(null);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState("");
  const [opponentId, setOpponentId] = useState("");
  const [view, setView] = useState<"rankings" | "scores">("rankings");
  useEffect(() => {
    let ignore = false;
    fetch(basePath + "/current/2027.json").then(res => {
      if (!res.ok) throw new Error("A confirmed current-season source snapshot has not yet been published.");
      return res.json();
    }).then((json: RatingsDataset) => {
      if (ignore) return;
      if (json.mode !== "current" || json.season !== 2027 || !json.retrievedAtUtc || !json.lastGameDate ||
          !json.teams?.length) throw new Error("Current-season source record failed validation.");
      setData(json); setSelectedId(json.teams[0]?.teamId || "");setOpponentId(json.teams[1]?.teamId || "");
    }).catch((e: Error) => { if (!ignore) setError(e.message); });
    return () => { ignore = true; };
  }, []);
  const teams = useMemo(()=>[...(data?.teams || [])].sort((a,b)=>a.rank - b.rank), [data]);
  const filtered = useMemo(()=>teams.filter(t=>t.name.toLowerCase().includes(search.toLowerCase())), [teams,search]);
  const selected = teams.find(t=>t.teamId === selectedId) || teams[0];
  const opponent = teams.find(t=>t.teamId === opponentId) || teams[1];
  const probability = selected && opponent && selected.teamId !== opponent.teamId ? matchupProbability(selected.projectedRating, opponent.projectedRating) : null;
  const updated = data?.retrievedAtUtc ? new Date(data.retrievedAtUtc).toLocaleString("en-US",{year:"numeric",month:"short",day:"numeric",hour:"numeric",minute:"2-digit",timeZone:"UTC"})+" UTC" : "Unknown";
  return <section className="content-section current-exp">
    <div className="section-heading"><div><span className="section-kicker">01 / 2026–27 SEASON</span><h2>Current <span>pulse</span></h2><p>Real NCAA-source final scores, independently updated power ratings, and transparent freshness metadata.</p></div><span className="research-pill">SEASON 2027</span></div>
    <div className="feature-banner live-banner"><div className="banner-copy"><span className="feature-kicker">THE ROAD TO MARCH 2027</span><h3>EVERY GAME<br/><em>CHANGES THE PICTURE.</em></h3><p>Team strength evolves as real results arrive. These are current-season Elo estimates — not committee rankings or a predicted 76-team selection.</p></div><div className="live-watermark" aria-hidden="true">27<span>✳</span></div></div>
    {!data ? <div className="premium-empty" role={error?"alert":"status"}><span className="empty-spark">◉</span><h3>{error?"SOURCE NOT YET AVAILABLE":"CHECKING VERIFIED SOURCE"}</h3><p>{error || "Fetching the latest published current-season snapshot…"}</p><p>No scores or rankings will be fabricated when the feed is unavailable.</p></div> : <>
      <div className="source-status"><span className="status-bullet"/><div><strong>CONFIRMED SOURCE SNAPSHOT</strong><span>Last included game {data.lastGameDate} · retrieved {updated} · not a live second-by-second scoreboard</span></div><a href={data.sourceUrl} target="_blank" rel="noreferrer">SOURCE ↗</a></div>
      <div className="mini-metrics"><div><small>RATED PROGRAMS</small><strong>{data.teams.length}</strong><span>Games available in feed</span></div><div><small>CONFIRMED FINALS</small><strong>{data.regularSeasonGames?.toLocaleString()}</strong><span>Through published cutoff</span></div><div><small>MODEL</small><strong>ELO+</strong><span>K=24 / home 65</span></div><div><small>2027 FIELD</small><strong>76</strong><span>Not yet selected</span></div></div>
      {data.pregameDiagnostics && <div className="current-evaluation">
        <div className="eval-intro"><span className="feature-kicker">MODEL SCORECARD / SEQUENTIAL HISTORY</span><h3>MEASURE THE PICKS.</h3><p>Every confirmed result is scored using Elo ratings before that game updates them. This is a retrospective pre-game backtest, not a record of timestamped forecasts publicly posted before tipoff.</p></div>
        <div className="eval-number"><span>Brier error ↓</span><strong>{data.pregameDiagnostics.brier.toFixed(4)}</strong><small>50/50 reference {data.pregameDiagnostics.coinFlipBrier.toFixed(4)}</small></div>
        <div className="eval-number"><span>Winner accuracy ↑</span><strong>{(data.pregameDiagnostics.accuracy*100).toFixed(1)}%</strong><small>{data.pregameDiagnostics.evaluatedGames.toLocaleString()} recorded games</small></div>
      </div>}
      <div className="live-view-switch" role="group" aria-label="Current season view"><button className={view==="rankings"?"active":""} onClick={()=>setView("rankings")}>POWER BOARD</button><button className={view==="scores"?"active":""} onClick={()=>setView("scores")}>RECENT FINALS</button></div>
      {view==="rankings"?<div className="live-layout">
        <div className="live-ranking-card"><div className="table-toolbar"><label className="search-field"><span>⌕</span><input aria-label="Find current-season team" placeholder="Find a program..." value={search} onChange={e=>setSearch(e.target.value)}/></label><span className="current-count">{filtered.length} PROGRAMS</span></div>
          <div className="live-ranking-head"><span>#</span><span>TEAM</span><span>RECORD</span><span>RATING</span></div>
          <div className="live-ranking-scroll">{filtered.slice(0,150).map(t=><button className={selected?.teamId===t.teamId?"live-ranking-row active":"live-ranking-row"} key={t.teamId} onClick={()=>setSelectedId(t.teamId)}><span className="rank-num">{String(t.rank).padStart(2,"0")}</span><strong>{t.name}</strong><small>{t.wins}–{t.losses}</small><b>{t.projectedRating.toFixed(0)}</b></button>)}</div>
          {filtered.length>150&&<p className="method-note">Showing the first 150. Refine the team search to find others.</p>}
        </div>
        <div className="live-spotlight">{selected && <><span className="feature-kicker">PROGRAM INTELLIGENCE / #{selected.rank}</span><h3>{selected.name}</h3><div className="live-rating">{selected.projectedRating.toFixed(0)}<small>PROJECTED ELO</small></div>
          <div className="live-stat-grid"><div><span>RECORD</span><strong>{selected.wins}–{selected.losses}</strong></div><div><span>POINT DIFF / GAME</span><strong>{selected.marginPerGame?.toFixed(1) ?? "—"}</strong></div><div><span>AVG OPP ELO</span><strong>{selected.opponentAverageElo?.toFixed(0) ?? "—"}</strong></div><div><span>FORM ADJUSTMENT</span><strong>{selected.trend >= 0 ? "+" : ""}{selected.trend.toFixed(1)}</strong></div></div>
          <div className="spotlight-separator"/>
          <label className="feature-kicker" htmlFor="live-opponent">NEUTRAL-COURT MATCHUP VS</label>
          <select id="live-opponent" className="live-opponent-select" value={opponent?.teamId} onChange={e=>setOpponentId(e.target.value)}>{teams.map(t=><option key={t.teamId} value={t.teamId}>{t.name}</option>)}</select>
          {probability !== null && <div className="live-probability"><strong>{pct(probability)}</strong><span>ESTIMATED WIN PROBABILITY</span><div className="prob-bar"><div style={{width:pct(probability)}}/></div><small>{pct(1-probability)} for {opponent.name}</small></div>}
          {probability===null&&<p className="method-note">Choose another team to compare.</p>}
          <p className="method-note">Live Elo estimates are not calibrated against 2027 tournament results. Descriptive point margins are NOT possession-adjusted efficiency ratings.</p>
        </>}</div>
      </div>:<div className="scoreboard-grid">{data.recentGames?.map(g=><div className="scorecard" key={g.id}><div><span>FINAL · {g.date}</span><small>NCAA ID {g.id}</small></div><div className="scoreline"><strong>{g.away}</strong><b>{g.awayScore}</b></div><div className="scoreline"><strong>{g.home}</strong><b>{g.homeScore}</b></div></div>)}</div>}
      <p className="source-note">SportsDataverse republishes NCAA statistics; the source may lag the latest tip-off or exclude games not yet captured. This season is modeled independently because NCAA name-based identities are not a verified historical Kaggle-ID crosswalk. Data after Selection Sunday is excluded from the pre-tournament rating snapshot. The 2027 NCAA men's field will have 76 teams and 12 Opening Round games; selection odds are not yet available. <a href="https://www.ncaa.com/news/basketball-men/article/2026-05-07/2027-march-madness-mens-ncaa-tournament-schedule-dates" target="_blank" rel="noreferrer">Official format ↗</a></p>
    </>}
  </section>;
}
