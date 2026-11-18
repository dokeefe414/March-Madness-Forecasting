"use client";

import { useEffect, useMemo, useState } from "react";
import type { RatingsDataset } from "../lib/models";
import BracketScenario from "./BracketScenario";
import BracketBuilder from "./BracketBuilder";
import BracketDuel from "./BracketDuel";
import {fetchHistoricalJson} from "../lib/historicalAssets";
import {
  buildHistoricalField, simulateFullBracket, firstRoundUpsetCandidates, SEED_ORDER, type BracketArchive,
  type BracketField, type BracketResult,
} from "../lib/fullBracket";


const stages = [
  ["round32", "R32"], ["sweet16", "S16"], ["elite8", "E8"],
  ["final4", "F4"], ["titleGame", "FINAL"], ["champion", "TITLE"],
] as const;
const fmt = (v: number) => (v * 100).toFixed(v < .01 ? 2 : 1) + "%";

export default function FullBracketLab({ data,onOpenArchive }: { data: RatingsDataset;onOpenArchive?:()=>void }) {
  const [archive, setArchive] = useState<BracketArchive | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [message, setMessage] = useState("");
  const [runs, setRuns] = useState(5000);
  const [seed, setSeed] = useState(42);
  const [results, setResults] = useState<BracketResult[] | null>(null);
  const [regionView, setRegionView] = useState("W");
  const [selectedTeam, setSelectedTeam] = useState<string>("");

  useEffect(() => {
    let ignore = false;
    setStatus("loading");
    setResults(null);
    setArchive(null);
    fetchHistoricalJson<BracketArchive>("tournaments",data.season,(value):value is BracketArchive=>{
      const archive=value as Partial<BracketArchive>|null;
      return archive?.season===data.season&&Array.isArray(archive.games)&&
             archive.teams!=null&&typeof archive.teams==="object";
    })
      .then((raw) => {
        if (ignore) return;
        setArchive(raw);setMessage("");setStatus("ready");
      })
      .catch((error: Error) => { if (!ignore) { setMessage(error.message); setStatus("error"); } });
    return () => { ignore = true; };
  }, [data.season]);

  const field = useMemo(() => {
    if (!archive || status !== "ready") return null;
    try { return buildHistoricalField(archive, data.teams); }
    catch { return null; }
  }, [archive, data, status]);
  const error = useMemo(() => {
    if (!archive || status !== "ready") return null;
    try { buildHistoricalField(archive, data.teams); return null; }
    catch (e) { return e instanceof Error ? e.message : "Could not reconstruct field."; }
  }, [archive, data, status]);
  const upsetCandidates=useMemo(()=>field?firstRoundUpsetCandidates(field).slice(0,8):[],[field]);
  const leaders = results?.slice(0, 12) ?? [];
  const active = results?.find((team) => team.teamId === selectedTeam) ?? results?.[0];

  function run() {
    if (!field) return;
    try {
      const evaluated = simulateFullBracket(field, runs, seed);
      setResults(evaluated);
      setSelectedTeam(evaluated[0]?.teamId ?? "");
    } catch (e) { setMessage(e instanceof Error ? e.message : "Simulation failed"); setStatus("error"); }
  }
  return (
    <section className="content-section bracket-exp" id="bracket">
      <div className="section-heading">
        <div>
          <div className="section-kicker">03 / THE ROAD TO THE TITLE</div>
          <h2>Bracket <span>laboratory</span></h2>
          <p>Real historical seeded fields. Simulated probabilities. Every Opening Round matchup accounted for.</p>
        </div>
        <span className="research-pill">REPRODUCIBLE MONTE CARLO</span>
      </div>
      <div className="feature-banner bracket-banner">
        <div className="banner-copy">
          <span className="feature-kicker">HISTORICAL FIELD / {data.season}</span>
          <h3>ONE BRACKET.<br /><em>THOUSANDS OF FUTURES.</em></h3>
          <p>Use the actual archived tournament entrants and frozen regular-season Elo. We model play-ins and every round to the title — without using the games' real outcomes to simulate them.</p>
        </div>
        <div className="big-orb" aria-hidden="true"><span>64</span><small>MAIN DRAW</small></div>
      </div>
      {status === "loading" && <div className="premium-empty" role="status">Loading verified tournament seed data…</div>}
      {(status === "error" || error) && <div className="premium-empty" role="alert"><strong>{error&&data.tournament?.mainDrawOnly?"TOURNAMENT BRACKET IS INCOMPLETE":"FIELD UNAVAILABLE"}</strong><p>{error || message}</p>
        <p>{data.season===2026?"The archived 2026 results do not contain all four First Four seed entrants, so a full 68-team bracket cannot be reconstructed without inventing teams. The actual recorded games remain available in the Tournament Archive.":"Choose a complete historical season such as 2025 or 2024 to view its full sourced bracket."}</p>
        {onOpenArchive&&<button type="button" className="button-outline" onClick={onOpenArchive}>VIEW RECORDED TOURNAMENT RESULTS ↗</button>}
      </div>}
      {field && (
        <>
          <div className="mini-metrics">
            <div><small>ENTRANTS</small><strong>{field.entrants.length}</strong><span>Official historical field</span></div>
            <div><small>OPENING GAMES</small><strong>{field.openingRoundGames}</strong><span>Before 64-team draw</span></div>
            <div><small>SIMULATIONS</small><strong>{runs.toLocaleString()}</strong><span>Per run</span></div>
            <div><small>MODEL</small><strong>ELO+</strong><span>Historical frozen ratings</span></div>
          </div>
          <div className="sim-controls">
            <label>SIMULATION DEPTH<select value={runs} onChange={(e) => setRuns(Number(e.target.value))}>
              <option value={1000}>1,000 runs / quick</option>
              <option value={5000}>5,000 runs / balanced</option>
              <option value={20000}>20,000 runs / detailed</option>
            </select></label>
            <label>REPRODUCIBLE SEED<input type="number" min="0" max="999999" value={seed} onChange={(e) => setSeed(Math.min(999999, Math.max(0, Number(e.target.value) || 0)))} /></label>
            <button className="button-primary" onClick={run}>SIMULATE FULL FIELD <span aria-hidden="true">↗</span></button>
          </div>
          <div className="region-switch" role="group" aria-label="Bracket region">
            {field.regions.map((r) =>
              <button key={r.code} className={regionView === r.code ? "active" : ""} onClick={() => setRegionView(r.code)}>REGION {r.code}</button>)}
          </div>
          <div className="region-canvas">
            <div className="region-header"><div><span>ROUND OF 64 / SEEDED PAIRINGS</span><h3>REGION {regionView}</h3></div><span>32 TEAMS · 16 SEEDS</span></div>
            <div className="pairings-grid">
              {Array.from({length: 8}, (_, i) => {
                const region = field.regions.find((r) => r.code === regionView)!;
                const slots = region.slots.slice(i * 2, i * 2 + 2);
                return <div className="bracket-match" key={i}>
                  <span className="match-num">MATCHUP {String(i+1).padStart(2,"0")}</span>
                  {slots.map((slot) =>
                    <div className="bracket-team-line" key={slot.seed}>
                      <span className="seed-chip">{String(slot.seed).padStart(2,"0")}</span>
                      <span className="match-name">{slot.teams.map((t) => t.name).join(" / ")}</span>
                      {slot.teams.length > 1 && <span className="opening-badge">OPENING</span>}
                    </div>)}
                </div>;
              })}
            </div>
          </div>
          {results ? (
            <div className="bracket-results">
              <div className="result-head"><span>MODEL-BASED ADVANCEMENT PROBABILITIES</span><strong>TOP CONTENDERS / {data.season}</strong></div>
              <div className="bracket-leaderboard">
                <div className="bracket-leaders">
                  {leaders.map((team, index) => <button onClick={() => setSelectedTeam(team.teamId)} key={team.teamId} className={active?.teamId === team.teamId ? "bracket-leader active" : "bracket-leader"}>
                    <span className="contender-index">{String(index + 1).padStart(2,"0")}</span>
                    <span className="contender-info"><strong>{team.name}</strong><small>{team.region} · SEED {team.seed}</small><i style={{width:fmt(team.champion)}} /></span>
                    <strong className="contender-chance">{fmt(team.champion)}</strong>
                  </button>)}
                </div>
                {active && <div className="bracket-spotlight">
                  <span className="feature-kicker">SIMULATION SPOTLIGHT</span>
                  <h3>{active.name}</h3>
                  <p>Chance of advancing to each stage in this historical-field simulation.</p>
                  {stages.map(([key, label]) => <div className="spotlight-stage" key={key}>
                    <div><span>{label}</span><strong>{fmt(active[key])}</strong></div>
                    <div className="sim-track"><div style={{width:fmt(active[key])}} /></div>
                  </div>)}
                  <div className="v20-bracket-summary">
                    <div><small>EXPECTED TOURNAMENT WINS</small><strong>{active.expectedWins.toFixed(2)}</strong></div>
                    <div><small>MC TITLE SAMPLING BAND (95%)</small><strong>{fmt(active.championMonteCarlo95[0])}–{fmt(active.championMonteCarlo95[1])}</strong></div>
                  </div>
                  {active.openingRoundWin !== null && <small>Opening Round win chance: {fmt(active.openingRoundWin)}</small>}
                </div>}
              </div>
            </div>
          ) : <div className="premium-empty"><span className="empty-spark">✳</span><h3>RUN THE TOURNAMENT.</h3><p>The title probability leaderboard and every-round advancement paths will appear here.</p></div>}
          <details className="v20-upsets" aria-label="Historical field model upset scenarios">
            <summary>First-round upset watch · {upsetCandidates.length} seeded matchups</summary>
            <p>Seed-based upsets in the <strong>real sourced historical field</strong>. Only fully resolved Round-of-64 opponents are shown; unplayed First Four winners are not invented. These are Elo-derived model estimates, not actual outcomes or betting odds.</p>
            <div className="v20-upset-grid">
              {upsetCandidates.map(x=><div key={x.underdogId} className="v20-upset-item">
                <span>REGION {x.region} · #{x.underdogSeed} vs #{x.favoriteSeed}</span>
                <strong>{x.underdog} over {x.favorite}</strong>
                <b>{fmt(x.underdogWinProbability)}</b>
              </div>)}
              {!upsetCandidates.length&&<p>No fully sourced opening matchups are available for this field.</p>}
            </div>
          </details>
          <BracketBuilder key={"builder-"+data.season} field={field}/>
          <BracketDuel key={"duel-"+data.season} field={field}/>
          {results&&<BracketScenario key={data.season} field={field} runs={runs} seed={seed} baseline={results}/>}
          <p className="source-note">Expected wins include any First Four win and subsequent round advances. Wilson 95% title bands reflect Monte Carlo sampling error only, not model calibration or uncertainty about team strength. Source: actual archived tournament seeds; team strength frozen before tournament play. Opening Round is modeled for historical 65/68 fields; the simulator also supports a future 76-team / 12-opening-game field when verified seed placements are available. Final Four region crossover uses an illustrative W–X / Y–Z pairing; actual year-specific national semifinal placement may differ. This is not the official 2027 field.</p>
        </>
      )}
    </section>
  );
}
