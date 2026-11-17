import {expect, test} from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

async function section(page: import("@playwright/test").Page, label:string) {
  const button=page.locator("button:visible").filter({hasText:new RegExp("^"+label+"$")}).first();
  await expect(button).toBeVisible();
  await button.click();
}

test("v0.9 games, real accuracy, models and historical workspaces navigate",async ({page},testInfo)=>{
  await page.goto("/");
  await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
  await expect(page.getByRole("heading",{name:/Game intelligence/i})).toBeVisible();
  await section(page,"2027 Pulse");
  await expect(page.getByRole("heading",{name:/Current pulse/i})).toBeVisible();
  await section(page,"Field Watch");
  await expect(page.getByRole("heading",{name:/Field watchlist/i})).toBeVisible();
  await expect(page.getByText(/ZERO LOCKS YET/i)).toBeVisible();
  await section(page,"Accuracy & Picks");
  await expect(page.getByRole("heading",{name:/Prediction ledger/i})).toBeVisible();
  await expect(page.getByText(/NO HINDSIGHT/i)).toBeVisible();
  await section(page,"Model Lab");
  await expect(page.locator("#model-lab")).toBeVisible();
  await expect(page.getByRole("heading",{name:/WHICH MODEL EARNS THE PICK/i})).toBeVisible();
  await section(page,"Research");
  await expect(page.getByRole("heading",{name:/Research laboratory/i})).toBeVisible();
  await section(page,"Historical");
  await expect(page.getByRole("heading",{name:/Power rankings/i})).toBeVisible();
  await section(page,"Matchups");
  await expect(page.getByRole("heading",{name:/Matchup lab/i})).toBeVisible();
  await section(page,"Bracket");
  await expect(page.getByRole("heading",{name:/Bracket laboratory/i})).toBeVisible();
  await expect(page.getByRole("button",{name:/SIMULATE FULL FIELD/i})).toBeVisible({timeout:20000});
  await page.getByRole("button",{name:/SIMULATE FULL FIELD/i}).click();
  await expect(page.locator(".bracket-results")).toBeVisible({timeout:20000});
  await section(page,"Archive");
  await expect(page.getByRole("heading",{name:/Tournament archive/i})).toBeVisible();
  await page.screenshot({path:"test-results/"+testInfo.project.name+"-archive.png",fullPage:true});
});

test("at supported breakpoints, no viewport-wide horizontal overflow",async ({page},testInfo)=>{
  await page.goto("/");
  for (const name of ["Find a Game","2027 Pulse","Accuracy & Picks","Model Lab","Field Watch","Research","Historical","Bracket"]) {
    await section(page,name);
    await page.waitForTimeout(120);
    const size=await page.evaluate(()=>({
      content:document.documentElement.scrollWidth,
      viewport:document.documentElement.clientWidth,
    }));
    expect(size.content, name+" overflow").toBeLessThanOrEqual(size.viewport+3);
  }
  await page.screenshot({path:"test-results/"+testInfo.project.name+"-layout.png",fullPage:true});
});

test("core page has no critical WCAG violations",async ({page})=>{
  await page.goto("/");
  await section(page,"Find a Game");
  const result=await new AxeBuilder({page}).withTags(["wcag2a","wcag2aa","wcag21a","wcag21aa"]).analyze();
  const severe=result.violations.filter(v=>v.impact==="critical");
  expect(severe.map(v=>v.id+": "+v.description)).toEqual([]);
});

