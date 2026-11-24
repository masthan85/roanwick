import { expect, test } from "@playwright/test";
import { uniqueEmail } from "./helpers";

test("a new customer prices, books, has a card declined, pays and sees the booking", async ({ page }) => {
  const email = uniqueEmail("customer");
  await page.goto("/");
  await page.getByLabel("Your postcode").first().fill("SW11 1AB");
  await page.getByRole("button", { name: "Check availability" }).first().click();
  await expect(page.getByText("we cover Battersea")).toBeVisible();
  await page.getByRole("link", { name: "Continue to book and see your price" }).click();

  // Step 1: the itemised price appears before any account or payment step.
  const summary = page.getByRole("complementary", { name: "Price summary" });
  await expect(summary.getByText("Total payable")).toBeVisible();
  await expect(summary.getByText("£66.00").first()).toBeVisible();
  await page.getByLabel(/Inside the oven/).check();
  await expect(summary.getByText("Inside the oven")).toBeVisible();
  await expect(summary.getByText("£91.00")).toBeVisible();
  await page.getByRole("button", { name: "Continue" }).click();

  // Step 2: real availability.
  // Pick a date several days out, so the full-refund tier applies when we cancel at the end.
  await expect(page.getByRole("radiogroup", { name: "Date" }).getByRole("radio").nth(3)).toBeVisible();
  await page.getByRole("radiogroup", { name: "Date" }).getByRole("radio").nth(3).click();
  const firstTime = page.getByRole("radiogroup", { name: "Start time" }).getByRole("radio").first();
  await expect(firstTime).toBeVisible();
  await firstTime.click();
  await page.getByRole("button", { name: "Continue" }).click();

  // Step 3: create an account inline, add the address.
  await page.getByLabel("Full name").fill("Priya Test");
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password").fill("Correct-horse-9");
  await page.getByLabel(/I accept the/).check();
  await page.getByRole("button", { name: "Create account and continue" }).click();
  await page.getByLabel("Address line 1").fill("12 Example Road");
  await page.getByRole("button", { name: "Review booking" }).click();

  // Step 4: terms, then payment. A declined card keeps the slot and allows a retry.
  await expect(page.getByRole("heading", { name: "Cancellation terms" })).toBeVisible();
  await expect(page.getByText("More than 48 hours before the start: full refund.")).toBeVisible();
  await page.getByLabel(/I agree to the/).check();
  await page.getByRole("button", { name: /Continue to payment/ }).click();
  await expect(page.getByText("Test mode: no real money is taken.")).toBeVisible();
  await page.getByLabel("Card that is declined").check();
  await page.getByRole("button", { name: /^Pay / }).click();
  await expect(page.getByRole("alert").filter({ hasText: "declined" })).toBeVisible();
  await expect(page.getByText("Your slot is still held")).toBeVisible();
  await page.getByLabel(/Visa ending 4242/).check();
  await page.getByRole("button", { name: /^Pay / }).click();
  await expect(page.getByText("Your booking is confirmed.")).toBeVisible();

  await page.getByRole("link", { name: "View booking" }).click();
  await expect(page.getByRole("heading", { name: "Regular home cleaning" })).toBeVisible();
  await expect(page.getByText("Confirmed", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Free cancellation").or(page.getByText("More than 48 hours before the start: full refund.")).first()).toBeVisible();

  // The refund is shown before cancelling and matches what is refunded.
  await page.getByRole("button", { name: "Cancel booking" }).first().click();
  await expect(page.getByText("Refund: £91.00")).toBeVisible();
  await page.getByRole("dialog").getByRole("button", { name: "Cancel booking" }).click();
  await expect(page.getByText("Cancelled", { exact: true }).first()).toBeVisible();
});

test("an uncovered postcode offers the waiting list", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Your postcode").first().fill("E1 6AN");
  await page.getByRole("button", { name: "Check availability" }).first().click();
  await expect(page.getByText("We do not cover E1 yet.")).toBeVisible();
  await page.getByLabel("Email address").fill(uniqueEmailLocal());
  await page.getByRole("button", { name: "Join the waiting list" }).click();
  await expect(page.getByText("You are on the list.")).toBeVisible();
});

test("validation errors are announced and a bad postcode is rejected", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Your postcode").first().fill("nonsense");
  await page.getByRole("button", { name: "Check availability" }).first().click();
  await expect(page.getByRole("alert").filter({ hasText: "Enter a full UK postcode" })).toBeVisible();
});

const uniqueEmailLocal = () => `waitlist+${Date.now()}@example.com`;
