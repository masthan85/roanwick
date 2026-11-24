"use client";
import Link from "next/link";
import { useState } from "react";
import useSWR from "swr";
import { api, fetcher, qs } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { dateTime, longDate, money, shortDate, timeFmt } from "@/lib/format";
import { Container } from "@/components/shell";
import { BookingCard } from "@/components/booking-card";
import { Alert, Badge, Button, Card, Check, DataTable, Empty, ErrorAlert, Field, LinkButton, Pager, Panel, PageLoading, Select, Stars, Tabs, TextArea, fieldErr, statusTone, useAsync } from "@/components/ui";

const TABS = [
  { id: "bookings", label: "Bookings" },
  { id: "plans", label: "Plans" },
  { id: "payments", label: "Payments" },
  { id: "favourites", label: "Favourites" },
  { id: "referrals", label: "Refer a friend" },
  { id: "notifications", label: "Notifications" },
  { id: "profile", label: "Profile" },
  { id: "support", label: "Help" },
];

export default function Account() {
  const { user } = useAuth();
  const [tab, setTab] = useState("bookings");
  return (
    <Container className="py-10">
      <h1 className="text-3xl md:text-4xl">Hello, {user?.full_name.split(" ")[0]}</h1>
      {user && !user.email_verified && <Alert tone="warn" className="mt-4">Please confirm your email address using the link we sent you.</Alert>}
      <div className="mt-6"><Tabs label="Account sections" tabs={TABS} value={tab} onChange={setTab} /></div>
      <Panel id={tab}>
        {tab === "bookings" && <Bookings />}
        {tab === "plans" && <Plans />}
        {tab === "payments" && <Payments />}
        {tab === "favourites" && <Favourites />}
        {tab === "referrals" && <Referrals />}
        {tab === "notifications" && <Notifications />}
        {tab === "profile" && <Profile />}
        {tab === "support" && <Support />}
      </Panel>
    </Container>
  );
}

function Bookings() {
  const [which, setWhich] = useState<"upcoming" | "past">("upcoming");
  const [page, setPage] = useState(1);
  const { data, error, isLoading } = useSWR(`/bookings${qs({ upcoming: which === "upcoming", page, page_size: 10 })}`, fetcher);
  return (
    <div>
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex gap-2" role="group" aria-label="Filter bookings">
          {(["upcoming", "past"] as const).map((w) => <Button key={w} variant={which === w ? "primary" : "secondary"} aria-pressed={which === w} onClick={() => { setWhich(w); setPage(1); }}>{w === "upcoming" ? "Upcoming" : "Past"}</Button>)}
        </div>
        <LinkButton href="/book/regular-cleaning">Book a clean</LinkButton>
      </div>
      <div className="mt-6 grid gap-4">
        <ErrorAlert error={error} />
        {isLoading && <PageLoading />}
        {data && data.items.length === 0 && <Empty title={which === "upcoming" ? "No upcoming bookings" : "No past bookings yet"} action={which === "upcoming" ? <LinkButton href="/book/regular-cleaning">Get a price</LinkButton> : undefined}>{which === "upcoming" ? "When you book, your visits will appear here." : "Completed and cancelled visits are kept here."}</Empty>}
        {data?.items.map((b: any) => <BookingCard key={b.id} b={b} href={`/account/bookings/${b.id}`} />)}
        {data && <Pager page={data.page} pageSize={data.page_size} total={data.total} onChange={setPage} />}
      </div>
    </div>
  );
}

