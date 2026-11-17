"use client";

import { useEffect, useMemo, useState } from "react";
import rawData from "../data/rankings.json";
import yearIndex from "../data/history-index.json";
import { matchupProbability, type RatingsDataset } from "../lib/models";
import FullBracketLab from "./FullBracketLab";
import ResearchLab from "./ResearchLab";
import LiveSeason from "./LiveSeason";
import GameCenter from "./GameCenter";
import ModelLab from "./ModelLab";
import SelectionLab from "./SelectionLab";
import ForecastTracker from "./ForecastTracker";
import TeamIntelligence from "./TeamIntelligence";

const initialData = rawData as RatingsDataset;
const initialTeams = [...initialData.teams].sort((a, b) => b.projectedRating - a.projectedRating);
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || "";
type TournamentArchive = {
  season: number;
  champion: string | null;
  mainDrawOnly: boolean;
  note: string;
  teams: Record<string, string>;
  seeds: Record<string, string>;
  games: Array<{ day?: number; round?: string; winnerId: string; loserId: string; winnerScore: number; loserScore: number }>;
};
type Tab = "games" | "teams" | "models" | "current" | "selection" | "predictions" | "rankings" | "compare" | "bracket" | "research" | "history" | "method";
type Sort = "rank" | "momentum" | "wins";

function percent(value: number): string {
  return (value * 100).toFixed(1) + "%";
}

