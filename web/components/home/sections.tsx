"use client";
import Link from "next/link";
import { COMING_LATER, FAQ_GROUPS } from "@/lib/content";
import { hours, money } from "@/lib/format";
import { ArrowIcon, CheckIcon } from "@/components/icons";
import { Container } from "@/components/shell";
import { PostcodeCheck } from "@/components/postcode-check";
import { LinkButton, Skeleton } from "@/components/ui";
import { exampleQuote, useHome } from "./data";

const Eyebrow = ({ children, onBand }: { children: React.ReactNode; onBand?: boolean }) => (
  <p className={`text-small font-medium ${onBand ? "text-band-muted" : "text-brand"}`}>{children}</p>
);

export function Hero() {
  const { regular, config } = useHome();
  const q = regular && config ? exampleQuote(regular, config.booking_fee_pence) : null;
  return (
    <section aria-labelledby="hero" className="border-b border-line">
      <Container className="grid items-center gap-12 py-14 md:py-24 lg:grid-cols-[1.15fr_1fr]">
        <div>
          <Eyebrow>South-west London pilot</Eyebrow>
          <h1 id="hero" className="mt-4 text-h1">The same trusted cleaner, every visit.</h1>
          <p className="mt-6 max-w-xl text-lead text-muted">
            Book regular or end-of-tenancy cleaning. You see the full price and the cancellation terms before you pay, and you can ask for the same professional each time.
          </p>
          <div className="mt-8 max-w-xl rounded-card border border-line bg-surface p-5">
            <PostcodeCheck />
          </div>
        </div>
        <div className="rounded-panel border border-line bg-surface p-6 shadow-raised md:p-8" aria-label="Example quote">
          <p className="text-small text-muted">An example quote, from today&apos;s prices</p>
          <p className="mt-1 font-display text-h3">Three hours, the oven, every other week</p>
          {q ? (
            <>
              <dl className="mt-5 divide-y divide-line text-small">
                {q.lines.map((l) => (
                  <div key={l.label} className="flex justify-between gap-4 py-3">
                    <dt className={l.pence < 0 ? "text-success" : ""}>{l.label}</dt>
                    <dd className="tabular-nums whitespace-nowrap">{l.pence < 0 ? "−" : ""}{money(Math.abs(l.pence))}</dd>
                  </div>
                ))}
              </dl>
              <div className="flex items-baseline justify-between border-t border-ink pt-4">
                <span className="font-medium">Total payable</span>
                <span className="text-price font-display">{money(q.total)}</span>
              </div>
              <p className="mt-3 text-caption text-muted">The quote you are shown is the price you pay. Fees and prices can change during the pilot.</p>
            </>
          ) : (
            <div className="mt-5 space-y-3" aria-busy="true" aria-label="Loading prices"><Skeleton className="h-5" /><Skeleton className="h-5" /><Skeleton className="h-5" /><Skeleton className="h-10 w-1/2" /></div>
          )}
        </div>
      </Container>
    </section>
  );
}

export function FactStrip() {
  const { areas, config } = useHome();
  const free = config?.cancellation_terms?.tiers?.[0]?.hours_before;
  return (
    <section aria-label="At a glance" className="border-b border-line bg-sunken">
      <Container className="grid gap-4 py-5 text-small md:grid-cols-3">
        <p><span className="font-medium">Pilot districts: </span><span className="text-muted">{areas ? [...areas].sort((a, b) => a.outward_code.localeCompare(b.outward_code, "en", { numeric: true })).map((a) => a.outward_code).join(", ") : "loading"}</span></p>
        <p><span className="font-medium">Price first. </span><span className="text-muted">Every quote lists each line and the total before payment.</span></p>
        <p><span className="font-medium">Free cancellation </span><span className="text-muted">{free ? `more than ${free} hours before the start.` : "terms shown on every quote."}</span></p>
      </Container>
    </section>
  );
}

