import { expect, Page } from "@playwright/test";

export const DEMO_PASSWORD = process.env.E2E_DEMO_PASSWORD ?? "DemoPass-2026!";

export async function signIn(page: Page, email: string, password = DEMO_PASSWORD) {
  await page.goto("/login");
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL((u) => !u.pathname.startsWith("/login"));
}

export const uniqueEmail = (p = "e2e") => `${p}+${Date.now()}${Math.floor(Math.random() * 1000)}@example.com`;

export async function expectNoHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow, "page should not scroll sideways").toBeLessThanOrEqual(1);
}

/** Next streams page content in behind a hidden template and swaps it in. For a few milliseconds two copies exist in the DOM,
 *  which breaks strict locators. Wait for the swap to finish before interacting. */
export async function settled(page: Page) {
  await page.waitForLoadState("load");
  await page.waitForFunction(() => !document.querySelector('[hidden][id^="S:"]'));
}
