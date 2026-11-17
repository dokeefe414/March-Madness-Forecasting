import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  // Avoid duplicate Next compilations and simultaneous mobile/desktop hydration.
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"],["html",{open:"never",outputFolder:"playwright-report"}]] : "list",
  use: {
    baseURL: "http://127.0.0.1:3100",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    viewport: { width: 1440, height: 900 },
  },
  projects: [
    {name:"chromium-desktop", use:{...devices["Desktop Chrome"], viewport:{width:1440,height:900}}},
    {name:"chromium-mobile", use:{...devices["Desktop Chrome"], viewport:{width:390,height:844}}},
  ],
  webServer: {
    // Test the same static artifact delivered by GitHub Pages, not the Turbopack
    // dev HMR server (which can fail WebSocket handshakes under CI).
    command: "npm run build && python3 -m http.server 3100 --bind 127.0.0.1 --directory out",
    url: "http://127.0.0.1:3100",
    timeout: 180_000,
    reuseExistingServer: !process.env.CI,
  },
});
