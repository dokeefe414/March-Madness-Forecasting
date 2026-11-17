"use client";
import {useMemo} from "react";
import type {Team} from "../lib/models";
import {estimateScore} from "../lib/scoreProjection";
export default function ScoreProjection({home,away,neutralSite,winProbability}:{home:Team|undefined;away:Team|undefined;neutralSite:boolean;winProbability:number|null}){
 const score=useMemo(()=>estimateScore(home,away),[home,away]);
 return <section className="v14-score-projection" aria-label="Experimental game score and spread projection">
   <div className="v13-feature-head"><span className="section-kicker">RESEARCH / SOURCE-BASED SCORING + PROJECTED MARGIN</span>
    <h3>THE SCORE <em>SCENARIO.</em></h3>
    <p>Estimated final score, point difference and total. Uses verified opponent-adjusted possession efficiency when both teams have sufficient data; otherwise an explicitly labeled scoring-average baseline. Not a sportsbook line or calibrated probability.</p></div>
   {!score?<div className="v14-empty-result"><strong>NOT ENOUGH VERIFIED SCORING DATA</strong>
    <p>At least five source-recorded games per team and both teams&apos; scored/allowed points per game are required. We won&apos;t fill missing values with invented estimates.</p>
    </div>:<>
     <p className="v12-subtle"><strong>{score.methodKind==="opponent-adjusted-possessions"?"OPPONENT-ADJUSTED POSSESSION MODEL":"FALLBACK: UNADJUSTED SCORING MEANS"}</strong> · {score.method}</p>
     <div className="v14-projected-score">
       <div><small>AWAY · {away?.name}</small><strong>{score.awayPoints.toFixed(1)}</strong></div>
       <span>—</span>
       <div><small>HOME · {home?.name}</small><strong>{score.homePoints.toFixed(1)}</strong></div>
     </div>
     <div className="v14-projection-metrics">
       <div><small>PROJECTED SPREAD</small><strong>{score.favorite==="Even"?"PICK'EM":score.favorite+" −"+score.spread.toFixed(1)}</strong>
        <span>A model-implied point difference, not a bookmaker&apos;s handicap</span></div>
       <div><small>ESTIMATED TOTAL</small><strong>{score.total.toFixed(1)}</strong><span>Combined projected points</span></div>
       <div><small>{score.expectedPossessions!=null?"EXPECTED PACE":"EVIDENCE"}</small><strong>{score.expectedPossessions!=null?score.expectedPossessions.toFixed(1):score.awayGames+" / "+score.homeGames}</strong><span>{score.observedPossessionGames!=null?score.observedPossessionGames+" source-linked possession games per team minimum":"Away/home source-recorded games; possession coverage insufficient"}</span></div>
     </div>
     {winProbability!=null&&((score.homeMargin>0)!==(winProbability>.5))&&score.homeMargin!==0&&winProbability!==.5&&
       <p className="v14-projection-warning">The simple points-based spread favors a different team than the main Elo win-probability forecast. These are independent models; do not interpret the score estimate as an explanation of the Elo percentage.</p>}
     <p className="v12-subtle">{neutralSite?"Listed game is neutral-site.":"Listed game is not neutral-site, but this elementary estimate has no fitted home-court scoring adjustment."} The opponent-adjusted projection (where available) combines each team&apos;s NCAA-derived per-100-possession offense with the opponent&apos;s adjusted defense and the average observed tempo. When source possession data are insufficient, the fallback averages scored/allowed points per game. Neither method incorporates injuries, rest, verified betting lines, or a validated game-margin distribution. Score projection is research-only and is <strong>not</strong> added to the real first-pick accuracy ledger.</p>
   </>}
 </section>;
}
