import { defineConfig, devices } from "@playwright/test";

// The pre-installed Chromium is used when present (CI installs its own via `npx playwright install chromium`).
const executablePath = process.env.CHROMIUM_PATH ?? (require("node:fs").existsSync("/opt/pw-browsers/chromium") ? "/opt/pw-browsers/chromium" : undefined);

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  use: {
    baseURL: process.env.BASE_URL ?? "http://localhost:3000",
    trace: "off",
    locale: "en-GB",
    timezoneId: "Europe/London",
    launchOptions: { executablePath },
  },
  projects: [{ name: "desktop", use: { ...devices["Desktop Chrome"], launchOptions: { executablePath } } }],
});