test("game finder supports sourced fixture search, explanations and opponent evidence",async ({page},testInfo)=>{
  // Hermetic browser fixture: never rely on ESPN / NCAA network in CI.
  const fixture=new Date(Date.now()+3*24*60*60*1000).toISOString();
  const profile=(name:string,id:string,elo:number)=>({
    name,teamId:id,rating:elo,trend:3,wins:7,losses:3,
    conference:"Example conference",opponentAverageElo:1502,
    pointsForPerGame:id==="ncaa-home"?82:74,pointsAgainstPerGame:id==="ncaa-home"?72:77,
    recentGames:[{id:"old",date:"2027-01-10",opponent:"Example University",
      home:true,for:80,against:71,outcome:"W"}],ratingHistory:[1500,elo]
  });
  const away=profile("Example Away","ncaa-away",1510);
  const home=profile("Example Home","ncaa-home",1540);
  await page.route("**/current/2027.json",route=>route.fulfill({
    contentType:"application/json",body:JSON.stringify({mode:"current",season:2027,
      retrievedAtUtc:"2027-01-15T12:00:00Z",lastGameDate:"2027-01-14",
      teams:[{...away,rank:2,projectedRating:1513},{...home,rank:1,projectedRating:1543}]}),
  }));
  await page.route("**/current/upcoming.json",route=>route.fulfill({
    contentType:"application/json",body:JSON.stringify({schemaVersion:1,
      generatedAtUtc:"2027-01-15T12:00:00Z",ratingRetrievedAtUtc:"2027-01-15T12:00:00Z",
      lastIncludedGameDate:"2027-01-14",
      coverage:{futureScheduled:1,eligibleForecasts:1,unmatchedOrAmbiguous:0},
      games:[{eventId:"test-fixture-1",scheduledStartUtc:fixture,scheduledEasternDate:fixture.slice(0,10),
        neutralSite:false,home:"Example Home",away:"Example Away",homeTeamId:"ncaa-home",awayTeamId:"ncaa-away",homeWinProbability:.69,
        baselineHomeWinProbability:.65,status:"ready",model:"as-of regular-season Elo",
        homeProfile:home,awayProfile:away,
        factors:[{title:"Strength gap",value:30,detail:"Earlier results influence Elo."},
                 {title:"Venue adjustment",value:65,detail:"Home-court assumption."}],
        commonOpponents:[{opponent:"Example University",homeResultDate:"2027-01-10",
          awayResultDate:"2027-01-11",homeMargin:9,awayMargin:2}],
        headToHead:[]}]})
  }));
  await page.goto("/");
  await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
  await expect(page.getByRole("heading",{name:/Game intelligence/i})).toBeVisible();
  await expect(page.getByLabel("Search upcoming games")).toBeVisible();
  await expect(page.locator(".gc-fixture")).toHaveCount(1);
  await page.locator(".gc-fixture").first().click();
  await expect(page.locator(".gc-detail")).toContainText("69.0%");
  await expect(page.locator(".gc-detail")).toContainText("Example University");
  await expect(page.getByRole("region",{name:"Experimental game score and spread projection"})).toContainText("79.5");
  await expect(page.getByRole("region",{name:"Experimental game score and spread projection"})).toContainText("73.0");
  await expect(page.getByRole("region",{name:"Experimental game score and spread projection"})).toContainText("−6.5");
  await expect(page.getByLabel("Hypothetical team A")).toBeVisible();
  await expect(page.getByLabel("Hypothetical team B")).toBeVisible();
  await page.screenshot({path:"test-results/"+testInfo.project.name+"-game-intelligence.png",fullPage:true});
});

test("v0.9 model lab has deep link, source-honest unavailable forward evidence and one-click game exit",async ({page})=>{
  await page.goto("/?view=models");
  await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
  await expect(page.locator("#model-lab")).toBeVisible();
  await expect(page.getByRole("heading",{name:/WHICH MODEL EARNS THE PICK/i})).toBeVisible();
  await expect(page.getByRole("button",{name:/Opponent-aware research/i})).toBeVisible();
  await page.getByRole("button",{name:/Opponent-aware research/i}).click();
  await expect(page.locator(".ml-focus")).toContainText("PREVIOUS-date Elo");
  await page.getByRole("button",{name:/FIND A REAL GAME/i}).click();
  await expect(page.getByRole("heading",{name:/GAME INTELLIGENCE/i})).toBeVisible();
});

