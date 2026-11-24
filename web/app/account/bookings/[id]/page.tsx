"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import useSWR from "swr";
import { api, fetcher, qs } from "@/lib/api";
import { STATUS_LABEL, dateFmt, dateTime, hours, longDate, money, shortDate, timeFmt } from "@/lib/format";
import { Container } from "@/components/shell";
import { Alert, Badge, Button, Card, Empty, ErrorAlert, Field, LinkButton, Modal, PageLoading, Select, Spinner, Stars, TextArea, statusTone, useAsync } from "@/components/ui";

export default function BookingDetail() {
  const { id } = useParams<{ id: string }>();
  const { data: b, error, mutate } = useSWR(`/bookings/${id}`, fetcher, { refreshInterval: 20000 });
  const [modal, setModal] = useState<null | "cancel" | "reschedule" | "problem" | "refund" | "review">(null);
  if (error) return <Container narrow className="py-14"><ErrorAlert error={error} /><div className="mt-4"><LinkButton href="/account" variant="secondary">Back to my account</LinkButton></div></Container>;
  if (!b) return <PageLoading />;
  const active = ["pending_payment", "awaiting_provider", "confirmed"].includes(b.status);
  const mins = Math.round((new Date(b.ends_at).getTime() - new Date(b.starts_at).getTime()) / 60000);
  return (
    <Container className="py-10">
      <p className="text-sm"><Link href="/account" className="underline underline-offset-4">My account</Link> / {b.reference}</p>
      <div className="mt-2 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl md:text-4xl">{b.offering.name}</h1>
          <p className="mt-1 text-lg text-muted">{longDate(b.starts_at)} at {timeFmt(b.starts_at)} · {hours(mins)}</p>
        </div>
        <Badge tone={statusTone(b.status)}>{STATUS_LABEL[b.status]}</Badge>
      </div>

      {b.status === "pending_payment" && <Alert tone="warn" className="mt-6" title="Payment not completed">Your slot is held until {b.hold_expires_at ? timeFmt(b.hold_expires_at) : "shortly"}. <Link className="underline" href={`/book/${b.offering.slug}`}>Start again</Link> if it has lapsed.</Alert>}
      {b.status === "awaiting_provider" && !b.professional && <Alert tone="warn" className="mt-6" title="We are finding a professional for you">Your original professional could not make it. Our team is arranging a replacement and will be in touch. You can cancel for a full refund at any time.</Alert>}
      {b.status === "awaiting_provider" && b.professional && <Alert tone="info" className="mt-6" title="Waiting for your professional to accept">If they do not respond in time we will offer the visit to someone else. You will not be charged twice.</Alert>}

      <div className="mt-8 grid gap-6 lg:grid-cols-[1.4fr_1fr] items-start">
        <div className="grid gap-6">
          <Card>
            <h2 className="text-xl">Price</h2>
            <dl className="mt-3 divide-y divide-line text-small">
              {b.lines.map((l: any, i: number) => <div key={i} className="flex justify-between gap-4 py-2"><dt>{l.description}</dt><dd className="tabular-nums">{l.amount_pence < 0 ? "−" : ""}{money(Math.abs(l.amount_pence))}</dd></div>)}
              <div className="flex justify-between gap-4 py-3 font-semibold text-base"><dt>Total</dt><dd className="tabular-nums">{money(b.total_pence)}</dd></div>
            </dl>
            {b.payment && <p className="text-sm text-muted">Payment: {b.payment.status.replace("_", " ")}{b.payment.credit_applied_pence ? `, including ${money(b.payment.credit_applied_pence)} account credit` : ""}.</p>}
          </Card>
          <Card>
            <h2 className="text-xl">Address</h2>
            <p className="mt-2 text-small">{b.address.line1}{b.address.line2 ? `, ${b.address.line2}` : ""}, {b.address.city}, {b.address.postcode}</p>
            {b.address.access_notes && <p className="text-sm text-muted mt-1">Access: {b.address.access_notes}</p>}
          </Card>
          <Card>
            <h2 className="text-xl">History</h2>
            <ol className="mt-3 space-y-3">
              {b.history.map((h: any, i: number) => (
                <li key={i} className="flex gap-3 text-small"><span aria-hidden className="mt-2 h-2 w-2 rounded-full bg-brand shrink-0" /><div><p className="font-medium">{STATUS_LABEL[h.status] ?? h.status}</p><p className="text-muted text-sm">{dateTime(h.at)}{h.note ? ` · ${h.note}` : ""}</p></div></li>
              ))}
            </ol>
          </Card>
          {["confirmed", "in_progress", "completed", "awaiting_provider"].includes(b.status) && <Messages id={b.id} />}
        </div>

        <div className="grid gap-6">
          <Card>
            <h2 className="text-xl">Your professional</h2>
            {b.professional ? (
              <div className="mt-3">
                <Link className="font-display text-lg underline underline-offset-4" href={`/professionals/${b.professional.id}`}>{b.professional.display_name}</Link>
                <div className="mt-1"><Stars value={b.professional.rating_avg} count={b.professional.rating_count} /></div>
                <ul className="mt-3 text-sm text-muted space-y-1">{b.professional.badges.map((x: any) => <li key={x.type}>{x.label}{x.valid_until ? ` (valid to ${shortDate(x.valid_until)})` : ""}</li>)}</ul>
                {b.status === "completed" && <FavouriteButton id={b.professional.id} />}
              </div>
            ) : <p className="mt-2 text-muted">Not assigned yet.</p>}
          </Card>
          <Card>
            <h2 className="text-xl">Manage</h2>
            <div className="mt-3 grid gap-2">
              {b.status === "completed" && !b.reviewed && <Button onClick={() => setModal("review")}>Leave a review</Button>}
              {b.status === "completed" && <LinkButton href={`/book/${b.offering.slug}?rebook=${b.id}`} variant="secondary">Book again{b.professional ? ` with ${b.professional.display_name}` : ""}</LinkButton>}
              {active && b.status !== "pending_payment" && <Button variant="secondary" onClick={() => setModal("reschedule")}>Change date or time</Button>}
              {active && <Button variant="secondary" onClick={() => setModal("cancel")}>Cancel booking</Button>}
              {["completed", "in_progress", "cancelled"].includes(b.status) && <Button variant="secondary" onClick={() => setModal("problem")}>Report a problem</Button>}
              {["completed", "cancelled"].includes(b.status) && <Button variant="secondary" onClick={() => setModal("refund")}>Request a refund</Button>}
              {!active && !["completed", "in_progress", "cancelled"].includes(b.status) && <p className="text-sm text-muted">No actions available.</p>}
            </div>
          </Card>
          {b.terms?.summary && <Card><h2 className="text-lg">Cancellation terms for this booking</h2><ul className="mt-2 text-sm text-muted list-disc pl-5 space-y-1">{b.terms.summary.map((t: string) => <li key={t}>{t}</li>)}</ul></Card>}
        </div>
      </div>

      <CancelModal b={b} open={modal === "cancel"} onClose={() => setModal(null)} done={() => { setModal(null); mutate(); }} />
      <RescheduleModal b={b} open={modal === "reschedule"} onClose={() => setModal(null)} done={() => { setModal(null); mutate(); }} />
      <ProblemModal b={b} open={modal === "problem"} onClose={() => setModal(null)} />
      <RefundModal b={b} open={modal === "refund"} onClose={() => setModal(null)} />
      <ReviewModal b={b} open={modal === "review"} onClose={() => setModal(null)} done={() => { setModal(null); mutate(); }} />
    </Container>
  );
}

