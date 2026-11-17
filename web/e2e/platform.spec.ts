import {expect, test} from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

async function section(page: import("@playwright/test").Page, label:string) {
  const button=page.locator("button:visible").filter({hasText:new RegExp("^"+label+"$")}).first();
  await expect(button).toBeVisible();
  await button.click();
}

test("v0.8 game-first workspaces navigate without synthetic predictions",async ({page},testInfo)=>{
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
  for (const name of ["Find a Game","2027 Pulse","Accuracy & Picks","Field Watch","Research","Historical","Bracket"]) {
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

test("game finder supports sourced fixture search, explanations and opponent evidence",async ({page})=>{
  // Hermetic browser fixture: never rely on ESPN / NCAA network in CI.
  const fixture="2027-01-15T20:00:00Z";
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
      games:[{eventId:"test-fixture-1",scheduledStartUtc:fixture,scheduledEasternDate:"2027-01-15",
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
});
