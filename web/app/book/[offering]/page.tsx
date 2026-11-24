"use client";
import { CheckIcon } from "@/components/icons";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import useSWR from "swr";
import { api, ApiError, fetcher, newKey, qs } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { dateFmt, hours, longDate, money, normalisePostcode, POSTCODE_RE, timeFmt } from "@/lib/format";
import { Container } from "@/components/shell";
import { Alert, Badge, Button, Card, Check, ErrorAlert, Field, LinkButton, PageLoading, Select, Skeleton, Spinner, Stars, TextArea, fieldErr, useAsync } from "@/components/ui";

type Quote = { id: string; lines: { kind: string; description: string; amount_pence: number }[]; total_pence: number; duration_minutes: number; terms: { summary: string[] }; promo_code: string | null };
type Slots = { duration_minutes: number; days: Record<string, { time: string; starts_at: string; professionals: number }[]> };

const STEPS = ["Your home", "Date and time", "Your details", "Review and pay"];
const TEST_CARDS = [
  ["pm_card_visa", "Visa ending 4242 (succeeds)"],
  ["pm_card_declined", "Card that is declined"],
  ["pm_card_insufficient_funds", "Card with insufficient funds"],
];

export default function BookPage() {
  const { offering: slug } = useParams<{ offering: string }>();
  const sp = useSearchParams();
  const { user, loading: authLoading, register, login } = useAuth();
  const { data: off, error: offErr } = useSWR(`/catalogue/offerings/${slug}`, fetcher);
  const { data: cfg } = useSWR("/public/config", fetcher);

  const [step, setStep] = useState(0);
  const [postcode, setPostcode] = useState(sp.get("postcode") ?? "");
  const [minutes, setMinutes] = useState(180);
  const [bedrooms, setBedrooms] = useState<number | "">("");
  const [addons, setAddons] = useState<string[]>([]);
  const [frequency, setFrequency] = useState("once");
  const [promo, setPromo] = useState("");
  const [promoOpen, setPromoOpen] = useState(false);
  const [bundle, setBundle] = useState<string>(sp.get("bundle") ?? "");
  const { data: bundles } = useSWR(`/catalogue/bundles?offering=${slug}`, fetcher);
  const rebookId = sp.get("rebook");

  const [quote, setQuote] = useState<Quote | null>(null);
  const [quoteErr, setQuoteErr] = useState<unknown>(null);
  const [quoting, setQuoting] = useState(false);

  const [pro, setPro] = useState<string>("any");
  const [weekStart, setWeekStart] = useState(0);
  const [slots, setSlots] = useState<Slots | null>(null);
  const [slotErr, setSlotErr] = useState<unknown>(null);
  const [day, setDay] = useState<string>("");
  const [slot, setSlot] = useState<{ time: string; starts_at: string } | null>(null);

  useEffect(() => {
    if (off && off.pricing_model === "hourly") setMinutes(Math.max(off.min_minutes, 180));
  }, [off]);

  // "Book again": pre-fill from an earlier booking, including the same professional.
  const [rebooked, setRebooked] = useState(false);
  useEffect(() => {
    if (!rebookId || !user || rebooked) return;
    setRebooked(true);
    api<any>(`/bookings/${rebookId}/rebook-quote`, { method: "POST" })
      .then((r) => {
        setPostcode(r.address_postcode ?? "");
        if (r.inputs?.minutes) setMinutes(r.inputs.minutes);
        if (r.inputs?.bedrooms != null) setBedrooms(r.inputs.bedrooms);
        if (r.inputs?.addons) setAddons(r.inputs.addons);
        if (r.inputs?.bundle) setBundle(r.inputs.bundle);
        if (r.provider_id) setPro(r.provider_id);
      })
      .catch(() => undefined);
  }, [rebookId, user, rebooked]);

  // Choosing a bundle ticks its extras.
  const chosenBundle = (bundles ?? []).find((b: any) => b.slug === bundle);
  useEffect(() => {
    if (chosenBundle) setAddons((a) => Array.from(new Set([...a, ...chosenBundle.addon_codes])));
  }, [chosenBundle?.slug]); // eslint-disable-line react-hooks/exhaustive-deps

  const postcodeOk = POSTCODE_RE.test(postcode.trim());
  const ready = !!off && postcodeOk && (off.pricing_model === "hourly" || bedrooms !== "");
  const body = useMemo(
    () => (off && ready ? { offering_id: off.id, postcode, minutes: off.pricing_model === "hourly" ? minutes : null, bedrooms: off.pricing_model === "tiered" ? Number(bedrooms) : null, addons, frequency, promo_code: promo.trim() || null, bundle: bundle || null } : null),
    [off, ready, postcode, minutes, bedrooms, addons, frequency, promo, bundle],
  );

  // Live quote, debounced so typing does not hammer the API.
  const quoteSeq = useRef(0);
  useEffect(() => {
    if (!body) { setQuote(null); return; }
    const seq = ++quoteSeq.current;
    setQuoting(true);
    const t = setTimeout(async () => {
      try {
        const q = await api<Quote>("/quotes", { body });
        if (seq === quoteSeq.current) { setQuote(q); setQuoteErr(null); }
      } catch (e) {
        if (seq === quoteSeq.current) { setQuote(null); setQuoteErr(e); }
      } finally {
        if (seq === quoteSeq.current) setQuoting(false);
      }
    }, 350);
    return () => clearTimeout(t);
  }, [body]);

  // Selecting different options invalidates a chosen slot.
  useEffect(() => { setSlot(null); setSlots(null); }, [body?.minutes, body?.bedrooms, addons, postcode, pro, frequency]);

  const { data: pros } = useSWR(ready && cfg?.features?.customer_chooses_provider ? `/catalogue/professionals${qs({ offering: slug, postcode })}` : null, fetcher);

  useEffect(() => {
    if (step !== 1 || !body || !quote) return;
    const from = new Date();
    from.setDate(from.getDate() + weekStart);
    const from_date = new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/London" }).format(from);
    setSlots(null);
    setSlotErr(null);
    api<Slots>(`/catalogue/slots${qs({ offering: slug, postcode, minutes: body.minutes, bedrooms: body.bedrooms, addons: addons.join(","), frequency, from_date, days: 7, provider_id: pro === "any" ? null : pro })}`)
      .then((s) => { setSlots(s); setDay(Object.keys(s.days)[0] ?? ""); })
      .catch(setSlotErr);
  }, [step, weekStart, quote?.id, pro]); // eslint-disable-line react-hooks/exhaustive-deps

  // ---- account and address ----
  const [mode, setMode] = useState<"register" | "login">("register");
  const [acct, setAcct] = useState({ full_name: "", email: "", password: "", phone: "", accept_terms: false, marketing_consent: false });
  const acctAsync = useAsync();
  const { data: addresses, mutate: reloadAddresses } = useSWR(user?.roles.includes("customer") ? "/addresses" : null, fetcher);
  const [addrId, setAddrId] = useState("new");
  const [addr, setAddr] = useState({ line1: "", line2: "", access_notes: "" });
  const [notes, setNotes] = useState("");
  const addrAsync = useAsync();
  const outward = normalisePostcode(postcode).split(" ")[0];
  const matching = (addresses ?? []).filter((a: any) => a.postcode.split(" ")[0] === outward);
  useEffect(() => { if (matching.length && addrId === "new") setAddrId(matching.find((a: any) => a.is_default)?.id ?? matching[0].id); }, [addresses]); // eslint-disable-line react-hooks/exhaustive-deps

  // ---- booking and payment ----
  const [accepted, setAccepted] = useState(false);
  const [useCredit, setUseCredit] = useState(false);
  const { data: referral } = useSWR(user?.roles.includes("customer") ? "/me/referral" : null, fetcher);
  const [booking, setBooking] = useState<any>(null);
  const [plan, setPlan] = useState<any>(null);
  const [card, setCard] = useState("pm_card_visa");
  const createKey = useRef(newKey());
  useEffect(() => { createKey.current = newKey(); }, [quote?.id, slot?.starts_at, pro, useCredit, addrId]);
  const book = useAsync();
  const payA = useAsync();
  const [paid, setPaid] = useState<any>(null);

  const canNext = [!!quote && !quoting, !!slot, !!user?.roles.includes("customer") && (addrId !== "new" || addr.line1.trim().length >= 3), accepted][step];

  async function ensureAddress() {
    if (addrId !== "new") return addrId;
    const a = await api<{ id: string }>("/addresses", { body: { line1: addr.line1, line2: addr.line2 || null, postcode, bedrooms: off.pricing_model === "tiered" ? Number(bedrooms) : null, access_notes: addr.access_notes || null } });
    await reloadAddresses();
    setAddrId(a.id);
    return a.id;
  }

  async function confirm() {
    if (!quote || !slot || !user) return;
    const r = await book.run(async () => {
      const address_id = await ensureAddress();
      if (frequency !== "once") {
        const local = slot.time;
        const first = day;
        return { kind: "plan", data: await api("/subscriptions", { body: { offering_id: off.id, address_id, frequency, first_visit_on: first, start_time: `${local}:00`, minutes: off.pricing_model === "hourly" ? minutes : null, addons, preferred_provider_id: pro === "any" ? null : pro, payment_method: card, accept_terms: true } }) };
      }
      return { kind: "booking", data: await api("/bookings", { idempotencyKey: createKey.current, body: { quotation_id: quote.id, address_id, starts_at: slot.starts_at, provider_id: pro === "any" ? null : pro, notes: notes || null, use_credit: useCredit, accept_terms: true } }) };
    });
    if (!r) return;
    if (r.kind === "plan") setPlan(r.data);
    else {
      setBooking(r.data);
      if (r.data.payment?.amount_pence === 0 || r.data.status === "confirmed") setPaid(r.data);
    }
  }

  async function pay() {
    const r = await payA.run(() => api(`/bookings/${booking.id}/pay`, { idempotencyKey: newKey(), body: { payment_method: card } }));
    if (r) setPaid(r);
    else if (payA.error instanceof ApiError && payA.error.code === "payment_failed") {/* message shown below */}
  }

  if (offErr) return <Container narrow className="py-16"><Alert title="We could not find that service.">Please check the link, or <Link className="underline" href="/services">browse our services</Link>.</Alert></Container>;
  if (!off) return <Container className="py-12"><Skeleton className="h-10 w-1/2" /><div className="mt-6"><PageLoading label="Loading service" /></div></Container>;

  if (paid || plan) return <Success booking={paid} plan={plan} off={off} />;

  const discountHint = off.supports_recurring && frequency === "once" ? "Weekly plans save 10% on labour and fortnightly plans save 5%." : null;
  const dayKeys = slots ? Object.keys(slots.days) : [];
  const freeCard = booking && booking.payment?.amount_pence === 0;

  return (
    <Container className="py-8 md:py-12">
      <p className="text-sm text-muted"><Link href={`/services/${off.category.slug}/${off.slug}`} className="underline underline-offset-4">{off.name}</Link></p>
      <h1 className="text-3xl md:text-4xl mt-1">Book {off.name.toLowerCase()}</h1>
      <ol className="mt-6 flex gap-2 overflow-x-auto" aria-label="Progress">
        {STEPS.map((s, i) => (
          <li key={s} aria-current={i === step ? "step" : undefined} className={`flex items-center gap-2 rounded-full border px-3.5 py-2 text-small whitespace-nowrap ${i === step ? "border-brand bg-brand-soft font-medium text-ink" : i < step ? "border-line text-ink" : "border-line text-muted"}`}>
            <span aria-hidden className={`h-6 w-6 rounded-full grid place-items-center text-caption ${i <= step ? "bg-brand text-brand-fg" : "bg-sunken"}`}>{i < step ? <CheckIcon size={12} /> : i + 1}</span>{s}
          </li>
        ))}
      </ol>

      <div className="mt-8 grid gap-8 lg:grid-cols-[1.5fr_1fr] items-start">
        <div>
          {step === 0 && (
            <div className="grid gap-6">
              <Field label="Postcode" value={postcode} onChange={(e) => setPostcode(e.target.value)} autoComplete="postal-code" placeholder="SW11 1AB" error={postcode && !postcodeOk ? "Enter a full UK postcode." : undefined} className="max-w-xs" />
              {off.pricing_model === "hourly" ? (
                <Select label="How long do you need?" value={minutes} onChange={(e) => setMinutes(Number(e.target.value))} hint={`Between ${hours(off.min_minutes)} and ${hours(off.max_minutes)}. ${money(off.hourly_rate_pence)} per hour.`} className="max-w-xs">
                  {Array.from({ length: (off.max_minutes - off.min_minutes) / off.step_minutes + 1 }, (_, i) => off.min_minutes + i * off.step_minutes).map((m) => <option key={m} value={m}>{hours(m)}</option>)}
                </Select>
              ) : (
                <Select label="Property size" value={bedrooms} onChange={(e) => setBedrooms(e.target.value === "" ? "" : Number(e.target.value))} className="max-w-xs">
                  <option value="">Choose…</option>
                  {off.tiers.map((t: any) => <option key={t.bedrooms} value={t.bedrooms}>{t.label}: {money(t.price_pence)}</option>)}
                </Select>
              )}
              {bundles && bundles.length > 0 && (
                <fieldset>
                  <legend className="text-sm font-medium mb-2">Bundles <span className="text-muted font-normal">(packages of extras at a saving)</span></legend>
                  <div className="grid gap-2">
                    {[{ slug: "", name: "No bundle", description: "Choose your own extras" }, ...bundles].map((b: any) => (
                      <label key={b.slug} className={`cursor-pointer rounded-control border p-3 ${bundle === b.slug ? "border-brand bg-brand-soft" : "border-line bg-surface"}`}>
                        <input type="radio" name="bundle" className="sr-only" checked={bundle === b.slug} onChange={() => { setBundle(b.slug); if (!b.slug) setAddons([]); }} />
                        <span className="font-medium">{b.name}{b.discount_bps ? <span className="ml-2 text-success text-sm">{b.discount_bps / 100}% off</span> : null}</span>
                        <span className="block text-small text-muted">{b.addons?.length ? `Includes ${b.addons.map((a: any) => a.name.toLowerCase()).join(", ")}.` : b.description}</span>
                      </label>
                    ))}
                  </div>
                </fieldset>
              )}
              {off.addons.length > 0 && (
                <fieldset>
                  <legend className="text-sm font-medium mb-2">Extras</legend>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {off.addons.map((a: any) => (
                      <Check key={a.code} checked={addons.includes(a.code)} disabled={!!chosenBundle?.addon_codes.includes(a.code)} onChange={(e) => setAddons(e.target.checked ? [...addons, a.code] : addons.filter((c) => c !== a.code))} label={<span>{a.name} <span className="text-muted">{money(a.price_pence)}, adds {a.extra_minutes} min</span></span>} className="rounded-control border border-line bg-surface p-3" />
                    ))}
                  </div>
                </fieldset>
              )}
              {off.supports_recurring && (
                <fieldset>
                  <legend className="text-sm font-medium mb-2">How often?</legend>
                  <div className="grid gap-2 sm:grid-cols-3">
                    {[["once", "One-off", ""], ["weekly", "Weekly", "10% off labour"], ["fortnightly", "Fortnightly", "5% off labour"]].map(([v, l, h]) => (
                      <label key={v} className={`cursor-pointer rounded-control border p-3 ${frequency === v ? "border-brand bg-brand-soft" : "border-line bg-surface"}`}>
                        <input type="radio" name="freq" value={v} checked={frequency === v} onChange={() => setFrequency(v)} className="sr-only" />
                        <span className="font-medium block">{l}</span><span className="text-sm text-muted">{h || "No commitment"}</span>
                      </label>
                    ))}
                  </div>
                  {discountHint && <p className="mt-2 text-sm text-muted">{discountHint}</p>}
                </fieldset>
              )}
              {cfg?.features?.promotions && (
                <div>
                  {!promoOpen ? <button className="text-sm underline underline-offset-4" onClick={() => setPromoOpen(true)}>Have a promotional code?</button> : <Field label="Promotional code" value={promo} onChange={(e) => setPromo(e.target.value.toUpperCase())} className="max-w-xs" />}
                </div>
              )}
              {quoteErr instanceof ApiError && quoteErr.code === "outside_coverage" ? <Alert tone="warn" title="We do not cover that postcode yet.">Use the <Link className="underline" href="/#top">postcode check</Link> to join the waiting list.</Alert> : <ErrorAlert error={quoteErr} />}
            </div>
          )}

          {step === 1 && (
            <div className="grid gap-6">
              {cfg?.features?.customer_chooses_provider && pros && pros.length > 0 && (
                <fieldset>
                  <legend className="text-lg font-display mb-2">Who would you like?</legend>
                  <div className="grid gap-2">
                    <label className={`cursor-pointer rounded-control border p-4 ${pro === "any" ? "border-brand bg-brand-soft" : "border-line bg-surface"}`}>
                      <input type="radio" name="pro" className="sr-only" checked={pro === "any"} onChange={() => setPro("any")} />
                      <span className="font-medium">Best available professional</span><span className="block text-sm text-muted">More times to choose from. We match on rating and punctuality.</span>
                    </label>
                    {pros.map((p: any) => (
                      <label key={p.id} className={`cursor-pointer rounded-control border p-4 ${pro === p.id ? "border-brand bg-brand-soft" : "border-line bg-surface"}`}>
                        <input type="radio" name="pro" className="sr-only" checked={pro === p.id} onChange={() => setPro(p.id)} />
                        <span className="flex flex-wrap items-center justify-between gap-2"><span className="font-medium">{p.display_name}</span><Stars value={p.rating_avg} count={p.rating_count} /></span>
                        <span className="block text-sm text-muted">{p.jobs_completed} visits completed. {p.badges.map((b: any) => b.label).join(", ") || "Documents awaiting review"}.</span>
                      </label>
                    ))}
                  </div>
                </fieldset>
              )}
              <div>
                <h2 className="text-lg font-display">Choose a date</h2>
                {!slots && !slotErr && <div className="mt-3 flex items-center gap-2 text-muted" role="status"><Spinner small /> Finding times…</div>}
                <ErrorAlert error={slotErr} className="mt-3" />
                {slots && dayKeys.length === 0 && (
                  <Alert tone="warn" className="mt-3" title="No times in this week.">
                    {pro !== "any" ? "This professional is fully booked. Try another week, or choose any available professional." : "Try the following week."}
                  </Alert>
                )}
                {slots && dayKeys.length > 0 && (
                  <>
                    <div className="mt-3 flex gap-2 overflow-x-auto pb-1" role="radiogroup" aria-label="Date">
                      {dayKeys.map((d) => (
                        <button key={d} role="radio" aria-checked={day === d} onClick={() => { setDay(d); setSlot(null); }} className={`min-h-14 min-w-20 rounded-control border px-3 text-center ${day === d ? "border-brand bg-brand-soft font-medium" : "border-line bg-surface"}`}>
                          <span className="block text-xs text-muted">{dateFmt(d + "T12:00:00Z", { weekday: "short" })}</span>{dateFmt(d + "T12:00:00Z", { day: "numeric", month: "short" })}
                        </button>
                      ))}
                    </div>
                    <h3 className="mt-5 text-lg font-display">Choose a start time</h3>
                    <div className="mt-3 grid grid-cols-3 sm:grid-cols-5 gap-2" role="radiogroup" aria-label="Start time">
                      {(slots.days[day] ?? []).map((s) => (
                        <button key={s.starts_at} role="radio" aria-checked={slot?.starts_at === s.starts_at} onClick={() => setSlot(s)} className={`min-h-11 rounded-control border ${slot?.starts_at === s.starts_at ? "border-brand bg-brand text-brand-fg" : "border-line bg-surface hover:border-brand"}`}>{s.time}</button>
                      ))}
                    </div>
                  </>
                )}
                <div className="mt-4 flex gap-2">
                  <Button variant="secondary" disabled={weekStart === 0} onClick={() => setWeekStart(Math.max(0, weekStart - 7))}>Earlier week</Button>
                  <Button variant="secondary" onClick={() => setWeekStart(weekStart + 7)}>Later week</Button>
                </div>
                <p className="mt-3 text-sm text-muted">Times shown are when the visit begins, in UK time. Your professional needs a short gap between jobs, so some times may be unavailable.</p>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="grid gap-6">
              {authLoading ? <PageLoading /> : !user ? (
                <Card>
                  <div className="flex gap-2 mb-4" role="tablist" aria-label="Account">
                    {(["register", "login"] as const).map((m) => <button key={m} role="tab" aria-selected={mode === m} onClick={() => setMode(m)} className={`min-h-11 px-4 rounded-control ${mode === m ? "bg-brand-soft font-medium" : ""}`}>{m === "register" ? "Create an account" : "I already have one"}</button>)}
                  </div>
                  <form className="grid gap-4" onSubmit={async (e) => { e.preventDefault(); await acctAsync.run(() => mode === "login" ? login(acct.email, acct.password) : register({ ...acct, phone: acct.phone || null, source: sp.get("utm_source") ?? "direct", referral_code: sp.get("ref") })); }}>
                    <ErrorAlert error={acctAsync.error} />
                    {mode === "register" && <Field label="Full name" autoComplete="name" required value={acct.full_name} onChange={(e) => setAcct({ ...acct, full_name: e.target.value })} error={fieldErr(acctAsync.error, "full_name")} />}
                    <Field label="Email address" type="email" autoComplete="email" required value={acct.email} onChange={(e) => setAcct({ ...acct, email: e.target.value })} error={fieldErr(acctAsync.error, "email")} />
                    {mode === "register" && <Field label="Mobile number" optional type="tel" autoComplete="tel" value={acct.phone} onChange={(e) => setAcct({ ...acct, phone: e.target.value })} hint="We text you booking reminders." error={fieldErr(acctAsync.error, "phone")} />}
                    <Field label="Password" type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} required minLength={mode === "register" ? 10 : undefined} value={acct.password} onChange={(e) => setAcct({ ...acct, password: e.target.value })} hint={mode === "register" ? "At least 10 characters." : undefined} error={fieldErr(acctAsync.error, "password")} />
                    {mode === "register" && <Check checked={acct.accept_terms} onChange={(e) => setAcct({ ...acct, accept_terms: e.target.checked })} required label={<>I accept the <Link className="underline" href="/legal/terms" target="_blank">terms</Link> and the <Link className="underline" href="/legal/privacy" target="_blank">privacy notice</Link>.</>} />}
                    <Button type="submit" loading={acctAsync.loading} className="justify-self-start">{mode === "register" ? "Create account and continue" : "Sign in and continue"}</Button>
                  </form>
                </Card>
              ) : !user.roles.includes("customer") ? (
                <Alert tone="warn" title="You are signed in with a professional or staff account.">Please sign out and use a customer account to book.</Alert>
              ) : (
                <>
                  <h2 className="text-lg font-display">Where is the visit?</h2>
                  {matching.length > 0 && (
                    <fieldset className="grid gap-2">
                      <legend className="sr-only">Saved addresses</legend>
                      {matching.map((a: any) => (
                        <label key={a.id} className={`cursor-pointer rounded-control border p-3 ${addrId === a.id ? "border-brand bg-brand-soft" : "border-line bg-surface"}`}>
                          <input type="radio" name="addr" className="sr-only" checked={addrId === a.id} onChange={() => setAddrId(a.id)} />
                          {a.line1}{a.line2 ? `, ${a.line2}` : ""}, {a.postcode}
                        </label>
                      ))}
                      <label className={`cursor-pointer rounded-control border p-3 ${addrId === "new" ? "border-brand bg-brand-soft" : "border-line bg-surface"}`}>
                        <input type="radio" name="addr" className="sr-only" checked={addrId === "new"} onChange={() => setAddrId("new")} />Use a different address in {normalisePostcode(postcode)}
                      </label>
                    </fieldset>
                  )}
                  {addrId === "new" && (
                    <div className="grid gap-4 max-w-md">
                      <Field label="Address line 1" autoComplete="address-line1" required value={addr.line1} onChange={(e) => setAddr({ ...addr, line1: e.target.value })} error={fieldErr(addrAsync.error, "line1")} />
                      <Field label="Address line 2" optional autoComplete="address-line2" value={addr.line2} onChange={(e) => setAddr({ ...addr, line2: e.target.value })} />
                      <Field label="Postcode" value={normalisePostcode(postcode)} readOnly hint="Change the postcode on the first step if this is wrong." />
                      <TextArea label="Access notes" optional value={addr.access_notes} onChange={(e) => setAddr({ ...addr, access_notes: e.target.value })} hint="For example key safe code, parking or pets. Shared with your professional once the booking is confirmed." />
                    </div>
                  )}
                  <TextArea label="Anything else your professional should know?" optional value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={500} />
                </>
              )}
            </div>
          )}

          {step === 3 && quote && slot && (
            <div className="grid gap-6">
              <Card>
                <h2 className="text-xl">Your booking</h2>
                <dl className="mt-3 grid gap-2 text-small">
                  <div className="flex justify-between gap-4"><dt className="text-muted">Service</dt><dd>{off.name}</dd></div>
                  <div className="flex justify-between gap-4"><dt className="text-muted">{frequency === "once" ? "When" : "First visit"}</dt><dd>{longDate(slot.starts_at)} at {timeFmt(slot.starts_at)}</dd></div>
                  <div className="flex justify-between gap-4"><dt className="text-muted">Length</dt><dd>{hours(quote.duration_minutes)}</dd></div>
                  <div className="flex justify-between gap-4"><dt className="text-muted">Professional</dt><dd>{pro === "any" ? "Best available" : pros?.find((p: any) => p.id === pro)?.display_name}</dd></div>
                  {frequency !== "once" && <div className="flex justify-between gap-4"><dt className="text-muted">Repeats</dt><dd>{frequency === "weekly" ? "Every week" : "Every two weeks"}, charged about a week before each visit</dd></div>}
                </dl>
              </Card>
              <Card>
                <h2 className="text-xl">Cancellation terms</h2>
                <ul className="mt-2 list-disc pl-5 text-small text-muted space-y-1">{quote.terms.summary.map((t) => <li key={t}>{t}</li>)}<li>If your professional cancels you get a full refund.</li></ul>
                <p className="mt-3 text-sm text-muted">Read the full <Link className="underline" href="/legal/cancellation" target="_blank">cancellation policy</Link>.</p>
              </Card>
              {referral?.credit_pence > 0 && frequency === "once" && <Check checked={useCredit} onChange={(e) => setUseCredit(e.target.checked)} label={`Use my ${money(referral.credit_pence)} account credit`} />}
              {!booking && <Check checked={accepted} onChange={(e) => setAccepted(e.target.checked)} label={<>I agree to the <Link className="underline" href="/legal/terms" target="_blank">terms of service</Link> and the cancellation terms above, and I ask for the service to start on the date shown.</>} />}
              <ErrorAlert error={book.error} />
              {!booking && <Button onClick={confirm} loading={book.loading} disabled={!accepted} className="justify-self-start">{frequency === "once" ? `Continue to payment: ${money(quote.total_pence)}` : "Start my plan"}</Button>}
              {frequency !== "once" && !booking && (
                <fieldset>
                  <legend className="text-sm font-medium mb-2">Payment method for plan visits {cfg?.payment_mode === "sandbox" && <Badge tone="warn">Test mode</Badge>}</legend>
                  {TEST_CARDS.map(([v, l]) => <label key={v} className="flex items-center gap-2 py-1"><input type="radio" name="card" checked={card === v} onChange={() => setCard(v)} /> {l}</label>)}
                </fieldset>
              )}
              {booking && !freeCard && (
                <Card className="border-brand">
                  <h2 className="text-xl">Payment</h2>
                  {cfg?.payment_mode === "sandbox" ? (
                    <Alert tone="warn" className="mt-3" title="Test mode: no real money is taken.">Choose a test card below. Live card payments need our payment provider&apos;s approval and keys.</Alert>
                  ) : <Alert tone="info" className="mt-3">Card entry is handled by our payment provider.</Alert>}
                  <p className="mt-3 text-sm text-muted">We are holding your slot until <strong>{timeFmt(booking.hold_expires_at)}</strong>. Booking reference {booking.reference}.</p>
                  <fieldset className="mt-4">
                    <legend className="sr-only">Test card</legend>
                    {TEST_CARDS.map(([v, l]) => <label key={v} className="flex items-center gap-2 py-1.5 min-h-11"><input type="radio" name="card2" checked={card === v} onChange={() => setCard(v)} className="h-4 w-4" /> {l}</label>)}
                  </fieldset>
                  <ErrorAlert error={payA.error} className="mt-3" />
                  {payA.error instanceof ApiError && <p className="mt-2 text-sm text-muted">Your slot is still held. You can try a different card.</p>}
                  <Button className="mt-4" loading={payA.loading} onClick={pay}>Pay {money(booking.payment?.amount_pence ?? booking.total_pence)}</Button>
                </Card>
              )}
            </div>
          )}

          <div className="mt-8 flex items-center justify-between gap-3">
            <Button variant="secondary" onClick={() => setStep(step - 1)} disabled={step === 0 || !!booking}>Back</Button>
            {step < 3 && <Button onClick={() => setStep(step + 1)} disabled={!canNext}>{step === 2 ? "Review booking" : "Continue"}</Button>}
          </div>
        </div>

        <aside aria-label="Price summary" className="lg:sticky lg:top-24">
          <Card>
            <h2 className="text-xl">Your price</h2>
            {!ready && <p className="mt-2 text-muted text-small">Enter your postcode{off.pricing_model === "tiered" ? " and property size" : ""} to see the full price.</p>}
            {ready && quoting && !quote && <div className="mt-3 space-y-2"><Skeleton /><Skeleton className="h-5 w-2/3" /></div>}
            {quote && (
              <div aria-live="polite" className={quoting ? "opacity-60" : ""}>
                <dl className="mt-3 divide-y divide-line text-small">
                  {quote.lines.map((l, i) => (
                    <div key={i} className="flex justify-between gap-4 py-2"><dt className={["discount", "promo", "bundle"].includes(l.kind) ? "text-success" : ""}>{l.description}</dt><dd className="tabular-nums whitespace-nowrap">{l.amount_pence < 0 ? "−" : ""}{money(Math.abs(l.amount_pence))}</dd></div>
                  ))}
                  <div className="flex justify-between gap-4 py-3 font-semibold text-base"><dt>Total payable</dt><dd className="tabular-nums">{money(quote.total_pence)}</dd></div>
                </dl>
                <p className="text-sm text-muted">Visit length {hours(quote.duration_minutes)}. {cfg ? `Booking fee ${money(cfg.booking_fee_pence)}.` : ""} No other charges.</p>
                {slot && step >= 1 && <p className="mt-3 text-small"><span className="text-muted">Starts:</span> {longDate(slot.starts_at)} at {timeFmt(slot.starts_at)}</p>}
              </div>
            )}
          </Card>
        </aside>
      </div>
    </Container>
  );
}