function FavouriteButton({ id }: { id: string }) {
  const { data, mutate } = useSWR("/favourites", fetcher);
  const fav = data?.some((p: any) => p.id === id);
  const a = useAsync();
  return (
    <div className="mt-4">
      <Button variant="secondary" loading={a.loading} aria-pressed={!!fav} onClick={async () => { await a.run(() => api(`/favourites/${id}`, { method: fav ? "DELETE" : "PUT" })); mutate(); }}>{fav ? "Saved as favourite" : "Save as favourite"}</Button>
      <ErrorAlert error={a.error} className="mt-2" />
    </div>
  );
}

function Messages({ id }: { id: string }) {
  const { data, mutate } = useSWR(`/bookings/${id}/messages`, fetcher, { refreshInterval: 10000 });
  const [text, setText] = useState("");
  const a = useAsync();
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView({ block: "nearest" }); }, [data?.length]);
  return (
    <Card>
      <h2 className="text-xl">Messages</h2>
      <div className="mt-3 max-h-80 overflow-y-auto space-y-2" aria-live="polite" aria-label="Conversation">
        {data?.length === 0 && <p className="text-muted text-small">No messages yet. Use this to share access details or ask a question. Please keep contact details out of messages so we can help if something goes wrong.</p>}
        {data?.map((m: any) => <div key={m.id} className={`max-w-[85%] rounded-xl px-3 py-2 text-small ${m.mine ? "ml-auto bg-brand-soft" : "bg-sunken"}`}><p>{m.body}</p><p className="text-xs text-muted mt-1">{m.mine ? "You" : "Professional"} · {dateTime(m.created_at)}</p></div>)}
        <div ref={end} />
      </div>
      <ErrorAlert error={a.error} className="mt-3" />
      <form className="mt-3 flex gap-2 items-end" onSubmit={async (e) => { e.preventDefault(); if (!text.trim()) return; const r = await a.run(() => api(`/bookings/${id}/messages`, { body: { body: text } })); if (r) { setText(""); mutate(); } }}>
        <Field label="Message" className="flex-1" value={text} onChange={(e) => setText(e.target.value)} maxLength={2000} />
        <Button type="submit" loading={a.loading}>Send</Button>
      </form>
    </Card>
  );
}

