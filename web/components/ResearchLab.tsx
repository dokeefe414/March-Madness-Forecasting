"use client";

import { useEffect, useMemo, useState } from "react";

type Method = "coin_flip" | "elo" | "trend_elo" | "calibrated_trend_elo" | "logistic";
type Metric = {games: number; brier: number; logLoss: number; accuracy: number};
type Bin = {lower: number; upper: number; count: number; confidence: number | null; accuracy: number | null};
type Report = {
  schemaVersion: number;
  evaluatedYears: number;
  firstTestSeason: number;
  lastTestSeason: number;
  sourceCommit: string;
  minTrainingSeasons: number;
  aggregate: Record<Method, Metric>;
  reliability: Record<Method, Bin[]>;
  seasonBlockUncertainty: Partial<Record<Method, {deltaBrierVsElo: number; interval95: number[]; samples: number}>>;
  yearByYear: Array<{season: number; evaluatedGames: number; trainingThrough: number; models: Record<Method, Metric>; calibrationTemperature: number; logisticWeights?: number[]}>;
};
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || "";
const methods: Array<[Method, string]> = [
  ["coin_flip", "Coin flip"], ["elo", "Standard Elo"], ["trend_elo", "Form-adjusted Elo"],
  ["calibrated_trend_elo", "Calibrated Elo"], ["logistic", "Trained logistic"],
];
const label = (id: Method) => methods.find(([key]) => key === id)?.[1] ?? id;
const metricDisplay = (value: number, metric: keyof Metric) =>
  metric === "accuracy" ? (value * 100).toFixed(1) + "%" : value.toFixed(4);
const colors = ["#8dffc5", "#9bd9ff", "#ffb77c", "#d5bcff"];

function ReliabilityChart({bins}:{bins: Bin[]}) {
  const points = bins.filter((b) => b.count > 0 && b.confidence != null && b.accuracy != null);
  const px = (v: number) => 64 + (v - .5) * 1050;
  const py = (v: number) => 316 - (v - .5) * 550;
  return <div className="chart-shell">
    <div className="chart-top"><strong>DOES CONFIDENCE MATCH REALITY?</strong><span>HISTORICAL FAVORITE RELIABILITY</span></div>
    <svg viewBox="0 0 675 355" role="img" aria-label="Predicted favorite confidence compared with observed favorite accuracy; the diagonal is perfect calibration">
      <defs><linearGradient id="calibrationFade" x1="0" y1="0" x2="1" y2="0"><stop stopColor="#8dffc5"/><stop offset="1" stopColor="#9bd9ff"/></linearGradient></defs>
      {[.5,.6,.7,.8,.9,1].map(t => {
        const x = 64 + (t-.5)*1120;
        const y = 316 - (t-.5)*560;
        return <g key={t}>
          <line x1={x} x2={x} y1="36" y2="316" stroke="#28434b" strokeDasharray="3 6"/>
          <line x1="64" x2="624" y1={y} y2={y} stroke="#28434b" strokeDasharray="3 6"/>
          <text x={x} y="336" fill="#91a7b3" fontSize="12" textAnchor="middle">{(t*100).toFixed(0)}%</text>
          <text x="49" y={y+4} fill="#91a7b3" fontSize="12" textAnchor="end">{(t*100).toFixed(0)}%</text>
        </g>;
      })}
      <line x1="64" y1="316" x2="624" y2="36" stroke="#748894" strokeWidth="2" strokeDasharray="7 7"/>
      {points.length > 1 && <polyline fill="none" stroke="url(#calibrationFade)" strokeWidth="4" strokeLinejoin="round"
        points={points.map(p => (64+(p.confidence!-.5)*1120) + "," + (316-(p.accuracy!-.5)*560)).join(" ")}/>}
      {points.map((p, i) => <circle key={i} cx={64+(p.confidence!-.5)*1120} cy={316-(p.accuracy!-.5)*560} r={Math.max(4,Math.min(11,Math.sqrt(p.count)/3))} fill="#8dffc5" stroke="#0d1d27" strokeWidth="2">
        <title>{p.count} games · {(p.confidence!*100).toFixed(1)}% confidence · {(p.accuracy!*100).toFixed(1)}% accuracy</title>
      </circle>)}
      <text x="344" y="352" fill="#a4b9c2" fontSize="12" textAnchor="middle">Predicted favorite confidence →</text>
    </svg>
    <div className="chart-legend"><span><i className="legend-model"/> Model reliability</span><span><i className="legend-reference"/> Perfect calibration</span></div>
  </div>;
}

