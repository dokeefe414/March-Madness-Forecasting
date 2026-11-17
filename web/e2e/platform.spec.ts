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

test("game finder has accessible search, fixture details and honest empty outcomes",async ({page})=>{
  await page.goto("/");
  await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
  await expect(page.getByRole("heading",{name:/Game intelligence/i})).toBeVisible();
  await expect(page.getByLabel("Search upcoming games")).toBeVisible();
  await expect(page.getByLabel("Hypothetical team A")).toBeVisible();
  await expect(page.getByLabel("Hypothetical team B")).toBeVisible();
  // In CI, there may be no external fixture file; do not invent a probability.
  const data=await page.locator(".gc-fixture").count();
  if(data){
    await page.locator(".gc-fixture").first().click();
    await expect(page.locator(".gc-detail")).toBeVisible();
  }else{
    await expect(page.locator(".gc-unmatched").or(page.locator(".premium-empty")).first()).toBeVisible();
  }
});
