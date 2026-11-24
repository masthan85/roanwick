import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { expectNoHorizontalScroll, signIn } from "./helpers";

const PUBLIC = ["/", "/services", "/services/home-cleaning/regular-cleaning", "/services/home-cleaning/end-of-tenancy-cleaning", "/how-it-works", "/trust", "/help", "/contact", "/login", "/signup", "/join", "/legal/terms", "/book/regular-cleaning"];

for (const path of PUBLIC) {
  test(`accessibility (WCAG 2.2 AA rules): ${path}`, async ({ page }) => {
    await page.goto(path);
    await page.waitForLoadState("load");
    await page.waitForTimeout(600);
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
    const serious = results.violations.filter((v) => ["serious", "critical"].includes(v.impact ?? ""));
    expect(serious.map((v) => `${v.id}: ${v.help} (${v.nodes.length})`), "serious or critical accessibility violations").toEqual([]);
  });
}

test("accessibility: signed-in customer, professional and admin screens", async ({ page }) => {
  for (const [email, path] of [["priya@example.com", "/account"], ["elena@example.com", "/pro"], ["admin@roanwick.example", "/admin"], ["admin@roanwick.example", "/admin/finance"], ["admin@roanwick.example", "/admin/security"], ["admin@roanwick.example", "/admin/catalogue"]]) {
    await page.context().clearCookies();
    await signIn(page, email);
    await page.goto(path);
    await page.waitForTimeout(1200);
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
    const serious = results.violations.filter((v) => ["serious", "critical"].includes(v.impact ?? ""));
    expect(serious.map((v) => `${path} ${v.id}: ${v.help}`), "serious or critical violations").toEqual([]);
  }
});

test.describe("mobile layout", () => {
  test.use({ viewport: { width: 375, height: 800 } });
  for (const path of ["/", "/services/home-cleaning/regular-cleaning", "/book/regular-cleaning", "/help", "/join", "/login"]) {
    test(`no sideways scroll at 375px: ${path}`, async ({ page }) => {
      await page.goto(path);
      await page.waitForTimeout(500);
      await expectNoHorizontalScroll(page);
    });
  }
  test("mobile navigation opens, lists the main links and closes", async ({ page }) => {
    await page.goto("/");
    const toggle = page.getByRole("button", { name: "Open menu" });
    await toggle.click();
    await expect(page.getByRole("navigation", { name: "Mobile" }).getByRole("link", { name: "Trust and safety" })).toBeVisible();
    await page.getByRole("button", { name: "Close menu" }).click();
    await expect(page.getByRole("navigation", { name: "Mobile" })).toHaveCount(0);
  });
});

test("keyboard users get a skip link and a visible focus target", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to main content" })).toBeFocused();
});

test("unknown pages show a helpful 404", async ({ page }) => {
  const res = await page.goto("/definitely-not-a-page");
  expect(res?.status()).toBe(404);
  await expect(page.getByRole("heading", { name: "We could not find that page" })).toBeVisible();
});
