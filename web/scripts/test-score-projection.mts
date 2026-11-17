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
 assert.equal(r.method.includes("neutral-court"),true);
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