function Plans() {
  const { data, error, isLoading, mutate } = useSWR("/subscriptions", fetcher);
  const act = useAsync();
  const [skipId, setSkipId] = useState<string | null>(null);
  const [skipDate, setSkipDate] = useState("");
  return (
    <div className="grid gap-4">
      <ErrorAlert error={error || act.error} />
      {isLoading && <PageLoading />}
      {data?.length === 0 && <Empty title="No recurring plans" action={<LinkButton href="/book/regular-cleaning">Set up a plan</LinkButton>}>Weekly and fortnightly plans are discounted, and you can keep the same professional.</Empty>}
      {data?.map((s: any) => (
        <Card key={s.id}>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-xl">{s.offering}, {s.frequency}</h2>
              <p className="text-muted text-small">Starts at {s.start_time} · {s.preferred_professional ? `with ${s.preferred_professional.display_name}` : "best available professional"}</p>
            </div>
            <Badge tone={s.status === "active" ? "success" : "neutral"}>{s.status}</Badge>
          </div>
          <ul className="mt-3 text-small divide-y divide-line">
            {s.upcoming.map((u: any) => <li key={u.id} className="py-2 flex justify-between gap-3"><Link className="underline underline-offset-4" href={`/account/bookings/${u.id}`}>{dateTime(u.starts_at)}</Link><span className="text-muted">{u.status.replace("_", " ")}</span></li>)}
            {s.upcoming.length === 0 && <li className="py-2 text-muted">The next visit will be scheduled and charged about a week before it is due.</li>}
          </ul>
          <div className="mt-4 flex flex-wrap gap-2">
            {s.status === "active" ? <Button variant="secondary" loading={act.loading} onClick={async () => { await act.run(() => api(`/subscriptions/${s.id}/actions`, { body: { action: "pause" } })); mutate(); }}>Pause plan</Button> : <Button variant="secondary" loading={act.loading} onClick={async () => { await act.run(() => api(`/subscriptions/${s.id}/actions`, { body: { action: "resume" } })); mutate(); }}>Resume plan</Button>}
            <Button variant="secondary" onClick={() => setSkipId(s.id)}>Skip a visit</Button>
            <Button variant="danger" loading={act.loading} onClick={async () => { if (confirm("Cancel this plan and all upcoming visits? Refunds follow the cancellation terms.")) { await act.run(() => api(`/subscriptions/${s.id}/actions`, { body: { action: "cancel" } })); mutate(); } }}>Cancel plan</Button>
          </div>
          {skipId === s.id && (
            <form className="mt-4 flex flex-wrap items-end gap-3" onSubmit={async (e) => { e.preventDefault(); await act.run(() => api(`/subscriptions/${s.id}/actions`, { body: { action: "skip", skip_date: skipDate } })); setSkipId(null); mutate(); }}>
              <Field label="Date to skip" type="date" required value={skipDate} onChange={(e) => setSkipDate(e.target.value)} />
              <Button type="submit" loading={act.loading}>Skip this visit</Button>
            </form>
          )}
        </Card>
      ))}
    </div>
  );
}

function Payments() {
  const [page, setPage] = useState(1);
  const { data, error, isLoading } = useSWR(`/payments${qs({ page, page_size: 10 })}`, fetcher);
  return (
    <div>
      <ErrorAlert error={error} />
      {isLoading && <PageLoading />}
      {data && <DataTable caption="Payment history" empty="No payments yet." rows={data.items} columns={[
        { key: "d", header: "Date", render: (p) => shortDate(p.paid_at ?? p.created_at) },
        { key: "r", header: "Booking", render: (p) => <Link className="underline underline-offset-4" href={`/account/bookings/${p.booking_id}`}>{p.booking_reference}</Link> },
        { key: "a", header: "Card", render: (p) => money(p.amount_pence) },
        { key: "c", header: "Credit", render: (p) => (p.credit_applied_pence ? money(p.credit_applied_pence) : "None") },
        { key: "f", header: "Refunded", render: (p) => (p.refunded_pence ? money(p.refunded_pence) : "None") },
        { key: "s", header: "Status", render: (p) => <Badge tone={statusTone(p.status)}>{p.status.replace("_", " ")}</Badge> },
      ]} />}
      {data && <Pager page={data.page} pageSize={data.page_size} total={data.total} onChange={setPage} />}
    </div>
  );
}

function Favourites() {
  const { data, error, isLoading, mutate } = useSWR("/favourites", fetcher);
  return (
    <div className="grid gap-4">
      <ErrorAlert error={error} />
      {isLoading && <PageLoading />}
      {data?.length === 0 && <Empty title="No favourites yet">After a visit, save a professional you liked from the booking page. You can then ask for them by name next time.</Empty>}
      {data?.map((p: any) => (
        <Card key={p.id} className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <Link href={`/professionals/${p.id}`} className="font-display text-lg underline underline-offset-4">{p.display_name}</Link>
            <div><Stars value={p.rating_avg} count={p.rating_count} /></div>
          </div>
          <div className="flex gap-2">
            <LinkButton href="/book/regular-cleaning" variant="secondary">Book</LinkButton>
            <Button variant="ghost" onClick={async () => { await api(`/favourites/${p.id}`, { method: "DELETE" }); mutate(); }}>Remove</Button>
          </div>
        </Card>
      ))}
    </div>
  );
}

