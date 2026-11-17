import {expect, test} from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

async function section(page: import("@playwright/test").Page, label:string) {
  const button=page.locator("button:visible").filter({hasText:new RegExp("^"+label+"$")}).first();
  await expect(button).toBeVisible();
  await button.click();
}

test("v0.6 workspaces navigate without synthetic predictions",async ({page},testInfo)=>{
  await page.goto("/");
  await expect(page.getByRole("heading",{name:/Current pulse/i})).toBeVisible();
  await section(page,"Field Watch");
  await expect(page.getByRole("heading",{name:/Field watchlist/i})).toBeVisible();
  await expect(page.getByText(/ZERO LOCKS YET/i)).toBeVisible();
  await section(page,"Picks Ledger");
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
  for (const name of ["Field Watch","Picks Ledger","Research","Historical","Bracket"]) {
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
  await section(page,"Field Watch");
  const result=await new AxeBuilder({page}).withTags(["wcag2a","wcag2aa","wcag21a","wcag21aa"]).analyze();
  const severe=result.violations.filter(v=>v.impact==="critical");
  expect(severe.map(v=>v.id+": "+v.description)).toEqual([]);
});
