"use client";
import { useEffect, useMemo, useState } from "react";
import type { RatingsDataset, Team } from "../lib/models";
import { matchupProbability } from "../lib/models";
import TeamTrend from "./TeamTrend";
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || "";
const pct = (n: number) => (n * 100).toFixed(1) + "%";

export default function LiveSeason() {
  const [data, setData] = useState<RatingsDataset | null>(null);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState("");
  const [opponentId, setOpponentId] = useState("");
  const [view, setView] = useState<"rankings" | "scores">("rankings");
  const [verifiedOnly,setVerifiedOnly] = useState(false);
  const [probabilityModel,setProbabilityModel] = useState<"elo"|"calibrated"|"blend">("blend");
  const [conferenceFilter,setConferenceFilter] = useState("all");
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
  const conferenceNames=useMemo(()=>[...new Set(teams.map(t=>t.conference).filter((c):c is string=>Boolean(c)))].sort(),[teams]);
  const filtered = useMemo(()=>teams.filter(t=>(t.name+" "+(t.conference||"")).toLowerCase().includes(search.toLowerCase()) &&
    (!verifiedOnly||t.conferenceVerified) && (conferenceFilter==="all"||t.conference===conferenceFilter)),
    [teams,search,verifiedOnly,conferenceFilter]);
  const selected = teams.find(t=>t.teamId === selectedId) || teams[0];
  const opponent = teams.find(t=>t.teamId === opponentId) || teams[1];
  const comparisonReady = Boolean(selected && opponent && selected.teamId !== opponent.teamId);
  const eloP = comparisonReady ? matchupProbability(selected.rating,opponent.rating) : null;
  const calibratedP = comparisonReady && data?.historicalCalibration ?
    1/(1+Math.pow(10,-(selected.projectedRating-opponent.projectedRating)/(400*data.historicalCalibration.temperature))) : null;
  const probability = probabilityModel==="elo" || calibratedP===null ? eloP :
    probabilityModel==="calibrated" ? calibratedP :
    (1-data!.historicalCalibration!.blendWeight)*eloP!+data!.historicalCalibration!.blendWeight*calibratedP;
  const updated = data?.retrievedAtUtc ? new Date(data.retrievedAtUtc).toLocaleString("en-US",{year:"numeric",month:"short",day:"numeric",hour:"numeric",minute:"2-digit",timeZone:"UTC"})+" UTC" : "Unknown";
  return <section className="content-section current-exp">
    <div className="section-heading"><div><span className="section-kicker">01 / 2026–27 SEASON</span><h2>Current <span>pulse</span></h2><p>Real NCAA-source final scores, independently updated power ratings, and transparent freshness metadata.</p></div><span className="research-pill">SEASON 2027</span></div>
    <div className="feature-banner live-banner"><div className="banner-copy"><span className="feature-kicker">THE ROAD TO MARCH 2027</span><h3>EVERY GAME<br/><em>CHANGES THE PICTURE.</em></h3><p>Team strength evolves as real results arrive. These are current-season Elo estimates — not committee rankings or a predicted 76-team selection.</p></div><div className="live-watermark" aria-hidden="true">27<span>✳</span></div></div>
    {!data ? <div className="premium-empty" role={error?"alert":"status"}><span className="empty-spark">◉</span><h3>{error?"SOURCE NOT YET AVAILABLE":"CHECKING VERIFIED SOURCE"}</h3><p>{error || "Fetching the latest published current-season snapshot…"}</p><p>No scores or rankings will be fabricated when the feed is unavailable.</p></div> : <>
      <div className="source-status"><span className="status-bullet"/><div><strong>CONFIRMED SOURCE SNAPSHOT</strong><span>Last included game {data.lastGameDate} · retrieved {updated} · not a live second-by-second scoreboard</span><span>Scheduled refresh: 1:00 a.m. Eastern daily · late-game catch-up: 5:17 a.m. Eastern during season · subject to provider and GitHub delays</span></div><a href={data.sourceUrl} target="_blank" rel="noreferrer">SOURCE ↗</a></div>
      <div className="mini-metrics"><div><small>RATED TEAMS</small><strong>{data.teams.length}</strong><span>{data.identityCoverage?.matchedRatedTeams||0} conference-linked</span></div><div><small>CONFIRMED FINALS</small><strong>{data.regularSeasonGames?.toLocaleString()}</strong><span>Through published cutoff</span></div><div><small>POSSESSION ROWS</small><strong>{data.efficiencyCoverage?.matchedTeamGames||0}</strong><span>{data.efficiencyCoverage?.teamsWithMetrics||0} with pace estimates</span></div><div><small>2027 FIELD</small><strong>76</strong><span>Not yet selected</span></div></div>
      <div className="source-quality"><div><span className="feature-kicker">NCAA-SOURCE CONFERENCE NAME CROSSWALK</span><strong>{data.identityCoverage?.status==="ready"?"Conference crosswalk available":"Crosswalk unavailable"}</strong><small>{data.identityCoverage?.matchedRatedTeams||0} of {data.teams.length} source results teams matched by exact full name · {data.identityCoverage?.conferencesRepresented||0} conferences represented · Unmatched opponents remain unrated for selection eligibility</small></div>
        <div><span className="feature-kicker">D-I SUBDIVISION REFERENCE</span><strong>{data.divisionCoverage?.status==="ready"?"Season-linked group source available":"Division evidence unavailable"}</strong><small>{data.divisionCoverage?.divisionIConfirmed||0} source-linked D-I programs, {data.divisionCoverage?.explicitlyNonDI||0} explicitly other subdivisions, {data.divisionCoverage?.unmatchedRatedTeams||0} unverified (unknown ≠ ineligible). These are not individual postseason eligibility decisions.</small></div>
        <div><span className="feature-kicker">PACE / SOURCE BOX SCORES</span><strong>{data.efficiencyCoverage?.status==="ready"?"Actual possession metrics available":"Possession data unavailable"}</strong><small>Metrics are opponent-adjusted descriptive estimates with early-season shrinkage, not proven superior tournament predictions.</small></div></div>
      {data.pregameDiagnostics && <div className="current-evaluation">
        <div className="eval-intro"><span className="feature-kicker">MODEL SCORECARD / SEQUENTIAL HISTORY</span><h3>MEASURE THE PICKS.</h3><p>Every confirmed result is scored using Elo ratings before that game updates them. This is a retrospective pre-game backtest, not a record of timestamped forecasts publicly posted before tipoff.</p></div>
        <div className="eval-number"><span>Brier error ↓</span><strong>{data.pregameDiagnostics.brier.toFixed(4)}</strong><small>50/50 reference {data.pregameDiagnostics.coinFlipBrier.toFixed(4)}</small></div>
        <div className="eval-number"><span>Winner accuracy ↑</span><strong>{(data.pregameDiagnostics.accuracy*100).toFixed(1)}%</strong><small>{data.pregameDiagnostics.evaluatedGames.toLocaleString()} recorded games</small></div>
      </div>}
      <div className="live-view-switch" role="group" aria-label="Current season view"><button className={view==="rankings"?"active":""} onClick={()=>setView("rankings")}>POWER BOARD</button><button className={view==="scores"?"active":""} onClick={()=>setView("scores")}>RECENT FINALS</button></div>
      {view==="rankings"?<div className="live-layout">
        <div className="live-ranking-card"><div className="table-toolbar"><label className="search-field"><span>⌕</span><input aria-label="Find current-season team" placeholder="Find a program or conference..." value={search} onChange={e=>setSearch(e.target.value)}/></label><span className="current-count">{filtered.length} PROGRAMS</span></div>
          <div className="live-filters"><label><input type="checkbox" checked={verifiedOnly} onChange={e=>setVerifiedOnly(e.target.checked)}/> CONFERENCE-LINKED ONLY</label><label>CONFERENCE <select value={conferenceFilter} onChange={e=>setConferenceFilter(e.target.value)}><option value="all">All conferences</option>{conferenceNames.map(c=><option key={c} value={c}>{c}</option>)}</select></label></div>
          <div className="live-ranking-head"><span>#</span><span>TEAM</span><span>RECORD</span><span>RATING</span></div>
          <div className="live-ranking-scroll">{filtered.slice(0,150).map(t=><button className={selected?.teamId===t.teamId?"live-ranking-row active":"live-ranking-row"} key={t.teamId} onClick={()=>setSelectedId(t.teamId)}><span className="rank-num">{String(t.rank).padStart(2,"0")}</span><span className="live-row-name"><strong>{t.name}</strong><small>{t.divisionIConfirmed===true?"D-I SOURCE MATCH":t.divisionIConfirmed===false?"OUTSIDE D-I SOURCE":"DIVISION UNKNOWN"} · {t.conference||"Unmatched conference"}</small></span><small>{t.wins}–{t.losses}</small><b>{t.projectedRating.toFixed(0)}</b></button>)}</div>
          {filtered.length>150&&<p className="method-note">Showing the first 150. Refine the team search to find others.</p>}
        </div>
        <div className="live-spotlight">{selected && <><span className="feature-kicker">PROGRAM INTELLIGENCE / #{selected.rank}</span><h3>{selected.name}</h3><p className="team-conference">{selected.conference||"Conference identity not verified"}{selected.conferenceVerified?" · NCAA team source matched":""}{selected.divisionIConfirmed===true?" · Source D-I group":selected.divisionIConfirmed===false?" · Source non-D-I":" · Division unverified"}</p><div className="live-rating">{selected.projectedRating.toFixed(0)}<small>PROJECTED ELO</small></div>
          <div className="live-stat-grid"><div><span>RECORD</span><strong>{selected.wins}–{selected.losses}</strong></div><div><span>POINT DIFF / GAME</span><strong>{selected.marginPerGame?.toFixed(1) ?? "—"}</strong></div><div><span>AVG OPP ELO</span><strong>{selected.opponentAverageElo?.toFixed(0) ?? "—"}</strong></div><div><span>FORM ADJUSTMENT</span><strong>{selected.trend >= 0 ? "+" : ""}{selected.trend.toFixed(1)}</strong></div>
            <div><span>ADAPTIVE ELO / CAUSAL</span><strong>{selected.adaptiveRating?.toFixed(0)||"—"}</strong></div>
            <div><span>RECENT VOLATILITY</span><strong>{selected.volatility?.toFixed(1)??"—"}</strong></div></div>
          <div className="live-efficiency"><span className="feature-kicker">POSSESSION-BASED PROFILE</span><div className="efficiency-grid"><div><small>ADJUSTED OFF / 100</small><strong>{selected.adjOff100?.toFixed(1)??"—"}</strong></div><div><small>ADJUSTED DEF / 100</small><strong>{selected.adjDef100?.toFixed(1)??"—"}</strong></div><div><small>ADJ NET / 100</small><strong>{selected.adjNet100?.toFixed(1)??"—"}</strong></div><div><small>PACE (POSSESSIONS)</small><strong>{selected.pacePossessions?.toFixed(1)??"—"}</strong></div></div>
             <small>{selected.possessionGames?selected.possessionGames+" verified box-score team-games · ridge-adjusted opponent strength":"No verified possession box score for this program yet"}</small></div>
          <TeamTrend team={selected.name} ratings={selected.history}/>
          <div className="spotlight-separator"/>
          <label className="feature-kicker" htmlFor="live-opponent">NEUTRAL-COURT MATCHUP VS</label>
          <select id="live-opponent" className="live-opponent-select" value={opponent?.teamId} onChange={e=>setOpponentId(e.target.value)}>{teams.map(t=><option key={t.teamId} value={t.teamId}>{t.name}</option>)}</select>
          <label className="live-model-toggle">MATCHUP MODEL
            <select value={probabilityModel} onChange={e=>setProbabilityModel(e.target.value as "elo"|"calibrated"|"blend")}>
              <option value="elo">Uncalibrated regular Elo</option>
              <option value="calibrated" disabled={!data.historicalCalibration}>Historical-calibrated trend</option>
              <option value="blend" disabled={!data.historicalCalibration}>Held-out-year ensemble</option>
            </select>
          </label>
          {data.historicalCalibration && <div className="live-model-source">Prior-season calibration: through {data.historicalCalibration.trainedThroughSeason} · temperature {data.historicalCalibration.temperature.toFixed(2)} · ensemble weight {(data.historicalCalibration.blendWeight*100).toFixed(0)}%. Extrapolating historical neutral-tournament calibration to this regular-season matchup has not been validated for 2027.</div>}
          {probability !== null && <div className="live-probability"><strong>{pct(probability)}</strong><span>{probabilityModel==="elo"||!data.historicalCalibration?"BASE ELO WIN CHANCE":probabilityModel==="calibrated"?"HISTORICAL CALIBRATED SCENARIO":"HISTORICAL ENSEMBLE SCENARIO"}</span><div className="prob-bar"><div style={{width:pct(probability)}}/></div><small>{pct(1-probability)} for {opponent.name}</small></div>}
          {probability===null&&<p className="method-note">Choose another team to compare.</p>}
          <p className="method-note">Live Elo probabilities have not been calibrated on 2027 tournaments. Adjusted offensive/defensive ratings are possession-based **descriptive** team-box estimates, not a validated replacement for Elo probabilities.</p>
        </>}</div>
      </div>:<div className="scoreboard-grid">{data.recentGames?.map(g=><div className="scorecard" key={g.id}><div><span>FINAL · {g.date}</span><small>NCAA ID {g.id}</small></div><div className="scoreline"><strong>{g.away}</strong><b>{g.awayScore}</b></div><div className="scoreline"><strong>{g.home}</strong><b>{g.homeScore}</b></div></div>)}</div>}
      <p className="source-note">SportsDataverse republishes NCAA statistics; the source may lag the latest tip-off or exclude games not yet captured. The 2027 NCAA team/conference crosswalk links only exact names and does not certify tournament eligibility. Historic Kaggle team IDs are never silently joined. Data after Selection Sunday is excluded from the pre-tournament rating snapshot. The 2027 NCAA men's field will have 76 teams and 12 Opening Round games; selection odds are not yet available. <a href="https://www.ncaa.com/news/basketball-men/article/2026-05-07/2027-march-madness-mens-ncaa-tournament-schedule-dates" target="_blank" rel="noreferrer">Official format ↗</a></p>
    </>}
  </section>;
}