function Referrals() {
  const { data, error } = useSWR("/me/referral", fetcher);
  const [copied, setCopied] = useState(false);
  if (error) return <ErrorAlert error={error} />;
  if (!data) return <PageLoading />;
  return (
    <div className="grid gap-6 max-w-2xl">
      <Card>
        <h2 className="text-xl">Give {money(data.welcome_pence)}, get {money(data.reward_pence)}</h2>
        <p className="mt-2 text-muted">When a friend signs up with your link and has their first visit completed, you each receive account credit. Credit is applied to your next booking.</p>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <code className="rounded-control bg-sunken px-3 py-2 break-all">{data.share_url}</code>
          <Button variant="secondary" onClick={async () => { await navigator.clipboard.writeText(data.share_url); setCopied(true); }}>{copied ? "Copied" : "Copy link"}</Button>
        </div>
        <p className="mt-3 text-sm text-muted">Your code: <strong>{data.code}</strong> · Friends joined: {data.referred_count} · Credit available: <strong>{money(data.credit_pence)}</strong></p>
      </Card>
      {data.transactions.length > 0 && <DataTable caption="Credit history" rows={data.transactions} columns={[{ key: "at", header: "Date", render: (t) => shortDate(t.at) }, { key: "reason", header: "Reason", render: (t) => t.reason.replace(/_/g, " ") }, { key: "amt", header: "Amount", render: (t) => money(t.amount_pence) }]} />}
    </div>
  );
}

function Notifications() {
  const { data, error, isLoading, mutate } = useSWR("/notifications?page_size=30", fetcher);
  return (
    <div className="grid gap-3 max-w-3xl">
      <ErrorAlert error={error} />
      {isLoading && <PageLoading />}
      {data?.items.length === 0 && <Empty title="No notifications yet" />}
      {data?.unread > 0 && <Button variant="secondary" className="justify-self-start" onClick={async () => { await api("/notifications/read-all", { method: "POST" }); mutate(); }}>Mark all as read</Button>}
      {data?.items.map((n: any) => (
        <Card key={n.id} className={n.read ? "" : "border-brand"}>
          <p className="font-medium">{n.subject}{!n.read && <span className="ml-2"><Badge tone="brand">New</Badge></span>}</p>
          <p className="text-small text-muted mt-1">{n.body}</p>
          <p className="text-xs text-muted mt-2">{dateTime(n.created_at)}</p>
        </Card>
      ))}
    </div>
  );
}

