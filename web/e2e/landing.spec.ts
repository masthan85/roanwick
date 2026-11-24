import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { settled } from "./helpers";

test("the hero quote is computed from the live API, not typed into the page", async ({ page, request }) => {
  const off = await (await request.get("/api/v1/catalogue/offerings/regular-cleaning")).json();
  const cfg = await (await request.get("/api/v1/public/config")).json();
  const labour = off.hourly_rate_pence * 3;
  const oven = off.addons.find((a: { code: string }) => a.code === "oven").price_pence;
  const discount = Math.round((labour * off.frequency_discounts.fortnightly) / 10000);
  const total = (labour + oven - discount + cfg.booking_fee_pence) / 100;
  await page.goto("/");
  const card = page.getByLabel("Example quote");
  await expect(card.getByText(`£${total.toFixed(2)}`)).toBeVisible();
  await expect(card.getByText(`£${(labour / 100).toFixed(2)}`).first()).toBeVisible();
});

test("the cancellation section shows the tiers from our settings", async ({ page, request }) => {
  const cfg = await (await request.get("/api/v1/public/config")).json();
  await page.goto("/");
  const section = page.getByRole("region", { name: "The price you see is the price you pay." });
  for (const t of cfg.cancellation_terms.tiers) {
    const text = t.refund_bps >= 10000 ? "Full refund" : t.refund_bps <= 0 ? "No refund" : `${t.refund_bps / 100}% refunded`;
    await expect(section.getByText(text)).toBeVisible();
  }
});

test("the page has one h1 and a heading for every section, and example content is labelled", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
  for (const name of ["The price you see is the price you pay.", /The same person/, "What we check, and what we do not claim.", /four steps/, "Two services, done properly.", /Questions people ask first/, "Are you a professional cleaner?", "Check your postcode."]) {
    await expect(page.getByRole("heading", { level: 2, name })).toBeVisible();
  }
  await expect(page.locator("#main").getByText("Example profile")).toBeVisible(); // scoped: a streamed copy can briefly sit outside main
  await expect(page.getByText(/vetted/).first()).toBeVisible(); // only inside "we would rather list them than use a word like vetted"
  await expect(page.getByText(/insured|guaranteed|background-checked/i)).toHaveCount(0);
});

test("keyboard only: skip link, nav, postcode check and on to the booking flow", async ({ page }) => {
  await page.goto("/");
  await settled(page);
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to main content" })).toBeFocused();
  // Walk forward until the hero postcode field is focused. It must be reachable in a small number of presses.
  let reached = false;
  for (let i = 0; i < 14 && !reached; i++) {
    await page.keyboard.press("Tab");
    reached = await page.getByLabel("Your postcode").first().evaluate((el) => el === document.activeElement);
  }
  expect(reached, "postcode field reachable by keyboard").toBe(true);
  // Focus is visibly indicated.
  const outline = await page.evaluate(() => { const s = getComputedStyle(document.activeElement!); return { style: s.outlineStyle, width: parseFloat(s.outlineWidth) }; });
  expect(outline.style).not.toBe("none");
  expect(outline.width).toBeGreaterThanOrEqual(2);
  await page.keyboard.type("SW11 1AB");
  await page.keyboard.press("Enter");
  await expect(page.getByText("we cover Battersea").first()).toBeVisible();
  // Focus moves to the next step by itself.
  await expect(page.getByRole("link", { name: "Continue to book and see your price" }).first()).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/book\/regular-cleaning/);
  await expect(page.getByRole("heading", { name: "Book regular home cleaning" })).toBeVisible();
});

test("disclosures (FAQ) open and close from the keyboard", async ({ page }) => {
  await page.goto("/");
  await settled(page);
  const item = page.locator("details", { hasText: "How do I cancel?" });
  await expect(item).toHaveCount(1);
  await item.locator("summary").focus();
  await page.keyboard.press("Enter");
  await expect(item.getByText(/Open your booking in your account and choose Cancel/)).toBeVisible();
  await page.keyboard.press("Enter");
  await expect(item.getByText(/Open your booking in your account and choose Cancel/)).toBeHidden();
});

test.describe("dark mode", () => {
  test.use({ colorScheme: "dark" });
  for (const path of ["/", "/services/home-cleaning/regular-cleaning", "/book/regular-cleaning", "/login", "/trust"]) {
    test(`no serious accessibility violations in dark mode: ${path}`, async ({ page }) => {
      await page.goto(path);
      await page.waitForTimeout(1200);
      const dark = await page.evaluate(() => matchMedia("(prefers-color-scheme: dark)").matches);
      expect(dark).toBe(true);
      const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
      const serious = results.violations.filter((v) => ["serious", "critical"].includes(v.impact ?? ""));
      expect(serious.map((v) => `${v.id}: ${v.help} (${v.nodes.length})`)).toEqual([]);
    });
  }
});

test.describe("phone", () => {
  test.use({ viewport: { width: 375, height: 800 } });
  test("home page has no sideways scroll and the postcode form fits", async ({ page }) => {
    await page.goto("/");
    await page.waitForTimeout(800);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
    const box = await page.getByLabel("Your postcode").first().boundingBox();
    expect(box!.x).toBeGreaterThanOrEqual(0);
    expect(box!.x + box!.width).toBeLessThanOrEqual(375);
  });
});