export default function ResearchLab() {
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState("");
  const [method, setMethod] = useState<Method>("calibrated_trend_elo");
  const [metric, setMetric] = useState<"brier" | "logLoss" | "accuracy">("brier");
  useEffect(() => {
    let ignore = false;
    fetch(basePath + "/research/benchmark.json").then(r => {
      if (!r.ok) throw new Error("Research report has not been generated for this deployment.");
      return r.json();
    }).then((r: Report) => {
      if (ignore) return;
      if (!r.aggregate?.elo || !r.yearByYear?.length || !r.reliability) throw new Error("Unexpected benchmark report schema");
      setReport(r);
    }).catch((e: Error) => { if(!ignore) setError(e.message); });
    return () => { ignore = true; };
  }, []);
  const ranking = useMemo(() => report ? methods
    .filter(([key]) => report.aggregate[key])
    .sort((a,b) => {
      const x = report.aggregate[a[0]][metric], y = report.aggregate[b[0]][metric];
      return metric === "accuracy" ? y - x : x - y;
    }) : [], [report, metric]);
  const interval = report?.seasonBlockUncertainty?.[method];
  return <section className="content-section research-exp">
    <div className="section-heading">
      <div><span className="section-kicker">05 / THE EVIDENCE ROOM</span><h2>Research <span>laboratory</span></h2>
        <p>Blind held-out seasons, not cherry-picked games. Inspect calibration, model comparisons, and uncertainty.</p></div>
      <span className="research-pill">OPEN METHODOLOGY</span>
    </div>
    <div className="feature-banner research-banner"><div className="banner-copy"><span className="feature-kicker">PREDICTIONS, NOT PROMISES</span><h3>THE PROOF<br/><em>IS IN THE BACKTEST.</em></h3><p>Every score comes from historical tournament games that were not used to fit that year's model. Better accuracy is earned, not assumed.</p></div><div className="large-glyph" aria-hidden="true">∑</div></div>
    {!report && <div className="premium-empty" role={error ? "alert" : "status"}><strong>{error ? "RESEARCH REPORT UNAVAILABLE" : "LOADING ANALYSIS"}</strong><p>{error || "Loading the reproducible benchmark…"}</p><p>Generate locally with <code>PYTHONPATH=research python -m forecast.benchmark --out web/public/research/benchmark.json</code>.</p></div>}
    {report && <>
      <div className="mini-metrics">
        <div><small>HELD-OUT SEASONS</small><strong>{report.evaluatedYears}</strong><span>{report.firstTestSeason}–{report.lastTestSeason}</span></div>
        <div><small>EVALUATED GAMES</small><strong>{report.aggregate.elo.games.toLocaleString()}</strong><span>Actual NCAA matchups</span></div>
        <div><small>MODEL COMPARISONS</small><strong>{methods.filter(m => report.aggregate[m[0]]).length}</strong><span>Same holdout games</span></div>
        <div><small>CALIBRATION CUTOFF</small><strong>PAST</strong><span>Never test-year tuning</span></div>
      </div>
      <div className="research-grid">
        <div className="research-card">
          <div className="research-card-head"><div><small>MODEL LEADERBOARD</small><h3>Let the data decide.</h3></div>
            <label>METRIC<select value={metric} onChange={e => setMetric(e.target.value as "brier" | "logLoss" | "accuracy")}><option value="brier">Brier error ↓</option><option value="logLoss">Log loss ↓</option><option value="accuracy">Winner accuracy ↑</option></select></label></div>
          <div className="research-leaderboard">
            {ranking.map(([key, name], i) => {
              const val = report.aggregate[key][metric];
              const baseline = report.aggregate.coin_flip[metric];
              const baselineBound = metric === "accuracy" ? .8 : metric === "brier" ? .3 : .8;
              const pct = metric === "accuracy" ? val / baselineBound * 100 : (1 - val / baselineBound) * 100;
              return <button className={method === key ? "research-leader active" : "research-leader"} key={key} onClick={()=>setMethod(key)}>
                <span className="ranking-index">{String(i+1).padStart(2,"0")}</span>
                <span className="leader-description"><strong>{name}</strong><small>{key === "logistic" ? "Earlier-year learned coefficients" : key === "coin_flip" ? "No features" : key === "calibrated_trend_elo" ? "Past-year log-loss temperature" : "Fixed formula"}</small><span className="leaderbar"><i style={{width:Math.max(4,Math.min(100,pct))+"%"}}/></span></span>
                <strong className="leader-value">{metricDisplay(val, metric)}</strong>
              </button>;
            })}
          </div>
          <p className="method-note">{metric === "accuracy" ? "Higher is better; ties count 0.5." : "Lower is better. Every model scored the same " + report.aggregate.elo.games.toLocaleString() + " historical outcomes in the current report."} The 50/50 model is the reference baseline.</p>
        </div>
        <div className="research-card reliability-card">
          <div className="research-card-head"><div><small>CALIBRATION DIAGNOSTIC</small><h3>{label(method)}</h3></div>
            <label>MODEL<select value={method} onChange={e => setMethod(e.target.value as Method)}>{methods.filter(([key])=>report.aggregate[key]).map(([key,name])=><option value={key} key={key}>{name}</option>)}</select></label></div>
          <ReliabilityChart bins={report.reliability[method] ?? []}/>
          <div className="calibration-insight">
            <span className="feature-kicker">SEASON-BLOCK 95% INTERVAL</span>
            {interval ? <><strong>{interval.deltaBrierVsElo >= 0 ? "+" : ""}{interval.deltaBrierVsElo.toFixed(4)} <small>Brier vs Elo</small></strong><p>Interval: {interval.interval95[0].toFixed(4)} to {interval.interval95[1].toFixed(4)}. {interval.interval95[0] <= 0 && interval.interval95[1] >= 0 ? "Includes zero: improvement may be sampling noise." : "Does not cross zero in this descriptive resampling."}</p></> : <p>Standard Elo is the reference model.</p>}
          </div>
        </div>
      </div>
      <div className="research-card year-by-year"><div className="research-card-head"><div><small>CHRONOLOGICAL HOLDOUTS</small><h3>Season by season, no peeking.</h3></div><span className="research-pill">{report.firstTestSeason}—{report.lastTestSeason}</span></div>
        <div className="year-table-wrap"><table className="year-table"><thead><tr><th>TEST YEAR</th><th>TRAINED THROUGH</th><th>GAMES</th><th>ELO BRIER</th><th>{label(method).toUpperCase()} BRIER</th><th>Δ VS ELO</th></tr></thead><tbody>{[...report.yearByYear].reverse().map(row => <tr key={row.season}><td><strong>{row.season}</strong></td><td>{row.trainingThrough}</td><td>{row.evaluatedGames}</td><td>{row.models.elo.brier.toFixed(4)}</td><td>{row.models[method]?.brier.toFixed(4) ?? "—"}</td><td className={(row.models[method]?.brier ?? 0) < row.models.elo.brier ? "positive" : "negative"}>{((row.models[method]?.brier ?? 0)-row.models.elo.brier).toFixed(4)}</td></tr>)}</tbody></table></div>
      </div>
      <p className="source-note">Only completed historical regular seasons are evaluated. The model sees actual historical opponent pairs; it does not predict which teams the committee selected or future bracket paths. Logistic regression uses base Elo, recent adjustment, and in-season win percentage; possession-adjusted offense/defense data is not available in the committed archive. Season-bootstrap intervals are descriptive, not a guarantee of future results. <a target="_blank" rel="noreferrer" href="https://github.com/dokeefe414/March-Madness-Forecasting/blob/main/docs/validation.md">Read full methodology ↗</a></p>
    </>}
  </section>;
}
