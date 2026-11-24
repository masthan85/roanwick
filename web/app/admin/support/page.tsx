"use client";
import Link from "next/link";
import { useState } from "react";
import useSWR from "swr";
import { api, fetcher, qs } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { money, shortDate } from "@/lib/format";
import { PageHeader } from "@/components/admin";
import { Badge, Button, Card, Empty, ErrorAlert, Field, PageLoading, Panel, Select, Tabs, TextArea, statusTone, useAsync } from "@/components/ui";

export default function Support() {
  const [tab, setTab] = useState("complaints");
  return (
    <div>
      <PageHeader title="Complaints, refunds and tickets" />
      <Tabs label="Queues" value={tab} onChange={setTab} tabs={[{ id: "complaints", label: "Complaints" }, { id: "refunds", label: "Refund requests" }, { id: "tickets", label: "Tickets" }]} />
      <Panel id={tab}>
        {tab === "complaints" && <Complaints />}
        {tab === "refunds" && <Refunds />}
        {tab === "tickets" && <Tickets />}
      </Panel>
    </div>
  );
}

function Complaints() {
  const { can } = useAuth();
  const [status, setStatus] = useState("open");
  const { data, error, isLoading, mutate } = useSWR(`/admin/complaints${qs({ status, page_size: 30 })}`, fetcher);
  const [f, setF] = useState<Record<string, { status: string; resolution: string; refund: string; funded: string }>>({});
  const a = useAsync();
  const get = (id: string) => f[id] ?? { status: "resolved", resolution: "", refund: "", funded: "platform" };
  const set = (id: string, patch: object) => setF({ ...f, [id]: { ...get(id), ...patch } });
  return (
    <div className="grid gap-4">
      <Select label="Show" value={status} onChange={(e) => setStatus(e.target.value)} className="max-w-xs"><option value="open">Open</option><option value="investigating">Investigating</option><option value="resolved">Resolved</option><option value="rejected">Rejected</option></Select>
      <ErrorAlert error={error || a.error} />
      {isLoading && <PageLoading />}
      {data?.items.length === 0 && <Empty title="No complaints in this queue" />}
      {data?.items.map((c: any) => (
        <Card key={c.id}>
          <div className="flex flex-wrap justify-between gap-3">
            <div><p className="font-medium">{c.category.replace("_", " ")} · {c.reference}</p><p className="text-sm text-muted">{c.customer} about {c.provider ?? "no professional"} · <Link className="underline" href={`/admin/bookings/${c.booking_id}`}>{c.booking_reference}</Link> · {shortDate(c.created_at)}</p></div>
            <div className="flex gap-2">{c.severity === "high" && <Badge tone="danger">High severity</Badge>}<Badge tone={statusTone(c.status)}>{c.status}</Badge></div>
          </div>
          <p className="mt-3 text-small">{c.description}</p>
          {c.resolution && <p className="mt-2 rounded-control bg-sunken p-3 text-small">Outcome: {c.resolution}</p>}
          {["open", "investigating"].includes(c.status) && (
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <Select label="Decision" value={get(c.id).status} onChange={(e) => set(c.id, { status: e.target.value })}><option value="investigating">Investigating</option><option value="resolved">Resolved</option><option value="rejected">Not upheld</option></Select>
              {can("refunds.manage") && <Field label="Refund in pounds" optional type="number" step="0.01" min="0" value={get(c.id).refund} onChange={(e) => set(c.id, { refund: e.target.value })} />}
              {can("refunds.manage") && get(c.id).refund && <Select label="Who bears it?" value={get(c.id).funded} onChange={(e) => set(c.id, { funded: e.target.value })}><option value="platform">Platform</option><option value="provider">Professional</option></Select>}
              <TextArea label="Outcome, shown to the customer" className="sm:col-span-2" rows={2} value={get(c.id).resolution} onChange={(e) => set(c.id, { resolution: e.target.value })} />
              <Button loading={a.loading} className="justify-self-start" onClick={async () => { const x = get(c.id); await a.run(() => api(`/admin/complaints/${c.id}/decision`, { body: { status: x.status, resolution: x.resolution || null, refund_pence: x.refund ? Math.round(parseFloat(x.refund) * 100) : null, refund_funded_by: x.funded } })); mutate(); }}>Save decision</Button>
            </div>
          )}
        </Card>
      ))}
    </div>
  );
}

