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
        neutralSite:false,home:"Example Home",away:"Example Away",homeWinProbability:.69,
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