test("v0.9 real archived event snapshots render before-tipoff timeline and verifiable missed-game receipt",async ({page})=>{
  const tipoff=new Date(Date.now()+2*24*60*60*1000).toISOString();
  const fixtureData={schemaVersion:1,
    generatedAtUtc:new Date(Date.now()-60*60*1000).toISOString(),
    ratingRetrievedAtUtc:new Date(Date.now()-90*60*1000).toISOString(),
    coverage:{futureScheduled:1,eligibleForecasts:1,unmatchedOrAmbiguous:0},
    games:[{
      eventId:"upcoming-test",scheduledStartUtc:tipoff,scheduledEasternDate:tipoff.slice(0,10),
      neutralSite:false,status:"ready",home:"Example Home",away:"Example Away",
      homeTeamId:"h",awayTeamId:"a",homeWinProbability:.7,baselineHomeWinProbability:.68,
      model:"as-of regular-season Elo",homeProfile:{name:"Example Home",teamId:"h",
        rating:1550,trend:2,wins:7,losses:3,recentGames:[],ratingHistory:[1500,1550]},
      awayProfile:{name:"Example Away",teamId:"a",rating:1510,trend:1,wins:6,losses:4,
        recentGames:[],ratingHistory:[1500,1510]},factors:[],headToHead:[],commonOpponents:[],
    }]
  };
  const first=new Date(Date.now()-36*60*60*1000).toISOString();
  const second=new Date(Date.now()-12*60*60*1000).toISOString();
  const index={uniqueGames:{settledUniqueGames:1,forecastedUniqueGames:2,
      score:{accuracy:0,games:1,brier:.64}},
    snapshots:[
      {id:"snap-earliest",generatedAtUtc:first,count:1,
        predictions:[{eventId:"upcoming-test",homeWinProbability:.60,model:"Elo"}]},
      {id:"snap-next",generatedAtUtc:second,count:1,
        predictions:[{eventId:"upcoming-test",homeWinProbability:.70,model:"Elo"}]},
      {id:"snap-old",generatedAtUtc:"2026-11-06T11:00:00Z",count:1,
        predictions:[{eventId:"finished-test",homeWinProbability:.8,model:"Elo"}]},
    ],
    settlements:[{eventId:"finished-test",predictionKey:"snap-old:finished-test",
      actualResultDate:"2026-11-07",home:"Example Home",away:"Example Away",
      homeScore:60,awayScore:72,predictedHome:.8,observedHome:0,brier:.64,
      winnerCorrect:0,forecastAtUtc:"2026-11-06T11:00:00Z",
      scheduledStartUtc:"2026-11-07T23:00:00Z",espnFinalVerified:true}]
  };
  await page.route("**/current/upcoming.json",r=>r.fulfill({contentType:"application/json",body:JSON.stringify(fixtureData)}));
  await page.route("**/current/2027.json",r=>r.fulfill({contentType:"application/json",body:JSON.stringify({
    mode:"current",season:2027,teams:[{name:"Example Home",teamId:"h",rating:1550,wins:7,losses:3},
      {name:"Example Away",teamId:"a",rating:1510,wins:6,losses:4}]
  })}));
  await page.route("**/forecasts/index.json",r=>r.fulfill({contentType:"application/json",body:JSON.stringify(index)}));
  await page.route("**/current/archive-health.json",r=>r.fulfill({contentType:"application/json",body:JSON.stringify({
    status:"current",message:"Source-verified archive available",lastArchiveUtc:second})}));
  await page.goto("/?game=upcoming-test");
  await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
  await expect(page.getByRole("heading",{name:/GAME INTELLIGENCE/i})).toBeVisible();
  await expect(page.locator(".ga-history")).toContainText("2 originally published captures");
  await expect(page.locator(".ga-probability")).toContainText("60.0%");
  await expect(page.locator(".ga-probability")).toContainText("70.0%");
  await page.locator(".gc-recent-settled button").first().click();
  await expect(page.locator(".ga-postgame")).toContainText("MISSED");
  await expect(page.locator(".ga-postgame")).toContainText("FINAL");
  await expect(page).toHaveURL(/game=finished-test/);
});