export function Cancellation() {
  const { config } = useHome();
  const tiers: { hours_before: number; refund_bps: number }[] | undefined = config?.cancellation_terms?.tiers;
  const sorted = tiers ? [...tiers].sort((a, b) => b.hours_before - a.hours_before) : [];
  const label = (i: number) => (i === 0 ? `More than ${sorted[0].hours_before} hours` : i === sorted.length - 1 ? `Under ${sorted[i - 1].hours_before} hours` : `${sorted[i].hours_before} to ${sorted[i - 1].hours_before} hours`);
  const refund = (bps: number) => (bps >= 10000 ? "Full refund" : bps <= 0 ? "No refund" : `${bps / 100}% refunded`);
  return (
    <section aria-labelledby="price" className="py-20 md:py-28">
      <Container className="grid gap-12 lg:grid-cols-[1fr_1.1fr] lg:items-center">
        <div>
          <Eyebrow>Transparent pricing</Eyebrow>
          <h2 id="price" className="mt-3 text-h2">The price you see is the price you pay.</h2>
          <p className="mt-5 max-w-prose text-lead text-muted">
            Your quote lists the cleaning, each extra, any plan discount, any booking fee and the final total. The cancellation terms are shown before you pay and stay fixed for that booking, even if we change our policy later.
          </p>
          <ul className="mt-6 grid gap-3 text-body">
            {["No charges are added after you confirm.", "If your professional cancels, you are refunded in full.", "Rescheduling is free when there is enough notice."].map((t) => (
              <li key={t} className="flex gap-3"><CheckIcon className="mt-1.5 shrink-0 text-brand" /> {t}</li>
            ))}
          </ul>
        </div>
        <div className="rounded-panel border border-line bg-surface p-6 md:p-8">
          <h3 className="text-h3">If you need to cancel</h3>
          <p className="mt-1 text-small text-muted">Refund by how far ahead you cancel. Read from our current settings.</p>
          {sorted.length ? (
            <ol className="mt-6 grid gap-3">
              {sorted.map((t, i) => (
                <li key={t.hours_before} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 rounded-card border border-line px-5 py-4" style={{ background: `color-mix(in srgb, var(--brand-soft) ${Math.round(t.refund_bps / 100)}%, var(--surface))` }}>
                  <span className="text-muted">{label(i)}</span>
                  <span className="whitespace-nowrap font-display text-h3">{refund(t.refund_bps)}</span>
                </li>
              ))}
            </ol>
          ) : <div className="mt-6"><Skeleton className="h-24" /></div>}
        </div>
      </Container>
    </section>
  );
}

export function Continuity() {
  const { regular } = useHome();
  const weekly = regular?.frequency_discounts.weekly;
  const fortnightly = regular?.frequency_discounts.fortnightly;
  return (
    <section aria-labelledby="same" className="border-y border-line bg-sunken py-20 md:py-28">
      <Container className="grid gap-12 lg:grid-cols-[1.1fr_1fr] lg:items-center">
        <div className="order-2 lg:order-1">
          <Eyebrow>Preferred professional</Eyebrow>
          <h2 id="same" className="mt-3 text-h2">The same person, because that is what makes it feel easy.</h2>
          <ol className="mt-8 grid gap-6">
            {[
              ["Book once", "We match you with the best available professional for your postcode and time, or you can choose one."],
              ["Save them", "After a visit you can save a professional as a favourite."],
              ["Ask for them again", `Request them by name, or set up a weekly or fortnightly plan${weekly ? ` and save ${weekly / 100}% or ${(fortnightly ?? 0) / 100}% on labour` : ""}. We schedule around them.`],
            ].map(([t, d], i) => (
              <li key={t} className="grid grid-cols-[2.5rem_1fr] gap-4">
                <span className="font-display text-h3 text-accent">{i + 1}</span>
                <div><h3 className="text-h3">{t}</h3><p className="mt-1 text-muted">{d}</p></div>
              </li>
            ))}
          </ol>
          <p className="mt-8 text-small text-muted">Your preferred professional is a preference, not a guarantee. If they are not free, we offer the best available alternative and tell you.</p>
        </div>
        <div className="order-1 lg:order-2">
          <div className="mx-auto max-w-sm rounded-panel border border-line bg-surface p-6" aria-label="Example professional profile">
            <p className="inline-block rounded-full bg-accent-soft px-3 py-1 text-caption font-medium text-accent">Example profile</p>
            <div className="mt-5 flex items-center gap-4">
              <span aria-hidden className="grid h-14 w-14 place-items-center rounded-full bg-brand-soft font-display text-h3 text-brand">E.K.</span>
              <div><p className="font-display text-h3">Example professional</p><p className="text-small text-muted">No reviews yet</p></div>
            </div>
            <ul className="mt-6 divide-y divide-line text-small">
              {["Identity document checked", "Right to work checked", "Public liability insurance certificate seen"].map((b) => (
                <li key={b} className="flex items-center gap-3 py-3"><CheckIcon className="text-brand" /> {b}</li>
              ))}
            </ul>
            <p className="mt-4 text-caption text-muted">A badge appears on a real profile only when we have approved that document and it is still in date.</p>
          </div>
        </div>
      </Container>
    </section>
  );
}

