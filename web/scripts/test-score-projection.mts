import assert from "node:assert/strict";
import test from "node:test";
import {estimateScore} from "../lib/scoreProjection.ts";
import type {Team} from "../lib/models.ts";
const team=(teamId:string,name:string,pointsForPerGame:number,pointsAgainstPerGame:number,wins=7,losses=2):Team=>({
 teamId,name,rank:1,rating:1520,projectedRating:1520,trend:0,wins,losses,history:[1500,1520],
 pointsForPerGame,pointsAgainstPerGame
});
test("a neutral projected spread matches the two derived scores and combined total",()=>{
 const home=team("h","Home",84,70),away=team("a","Away",74,77);
 const r=estimateScore(home,away);
 assert.ok(r);
 assert.equal(r.homePoints,80.5);
 assert.equal(r.awayPoints,72);
 assert.equal(r.homeMargin,8.5);
 assert.equal(r.spread,8.5);
 assert.equal(r.total,152.5);
 assert.equal(r.favorite,"Home");
});
test("a team may be the away favorite without an invented bookmaker line",()=>{
 const r=estimateScore(team("h","Home",66,84),team("a","Away",82,65));
 assert.ok(r);
 assert.equal(r.favorite,"Away");
 assert.equal(r.spread,17.5);
 assert.equal(r.methodKind,"raw-scoring-means");
});
test("refuses too few games, missing values, suspicious score fields and self matchups",()=>{
 const home=team("h","Home",80,70),away=team("a","Away",85,68);
 assert.equal(estimateScore({...home,wins:3,losses:1},away),null);
 assert.equal(estimateScore({...home,pointsForPerGame:undefined},away),null);
 assert.equal(estimateScore({...home,pointsForPerGame:205},away),null);
 assert.equal(estimateScore(home,{...away,teamId:"h"}),null);
});
test("identical scoring estimates produce pick'em with zero projected spread",()=>{
 const r=estimateScore(team("h","Home",75,75),team("a","Away",75,75));
 assert.ok(r);
 assert.equal(r.favorite,"Even");
 assert.equal(r.spread,0);
});

test("prefers opponent-adjusted possession rates when both teams have verified box-score support",()=>{
 const home={...team("h","Home",84,70),adjOff100:116,adjDef100:98,
   offRating100:113,defRating100:102,pacePossessions:69,possessionGames:9};
 const away={...team("a","Away",74,77),adjOff100:109,adjDef100:105,
   offRating100:107,defRating100:106,pacePossessions:71,possessionGames:8};
 const r=estimateScore(home,away);
 assert.ok(r);
 assert.equal(r.methodKind,"opponent-adjusted-possessions");
 assert.equal(r.expectedPossessions,70);
 assert.equal(r.observedPossessionGames,8);
 const anchor=(113+102+107+106)/4;
 assert.equal(r.homePoints,Math.round(116*105/anchor*.7*10)/10);
 assert.equal(r.awayPoints,Math.round(109*98/anchor*.7*10)/10);
 assert.equal(r.total,Math.round((r.homePoints+r.awayPoints)*10)/10);
});
test("fails closed to scoring baseline when adjusted efficiency is missing or coverage is thin",()=>{
 const home={...team("h","Home",84,70),adjOff100:116,adjDef100:98,
   offRating100:113,defRating100:102,pacePossessions:69,possessionGames:9};
 const away={...team("a","Away",74,77),adjOff100:109,adjDef100:105,
   offRating100:107,defRating100:106,pacePossessions:71,possessionGames:3};
 assert.equal(estimateScore(home,away)?.methodKind,"raw-scoring-means");
 assert.equal(estimateScore(home,{...away,possessionGames:9,pacePossessions:110})?.methodKind,"raw-scoring-means");
 assert.equal(estimateScore(home,{...away,possessionGames:9,adjDef100:undefined})?.methodKind,"raw-scoring-means");
});
test("venue neutrality is symmetric when teams swap places",()=>{
 const a={...team("a","A",82,70),adjOff100:112,adjDef100:99,
   offRating100:112,defRating100:99,pacePossessions:68,possessionGames:7};
 const b={...team("b","B",74,78),adjOff100:105,adjDef100:108,
   offRating100:105,defRating100:108,pacePossessions:72,possessionGames:7};
 const ab=estimateScore(a,b),ba=estimateScore(b,a);
 assert.ok(ab&&ba);
 assert.equal(ab.homePoints,ba.awayPoints);
 assert.equal(ab.awayPoints,ba.homePoints);
 assert.equal(ab.homeMargin,-ba.homeMargin);
});
