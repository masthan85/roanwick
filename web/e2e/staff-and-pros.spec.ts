import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

test("a professional sees jobs, availability and earnings with their commission", async ({ page }) => {
  await signIn(page, "elena@example.com");
  await expect(page).toHaveURL(/\/pro/);
  await expect(page.getByRole("heading", { name: /Hello, Elena/ })).toBeVisible();
  await page.getByRole("tab", { name: "Availability" }).click();
  await expect(page.getByText("Weekly working hours")).toBeVisible();
  await page.getByRole("tab", { name: "Earnings" }).click();
  await expect(page.getByText("Commission", { exact: true })).toBeVisible();
});

test("customers cannot open staff or professional areas", async ({ page }) => {
  await signIn(page, "priya@example.com");
  await page.goto("/admin");
  await expect(page.getByText("This area is not for your account type.")).toBeVisible();
  await page.goto("/pro");
  await expect(page.getByText("This area is not for your account type.")).toBeVisible();
});

test("admin sees money labelled as actual, estimated or manual and cannot mistake gross value for revenue", async ({ page }) => {
  await signIn(page, "admin@roanwick.example");
  await expect(page).toHaveURL(/\/admin/);
  await page.getByRole("link", { name: "Finance and growth" }).click();
  await expect(page.getByText("Gross booking value is money we collect")).toBeVisible();
  await expect(page.getByRole("tabpanel").getByText("Platform revenue", { exact: true })).toBeVisible();
  await expect(page.getByRole("tabpanel").getByText("Customer acquisition cost", { exact: true })).toBeVisible();
  await page.getByRole("tab", { name: "Manual costs" }).click();
  await expect(page.getByText("typed in by staff")).toBeVisible();
});

test("support staff only see what their role allows", async ({ page }) => {
  await signIn(page, "support@roanwick.example");
  await expect(page.getByRole("link", { name: "Complaints and refunds" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Settings and flags" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Finance and growth" })).toHaveCount(0);
});

test("regulated categories cannot be switched on without compliance requirements", async ({ page }) => {
  await signIn(page, "admin@roanwick.example");
  await page.goto("/admin/catalogue");
  const card = page.getByRole("heading", { name: "Plumbing", level: 2 }).locator("xpath=ancestor::div[@data-card][1]");
  await card.getByLabel(/I confirm the compliance requirements/).check();
  await card.getByRole("button", { name: "Try to switch on" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "verification requirements defined" })).toBeVisible();
});