function Refunds() {
  const { data, error, isLoading, mutate } = useSWR("/admin/refund-requests?status=open&page_size=30", fetcher);
  const [x, setX] = useState<Record<string, { amount: string; note: string; funded: string }>>({});
  const a = useAsync();
  const get = (id: string) => x[id] ?? { amount: "", note: "", funded: "platform" };
  const set = (id: string, p: object) => setX({ ...x, [id]: { ...get(id), ...p } });
  const decide = async (r: any, decision: string) => { const v = get(r.id); await a.run(() => api(`/admin/refund-requests/${r.id}/decision`, { body: { decision, approved_pence: v.amount ? Math.round(parseFloat(v.amount) * 100) : null, funded_by: v.funded, note: v.note } })); mutate(); };
  return (
    <div className="grid gap-4">
      <ErrorAlert error={error || a.error} />
      {isLoading && <PageLoading />}
      {data?.items.length === 0 && <Empty title="No open refund requests" />}
      {data?.items.map((r: any) => (
        <Card key={r.id}>
          <p className="font-medium"><Link className="underline" href={`/admin/bookings/${r.booking_id}`}>{r.booking_reference}</Link> · {r.customer} · paid {money(r.total_pence)}</p>
          <p className="text-sm text-muted">Asked for {r.requested_pence ? money(r.requested_pence) : "an unspecified amount"} on {shortDate(r.created_at)}</p>
          <p className="mt-2 text-small">{r.reason}</p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <Field label="Approve amount in pounds" type="number" step="0.01" min="0.01" value={get(r.id).amount} onChange={(e) => set(r.id, { amount: e.target.value })} hint="Blank approves the amount requested, or the full booking if none." />
            <Select label="Who bears the cost?" value={get(r.id).funded} onChange={(e) => set(r.id, { funded: e.target.value })}><option value="platform">Platform</option><option value="provider">Professional</option></Select>
            <Field label="Decision note, shown to the customer" className="sm:col-span-2" value={get(r.id).note} onChange={(e) => set(r.id, { note: e.target.value })} />
            <div className="flex gap-2"><Button loading={a.loading} disabled={get(r.id).note.length < 3} onClick={() => decide(r, "approve")}>Approve refund</Button><Button variant="danger" loading={a.loading} disabled={get(r.id).note.length < 3} onClick={() => decide(r, "reject")}>Decline</Button></div>
          </div>
        </Card>
      ))}
    </div>
  );
}

function Tickets() {
  const { data, error, isLoading, mutate } = useSWR("/admin/tickets?status=open&page_size=30", fetcher);
  const [reply, setReply] = useState<Record<string, string>>({});
  const a = useAsync();
  return (
    <div className="grid gap-4">
      <ErrorAlert error={error || a.error} />
      {isLoading && <PageLoading />}
      {data?.items.length === 0 && <Empty title="No open tickets" />}
      {data?.items.map((t: any) => (
        <Card key={t.id}>
          <div className="flex justify-between gap-3"><p className="font-medium">{t.subject}</p><Badge tone="neutral">{t.kind.replace("_", " ")}</Badge></div>
          <p className="text-sm text-muted">{t.contact} · {t.reference} · {shortDate(t.created_at)}</p>
          <p className="mt-2 text-small whitespace-pre-wrap">{t.body}</p>
          <TextArea label="Reply" rows={2} className="mt-3" value={reply[t.id] ?? ""} onChange={(e) => setReply({ ...reply, [t.id]: e.target.value })} />
          <Button className="mt-3" loading={a.loading} disabled={(reply[t.id] ?? "").length < 3} onClick={async () => { await a.run(() => api(`/admin/tickets/${t.id}/reply`, { body: { response: reply[t.id], close: true } })); mutate(); }}>Send reply and close</Button>
        </Card>
      ))}
    </div>
  );
}