function Sparkline({ values, large = false }: { values: number[]; large?: boolean }) {
  const width = 300;
  const height = large ? 126 : 52;
  const low = Math.min(...values) - 6;
  const high = Math.max(...values) + 6;
  const range = Math.max(high - low, 1);
  const points = values.map((value, index) => {
    const x = (index / Math.max(values.length - 1, 1)) * width;
    const y = 10 + (1 - (value - low) / range) * (height - 20);
    return [x, y];
  });
  const line = points.map((p, i) => (i === 0 ? "M" : "L") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ");
  return (
    <svg className={large ? "sparkline sparkline-large" : "sparkline"} viewBox={"0 0 " + width + " " + height} role="img" aria-label="Historical team rating trend">
      <line x1="0" y1={height - 10} x2={width} y2={height - 10} stroke="#23364a" strokeDasharray="4 7" />
      <path d={line} fill="none" stroke="#77e7bc" strokeWidth={large ? "3.5" : "2.5"} strokeLinecap="round" strokeLinejoin="round" />
      {points.length > 0 && <circle cx={points[points.length - 1][0]} cy={points[points.length - 1][1]} r="4" fill="#e9ffb4" />}
    </svg>
  );
}

function Delta({ value }: { value: number }) {
  const positive = value >= 0;
  return <span className={positive ? "delta positive" : "delta negative"}>{positive ? "+" : ""}{value.toFixed(1)}</span>;
}

function DataDisclaimer({ data }: { data: RatingsDataset }) {
  return (
    <div className="disclaimer" role="note">
      <span className="disclaimer-icon">i</span>
      <div><strong>{data.mode === "demo" ? "Demonstration data" : "Historical snapshot"}</strong><span>{data.mode === "demo" ? " All teams, records, and ratings on this page are synthetic examples — not NCAA rankings or real March 2027 predictions." : " Ratings reflect historical games through the displayed cutoff; these are model estimates, not NCAA rankings or live results."}</span></div>
    </div>
  );
}

export default function Dashboard() {
  const [data, setData] = useState<RatingsDataset>(initialData);
  const [selectedYear, setSelectedYear] = useState(initialData.season);
  const [loadStatus, setLoadStatus] = useState<"idle" | "loading" | "error">("idle");
  const [archive, setArchive] = useState<TournamentArchive | null>(null);
  const [archiveStatus, setArchiveStatus] = useState<"idle" | "loading" | "error">("idle");
  const sortedTeams = useMemo(() => [...data.teams].sort((a, b) => b.projectedRating - a.projectedRating), [data]);
  const [tab, setTab] = useState<Tab>("games");
  useEffect(()=>{
    const requested=new URLSearchParams(window.location.search).get("view");
    const supported:Tab[]=["games","teams","current","predictions","models","selection","rankings","compare","bracket","research","history","method"];
    if(requested && supported.includes(requested as Tab))setTab(requested as Tab);
  },[]);
  function changeTab(next:Tab){
    setTab(next);
    window.scrollTo({top:0,behavior:"instant"});
    const url=new URL(window.location.href);
    url.searchParams.set("view",next);
    window.history.replaceState(null,"",url.toString());
  }
  function openTeam(teamId:string){
    const url=new URL(window.location.href);
    url.searchParams.set("view","games");
    url.searchParams.set("team",teamId);
    url.searchParams.delete("game");
    window.history.pushState(null,"",url.toString());
    setTab("games");
  }
  // SSR markup may be visible before React attaches navigation handlers.
  // A deterministic hydration signal lets browser tests avoid lost clicks.
  const [hydrated,setHydrated] = useState(false);
  useEffect(()=>setHydrated(true),[]);
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<Sort>("rank");
  const [detailId, setDetailId] = useState(initialTeams[0]?.teamId ?? "");
  const [teamAId, setTeamAId] = useState(initialTeams[0]?.teamId ?? "");
  const [teamBId, setTeamBId] = useState(initialTeams[1]?.teamId ?? "");

  const teamA = sortedTeams.find((t) => t.teamId === teamAId) ?? sortedTeams[0];
  const teamB = sortedTeams.find((t) => t.teamId === teamBId) ?? sortedTeams[1];
  const detail = sortedTeams.find((t) => t.teamId === detailId) ?? sortedTeams[0];
  const leader = sortedTeams[0];

  const visible = useMemo(() => {
    const rows = sortedTeams.filter((team) => team.name.toLowerCase().includes(search.trim().toLowerCase()));
    if (sort === "momentum") rows.sort((a, b) => b.trend - a.trend);
    if (sort === "wins") rows.sort((a, b) => b.wins - a.wins);
    return rows;
  }, [search, sort, sortedTeams]);

  const probA = teamA && teamB ? matchupProbability(teamA.projectedRating, teamB.projectedRating) : 0.5;

  async function loadYear(year: number) {
    if (year === selectedYear) return;
    setLoadStatus("loading");
    try {
      const response = await fetch(basePath + "/seasons/" + year + ".json");
      if (!response.ok) throw new Error("Season unavailable");
      const snapshot = (await response.json()) as RatingsDataset;
      if (snapshot.mode !== "historical" || snapshot.season !== year || !Array.isArray(snapshot.teams) || snapshot.teams.length < 2) {
        throw new Error("Unexpected archive format");
      }
      const ordered = [...snapshot.teams].sort((a, b) => b.projectedRating - a.projectedRating);
      setData(snapshot);
      setSelectedYear(year);
      setDetailId(ordered[0].teamId);
      setTeamAId(ordered[0].teamId);
      setTeamBId(ordered[1].teamId);
      setSearch("");
      setSort("rank");
      setArchive(null);
      setArchiveStatus("idle");
      setLoadStatus("idle");
    } catch (error) {
      console.error(error);
      setLoadStatus("error");
    }
  }

  async function loadTournamentArchive() {
    setArchiveStatus("loading");
    try {
      const response = await fetch(basePath + "/tournaments/" + selectedYear + ".json");
      if (!response.ok) throw new Error("Tournament archive unavailable");
      const parsed = (await response.json()) as TournamentArchive;
      if (parsed.season !== selectedYear || !Array.isArray(parsed.games)) throw new Error("Unexpected tournament archive");
      setArchive(parsed);
      setArchiveStatus("idle");
    } catch (error) {
      console.error(error);
      setArchiveStatus("error");
    }
  }

  return (
    <main data-hydrated={hydrated?"yes":"no"}>
      <div className="site-shell">
        <a className="skip-content" href="#main-content">SKIP TO CONTENT</a>
        <header className="site-header">
          <button className="brand" onClick={() => changeTab("games")} aria-label="March Forecast home">
            <span className="brand-mark">M<span>F</span></span>
            <span className="brand-title">MARCH<span>FORECAST</span></span>
          </button>
          <nav aria-label="Main navigation" className="desktop-nav">
            {([["games", "Find a Game"], ["teams", "Teams"], ["current", "2027 Pulse"], ["predictions", "Accuracy & Picks"], ["models", "Model Lab"], ["selection", "Field Watch"], ["rankings", "Historical"], ["compare", "Matchups"], ["bracket", "Bracket"], ["research", "Research"], ["history", "Archive"], ["method", "About"]] as [Tab, string][]).map(([id, label]) => (
              <button key={id} className={tab === id ? "nav-link active" : "nav-link"} onClick={() => changeTab(id)}>{label}</button>
            ))}
          </nav>
          <a className="github-link" href="https://github.com/dokeefe414/March-Madness-Forecasting" target="_blank" rel="noreferrer">VIEW CODE <span aria-hidden="true">↗</span></a>
        </header>

        <div className="mobile-nav" aria-label="Page sections">
          {([["games", "Find a Game"], ["current", "2027 Pulse"], ["predictions", "Accuracy & Picks"], ["models", "Model Lab"], ["selection", "Field Watch"], ["rankings", "Historical"], ["compare", "Matchups"], ["bracket", "Bracket"], ["research", "Research"], ["history", "Archive"], ["method", "About"]] as [Tab, string][]).map(([id, label]) => (
            <button key={id} className={tab === id ? "mobile-link active" : "mobile-link"} onClick={() => changeTab(id)}>{label}</button>
          ))}
        </div>

        <div id="main-content" tabIndex={-1}/>
        {tab === "rankings" && (<>
        <section className="hero">
          <div className="hero-main">
            <div className="eyebrow"><span className="live-dot" /> COLLEGE BASKETBALL INTELLIGENCE <span className="eyebrow-rule" /> RESEARCH PREVIEW</div>
            <h1>THE NUMBERS <span>BEHIND</span> THE MADNESS<span className="headline-period">.</span></h1>
            <p className="hero-copy">Power rankings that move with the season. Head-to-head probabilities you can challenge. Research-backed models you can inspect, historical seasons you can replay, and a verified new-season data pulse.</p>
            <div className="hero-buttons">
              <button className="button-primary" onClick={() => changeTab("current")}>EXPLORE 2027 SEASON <span aria-hidden="true">↗</span></button>
              <button className="button-outline" onClick={() => changeTab("research")}>VIEW THE RESEARCH <span aria-hidden="true">→</span></button>
            </div>
            <div className="hero-footnote">SEASON {data.season} <span>✳</span> {data.mode === "demo" ? "SYNTHETIC MODEL SCENARIO" : "HISTORICAL RESULTS SNAPSHOT"} <span>✳</span> NO PAYWALLS</div>
          </div>
          {leader && (
            <div className="hero-panel">
              <div className="panel-top"><span>MODEL LEADER</span><span>#{leader.rank.toString().padStart(2, "0")}</span></div>
              <div className="panel-team">{leader.name}</div>
              <div className="panel-metric"><strong>{leader.projectedRating.toFixed(1)}</strong><span>PROJECTED<br />ELO RATING</span></div>
              <div className="panel-chart"><Sparkline values={leader.history} large /></div>
              <div className="panel-bottom"><span>RECENT FORECAST ADJUSTMENT</span><Delta value={leader.trend} /></div>
              <div className="panel-diagonal" aria-hidden="true" />
            </div>
          )}
        </section>

        <DataDisclaimer data={data} />
        <section className="year-picker-panel" aria-label="Historical season browser">
          <div className="year-picker-info">
            <span className="section-kicker">HISTORICAL DATA EXPLORER</span>
            <strong>42 seasons. Actual NCAA game results.</strong>
            <small>{data.label} · {data.regularSeasonGames?.toLocaleString() ?? "—"} source games · {data.teams.length} teams.</small>
          </div>
          <label className="year-picker-label">SELECT SEASON
            <select aria-label="Select historical season" value={selectedYear} disabled={loadStatus === "loading"} onChange={(event) => void loadYear(Number(event.target.value))}>
              {[...yearIndex.seasons].reverse().map((year) => <option key={year.season} value={year.season}>{year.season}{year.isComplete ? "" : " (partial)"}</option>)}
            </select>
          </label>
          {loadStatus === "loading" && <span className="year-status" role="status">Loading historical season…</span>}
          {loadStatus === "error" && <span className="year-status error" role="alert">Could not load that season. Please retry.</span>}
        </section>

        <section className="metrics-strip" aria-label="Research overview">
          <div className="strip-stat"><span>01 / TRACKED TEAMS</span><strong>{data.teams.length.toString().padStart(2, "0")}</strong><small>{data.mode === "demo" ? "Example programs" : "In this snapshot"}</small></div>
          <div className="strip-stat"><span>02 / RATING SYSTEM</span><strong>ELO<span className="strip-accent">+</span></strong><small>Recent form adjustment</small></div>
          <div className="strip-stat"><span>03 / MATCHUP ENGINE</span><strong>H2H</strong><small>Neutral-court probabilities</small></div>
          <div className="strip-stat"><span>04 / SIMULATOR</span><strong>76</strong><small>2027 field support</small></div>
        </section>

        </>)}
        {(tab === "compare" || tab === "bracket" || tab === "history") && (
          <div className="mode-toolbar">
            <div><span className="feature-kicker">HISTORICAL VIEW / FROZEN NCAA DATA</span><strong>{data.season} season · {data.isComplete ? "complete regular-season cutoff" : "incomplete source cutoff"}</strong></div>
            <label>CHOOSE SEASON<select value={selectedYear} disabled={loadStatus === "loading"} onChange={e => void loadYear(Number(e.target.value))}>
              {[...yearIndex.seasons].reverse().map(y => <option key={y.season} value={y.season}>{y.season}{y.isComplete ? "" : " (partial)"}</option>)}
            </select></label>
            {loadStatus === "error" && <span className="year-status error">Could not load historical season.</span>}
          </div>
        )}
        {tab === "games" && <GameCenter onOpenAccuracy={()=>changeTab("predictions")} onOpenModels={()=>changeTab("models")} onOpenSelection={()=>changeTab("selection")}/>}
        {tab === "teams" && <TeamIntelligence/>}
        {tab === "models" && <ModelLab onOpenGames={()=>changeTab("games")} onOpenAccuracy={()=>changeTab("predictions")}/>}
        {tab === "current" && <LiveSeason onOpenTeam={openTeam}/>}
        {tab === "selection" && <SelectionLab/>}
        {tab === "predictions" && <ForecastTracker/>}
        {tab === "research" && <ResearchLab/>}

        {tab === "rankings" && (
          <section className="content-section" id="rankings">
            <div className="section-heading"><div><div className="section-kicker">01 — THE FIELD</div><h2>Power <span>rankings</span></h2><p>Projected Elo rating based on the current model snapshot. Select a team for its trajectory.</p></div><div className="section-aside">SORTED BY MODEL STRENGTH, NOT AP POLL</div></div>
            <div className="ranking-layout">
              <div className="ranking-card">
                <div className="table-toolbar">
                  <label className="search-field"><span aria-hidden="true">⌕</span><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search for a team..." aria-label="Search teams" /></label>
                  <label className="sort-field">SORT <select value={sort} onChange={(e) => setSort(e.target.value as Sort)} aria-label="Sort rankings"><option value="rank">Power rating</option><option value="momentum">Momentum</option><option value="wins">Wins</option></select></label>
                </div>
                <div className="ranking-table" role="table" aria-label="Model power rankings">
                  <div className="table-heading table-grid" role="row"><span role="columnheader">RANK</span><span role="columnheader">TEAM</span><span role="columnheader">RECORD</span><span role="columnheader">ELO</span><span role="columnheader">PROJECTED</span><span role="columnheader">TREND</span></div>
                  {visible.map((team) => (
                    <button className={detailId === team.teamId ? "ranking-row table-grid selected" : "ranking-row table-grid"} key={team.teamId} onClick={() => setDetailId(team.teamId)} aria-label={"View " + team.name + " rating history"} role="row">
                      <span className="rank-num" role="cell">{team.rank.toString().padStart(2, "0")}</span>
                      <span className="team-name" role="cell"><span className="team-icon">{team.name.slice(0, 2).toUpperCase()}</span>{team.name}</span>
                      <span className="record" role="cell">{team.wins}–{team.losses}</span>
                      <span className="rating-raw" role="cell">{team.rating.toFixed(1)}</span>
                      <span className="rating-projected" role="cell">{team.projectedRating.toFixed(1)}</span>
                      <span role="cell"><Delta value={team.trend} /></span>
                    </button>
                  ))}
                  {visible.length === 0 && <div className="empty-state">No teams match that search.</div>}
                </div>
              </div>
              {detail && (
                <aside className="detail-card">
                  <div className="detail-eyebrow">TEAM SPOTLIGHT / #{detail.rank.toString().padStart(2, "0")}</div>
                  <h3>{detail.name}</h3>
                  <div className="detail-label">PROJECTED RATING</div>
                  <div className="detail-number">{detail.projectedRating.toFixed(1)}</div>
                  <div className="detail-rule" />
                  <div className="detail-label">ELO TRAJECTORY / RECENT GAMES</div>
                  <Sparkline values={detail.history} large />
                  <div className="detail-facts"><div><span>RECORD</span><strong>{detail.wins}–{detail.losses}</strong></div><div><span>FORM ADJUSTMENT</span><Delta value={detail.trend} /></div></div>
                  <button className="detail-cta" onClick={() => { setTeamAId(detail.teamId); setTeamBId(sortedTeams.find((t) => t.teamId !== detail.teamId)?.teamId ?? detail.teamId); changeTab("compare"); }}>COMPARE THIS TEAM <span aria-hidden="true">→</span></button>
                </aside>
              )}
            </div>
          </section>
        )}

        {tab === "compare" && teamA && teamB && (
          <section className="content-section" id="compare">
            <div className="section-heading"><div><div className="section-kicker">02 — HEAD TO HEAD</div><h2>Matchup <span>lab</span></h2><p>Choose any two teams. See what our Elo-based projected-strength baseline expects on a neutral court.</p></div></div>
            <div className="matchup-card">
              <div className="matchup-controls">
                <label>TEAM A<select value={teamAId} onChange={(e) => setTeamAId(e.target.value)}>{sortedTeams.map((team) => <option value={team.teamId} key={team.teamId}>{team.name}</option>)}</select></label>
                <span className="versus">VS</span>
                <label>TEAM B<select value={teamBId} onChange={(e) => setTeamBId(e.target.value)}>{sortedTeams.map((team) => <option value={team.teamId} key={team.teamId}>{team.name}</option>)}</select></label>
              </div>
              {teamAId === teamBId ? (
                <div className="empty-state">Choose two different teams for a matchup.</div>
              ) : (
                <>
                  <div className="matchup-sides"><div><span className="side-caption">TEAM A</span><h3>{teamA.name}</h3><strong>{percent(probA)}</strong><span>CHANCE TO WIN</span></div><div className="matchup-divider">↔</div><div className="side-right"><span className="side-caption">TEAM B</span><h3>{teamB.name}</h3><strong>{percent(1 - probA)}</strong><span>CHANCE TO WIN</span></div></div>
                  <div className="prob-bar" role="img" aria-label={teamA.name + " " + percent(probA) + " vs " + teamB.name + " " + percent(1 - probA)}><div style={{ width: percent(probA) }} /></div>
                  <div className="prob-key"><span>● TEAM A</span><span>TEAM B ●</span></div>
                  <div className="matchup-comparison">
                    <div className="compare-heading"><span>{teamA.name}</span><span>METRIC</span><span>{teamB.name}</span></div>
                    {([["Projected rating", teamA.projectedRating.toFixed(1), teamB.projectedRating.toFixed(1)], ["Current Elo", teamA.rating.toFixed(1), teamB.rating.toFixed(1)], ["Wins", String(teamA.wins), String(teamB.wins)], ["Losses", String(teamA.losses), String(teamB.losses)], ["Recent adjustment", (teamA.trend > 0 ? "+" : "") + teamA.trend.toFixed(1), (teamB.trend > 0 ? "+" : "") + teamB.trend.toFixed(1)]] as string[][]).map(([label, first, second]) => <div className="compare-row" key={label}><strong>{first}</strong><span>{label}</span><strong>{second}</strong></div>)}
                  </div>
                  <p className="method-note">Probabilities are for a neutral-site game and do not incorporate injuries, travel, or opponent-specific styles. These are model estimates, not guarantees.</p>
                </>
              )}
            </div>
          </section>
        )}

        {tab === "bracket" && <FullBracketLab data={data} />}

        {tab === "history" && (
          <section className="content-section" id="history">
            <div className="section-heading"><div><div className="section-kicker">04 — BACK THROUGH MARCH</div><h2>Tournament <span>archive</span></h2><p>Real tournament outcomes, documented season coverage, and frozen pre-tournament Elo evaluation on completed historical seasons.</p></div></div>
            <div className="history-summary">
              <div className="history-stat"><span>SEASON</span><strong>{selectedYear}</strong></div>
              <div className="history-stat"><span>CHAMPION</span><strong>{data.tournament?.champion ?? "No tournament"}</strong></div>
              <div className="history-stat"><span>RESULTS AVAILABLE</span><strong>{data.tournament?.games ?? 0} games</strong></div>
              <div className="history-stat"><span>TOURNAMENT BRIER</span><strong>{data.tournament?.brier == null ? "N/A" : data.tournament.brier.toFixed(4)}</strong></div>
            </div>
            <p className="archive-description">{data.isComplete ? "Regular-season results cover the Kaggle season through Selection Sunday." : "The source regular-season record is incomplete; we do not report a valid tournament score for this incomplete cutoff."} {data.tournament?.mainDrawOnly ? "The 2026 tournament archive includes 63 main-draw games, excluding four First Four play-ins." : ""} When shown, the tournament Brier score uses frozen regular-season ratings and never learns from the games being evaluated.</p>
            <div className="archive-controls">
              <button className="button-primary" onClick={() => void loadTournamentArchive()} disabled={archiveStatus === "loading"}>{archiveStatus === "loading" ? "LOADING…" : archive?.season === selectedYear ? "RELOAD RESULTS" : "VIEW ACTUAL TOURNAMENT GAMES"} <span aria-hidden="true">↗</span></button>
              {archiveStatus === "error" && <span className="year-status error" role="alert">Could not load results. Please retry.</span>}
            </div>
            {archive && archive.season === selectedYear && (
              <div className="archive-results">
                <div className="archive-results-head"><strong>{selectedYear} GAME RESULTS</strong><span>{archive.games.length} games</span></div>
                <p className="method-note">{archive.note}</p>
                {archive.games.length === 0 && <div className="empty-state">No NCAA men's tournament was held in 2020.</div>}
                <div className="archive-list">
                  {[...archive.games].reverse().map((game, index) => (
                    <div className="archive-game" key={index}>
                      <span className="game-round">{game.round || "DAY " + game.day}</span>
                      <strong>{archive.teams[game.winnerId] ?? game.winnerId}</strong>
                      <span className="game-score">{game.winnerScore}–{game.loserScore}</span>
                      <span>{archive.teams[game.loserId] ?? game.loserId}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </section>
        )}

        {tab === "method" && (
          <section className="content-section" id="method">
            <div className="section-heading"><div><div className="section-kicker">05 — OPEN METHODOLOGY</div><h2>Show the <span>work</span></h2><p>Open-source models, leak-aware evaluation, NCAA-source season updates, and simulation assumptions.</p></div></div>
            <div className="method-grid">
              <div className="method-card"><span>01 / DATA</span><h3>Games, in order.</h3><p>Our Python importer reads historical Kaggle regular-season results and team names. Each season is processed chronologically, with optional day cutoffs.</p></div>
              <div className="method-card"><span>02 / RATINGS</span><h3>Transparent Elo.</h3><p>Teams begin at 1500 each season. Opponent strength, game result, and home court determine rating changes. A bounded recent trend creates a simple forward projection.</p></div>
              <div className="method-card"><span>03 / PROBABILITIES</span><h3>Neutral-court matchups.</h3><p>Projected rating differences become head-to-head probabilities through the standard Elo logistic formula. Repeated simulated games produce bracket probabilities.</p></div>
              <div className="method-card"><span>04 / VALIDATION</span><h3>Make predictions testable.</h3><p>The research engine calculates pre-game regular-season Brier scores without using the result being predicted. Held-out-year tournament validation, calibrated probabilities, regularized logistic models and season-block uncertainty are implemented and reported.</p></div>
            </div>
            <div className="method-warning"><strong>NOT CLAIMED:</strong> This is not a trained ARIMA/Kalman model, official selection forecast, injury-aware model, or verified 2027 bracket prediction. The current-season source and historical tournament backtest use different ID spaces and are not silently joined.</div>
          </section>
        )}

        <footer className="footer"><div className="footer-brand">MARCH<span>FORECAST</span><small>RESEARCH-DRIVEN BASKETBALL ANALYTICS</small></div><div className="footer-right"><span>REPRODUCIBLE RESEARCH · PROVENANCE FIRST</span><a href="https://github.com/dokeefe414/March-Madness-Forecasting" target="_blank" rel="noreferrer">GITHUB ↗</a></div></footer>
      </div>
    </main>
  );
}