export function Verification() {
  return (
    <section aria-labelledby="trust" className="bg-band py-20 text-band-fg md:py-28">
      <Container className="grid gap-12 lg:grid-cols-2">
        <div>
          <Eyebrow onBand>Trust and safety</Eyebrow>
          <h2 id="trust" className="mt-3 text-h2">What we check, and what we do not claim.</h2>
          <p className="mt-5 max-w-prose text-lead text-band-muted">
            Before anyone can take a booking, a member of our team reviews three documents. We would rather list them than use a word like &quot;vetted&quot;.
          </p>
          <ul className="mt-8 grid gap-5">
            {[
              ["Identity", "A government-issued photo document, reviewed against the person who applied."],
              ["Right to work in the UK", "The evidence they provide, reviewed before approval."],
              ["Public liability insurance", "The certificate, with its expiry date tracked. If it lapses, they stop receiving bookings."],
            ].map(([t, d]) => (
              <li key={t} className="flex gap-4"><CheckIcon className="mt-1 shrink-0" size={22} /><div><p className="font-medium">{t}</p><p className="text-band-muted">{d}</p></div></li>
            ))}
          </ul>
        </div>
        <div className="self-start rounded-panel border border-band-muted/30 p-6 md:p-8">
          <h3 className="text-h3">What we do not claim</h3>
          <ul className="mt-5 grid gap-4 text-band-muted">
            <li>We do not run our own criminal record checks. An enhanced DBS certificate on a profile was obtained by the professional, and shows only if we have approved it.</li>
            <li>We do not guarantee any individual visit, though we will put things right where we agree it fell short.</li>
            <li>We do not offer our own insurance in place of the professional&apos;s. The certificate we have seen is theirs.</li>
          </ul>
          <Link href="/trust" className="mt-8 inline-flex min-h-11 items-center gap-2 font-medium underline underline-offset-4">Read the full trust and safety page <ArrowIcon /></Link>
        </div>
      </Container>
    </section>
  );
}

export function HowItWorks() {
  const steps = [
    ["Your postcode", "We only offer times where an approved professional covers your area."],
    ["Your quote", "Choose the length or the size of your home, and any extras. See the total."],
    ["Your time", "Pick from times when someone is actually free, including travel time between jobs."],
    ["Your payment", "Pay by card to confirm. Your professional is paid a few days after the visit."],
  ];
  return (
    <section aria-labelledby="how" className="py-20 md:py-28">
      <Container>
        <h2 id="how" className="max-w-2xl text-h2">From postcode to a clean home in four steps.</h2>
        <ol className="mt-12 grid gap-8 md:grid-cols-4">
          {steps.map(([t, d], i) => (
            <li key={t} className="relative border-t-2 border-ink pt-5">
              <span className="font-display text-h2 text-accent">{i + 1}</span>
              <h3 className="mt-2 text-h3">{t}</h3>
              <p className="mt-2 text-muted">{d}</p>
            </li>
          ))}
        </ol>
      </Container>
    </section>
  );
}

