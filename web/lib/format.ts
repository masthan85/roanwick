const gbp = new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP" });
export const money = (pence: number | null | undefined) => (pence == null ? "Not available" : gbp.format(pence / 100));

const TZ = "Europe/London";
export const dateFmt = (iso: string | Date, opts: Intl.DateTimeFormatOptions = { weekday: "short", day: "numeric", month: "short" }) =>
  new Intl.DateTimeFormat("en-GB", { timeZone: TZ, ...opts }).format(typeof iso === "string" ? new Date(iso) : iso);
// Composed from parts so the output ("Friday 6 November 2026") does not depend on the browser's ICU version.
export const longDate = (iso: string | Date) => {
  const parts = new Intl.DateTimeFormat("en-GB", { timeZone: TZ, weekday: "long", day: "numeric", month: "long", year: "numeric" }).formatToParts(typeof iso === "string" ? new Date(iso) : iso);
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? "";
  return `${get("weekday")} ${get("day")} ${get("month")} ${get("year")}`;
};
export const shortDate = (iso: string | Date) => dateFmt(iso, { day: "numeric", month: "short", year: "numeric" });
export const timeFmt = (iso: string | Date) => dateFmt(iso, { hour: "2-digit", minute: "2-digit", hour12: false });
export const dateTime = (iso: string | Date) => `${dateFmt(iso)} at ${timeFmt(iso)}`;

export const hours = (minutes: number) => {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m ? `${h}h ${m}m` : `${h} hour${h === 1 ? "" : "s"}`;
};

export const percent = (v: number | null | undefined) => (v == null ? "Not enough data" : `${Math.round(v * 1000) / 10}%`);

export const STATUS_LABEL: Record<string, string> = {
  pending_payment: "Awaiting payment",
  awaiting_provider: "Awaiting confirmation",
  confirmed: "Confirmed",
  in_progress: "In progress",
  completed: "Completed",
  cancelled: "Cancelled",
  expired: "Expired",
};

export const POSTCODE_RE = /^[A-Za-z]{1,2}[0-9][A-Za-z0-9]?\s*[0-9][A-Za-z]{2}$/;
export const normalisePostcode = (v: string) => {
  const c = v.replace(/\s+/g, "").toUpperCase();
  return c.length > 3 ? `${c.slice(0, -3)} ${c.slice(-3)}` : c;
};