function CancelModal({ b, open, onClose, done }: any) {
  const { data, error } = useSWR(open ? `/bookings/${b.id}/cancellation-preview` : null, fetcher);
  const [reason, setReason] = useState("");
  const a = useAsync();
  return (
    <Modal open={open} onOpenChange={(o) => !o && onClose()} title="Cancel this booking?" description="Check the refund below before you confirm.">
      {error ? <ErrorAlert error={error} /> : !data ? <Spinner /> : (
        <div className="grid gap-4">
          {data.note ? <p>{data.note}</p> : (
            <div className="rounded-control bg-sunken p-4">
              <p className="text-lg font-display">Refund: {money(data.refund_pence)}</p>
              {data.retained_pence > 0 && <p className="text-sm text-muted mt-1">{money(data.retained_pence)} is kept under the cancellation terms, because there are {Math.round(data.hours_before)} hours until the start.</p>}
            </div>
          )}
          <TextArea label="Reason" optional value={reason} onChange={(e) => setReason(e.target.value)} rows={2} />
          <ErrorAlert error={a.error} />
          <div className="flex gap-3 justify-end">
            <Button variant="secondary" onClick={onClose}>Keep booking</Button>
            <Button variant="danger" loading={a.loading} onClick={async () => { if (await a.run(() => api(`/bookings/${b.id}/cancel`, { body: { reason } }))) done(); }}>Cancel booking</Button>
          </div>
        </div>
      )}
    </Modal>
  );
}

function RescheduleModal({ b, open, onClose, done }: any) {
  const slug = "regular-cleaning";
  const minutes = b.inputs?.minutes ?? null;
  const [other, setOther] = useState(false);
  const [from, setFrom] = useState(0);
  const d0 = new Date(); d0.setDate(d0.getDate() + from);
  const from_date = new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/London" }).format(d0);
  const postcode = b.address.postcode;
  const { data, error } = useSWR(open ? `/catalogue/slots${qs({ offering: b.offering.slug ?? slug, postcode, minutes: b.inputs?.bedrooms != null ? null : minutes, bedrooms: b.inputs?.bedrooms, addons: (b.inputs?.addons ?? []).join(","), from_date, days: 7, provider_id: other ? null : b.professional?.id })}` : null, fetcher);
  const [pick, setPick] = useState("");
  const a = useAsync();
  const days = data ? Object.entries(data.days as Record<string, any[]>) : [];
  return (
    <Modal open={open} onOpenChange={(o) => !o && onClose()} title="Change date or time" description="Free changes are possible when there is enough notice. Otherwise the cancellation terms apply.">
      <div className="grid gap-4">
        <ErrorAlert error={error || a.error} />
        {!data && !error && <Spinner />}
        {data && days.length === 0 && <Alert tone="warn">No times this week{!other ? " with your professional" : ""}. Try a later week{!other ? " or allow another professional" : ""}.</Alert>}
        <label className="flex items-center gap-2 text-small"><input type="checkbox" className="h-5 w-5" checked={other} onChange={(e) => setOther(e.target.checked)} /> Another professional is fine</label>
        <Select label="New time" value={pick} onChange={(e) => setPick(e.target.value)}>
          <option value="">Choose…</option>
          {days.map(([d, ss]) => <optgroup key={d} label={dateFmt(d + "T12:00:00Z", { weekday: "long", day: "numeric", month: "long" })}>{ss.map((s) => <option key={s.starts_at} value={s.starts_at}>{s.time}</option>)}</optgroup>)}
        </Select>
        <div className="flex justify-between gap-3">
          <Button variant="secondary" onClick={() => setFrom(from + 7)}>Later week</Button>
          <Button disabled={!pick} loading={a.loading} onClick={async () => { if (await a.run(() => api(`/bookings/${b.id}/reschedule`, { body: { starts_at: pick, allow_other_professional: other } }))) done(); }}>Confirm new time</Button>
        </div>
      </div>
    </Modal>
  );
}

