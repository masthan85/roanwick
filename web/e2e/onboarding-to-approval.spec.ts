import { expect, test } from "@playwright/test";
import { signIn, uniqueEmail } from "./helpers";

const PDF = { name: "document.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.4\n%e2e test document\n") };

test("a professional applies, is blocked until documents are approved, then appears publicly with only verified badges", async ({ browser }) => {
  const display = `Nadia E2E ${Date.now() % 100000}`;
  const pro = await browser.newPage();

  // Apply and complete the application through the real screens.
  await pro.goto("/join");
  await pro.getByLabel("Full name").fill("Nadia Example");
  await pro.getByLabel("Name shown to customers").fill(display);
  await pro.getByLabel("Email address").fill(uniqueEmail("pro"));
  await pro.getByLabel("Mobile number").fill("07700900222");
  await pro.getByLabel("Password").fill("Correct-horse-9");
  await pro.getByLabel(/I accept the/).check();
  await pro.getByRole("button", { name: "Start my application" }).click();
  await expect(pro.getByRole("heading", { name: new RegExp(`Hello, ${display}`) })).toBeVisible();
  await expect(pro.getByText("Complete your application to start receiving jobs")).toBeVisible();

  await pro.getByRole("tab", { name: "Get approved" }).click();
  await pro.getByLabel("About you").fill("Six years cleaning homes across Battersea and Clapham. Reliable and tidy.");
  await pro.getByRole("button", { name: "Save profile" }).click();
  await pro.getByLabel("Regular home cleaning").check();
  await pro.getByLabel(/SW11 Battersea/).check();
  await pro.getByRole("button", { name: "Save services and areas" }).click();

  await pro.getByRole("tab", { name: "Availability" }).click();
  await pro.getByLabel("Monday", { exact: true }).check();
  await pro.getByRole("button", { name: "Save hours" }).click();
  await expect(pro.getByLabel("Monday start")).toBeVisible();

  await pro.getByRole("tab", { name: "Get approved" }).click();
  const upload = async (type: string, expiry?: string) => {
    await pro.getByLabel("Type").selectOption(type);
    if (expiry) await pro.getByLabel("Expiry date").fill(expiry);
    await pro.getByLabel("File").setInputFiles(PDF);
    await pro.getByRole("button", { name: "Upload", exact: true }).click();
  };
  const nextYear = `${new Date().getFullYear() + 1}-06-30`;
  await upload("identity");
  await expect(pro.getByText("Photo identity document").first()).toBeVisible();
  await upload("right_to_work");
  await upload("public_liability", nextYear);
  await expect(pro.getByRole("button", { name: "Submit for review" })).toBeEnabled();
  await pro.getByRole("button", { name: "Submit for review" }).click();
  await expect(pro.getByText("Your application is being reviewed")).toBeVisible();

  // Operations: the approval gate holds until each document is approved.
  const admin = await browser.newPage();
  await signIn(admin, "ops@roanwick.example");
  await admin.goto("/admin/providers?status=submitted");
  await admin.getByRole("link", { name: display }).click();
  await expect(admin.getByText("Cannot be approved yet")).toBeVisible();
  const providerId = admin.url().split("/").pop()!;
  await admin.getByRole("button", { name: "Approve", exact: true }).first().click();
  await expect(admin.getByRole("alert").filter({ hasText: "cannot be approved until every mandatory document" })).toBeVisible();

  for (const title of ["Photo identity document", "Right to work evidence", "Public liability insurance certificate"]) {
    await admin.locator("li").filter({ hasText: title }).getByRole("button", { name: "Approve" }).click();
    await expect(admin.locator("li").filter({ hasText: title }).getByText("approved", { exact: true })).toBeVisible();
  }
  await expect(admin.getByText("All mandatory documents are approved and in date.")).toBeVisible();
  await admin.getByRole("button", { name: "Approve", exact: true }).first().click();
  await expect(admin.getByText("approved", { exact: true }).first()).toBeVisible();

  // Public profile shows only what was checked, and nothing stronger.
  const publicPage = await browser.newPage();
  await publicPage.goto(`/professionals/${providerId}`);
  await expect(publicPage.getByRole("heading", { name: display })).toBeVisible();
  await expect(publicPage.getByText("Identity document checked")).toBeVisible();
  await expect(publicPage.getByText("Public liability insurance certificate seen")).toBeVisible();
  await expect(publicPage.getByText(/background|vetted|guaranteed/i)).toHaveCount(0);

  // And the professional's own dashboard reflects approval.
  await pro.reload();
  await expect(pro.getByText("Approved", { exact: true }).first()).toBeVisible();
});
