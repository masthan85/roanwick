import { createHmac } from "node:crypto";
import { expect, test } from "@playwright/test";
import { DEMO_PASSWORD, signIn, uniqueEmail } from "./helpers";

const PASSWORD = "Correct-horse-9";

function totp(secret: string): string {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = "";
  for (const c of secret.replace(/=+$/, "")) bits += alphabet.indexOf(c).toString(2).padStart(5, "0");
  const key = Buffer.from(bits.match(/.{8}/g)!.map((b) => parseInt(b, 2)));
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 30000)));
  const h = createHmac("sha1", key).update(counter).digest();
  const o = h[h.length - 1] & 0xf;
  return String(((h.readUInt32BE(o) & 0x7fffffff) % 1_000_000)).padStart(6, "0");
}

test("choosing a bundle ticks its extras and shows the discount as its own line", async ({ page }) => {
  await page.goto("/book/regular-cleaning?postcode=SW11%201AB");
  const summary = page.getByRole("complementary", { name: "Price summary" });
  await expect(summary.getByText("£66.00").first()).toBeVisible();
  await page.getByLabel(/Deep-clean refresh/).check({ force: true });
  await expect(summary.getByText(/Deep-clean refresh bundle \(10% off\)/)).toBeVisible();
  await expect(page.getByLabel(/Inside the oven/)).toBeChecked();
  await expect(page.getByLabel(/Inside the oven/)).toBeDisabled();
  // 66.00 + 25.00 + 15.00 + 20.00 = 126.00, less 10% = 113.40
  await expect(summary.getByText("£113.40")).toBeVisible();
  await page.getByLabel("No bundle").check({ force: true });
  await expect(summary.getByText("£66.00").first()).toBeVisible();
});

test("service pages list bundles with a link that pre-selects them", async ({ page }) => {
  await page.goto("/services/home-cleaning/end-of-tenancy-cleaning");
  await expect(page.getByText("Move-out pack")).toBeVisible();
  await page.getByRole("link", { name: "Book this bundle" }).click();
  await expect(page).toHaveURL(/bundle=move-out-pack/);
});

test("Book again pre-fills the booking from an earlier one", async ({ page, request }) => {
  // Set up a customer and a booking through the API, then use the real screens.
  const email = uniqueEmail("rebook");
  const reg = await request.post("/api/v1/auth/register", { data: { email, password: PASSWORD, full_name: "Rae Book", accept_terms: true } });
  const token = (await reg.json()).access_token;
  const h = { Authorization: `Bearer ${token}` };
  const q = await (await request.post("/api/v1/quotes", { headers: h, data: { offering_id: (await (await request.get("/api/v1/catalogue/offerings/regular-cleaning")).json()).id, postcode: "SW11 1AB", minutes: 240, addons: ["fridge"] } })).json();
  const addr = await (await request.post("/api/v1/addresses", { headers: h, data: { line1: "5 Rebook Road", postcode: "SW11 1AB" } })).json();
  const day = new Date(Date.now() + 9 * 86400000).toISOString().slice(0, 10);
  const slots = await (await request.get(`/api/v1/catalogue/slots?offering=regular-cleaning&postcode=SW11%201AB&minutes=${q.duration_minutes}&addons=fridge&from_date=${day}&days=7`)).json();
  const first = Object.values(slots.days as Record<string, { starts_at: string }[]>)[0][0];
  const b = await (await request.post("/api/v1/bookings", { headers: h, data: { quotation_id: q.id, address_id: addr.id, starts_at: first.starts_at, accept_terms: true } })).json();
  expect(b.reference).toBeTruthy();

  await signIn(page, email, PASSWORD);
  await page.goto(`/book/regular-cleaning?rebook=${b.id}`);
  const summary = page.getByRole("complementary", { name: "Price summary" });
  await expect(page.getByLabel("Postcode").first()).toHaveValue("SW11 1AB");
  await expect(page.getByLabel(/Inside the fridge/)).toBeChecked();
  await expect(summary.getByText("Cleaning, 4 hours at £22.00/hour")).toBeVisible();
});

test("staff can turn on two-step verification, must then use a code to sign in, and can turn it off", async ({ page }) => {
  await signIn(page, "finance@roanwick.example");
  await page.goto("/admin/security");
  await page.getByRole("button", { name: "Set up" }).click();
  const secret = (await page.locator("code").first().innerText()).trim();
  await page.getByLabel("Code from the app").fill(totp(secret));
  await page.getByRole("button", { name: "Turn on" }).click();
  await expect(page.getByText("Two-step verification is on.")).toBeVisible();

  // Sign out and back in: the password alone is no longer enough.
  await page.getByRole("button", { name: "Sign out" }).first().click();
  await page.goto("/login");
  await page.getByLabel("Email address").fill("finance@roanwick.example");
  await page.getByLabel("Password").fill(DEMO_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText("Enter the 6-digit code from your authenticator app.")).toBeVisible();
  await page.getByLabel("Authenticator code").fill("000000");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "not correct" })).toBeVisible();
  await page.getByLabel("Authenticator code").fill(totp(secret));
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL(/\/admin/);

  // Tidy up so other tests can still use this account.
  await page.goto("/admin/security");
  await page.getByLabel("Your password").fill(DEMO_PASSWORD);
  await page.getByLabel("Current code").fill(totp(secret));
  await page.getByRole("button", { name: "Turn off" }).click();
  await expect(page.getByRole("button", { name: "Set up" })).toBeVisible();
});

test("admin opens a customer's detail page from the accounts list", async ({ page }) => {
  await signIn(page, "admin@roanwick.example");
  await page.goto("/admin/users");
  await page.getByLabel("Search name or email").fill("priya");
  await page.getByRole("link", { name: "Priya Shah" }).click();
  await expect(page.getByRole("heading", { name: "Priya Shah" })).toBeVisible();
  await expect(page.getByText("Two-step verification")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Bookings" })).toBeVisible();
});

test("admin can add a bundle and a new service from the catalogue", async ({ page }) => {
  await signIn(page, "admin@roanwick.example");
  await page.goto("/admin/catalogue");
  await page.getByRole("button", { name: "Add a new service" }).click();
  const unique = Date.now() % 100000;
  const slug = `window-clean-${unique}`;
  const form = page.locator("form").filter({ has: page.getByRole("button", { name: "Create service" }) });
  await form.getByLabel("Name", { exact: true }).fill(`Window cleaning ${unique}`);
  await form.getByLabel("Web address").fill(slug);
  await form.getByLabel("Hourly rate in pounds").fill("24");
  await form.getByRole("button", { name: "Create service" }).click();
  await expect(page.getByRole("button", { name: "Add a new service" })).toBeVisible(); // the form closes once the service is created
  await expect(page.getByRole("heading", { name: new RegExp(`Window cleaning ${unique}`) })).toBeVisible();
  const res = await page.request.get(`/api/v1/catalogue/offerings/${slug}`);
  expect(res.status()).toBe(200);
});