function Profile() {
  const { user, reload, logout } = useAuth();
  const { data: addresses, mutate } = useSWR("/addresses", fetcher);
  const [f, setF] = useState({ full_name: user?.full_name ?? "", phone: user?.phone ?? "", marketing_consent: !!user?.marketing_consent });
  const save = useAsync();
  const [saved, setSaved] = useState(false);
  const pw = useAsync();
  const [pws, setPws] = useState({ current_password: "", new_password: "" });
  const [pwDone, setPwDone] = useState(false);
  const del = useAsync();
  const [delPw, setDelPw] = useState("");
  const [exportData, setExportData] = useState<string | null>(null);
  return (
    <div className="grid gap-8 max-w-2xl">
      <Card>
        <h2 className="text-xl">Your details</h2>
        <form className="mt-4 grid gap-4" onSubmit={async (e) => { e.preventDefault(); setSaved(false); const r = await save.run(() => api("/auth/me", { method: "PATCH", body: { ...f, phone: f.phone || null } })); if (r) { await reload(); setSaved(true); } }}>
          <ErrorAlert error={save.error} />
          <Field label="Full name" value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} error={fieldErr(save.error, "full_name")} />
          <Field label="Email address" value={user?.email ?? ""} readOnly hint="Contact us to change your email address." />
          <Field label="Mobile number" optional value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} error={fieldErr(save.error, "phone")} />
          <Check checked={f.marketing_consent} onChange={(e) => setF({ ...f, marketing_consent: e.target.checked })} label="Send me occasional offers by email." />
          <div className="flex items-center gap-3"><Button type="submit" loading={save.loading}>Save changes</Button>{saved && <span role="status" className="text-success text-sm">Saved</span>}</div>
        </form>
      </Card>
      <Card>
        <h2 className="text-xl">Saved addresses</h2>
        <ul className="mt-3 divide-y divide-line">
          {addresses?.length === 0 && <li className="py-2 text-muted">No saved addresses. One is saved when you book.</li>}
          {addresses?.map((a: any) => (
            <li key={a.id} className="py-3 flex justify-between gap-3 items-center">
              <span>{a.line1}{a.line2 ? `, ${a.line2}` : ""}, {a.postcode} {a.is_default && <Badge tone="brand">Default</Badge>}</span>
              <Button variant="ghost" onClick={async () => { try { await api(`/addresses/${a.id}`, { method: "DELETE" }); } catch (e: any) { alert(e.message); } mutate(); }}>Remove</Button>
            </li>
          ))}
        </ul>
      </Card>
      <Card>
        <h2 className="text-xl">Password</h2>
        <form className="mt-4 grid gap-4" onSubmit={async (e) => { e.preventDefault(); setPwDone(false); const r = await pw.run(() => api("/auth/change-password", { body: pws })); if (r !== undefined) { setPwDone(true); setPws({ current_password: "", new_password: "" }); } }}>
          <ErrorAlert error={pw.error} />
          <Field label="Current password" type="password" autoComplete="current-password" required value={pws.current_password} onChange={(e) => setPws({ ...pws, current_password: e.target.value })} />
          <Field label="New password" type="password" autoComplete="new-password" required minLength={10} value={pws.new_password} onChange={(e) => setPws({ ...pws, new_password: e.target.value })} hint="At least 10 characters." error={fieldErr(pw.error, "new_password")} />
          <div className="flex items-center gap-3"><Button type="submit" loading={pw.loading}>Change password</Button>{pwDone && <span role="status" className="text-success text-sm">Password changed</span>}</div>
        </form>
      </Card>
      <Card>
        <h2 className="text-xl">Your data</h2>
        <p className="mt-2 text-muted text-small">You can download a copy of your personal data, or close your account. Financial records are kept for the period the law requires.</p>
        <div className="mt-4 flex flex-wrap gap-3">
          <Button variant="secondary" onClick={async () => setExportData(JSON.stringify(await api("/auth/me/export"), null, 2))}>Show my data</Button>
          {exportData && <a className="inline-flex items-center min-h-11 underline" download="roanwick-my-data.json" href={`data:application/json;charset=utf-8,${encodeURIComponent(exportData)}`}>Download as a file</a>}
        </div>
        {exportData && <pre className="mt-3 max-h-64 overflow-auto rounded-control bg-sunken p-3 text-xs">{exportData}</pre>}
        <form className="mt-6 grid gap-3 border-t border-line pt-5" onSubmit={async (e) => { e.preventDefault(); if (!confirm("Close your account? This cannot be undone.")) return; const r = await del.run(() => api("/auth/me/delete", { body: { password: delPw } })); if (r !== undefined) { await logout(); window.location.href = "/"; } }}>
          <h3 className="text-lg">Close my account</h3>
          <ErrorAlert error={del.error} />
          <Field label="Confirm with your password" type="password" autoComplete="current-password" value={delPw} onChange={(e) => setDelPw(e.target.value)} required />
          <Button type="submit" variant="danger" loading={del.loading} className="justify-self-start">Close my account</Button>
        </form>
      </Card>
    </div>
  );
}

function Support() {
  const { data, mutate } = useSWR("/support/tickets", fetcher);
  const [f, setF] = useState({ subject: "", body: "" });
  const a = useAsync();
  return (
    <div className="grid gap-6 max-w-2xl">
      <Card>
        <h2 className="text-xl">Contact support</h2>
        <p className="text-sm text-muted mt-1">For a specific booking, open it and use Report a problem or Request a refund so we can see the details. Browse the <Link className="underline" href="/help">help centre</Link> for quick answers.</p>
        <form className="mt-4 grid gap-4" onSubmit={async (e) => { e.preventDefault(); const r = await a.run(() => api("/support/tickets", { body: { kind: "general", ...f } })); if (r) { setF({ subject: "", body: "" }); mutate(); } }}>
          <ErrorAlert error={a.error} />
          <Field label="Subject" required value={f.subject} onChange={(e) => setF({ ...f, subject: e.target.value })} error={fieldErr(a.error, "subject")} />
          <TextArea label="How can we help?" required value={f.body} onChange={(e) => setF({ ...f, body: e.target.value })} error={fieldErr(a.error, "body")} />
          <Button type="submit" loading={a.loading} className="justify-self-start">Send</Button>
        </form>
      </Card>
      {data?.map((t: any) => (
        <Card key={t.id}>
          <div className="flex justify-between gap-3"><p className="font-medium">{t.subject}</p><Badge tone={statusTone(t.status)}>{t.status.replace("_", " ")}</Badge></div>
          <p className="text-xs text-muted">Reference {t.reference} · {shortDate(t.created_at)}</p>
          {t.response && <p className="mt-3 rounded-control bg-brand-soft p-3 text-small"><strong>Our reply:</strong> {t.response}</p>}
        </Card>
      ))}
    </div>
  );
}
