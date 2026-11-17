import {expect,test} from "@playwright/test";

/** Executed against the exact same /March-Madness-Forecasting26-27 static
 * mount and Next build env used by production GitHub Pages. Old tests were
 * only verifying the unprefixed local root, which missed this regression.
 */
test.describe("published GitHub Pages historical archive",()=>{
  test.skip(!process.env.E2E_PAGES_BASE,"Run with production Next basePath and static mount.");

  test("loads 2024 and 2023 sourced tournament fields without 404 URLs",async ({page})=>{
    const broken:string[]=[];
    page.on("response",r=>{
      if(/\/(seasons|tournaments)\/\d{4}\.json/.test(r.url()) && r.status()>=400)
        broken.push(r.status()+" "+r.url());
    });
    await page.goto("./?view=bracket");
    await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
    await expect(page.getByRole("heading",{name:/Bracket laboratory/i})).toBeVisible();
    const seasons=page.locator(".mode-toolbar select");
    await expect(seasons).toBeVisible();
    await seasons.selectOption("2024");
    await expect(seasons).toHaveValue("2024");
    await expect(page.locator(".mode-toolbar")).toContainText("2024 season");
    await expect(page.locator(".bracket-exp .mini-metrics")).toBeVisible({timeout:20000});
    await expect(page.locator(".pairings-grid .bracket-match")).toHaveCount(8);
    await seasons.selectOption("2023");
    await expect(page.locator(".mode-toolbar")).toContainText("2023 season");
    await expect(page.locator(".bracket-exp .mini-metrics")).toBeVisible({timeout:20000});
    expect(broken).toEqual([]);
  });

  test("opens actual historical game results after changing years",async ({page})=>{
    await page.goto("./?view=history");
    await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
    await expect(page.getByRole("heading",{name:/Tournament archive/i})).toBeVisible();
    const season=page.locator(".mode-toolbar select");
    await season.selectOption("2024");
    await expect(page.locator(".history-summary")).toContainText("2024");
    await page.getByRole("button",{name:/VIEW ACTUAL TOURNAMENT GAMES/i}).click();
    await expect(page.locator(".archive-results")).toContainText("2024 GAME RESULTS");
    await expect(page.locator(".archive-game")).toHaveCount(67);
    await season.selectOption("2022");
    await expect(page.locator(".history-summary")).toContainText("2022");
    await page.getByRole("button",{name:/VIEW ACTUAL TOURNAMENT GAMES/i}).click();
    await expect(page.locator(".archive-results")).toContainText("2022 GAME RESULTS");
  });

  test("2026 partial bracket explains limitation and still opens real results",async ({page})=>{
    await page.goto("./?view=bracket");
    await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
    const seasons=page.locator(".mode-toolbar select");
    await seasons.selectOption("2026");
    await expect(page.getByRole("alert").filter({hasText:/2026|incomplete/i})).toBeVisible({timeout:15000});
    await page.getByRole("button",{name:/VIEW RECORDED TOURNAMENT RESULTS/i}).click();
    await expect(page.getByRole("heading",{name:/Tournament archive/i})).toBeVisible();
    await page.getByRole("button",{name:/VIEW ACTUAL TOURNAMENT GAMES/i}).click();
    await expect(page.locator(".archive-results")).toContainText("2026 GAME RESULTS");
  });
});