function Success({ booking, plan, off }: { booking: any; plan: any; off: any }) {
  return (
    <Container narrow className="py-14">
      <Alert tone="success" title={plan ? "Your plan is set up." : booking.status === "confirmed" ? "Your booking is confirmed." : "Thank you. Your booking is requested."}>
        {plan ? (
          <p>{plan.note ?? `We have scheduled ${plan.generation.created} visit${plan.generation.created === 1 ? "" : "s"} and will schedule more as they come within ${8} days.`}</p>
        ) : (
          <p>Reference <strong>{booking.reference}</strong>. {booking.status === "awaiting_provider" ? "Your professional has a few hours to accept. We will email you the moment they do, or find someone else." : "A confirmation is in your notifications."}</p>
        )}
      </Alert>
      <Card className="mt-6">
        <h2 className="text-xl">{off.name}</h2>
        {booking && <p className="mt-2 text-muted">{longDate(booking.starts_at)} at {timeFmt(booking.starts_at)}{booking.professional ? ` with ${booking.professional.display_name}` : ""}. Total {money(booking.total_pence)}.</p>}
        {plan && plan.upcoming.map((u: any) => <p key={u.id} className="mt-2 text-muted">{longDate(u.starts_at)} at {timeFmt(u.starts_at)} ({u.reference})</p>)}
        <p className="mt-4 text-sm text-muted">You can message your professional, reschedule or cancel from your account. The refund you would receive is shown before you cancel.</p>
      </Card>
      <div className="mt-6 flex gap-3">
        <LinkButton href={booking ? `/account/bookings/${booking.id}` : "/account"}>{booking ? "View booking" : "Go to my account"}</LinkButton>
        <LinkButton href="/account" variant="secondary">My account</LinkButton>
      </div>
    </Container>
  );
}
