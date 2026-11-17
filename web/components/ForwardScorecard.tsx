"use client";
/** Forward accuracy comes only from genuine before-tipoff, first-pick game records. */
type Forward = {
  forecastedUniqueGames:number;settledUniqueGames:number;
  score:{games:number;accuracy:number|null;brier:number|null;logLoss:number|null};
  byModel:Record<string,{games:number;accuracy:number|null;brier:number|null}>;
  shadowComparison:{pairedGames:number;eloBrier:number|null;challengerBrier:number|null;challengerBrierGain:number|null};
  reference:{pairedGames:number;eloBrier:number|null;actualModelBrier:number|null};
  trajectory:Array<{date:string;eventId:string;games:number;accuracy:number|null;brier:number|null}>;
  calibration:Array<{bin:string;count:number;predictedConfidence:number|null;realizedAccuracy:number|null}>;
  recentMisses:Array<{eventId:string;date:string;home:string;away:string;probability:number;confidence:number;model:string;note:string}>;
};
const pct=(x:number)=>(x*100).toFixed(1)+"%";
export default function ForwardScorecard({report}:{report:Forward|null|undefined}){
  const count=report?.settledUniqueGames||0;
  const trajectory=report?.trajectory||[];
  return <section className="fp-scoreboard" aria-label="Real unique-game forecasting accuracy">
    <div className="fp-scoreboard-main">
      <div><span className="feature-kicker">REAL GAMES · REAL PUBLIC PRETIPOFF PICKS</span>
        <h3>{report?.score.accuracy!=null?pct(report.score.accuracy):"—"} <small>CORRECT WINNER RATE</small></h3>
        <p>{count} unique settled events, from {report?.forecastedUniqueGames||0} uniquely predicted games.
          Each ESPN event counts only its <strong>earliest archived before-tipoff pick</strong>. We never cherry-pick the most accurate snapshot.</p>
      </div>
      <div className="fp-forward-facts">
        <div><small>UNIQUE GAME BRIER ↓</small><strong>{report?.score.brier?.toFixed(4)??"—"}</strong></div>
        <div><small>PAIRED ELO BRIER ↓</small><strong>{report?.reference.eloBrier?.toFixed(4)??"—"}</strong></div>
        <div><small>SHADOW LOGISTIC BRIER ↓</small><strong>{report?.shadowComparison.challengerBrier?.toFixed(4)??"—"}</strong></div>
      </div>
    </div>
    {count?<div className="fp-trajectory"><span className="feature-kicker">CORRECT WINNER RATE / CUMULATIVE GENUINE SETTLEMENTS</span>
      <svg viewBox="0 0 800 150" role="img" aria-label="Cumulative first-pick winner accuracy through successive settled actual games">
        <line x1="22" y1="15" x2="22" y2="125" stroke="#4c6867"/>
        <line x1="22" y1="125" x2="778" y2="125" stroke="#4c6867"/>
        <line x1="22" y1="70" x2="778" y2="70" stroke="#37544e" strokeDasharray="4 7"/>
        <text x="1" y="18" fill="#aec6c3" fontSize="10">100%</text>
        <text x="1" y="73" fill="#aec6c3" fontSize="10">50%</text>
        <path fill="none" stroke="#affbd1" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round"
          d={trajectory.map((x,i,a)=>(i===0?"M":"L")+" "+(22+756*i/Math.max(1,a.length-1)).toFixed(2)+" "+
                              (125-110*(x.accuracy||0)).toFixed(2)).join(" ")}/>
      </svg><p>Winner selection accuracy is measured on source-settled actual games. Even 50/50 calls contribute only half a correct pick.</p>
    </div>:<p className="fp-empty">No genuine first-archived pretipoff forecasts have settled yet. Accuracy is deliberately unavailable, not 0% or an invented 100%. The historical-date replay score is a different measurement.</p>}
    {!!count&&<div className="fp-analysis">
      <div><span className="feature-kicker">WHICH FROZEN MODEL ACTUALLY PICKED THE WINNER?</span>
        <h4>First-pick model scorecard.</h4>
        <table className="fp-table"><thead><tr><th scope="col">MODEL</th><th scope="col">GAMES</th><th scope="col">CORRECT</th><th scope="col">BRIER ↓</th></tr></thead>
          <tbody>{Object.entries(report?.byModel||{}).map(([name,metric])=><tr key={name}>
            <td>{name}</td><td>{metric.games}</td><td>{metric.accuracy==null?"—":pct(metric.accuracy)}</td><td>{metric.brier?.toFixed(4)??"—"}</td>
          </tr>)}</tbody></table>
        <p>These rows are separated by the actual frozen forecasting policy used at capture; a shadow model is not mislabeled as an active prediction.</p>
      </div>
      <div><span className="feature-kicker">ARE THE CONFIDENCE LEVELS WELL CALIBRATED?</span><h4>Favorite confidence vs results.</h4>
        <div className="fp-calib">{report?.calibration.map(bin=><div key={bin.bin} className="fp-calib-row">
          <span>{bin.bin}</span><div className="fp-calib-bar" aria-label={bin.count+" predictions, realized accuracy "+(bin.realizedAccuracy==null?"unavailable":pct(bin.realizedAccuracy))}>
            <i style={{width:(bin.predictedConfidence==null?0:bin.predictedConfidence*100).toFixed(1)+"%"}}/>
            <b style={{width:(bin.realizedAccuracy==null?0:bin.realizedAccuracy*100).toFixed(1)+"%"}}/>
          </div><small>{bin.count} GAMES</small></div>)}</div>
        <p><span className="fp-key-a">MODEL CONFIDENCE</span> vs <span className="fp-key-b">REALIZED WIN RATE</span>. Bins with zero games are deliberately blank. Small samples produce noisy percentages.</p>
      </div>
    </div>}
    <div className="fp-foot">
      <div><span className="feature-kicker">REVIEW THE MISSES · WITHOUT HINDSIGHT</span>
        <h4>Learning from wrong picks.</h4>
        {report?.recentMisses?.length?report.recentMisses.slice(0,5).map(x=><article className="fp-miss" key={x.eventId}>
          <b>{x.away} at {x.home}</b><small>{x.date} · {x.model} · {pct(x.confidence)} favorite</small>
          <p>{x.note}</p>
        </article>):<p className="fp-empty">No scored first-pick misses are yet archived. That is not evidence of perfect forecasting.</p>}
      </div>
      <div><span className="feature-kicker">THE MODEL EARNS ITS PROMOTION</span>
        <h4>Challenger vs Elo.</h4>
        <p>{report?.shadowComparison?.pairedGames||0} genuinely settled games have both a frozen Elo probability and an earlier pregame learned-model probability. We compare those predictions on the <strong>same outcomes</strong>.</p>
        <p>After a miss, the original pick remains immutable. New previous-day results enter the scheduled retraining, and the model must pass its chronological and forward-performance gates before replacing Elo.</p>
        <a href="https://github.com/dokeefe414/March-Madness-Forecasting/blob/main/docs/forward-performance.md" target="_blank" rel="noreferrer">READ ACCURACY METHODOLOGY ↗</a>
      </div>
    </div>
  </section>;
}