test("v1.1 daily shortcuts and empty-source navigation remain keyboard accessible",async ({page})=>{
  await page.goto("/");
  await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
  await expect(page.getByRole("navigation",{name:"Explore March Forecast"})).toBeVisible();
  await expect(page.getByRole("link",{name:/TODAY'S GAMES/i})).toBeVisible();
  await page.getByRole("navigation",{name:"Explore March Forecast"}).getByRole("button",{name:/ROAD TO MARCH/i}).click();
  await expect(page.getByRole("heading",{name:/Field watchlist/i})).toBeVisible();
  await section(page,"Find a Game");
  await expect(page.getByRole("heading",{name:/Game intelligence/i})).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(page.locator("body")).toBeVisible();
});
test("v1.1 model lab labels new challengers as retrospective, not public picks",async ({page})=>{
  await page.goto("/?view=models");
  await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
  await expect(page.getByRole("heading",{name:/Bayesian & residual learning/i})).toBeVisible();
  await expect(page.getByRole("heading",{name:/Is the model drifting/i})).toBeVisible();
  await expect(page.getByText(/Strict previous-date replay/i)).toBeVisible();
});

test("v1.2 team intelligence deep links and game evidence page exist",async ({page})=>{
 // Hermetic source-backed mock: the repository does not commit generated
 // /current artifacts (they are built by the Pages publication workflow).
 const team=(id:string,name:string,rating:number)=>({teamId:id,name,rank:1,rating,projectedRating:rating,trend:4,wins:6,losses:2,history:[1500,rating],conference:"Example League",conferenceVerified:true,
   opponentAverageElo:1490,adjOff100:109,adjDef100:97,pacePossessions:67});
 const retrievedAtUtc="2026-11-17T12:00:00Z";
 await page.route("**/current/2027.json",route=>route.fulfill({contentType:"application/json",body:JSON.stringify({
   season:2027,mode:"current",retrievedAtUtc,teams:[team("ncaa-duke","Duke",1550),team("ncaa-unc","North Carolina",1510)]})}));
 await page.route("**/current/2027-games.json",route=>route.fulfill({contentType:"application/json",body:JSON.stringify({
   season:2027,retrievedAtUtc,games:[{id:"game-1",date:"2026-11-16",home:"Duke",away:"North Carolina",homeScore:78,awayScore:72}]})}));
 await page.route("**/current/upcoming.json",route=>route.fulfill({contentType:"application/json",body:JSON.stringify({
   games:[{eventId:"next-1",homeTeamId:"ncaa-duke",awayTeamId:"ncaa-unc",home:"Duke",away:"North Carolina",scheduledStartUtc:new Date(Date.now()+3*86400000).toISOString(),homeWinProbability:.6}]})}));
 await page.goto("/?view=teams");
 await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
 await expect(page.getByRole("heading",{name:/TEAM INTELLIGENCE/i})).toBeVisible();
 await expect(page.getByRole("textbox",{name:"Search teams"})).toBeVisible();
 await expect(page.locator(".v12-team-detail")).toBeVisible({timeout:20000});
 await page.getByRole("textbox",{name:"Search teams"}).fill("Duke");
 await expect(page.locator(".v12-team-scroll button").first()).toBeVisible();
});
test("v1.2 bracket pick-em has rounds, chooser and reset",async ({page})=>{
 await page.goto("/?view=bracket");
 await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
 await expect(page.getByRole("button",{name:/SIMULATE FULL FIELD/i})).toBeVisible({timeout:20000});
 await expect(page.getByRole("heading",{name:/Build your own bracket/i})).toBeVisible();
 await expect(page.getByRole("group",{name:"Tournament round"})).toBeVisible();
 await page.getByRole("group",{name:"Tournament round"}).getByRole("button",{name:"ROUND OF 64"}).click();
 await expect(page.locator(".v12-match").first()).toBeVisible();
 await page.locator(".v12-match button:enabled").first().click();
 await expect(page.getByText(/available games picked/)).toBeVisible();
 await page.getByRole("button",{name:"RESET PICKS"}).click();
 await expect(page.getByText(/Bracket picks reset/)).toBeVisible();
});
test("v1.2 installable manifest and settlement diagnostic shell load",async ({page})=>{
 await page.goto("/?view=predictions");
 await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
 await expect(page.getByRole("heading",{name:/Prediction ledger/i})).toBeVisible();
 await expect(page.getByRole("heading",{name:/What happened after the pick/i})).toBeVisible();
 const manifest=await page.request.get("/manifest.webmanifest");
 expect(manifest.status()).toBe(200);
 const json=await manifest.json();
 expect(json.name).toMatch(/March Forecast/);
});

test("v1.3 two independent bracket players can disagree on identical matchups",async ({page})=>{
 await page.goto("/?view=bracket");
 await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
 const duel=page.getByRole("region",{name:"Two-player bracket competition"});
 await expect(duel.getByRole("heading",{name:/TWO PLAYERS/i})).toBeVisible({timeout:20000});
 await duel.getByRole("group",{name:"Duel round"}).getByRole("button",{name:"ROUND OF 64"}).click();
 // A historical play-in seed can leave one entrant pending in some first-round
 // matches. Pick an actual two-entrant fixture rather than clicking a disabled
 // legitimate "winner pending" placeholder.
 const game=duel.locator(".v13-duel-match").filter({has:page.locator("button:last-of-type:not([disabled])")}).first();
 await expect(game.getByRole("button")).toHaveCount(2);
 await expect(game.getByRole("button").last()).toBeEnabled();
 await game.getByRole("button").first().click();
 await duel.getByRole("group",{name:"Active bracket competitor"}).getByRole("button",{name:"PLAYER B"}).click();
 await game.getByRole("button").last().click();
 await expect(duel.getByRole("heading",{name:/HEAD-TO-HEAD DIFFERENCES/i})).toBeVisible();
 await expect(duel.getByText(/A: .* B:/)).toBeVisible();
});
test("v1.3 operations checklist exposes verifiable source evidence",async ({page})=>{
 await page.route("**/current/operations.json",route=>route.fulfill({contentType:"application/json",body:JSON.stringify({
  state:"review",archiveStatus:"current",checkedAtUtc:"2026-11-17T17:30:00Z",lastSuccessfulCaptureUtc:"2026-11-17T15:08:46Z",
  captureAgeHours:2.4,checkedSourceEvents:175,unmatchedSourceEvents:33,uniqueArchivedEvents:142,
  repeatSnapshots:0,uniqueSettledEvents:0,delayedSnapshotEntries:1,sourceWarnings:[],
  checks:[{name:"Verified-final backlog",state:"review",detail:"1 source final awaiting independent validation"}],
  delayedExamples:[{eventId:"123",home:"Duke",away:"UNC",hoursSinceListedStart:53}]
 })}));
 await page.goto("/?view=predictions");
 await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
 const panel=page.getByRole("region",{name:"Public forecast operations and source quality"});
 await expect(panel.getByRole("heading",{name:/Can we trust the feed/i})).toBeVisible({timeout:15000});
 await expect(panel.getByText(/ARCHIVE REVIEW/i)).toBeVisible();
 await expect(panel.getByText("Verified-final backlog")).toBeVisible();
});
test("v1.3 Model Lab differentiates fitted research from prospectively verified picks",async ({page})=>{
 await page.route("**/current/advanced-models.json",route=>route.fulfill({contentType:"application/json",body:JSON.stringify({
  mode:"research-only",retrievedAtUtc:"2026-11-17T15:00:00Z",evaluatedGames:80,
  methods:{elo:{games:80,brier:.228,accuracy:.56,logLoss:.67},
   bayesianGaussian:{games:80,brier:.221,accuracy:.58,logLoss:.65},
   gradientBoostedTrees:{games:80,brier:.23,accuracy:.54,logLoss:.68}},
  perDate:[{date:"2026-11-13",games:20,eloBrier:.22,bayesianBrier:.21,gradientBoostedBrier:.23},
           {date:"2026-11-14",games:20,eloBrier:.23,bayesianBrier:.22,gradientBoostedBrier:.24}]
 })}));
 await page.goto("/?view=models");
 await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
 const panel=page.getByRole("region",{name:"Interactive prediction research visualizations"});
 await expect(panel.getByRole("heading",{name:/Explore the evidence/i})).toBeVisible({timeout:15000});
 await expect(panel.getByText("Gradient-boosted CART")).toBeVisible();
 await expect(panel.getByText(/No truly settled first picks|Only earliest archived pregame predictions/i)).toBeVisible();
});

test("verified first-pick results show correct and missed without counting duplicate captures",async ({page})=>{
 const first="2026-11-16T13:00:00Z";
 const after="2026-11-17T17:00:00Z";
 const rows=[
  {eventId:"f1",date:"2026-11-17",scheduledStartUtc:"2026-11-17T23:00:00Z",forecastAtUtc:first,
   home:"Example Home",away:"Example Away",homeScore:68,awayScore:71,predictedHome:.8,observedHome:0,
   predictedWinner:"Example Home",actualWinner:"Example Away",correct:false,brier:.64,model:"Elo"},
  {eventId:"f2",date:"2026-11-17",scheduledStartUtc:"2026-11-17T23:00:00Z",forecastAtUtc:first,
   home:"Example Two",away:"Example Three",homeScore:81,awayScore:75,predictedHome:.7,observedHome:1,
   predictedWinner:"Example Two",actualWinner:"Example Two",correct:true,brier:.09,model:"Elo"}
 ];
 const index={
   schemaVersion:1,generatedAtUtc:after,
   snapshots:[{id:"a",generatedAtUtc:first,count:2,predictions:[]},
              {id:"b",generatedAtUtc:after,count:1,predictions:[]}],
   settlements:[],scores:{settledPredictions:3,brier:.3,logLoss:.6,winnerAccuracy:.67},
   uniqueGames:{forecastedUniqueGames:2,settledUniqueGames:2,verifiedOutcomes:rows,
     score:{games:2,accuracy:.5,brier:.365,logLoss:.6},
     byModel:{Elo:{games:2,accuracy:.5,brier:.365}},
     reference:{pairedGames:2,eloBrier:.365,actualModelBrier:.365},
     shadowComparison:{pairedGames:0,eloBrier:null,challengerBrier:null,challengerBrierGain:null},
     trajectory:[],calibration:[],recentMisses:[]},
 };
 await page.route("**/forecasts/index.json",r=>r.fulfill({contentType:"application/json",body:JSON.stringify(index)}));
 await page.goto("/?view=predictions");
 await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
 const outcomes=page.getByRole("region",{name:"Correct and missed original before-tipoff predictions"});
 await expect(outcomes.locator(".v14-outcome")).toHaveCount(2);
 await expect(outcomes.getByText("CORRECT FAVORITES")).toBeVisible();
 await expect(outcomes.locator(".v14-result-metrics")).toContainText("1");
 await expect(outcomes.locator(".v14-outcome.is-right")).toContainText("Example Two");
 await expect(outcomes.locator(".v14-outcome.is-wrong")).toContainText("Example Away");
 await outcomes.getByRole("button",{name:"MISSED"}).click();
 await expect(outcomes.locator(".v14-outcome")).toHaveCount(1);
 await expect(outcomes.locator(".v14-outcome")).toContainText("MISSED PICK");
 await outcomes.getByRole("button",{name:"CORRECT"}).click();
 await expect(outcomes.locator(".v14-outcome")).toHaveCount(1);
 await expect(outcomes.locator(".v14-outcome")).toContainText("CORRECT PICK");
});

test("score predictor declines unavailable per-game points rather than inventing a spread",async ({page})=>{
 const fixture=new Date(Date.now()+4*86400000).toISOString();
 const baseTeam=(name:string,teamId:string)=>({
  teamId,name,rank:1,rating:1500,projectedRating:1500,trend:0,wins:3,losses:1,history:[1500]});
 const away=baseTeam("Away","a"),home=baseTeam("Home","h");
 await page.route("**/current/2027.json",r=>r.fulfill({contentType:"application/json",body:JSON.stringify({
  mode:"current",season:2027,teams:[home,away]})}));
 await page.route("**/current/upcoming.json",r=>r.fulfill({contentType:"application/json",body:JSON.stringify({
   schemaVersion:1,coverage:{futureScheduled:1,eligibleForecasts:1,unmatchedOrAmbiguous:0},
   games:[{eventId:"score-test",scheduledStartUtc:fixture,scheduledEasternDate:fixture.slice(0,10),
    neutralSite:true,status:"ready",home:"Home",away:"Away",homeTeamId:"h",awayTeamId:"a",
    homeWinProbability:.55,baselineHomeWinProbability:.55,
    homeProfile:{...home,conference:"Test",recentGames:[],ratingHistory:[1500]},
    awayProfile:{...away,conference:"Test",recentGames:[],ratingHistory:[1500]},factors:[]}]
 })}));
 await page.goto("/");
 await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
 const score=page.getByRole("region",{name:"Experimental game score and spread projection"});
 await expect(score).toContainText("NOT ENOUGH VERIFIED SCORING DATA");
 await expect(score).not.toContainText("PROJECTED SPREAD");
});
