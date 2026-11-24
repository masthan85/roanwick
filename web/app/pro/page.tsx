"use client";
import { CheckIcon } from "@/components/icons";
import { useState } from "react";
import useSWR from "swr";
import { api, fetcher, qs } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { dateTime, hours, longDate, money, percent, shortDate, timeFmt } from "@/lib/format";
import { Container } from "@/components/shell";
import { Alert, Badge, Button, Card, Check, DataTable, Empty, ErrorAlert, Field, Pager, PageLoading, Panel, Select, Stat, Tabs, TextArea, fieldErr, statusTone, useAsync } from "@/components/ui";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const DOC_TYPES: [string, string][] = [["identity", "Photo identity document"], ["right_to_work", "Right to work evidence"], ["public_liability", "Public liability insurance certificate"], ["dbs", "Enhanced DBS certificate (optional)"], ["qualification", "Qualification (optional)"]];

export default function ProDashboard() {
  const { user } = useAuth();
  const { data: profile, mutate: reloadProfile } = useSWR("/provider/profile", fetcher);
  const [tab, setTab] = useState("jobs");
  if (!profile) return <PageLoading />;
  const approved = profile.status === "approved";
  const tabs = [
    { id: "jobs", label: "Jobs" },
    { id: "setup", label: approved ? "Profile and documents" : "Get approved" },
    { id: "availability", label: "Availability" },
    { id: "earnings", label: "Earnings" },
    { id: "performance", label: "Reviews and performance" },
    { id: "support", label: "Support" },
  ];
  return (
    <Container className="py-10">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-3xl md:text-4xl">Hello, {profile.display_name}</h1>
        <Badge tone={statusTone(profile.status)}>{{ draft: "Application not submitted", submitted: "In review", approved: "Approved", rejected: "Needs changes", suspended: "Suspended" }[profile.status as string]}</Badge>
      </div>
      {!approved && <Alert tone={profile.status === "suspended" || profile.status === "rejected" ? "danger" : "info"} className="mt-4" title={profile.status === "submitted" ? "Your application is being reviewed" : profile.status === "draft" ? "Complete your application to start receiving jobs" : "Your account cannot take bookings"}>
        {profile.status_reason ? profile.status_reason : profile.status === "submitted" ? "Our team checks each document. We will email you when we have decided." : "Work through the checklist under Get approved. You cannot receive bookings until our team has approved you."}
      </Alert>}
      {approved && Object.values(profile.verification_gaps as Record<string, string[]>).some((g) => g.length) && <Alert tone="warn" className="mt-4" title="A document needs attention">One of your required documents has expired or is missing, so you are not shown to customers. Upload a replacement under Profile and documents.</Alert>}
      <div className="mt-6"><Tabs label="Professional sections" tabs={tabs} value={tab} onChange={setTab} /></div>
      <Panel id={tab}>
        {tab === "jobs" && <Jobs approved={approved} />}
        {tab === "setup" && <Setup profile={profile} reload={reloadProfile} />}
        {tab === "availability" && <Availability />}
        {tab === "earnings" && <Earnings />}
        {tab === "performance" && <Performance />}
        {tab === "support" && <ProSupport />}
      </Panel>
    </Container>
  );
}