function ProblemModal({ b, open, onClose }: any) {
  const [f, setF] = useState({ category: "quality", description: "" });
  const [ref, setRef] = useState<string | null>(null);
  const a = useAsync();
  return (
    <Modal open={open} onOpenChange={(o) => !o && onClose()} title="Report a problem" description="Tell us what happened. We aim to reply within 48 hours.">
      {ref ? <Alert tone="success" title="Thank you, we have your report.">Your reference is {ref}. We will email you with an update.</Alert> : (
        <form className="grid gap-4" onSubmit={async (e) => { e.preventDefault(); const r = await a.run(() => api<{ reference: string }>(`/bookings/${b.id}/complaints`, { body: f })); if (r) setRef(r.reference); }}>
          <ErrorAlert error={a.error} />
          <Select label="What kind of problem?" value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })}>
            {[["quality", "Quality of the clean"], ["lateness", "Arrived late"], ["no_show", "Professional did not arrive"], ["damage", "Damage to property"], ["conduct", "Conduct"], ["safety", "Safety concern"], ["other", "Something else"]].map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </Select>
          <TextArea label="What happened?" required minLength={10} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} hint="If there is a safety risk right now, contact the emergency services first." />
          <Button type="submit" loading={a.loading} className="justify-self-end">Send report</Button>
        </form>
      )}
    </Modal>
  );
}

function RefundModal({ b, open, onClose }: any) {
  const [reason, setReason] = useState("");
  const [amount, setAmount] = useState("");
  const [ok, setOk] = useState(false);
  const a = useAsync();
  return (
    <Modal open={open} onOpenChange={(o) => !o && onClose()} title="Request a refund" description={`Total paid: ${money(b.total_pence)}. Tell us why and how much you are asking for.`}>
      {ok ? <Alert tone="success" title="Request received">We will review it and email you our decision.</Alert> : (
        <form className="grid gap-4" onSubmit={async (e) => { e.preventDefault(); const r = await a.run(() => api(`/bookings/${b.id}/refund-requests`, { body: { reason, requested_pence: amount ? Math.round(parseFloat(amount) * 100) : null } })); if (r) setOk(true); }}>
          <ErrorAlert error={a.error} />
          <TextArea label="Why are you asking for a refund?" required minLength={10} value={reason} onChange={(e) => setReason(e.target.value)} />
          <Field label="Amount in pounds" optional type="number" step="0.01" min="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} hint="Leave blank if you are not sure." />
          <Button type="submit" loading={a.loading} className="justify-self-end">Submit request</Button>
        </form>
      )}
    </Modal>
  );
}

function ReviewModal({ b, open, onClose, done }: any) {
  const [f, setF] = useState({ rating: 5, punctuality: 5, comment: "" });
  const a = useAsync();
  return (
    <Modal open={open} onOpenChange={(o) => !o && onClose()} title="How was your visit?" description={b.professional ? `Your review of ${b.professional.display_name} is shown on their public profile.` : ""}>
      <form className="grid gap-4" onSubmit={async (e) => { e.preventDefault(); if (await a.run(() => api(`/bookings/${b.id}/review`, { body: { ...f, comment: f.comment || null } }))) done(); }}>
        <ErrorAlert error={a.error} />
        <Select label="Overall rating" value={f.rating} onChange={(e) => setF({ ...f, rating: Number(e.target.value) })}>{[5, 4, 3, 2, 1].map((n) => <option key={n} value={n}>{n} out of 5</option>)}</Select>
        <Select label="Punctuality" value={f.punctuality} onChange={(e) => setF({ ...f, punctuality: Number(e.target.value) })}>{[5, 4, 3, 2, 1].map((n) => <option key={n} value={n}>{n} out of 5</option>)}</Select>
        <TextArea label="Comments" optional value={f.comment} onChange={(e) => setF({ ...f, comment: e.target.value })} maxLength={1500} />
        <Button type="submit" loading={a.loading} className="justify-self-end">Submit review</Button>
      </form>
    </Modal>
  );
}