export function Services() {
  const { regular, eot, bundles } = useHome();
  const fromTier = eot?.tiers.length ? Math.min(...eot.tiers.map((t) => t.price_pence)) : null;
  return (
    <section aria-labelledby="services" className="border-t border-line py-20 md:py-28">
      <Container>
        <h2 id="services" className="text-h2">Two services, done properly.</h2>
        <div className="mt-10 grid gap-6 lg:grid-cols-[3fr_2fr]">
          <Link href="/services/home-cleaning/regular-cleaning" className="group flex flex-col justify-between rounded-panel border border-line bg-surface p-8 hover:border-brand md:p-10">
            <div>
              <p className="text-small text-muted">{regular ? `From ${money(regular.hourly_rate_pence)} an hour, ${hours(regular.min_minutes)} minimum` : "Hourly pricing"}</p>
              <h3 className="mt-2 text-h2 group-hover:text-brand">Regular home cleaning</h3>
              <p className="mt-4 max-w-prose text-lead text-muted">One-off, weekly or fortnightly, with the same professional if you wish. Plans are discounted.</p>
            </div>
            <span className="mt-8 inline-flex items-center gap-2 font-medium text-brand">See what is included <ArrowIcon className="transition-transform group-hover:translate-x-1" /></span>
          </Link>
          <Link href="/services/home-cleaning/end-of-tenancy-cleaning" className="group flex flex-col justify-between rounded-panel border border-line bg-surface p-8 hover:border-brand">
            <div>
              <p className="text-small text-muted">{fromTier ? `Fixed price from ${money(fromTier)}` : "Fixed prices"}</p>
              <h3 className="mt-2 text-h3 group-hover:text-brand">End of tenancy cleaning</h3>
              <p className="mt-3 text-muted">A checklist-led deep clean priced by number of bedrooms, with a re-clean if your agent raises an issue within 48 hours.</p>
            </div>
            <span className="mt-8 inline-flex items-center gap-2 font-medium text-brand">See prices by size <ArrowIcon className="transition-transform group-hover:translate-x-1" /></span>
          </Link>
        </div>
        {bundles && bundles.length > 0 && (
          <div className="mt-8">
            <p className="text-small font-medium">Bundles</p>
            <ul className="mt-3 flex flex-wrap gap-3">
              {bundles.map((b) => (
                <li key={b.slug}><Link href={`/book/${b.offering}?bundle=${b.slug}`} className="inline-flex min-h-11 items-center gap-2 rounded-full border border-line bg-surface px-4 text-small hover:border-brand">{b.name} <span className="text-success">{b.discount_bps / 100}% off</span></Link></li>
              ))}
            </ul>
          </div>
        )}
        <p className="mt-8 max-w-prose text-small text-muted">Coming later, once we have defined the right checks for each trade: {COMING_LATER.map((c) => c.name.toLowerCase()).join(", ")}.</p>
      </Container>
    </section>
  );
}

export function Questions() {
  const picks = [FAQ_GROUPS[0].items[0], FAQ_GROUPS[1].items[0], FAQ_GROUPS[2].items[0], FAQ_GROUPS[2].items[1], FAQ_GROUPS[0].items[3]];
  return (
    <section aria-labelledby="faq" className="border-t border-line bg-sunken py-20 md:py-28">
      <Container className="grid gap-10 lg:grid-cols-[1fr_1.6fr]">
        <div>
          <h2 id="faq" className="text-h2">Questions people ask first.</h2>
          <p className="mt-4 text-muted">More answers are in the <Link className="underline underline-offset-4" href="/help">help centre</Link>.</p>
        </div>
        <div className="divide-y divide-line rounded-card border border-line bg-surface">
          {picks.map((f) => (
            <details key={f.q} className="group p-5">
              <summary className="flex min-h-6 cursor-pointer list-none justify-between gap-4 font-medium">{f.q}<span aria-hidden className="text-muted transition-transform group-open:rotate-45">+</span></summary>
              <p className="mt-3 max-w-prose text-muted">{f.a}</p>
            </details>
          ))}
        </div>
      </Container>
    </section>
  );
}

export function ForProfessionals() {
  return (
    <section aria-labelledby="pros" className="bg-band py-16 text-band-fg md:py-20">
      <Container className="grid gap-10 lg:grid-cols-[1.2fr_1fr] lg:items-center">
        <div>
          <h2 id="pros" className="text-h2">Are you a professional cleaner?</h2>
          <p className="mt-4 max-w-prose text-lead text-band-muted">Build a regular round of clients near you. You set your hours and areas, and you see what you will earn before you accept a job.</p>
          <div className="mt-8"><LinkButton href="/join" variant="secondary">See how it works for professionals</LinkButton></div>
        </div>
        <ul className="grid gap-4 text-band-muted">
          <li className="flex gap-3"><CheckIcon className="mt-1.5 shrink-0 text-band-fg" /> Commission is shown on every job, before you accept.</li>
          <li className="flex gap-3"><CheckIcon className="mt-1.5 shrink-0 text-band-fg" /> Paid a few days after each completed visit.</li>
          <li className="flex gap-3"><CheckIcon className="mt-1.5 shrink-0 text-band-fg" /> You are in business for yourself and can decline work.</li>
        </ul>
      </Container>
    </section>
  );
}

export function FinalCta() {
  return (
    <section aria-labelledby="final" className="pb-8 pt-20 md:pt-28">
      <Container narrow>
        <h2 id="final" className="text-center text-h2">Check your postcode.</h2>
        <p className="mx-auto mt-4 max-w-prose text-center text-lead text-muted">It takes a few seconds, and you will see your price before you give us anything else.</p>
        <div className="mx-auto mt-8 max-w-xl rounded-card border border-line bg-surface p-5"><PostcodeCheck /></div>
      </Container>
    </section>
  );
}