function Jobs({ approved }: { approved: boolean }) {
  const [scope, setScope] = useState<"upcoming" | "past">("upcoming");
  const [page, setPage] = useState(1);
  const { data, error, isLoading, mutate } = useSWR(`/provider/jobs${qs({ scope, page, page_size: 10 })}`, fetcher, { refreshInterval: 30000 });
  const act = useAsync();
  const [open, setOpen] = useState<string | null>(null);
  const do_ = async (id: string, action: string) => { await act.run(() => api(`/provider/jobs/${id}/${action}`, { method: "POST", body: {} })); mutate(); };
  return (
    <div className="grid gap-4">
      <div className="flex gap-2" role="group" aria-label="Filter jobs">
        {(["upcoming", "past"] as const).map((w) => <Button key={w} variant={scope === w ? "primary" : "secondary"} aria-pressed={scope === w} onClick={() => { setScope(w); setPage(1); }}>{w === "upcoming" ? "Upcoming" : "Past"}</Button>)}
      </div>
      <ErrorAlert error={error || act.error} />
      {isLoading && <PageLoading />}
      {data?.items.length === 0 && <Empty title={scope === "upcoming" ? "No upcoming jobs" : "No past jobs"}>{approved ? "Jobs appear here as soon as a customer books you. Keep your availability up to date to be matched." : "Once you are approved and have set your hours, jobs will appear here."}</Empty>}
      {data?.items.map((j: any) => {
        const mins = Math.round((new Date(j.ends_at).getTime() - new Date(j.starts_at).getTime()) / 60000);
        return (
          <Card key={j.id}>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="font-display text-xl">{longDate(j.starts_at)} at {timeFmt(j.starts_at)}</p>
                <p className="text-muted">{j.offering.name} · {hours(mins)} · {j.customer.first_name} · {j.reference}</p>
              </div>
              <Badge tone={statusTone(j.status)}>{j.status.replace(/_/g, " ")}</Badge>
            </div>
            <p className="mt-3 text-small">{j.address.line1 ? `${j.address.line1}${j.address.line2 ? ", " + j.address.line2 : ""}, ${j.address.postcode}` : `${j.address.postcode} area. The full address is shared once you accept.`}</p>
            {j.address.access_notes && <p className="text-sm text-muted">Access: {j.address.access_notes}</p>}
            {j.customer_notes && <p className="text-sm text-muted">Customer notes: {j.customer_notes}</p>}
            <p className="mt-3 text-small">You earn <strong>{money(j.earnings_preview.net_pence)}</strong> <span className="text-muted">({money(j.earnings_preview.service_value_pence)} less {j.earnings_preview.commission_bps / 100}% commission of {money(j.earnings_preview.commission_pence)})</span></p>
            <div className="mt-4 flex flex-wrap gap-2">
              {j.status === "awaiting_provider" && <><Button loading={act.loading} onClick={() => do_(j.id, "accept")}>Accept</Button><Button variant="secondary" loading={act.loading} onClick={() => do_(j.id, "decline")}>Decline</Button></>}
              {j.status === "confirmed" && <><Button loading={act.loading} onClick={() => do_(j.id, "start")}>Start job</Button><Button variant="secondary" loading={act.loading} onClick={() => { if (confirm("Withdrawing is recorded on your performance record. Continue?")) do_(j.id, "decline"); }}>Withdraw</Button></>}
              {j.status === "in_progress" && <Button loading={act.loading} onClick={() => do_(j.id, "complete")}>Mark as complete</Button>}
              {["confirmed", "in_progress", "completed", "awaiting_provider"].includes(j.status) && <Button variant="ghost" onClick={() => setOpen(open === j.id ? null : j.id)}>{open === j.id ? "Hide messages" : "Messages"}</Button>}
            </div>
            {open === j.id && <JobMessages id={j.id} />}
          </Card>
        );
      })}
      {data && <Pager page={data.page} pageSize={data.page_size} total={data.total} onChange={setPage} />}
    </div>
  );
}

function JobMessages({ id }: { id: string }) {
  const { data, mutate } = useSWR(`/bookings/${id}/messages`, fetcher, { refreshInterval: 10000 });
  const [t, setT] = useState("");
  const a = useAsync();
  return (
    <div className="mt-4 border-t border-line pt-4">
      <div className="max-h-60 overflow-y-auto space-y-2" aria-live="polite">
        {data?.length === 0 && <p className="text-sm text-muted">No messages yet.</p>}
        {data?.map((m: any) => <div key={m.id} className={`max-w-[85%] rounded-xl px-3 py-2 text-small ${m.mine ? "ml-auto bg-brand-soft" : "bg-sunken"}`}>{m.body}<p className="text-xs text-muted mt-1">{m.mine ? "You" : "Customer"} · {dateTime(m.created_at)}</p></div>)}
      </div>
      <ErrorAlert error={a.error} className="mt-2" />
      <form className="mt-3 flex gap-2 items-end" onSubmit={async (e) => { e.preventDefault(); if (await a.run(() => api(`/bookings/${id}/messages`, { body: { body: t } }))) { setT(""); mutate(); } }}>
        <Field label="Message the customer" className="flex-1" value={t} onChange={(e) => setT(e.target.value)} required />
        <Button type="submit" loading={a.loading}>Send</Button>
      </form>
    </div>
  );
}

function Setup({ profile, reload }: { profile: any; reload: () => void }) {
  const { data: checklist, mutate: reloadList } = useSWR("/provider/checklist", fetcher);
  const { data: cats } = useSWR("/catalogue/categories", fetcher);
  const { data: areas } = useSWR("/public/areas", fetcher);
  const { data: docs, mutate: reloadDocs } = useSWR("/provider/documents", fetcher);
  const [f, setF] = useState({ display_name: profile.display_name, bio: profile.bio ?? "", years_experience: profile.years_experience ?? "", auto_accept: profile.auto_accept, accepts_jobs: profile.accepts_jobs });
  const [offerings, setOfferings] = useState<string[]>(profile.offering_ids);
  const [codes, setCodes] = useState<string[]>(profile.areas);
  const save = useAsync();
  const svc = useAsync();
  const submit = useAsync();
  const up = useAsync();
  const [doc, setDoc] = useState({ doc_type: "identity", title: "", reference: "", expires_on: "" });
  const [file, setFile] = useState<File | null>(null);
  const refresh = () => { reload(); reloadList(); };
  const editable = ["draft", "rejected", "approved", "submitted"].includes(profile.status);
  const allOfferings = (cats ?? []).filter((c: any) => c.available).flatMap((c: any) => c.offerings);
  return (
    <div className="grid gap-6 max-w-3xl">
      {checklist && profile.status !== "approved" && (
        <Card>
          <h2 className="text-xl">Application checklist</h2>
          <ul className="mt-3 space-y-2">{checklist.items.map((i: any) => <li key={i.key} className="flex gap-3 items-center"><span aria-hidden className={`h-6 w-6 rounded-full grid place-items-center text-xs ${i.done ? "bg-brand text-brand-fg" : "border border-line"}`}>{i.done ? <CheckIcon size={14} /> : null}</span><span className={i.done ? "text-muted" : ""}>{i.label}<span className="sr-only">{i.done ? " (done)" : " (to do)"}</span></span></li>)}</ul>
          <ErrorAlert error={submit.error} className="mt-4" />
          {checklist.status === "submitted" ? <p className="mt-4 text-muted">Submitted. We will review your documents shortly.</p> : <Button className="mt-4" disabled={!checklist.ready_to_submit} loading={submit.loading} onClick={async () => { await submit.run(() => api("/provider/submit", { method: "POST" })); refresh(); }}>Submit for review</Button>}
        </Card>
      )}
      <Card>
        <h2 className="text-xl">Your profile</h2>
        <form className="mt-4 grid gap-4" onSubmit={async (e) => { e.preventDefault(); await save.run(() => api("/provider/profile", { method: "PATCH", body: { ...f, years_experience: f.years_experience === "" ? null : Number(f.years_experience) } })); refresh(); }}>
          <ErrorAlert error={save.error} />
          <Field label="Name shown to customers" value={f.display_name} onChange={(e) => setF({ ...f, display_name: e.target.value })} error={fieldErr(save.error, "display_name")} />
          <TextArea label="About you" value={f.bio} onChange={(e) => setF({ ...f, bio: e.target.value })} hint="At least 30 characters. Customers read this before choosing you." error={fieldErr(save.error, "bio")} />
          <Field label="Years of experience" type="number" min={0} max={60} value={f.years_experience} onChange={(e) => setF({ ...f, years_experience: e.target.value })} className="max-w-xs" />
          <Check checked={f.auto_accept} onChange={(e) => setF({ ...f, auto_accept: e.target.checked })} label="Confirm bookings automatically when they fall inside my published hours. If off, I review each one first." />
          <Check checked={f.accepts_jobs} onChange={(e) => setF({ ...f, accepts_jobs: e.target.checked })} label="I am currently taking new bookings (switch off for a break)." />
          <Button type="submit" loading={save.loading} className="justify-self-start">Save profile</Button>
        </form>
      </Card>
      <Card>
        <h2 className="text-xl">Services and areas</h2>
        <ErrorAlert error={svc.error} className="mt-3" />
        <fieldset className="mt-4"><legend className="text-sm font-medium mb-2">Services you offer</legend>
          {allOfferings.map((o: any) => <Check key={o.id} className="py-1" checked={offerings.includes(o.id)} onChange={(e) => setOfferings(e.target.checked ? [...offerings, o.id] : offerings.filter((x) => x !== o.id))} label={o.name} />)}
        </fieldset>
        <fieldset className="mt-4"><legend className="text-sm font-medium mb-2">Postcode districts you cover</legend>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-1">{(areas ?? []).map((a: any) => <Check key={a.outward_code} checked={codes.includes(a.outward_code)} onChange={(e) => setCodes(e.target.checked ? [...codes, a.outward_code] : codes.filter((x) => x !== a.outward_code))} label={`${a.outward_code} ${a.name}`} />)}</div>
        </fieldset>
        <Button className="mt-4" loading={svc.loading} onClick={async () => { await svc.run(async () => { await api("/provider/services", { method: "PUT", body: { offering_ids: offerings } }); await api("/provider/areas", { method: "PUT", body: { outward_codes: codes } }); }); refresh(); }}>Save services and areas</Button>
      </Card>
      <Card>
        <h2 className="text-xl">Documents</h2>
        <p className="text-sm text-muted mt-1">PDF, PNG or JPEG up to 5MB. Our team reviews each document. Once approved it is shown on your public profile as a checked item, with its expiry date if it has one.</p>
        <ul className="mt-4 divide-y divide-line">
          {docs?.length === 0 && <li className="py-2 text-muted">Nothing uploaded yet.</li>}
          {docs?.map((d: any) => (
            <li key={d.id} className="py-3 flex flex-wrap items-center justify-between gap-2">
              <div><p className="font-medium">{d.title}</p><p className="text-sm text-muted">{d.doc_type.replace(/_/g, " ")}{d.expires_on ? ` · expires ${shortDate(d.expires_on)}` : ""}{d.review_notes ? ` · ${d.review_notes}` : ""}</p></div>
              <div className="flex items-center gap-2"><Badge tone={statusTone(d.status)}>{d.status}</Badge>{d.status === "pending" && <Button variant="ghost" onClick={async () => { await api(`/provider/documents/${d.id}`, { method: "DELETE" }); reloadDocs(); refresh(); }}>Remove</Button>}</div>
            </li>
          ))}
        </ul>
        <form className="mt-5 grid gap-4 border-t border-line pt-5" onSubmit={async (e) => { e.preventDefault(); if (!file) return; const fd = new FormData(); fd.set("doc_type", doc.doc_type); fd.set("title", doc.title || DOC_TYPES.find((d) => d[0] === doc.doc_type)![1]); if (doc.reference) fd.set("reference", doc.reference); if (doc.expires_on) fd.set("expires_on", doc.expires_on); fd.set("file", file); if (await up.run(() => api("/provider/documents", { form: fd }))) { setFile(null); (e.target as HTMLFormElement).reset(); reloadDocs(); refresh(); } }}>
          <h3 className="text-lg">Upload a document</h3>
          <ErrorAlert error={up.error} />
          <Select label="Type" value={doc.doc_type} onChange={(e) => setDoc({ ...doc, doc_type: e.target.value })}>{DOC_TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</Select>
          <Field label="Reference or policy number" optional value={doc.reference} onChange={(e) => setDoc({ ...doc, reference: e.target.value })} />
          <Field label="Expiry date" type="date" optional={doc.doc_type !== "public_liability"} required={doc.doc_type === "public_liability"} value={doc.expires_on} onChange={(e) => setDoc({ ...doc, expires_on: e.target.value })} error={fieldErr(up.error, "expires_on")} />
          <div>
            <label htmlFor="docfile" className="block text-sm font-medium mb-1.5">File</label>
            <input id="docfile" type="file" accept="application/pdf,image/png,image/jpeg" required onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="block w-full text-sm" />
          </div>
          <Button type="submit" loading={up.loading} className="justify-self-start">Upload</Button>
        </form>
      </Card>
    </div>
  );
}

function Availability() {
  const { data, mutate } = useSWR("/provider/availability", fetcher);
  type Day = { on: boolean; start: string; end: string };
  const [rules, setRules] = useState<Record<number, Day> | null>(null);
  const save = useAsync();
  const exc = useAsync();
  const [x, setX] = useState({ on_date: "", start_time: "", end_time: "", note: "" });
  if (!data) return <PageLoading />;
  const state: Record<number, Day> = rules ?? Object.fromEntries(DAYS.map((_, i) => { const r = data.rules.find((q: any) => q.weekday === i); return [i, { on: !!r, start: r?.start_time ?? "08:00", end: r?.end_time ?? "17:00" }]; }));
  const set = (i: number, patch: object) => setRules({ ...state, [i]: { ...state[i], ...patch } });
  return (
    <div className="grid gap-6 max-w-3xl">
      <Card>
        <h2 className="text-xl">Weekly working hours</h2>
        <p className="text-sm text-muted mt-1">UK local time. Customers can only book you for visits that fit inside these hours, with a short gap between jobs.</p>
        <ErrorAlert error={save.error} className="mt-3" />
        <div className="mt-4 divide-y divide-line">
          {DAYS.map((d, i) => (
            <div key={d} className="py-3 flex flex-wrap items-center gap-3">
              <div className="w-32"><Check checked={state[i].on} onChange={(e) => set(i, { on: e.target.checked })} label={d} /></div>
              {state[i].on && <>
                <Field label={`${d} start`} type="time" value={state[i].start} onChange={(e) => set(i, { start: e.target.value })} />
                <Field label={`${d} finish`} type="time" value={state[i].end} onChange={(e) => set(i, { end: e.target.value })} />
              </>}
            </div>
          ))}
        </div>
        <Button className="mt-4" loading={save.loading} onClick={async () => { await save.run(() => api("/provider/availability", { method: "PUT", body: { rules: DAYS.flatMap((_, i) => (state[i].on ? [{ weekday: i, start_time: state[i].start, end_time: state[i].end }] : [])) } })); setRules(null); mutate(); }}>Save hours</Button>
      </Card>
      <Card>
        <h2 className="text-xl">Time off</h2>
        <ul className="mt-3 divide-y divide-line">
          {data.exceptions.length === 0 && <li className="py-2 text-muted">No time off booked.</li>}
          {data.exceptions.map((e: any) => <li key={e.id} className="py-2 flex justify-between gap-3"><span>{longDate(e.on_date + "T12:00:00Z")}{e.start_time ? ` ${e.start_time} to ${e.end_time}` : " (all day)"}{e.note ? ` · ${e.note}` : ""}</span><Button variant="ghost" onClick={async () => { await api(`/provider/availability/exceptions/${e.id}`, { method: "DELETE" }); mutate(); }}>Remove</Button></li>)}
        </ul>
        <form className="mt-4 grid gap-3 sm:grid-cols-2" onSubmit={async (e) => { e.preventDefault(); if (await exc.run(() => api("/provider/availability/exceptions", { body: { on_date: x.on_date, start_time: x.start_time || null, end_time: x.end_time || null, is_available: false, note: x.note || null } }))) { setX({ on_date: "", start_time: "", end_time: "", note: "" }); mutate(); } }}>
          <ErrorAlert error={exc.error} />
          <Field label="Date" type="date" required value={x.on_date} onChange={(e) => setX({ ...x, on_date: e.target.value })} className="sm:col-span-2" />
          <Field label="From" type="time" optional value={x.start_time} onChange={(e) => setX({ ...x, start_time: e.target.value })} hint="Leave both blank for the whole day." />
          <Field label="Until" type="time" optional value={x.end_time} onChange={(e) => setX({ ...x, end_time: e.target.value })} />
          <Field label="Note" optional value={x.note} onChange={(e) => setX({ ...x, note: e.target.value })} className="sm:col-span-2" />
          <Button type="submit" loading={exc.loading} className="justify-self-start">Block this time</Button>
        </form>
      </Card>
    </div>
  );
}

function Earnings() {
  const [page, setPage] = useState(1);
  const { data, error, isLoading } = useSWR(`/provider/earnings${qs({ page, page_size: 10 })}`, fetcher);
  if (error) return <ErrorAlert error={error} />;
  if (isLoading || !data) return <PageLoading />;
  return (
    <div className="grid gap-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Paid out" value={money(data.paid_pence)} />
        <Stat label="On the way" value={money(data.pending_pence)} note="Released a few days after each completed visit." />
        <Stat label="Commission" value={`${data.commission_bps / 100}%`} note="Your rate may differ if agreed individually." />
      </div>
      <DataTable caption="Earnings by job" empty="No earnings yet. They appear once you complete a job." rows={data.payouts.items} columns={[
        { key: "ref", header: "Job", render: (p) => p.booking_reference },
        { key: "date", header: "Completed", render: (p) => (p.completed_at ? shortDate(p.completed_at) : "") },
        { key: "gross", header: "Service value", render: (p) => money(p.service_value_pence) },
        { key: "comm", header: "Commission", render: (p) => `−${money(p.commission_pence)}` },
        { key: "net", header: "You receive", render: (p) => <strong>{money(p.net_pence)}</strong> },
        { key: "st", header: "Status", render: (p) => <div><Badge tone={statusTone(p.status)}>{p.status}</Badge><p className="text-xs text-muted mt-1">{p.status === "paid" ? `Paid ${shortDate(p.paid_at)}` : `Due ${shortDate(p.release_at)}`}{p.note ? ` · ${p.note}` : ""}</p></div> },
      ]} />
      <Pager page={data.payouts.page} pageSize={data.payouts.page_size} total={data.payouts.total} onChange={setPage} />
    </div>
  );
}

function Performance() {
  const { data: m } = useSWR("/provider/metrics", fetcher);
  const { data: reviews, mutate } = useSWR("/provider/reviews", fetcher);
  const { data: alerts } = useSWR("/provider/document-alerts", fetcher);
  const [replyId, setReplyId] = useState<string | null>(null);
  const [replyText, setReplyText] = useState("");
  const a = useAsync();
  return (
    <div className="grid gap-6">
      {alerts?.length > 0 && <Alert tone="warn" title="Documents expiring or expired">{alerts.map((d: any) => <p key={d.id}>{d.title}: {d.expired ? "expired" : "expires"} {shortDate(d.expires_on)}</p>)}</Alert>}
      {m && <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Average rating" value={m.rating_count ? m.rating_avg.toFixed(2) : "No reviews yet"} note={`${m.rating_count} reviews`} />
        <Stat label="Visits completed" value={m.jobs_completed} />
        <Stat label="On-time start rate" value={percent(m.on_time_rate)} note="Started within 15 minutes of the booked time." />
        <Stat label="Repeat customers" value={percent(m.repeat_customer_rate)} />
        <Stat label="Cancellations" value={m.cancellations} note="Withdrawals from confirmed jobs." />
        <Stat label="Complaints per 100 jobs" value={m.complaints_per_100_jobs ?? "Not enough data"} />
      </div>}
      <h2 className="text-2xl">Reviews</h2>
      <ErrorAlert error={a.error} />
      {reviews?.length === 0 && <Empty title="No reviews yet" />}
      {reviews?.map((r: any) => (
        <Card key={r.id}>
          <p className="font-medium">{r.rating} out of 5 · punctuality {r.punctuality} out of 5 <span className="text-muted font-normal">· {shortDate(r.created_at)}</span></p>
          {r.comment && <p className="mt-1">{r.comment}</p>}
          {r.reply ? <p className="mt-2 rounded-control bg-sunken p-3 text-small"><strong>Your reply:</strong> {r.reply}</p> : replyId === r.id ? (
            <form className="mt-3 grid gap-3" onSubmit={async (e) => { e.preventDefault(); if ((await a.run(() => api(`/provider/reviews/${r.id}/reply`, { body: { reply: replyText } }))) !== undefined) { setReplyId(null); setReplyText(""); mutate(); } }}>
              <TextArea label="Public reply" required value={replyText} onChange={(e) => setReplyText(e.target.value)} rows={3} />
              <Button type="submit" loading={a.loading} className="justify-self-start">Post reply</Button>
            </form>
          ) : <Button variant="ghost" onClick={() => { setReplyId(r.id); setReplyText(""); }}>Reply</Button>}
        </Card>
      ))}
    </div>
  );
}

function ProSupport() {
  const { data, mutate } = useSWR("/support/tickets", fetcher);
  const [f, setF] = useState({ kind: "general", subject: "", body: "" });
  const a = useAsync();
  return (
    <div className="grid gap-6 max-w-2xl">
      <Card>
        <h2 className="text-xl">Contact support or raise a dispute</h2>
        <form className="mt-4 grid gap-4" onSubmit={async (e) => { e.preventDefault(); if (await a.run(() => api("/support/tickets", { body: f }))) { setF({ kind: "general", subject: "", body: "" }); mutate(); } }}>
          <ErrorAlert error={a.error} />
          <Select label="What is it about?" value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })}>
            <option value="general">General question</option><option value="provider_dispute">A dispute about a job or review</option><option value="payout">A payout</option><option value="account">My account or documents</option>
          </Select>
          <Field label="Subject" required value={f.subject} onChange={(e) => setF({ ...f, subject: e.target.value })} error={fieldErr(a.error, "subject")} />
          <TextArea label="Details" required value={f.body} onChange={(e) => setF({ ...f, body: e.target.value })} error={fieldErr(a.error, "body")} />
          <Button type="submit" loading={a.loading} className="justify-self-start">Send</Button>
        </form>
      </Card>
      {data?.map((t: any) => <Card key={t.id}><div className="flex justify-between gap-3"><p className="font-medium">{t.subject}</p><Badge tone={statusTone(t.status)}>{t.status.replace("_", " ")}</Badge></div><p className="text-xs text-muted">Reference {t.reference}</p>{t.response && <p className="mt-3 rounded-control bg-brand-soft p-3 text-small"><strong>Our reply:</strong> {t.response}</p>}</Card>)}
    </div>
  );
}
