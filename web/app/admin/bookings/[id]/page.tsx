"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import useSWR from "swr";
import { api, fetcher } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { STATUS_LABEL, dateTime, money } from "@/lib/format";
import { PageHeader } from "@/components/admin";
import { Alert, Badge, Button, Card, ErrorAlert, Field, PageLoading, Select, TextArea, statusTone, useAsync } from "@/components/ui";

export default function AdminBooking() {
  const { id } = useParams<{ id: string }>();
  const { can } = useAuth();
  const { data: b, error, mutate } = useSWR(`/admin/bookings/${id}`, fetcher);
  const { data: cands } = useSWR(b && can("bookings.manage") && ["awaiting_provider", "confirmed"].includes(b.status) ? `/admin/bookings/${id}/candidates` : null, fetcher);
  const { data: msgs } = useSWR(`/bookings/${id}/messages`, fetcher);
  const [pick, setPick] = useState("");
  const assign = useAsync();
  const cancel = useAsync();
  const refund = useAsync();
  const [reason, setReason] = useState("");
  const [rf, setRf] = useState({ amount: "", reason: "goodwill", funded_by: "platform", note: "" });
  if (error) return <ErrorAlert error={error} />;
  if (!b) return <PageLoading />;
  return (
    <div>
      <PageHeader title={b.reference}><Badge tone={statusTone(b.status)}>{STATUS_LABEL[b.status]}</Badge></PageHeader>
      <p className="mb-6"><Link className="underline underline-offset-4" href="/admin/bookings">Back to bookings</Link></p>
      <div className="grid gap-6 lg:grid-cols-2 items-start">
        <Card>
          <h2 className="text-xl">Summary</h2>
          <dl className="mt-3 grid gap-2 text-small">
            {[["Service", b.offering.name], ["Starts", dateTime(b.starts_at)], ["Customer", `${b.customer.name} (${b.customer.email})`], ["Professional", b.professional?.display_name ?? "Unassigned"], ["Assignment", b.assignment_mode], ["Address", `${b.address.line1}, ${b.address.postcode}`], ["Total", money(b.total_pence)]].map(([k, v]) => <div key={k} className="flex justify-between gap-4"><dt className="text-muted">{k}</dt><dd className="text-right">{v}</dd></div>)}
          </dl>
          {b.payment && <p className="mt-3 text-sm text-muted">Payment {b.payment.status}.</p>}
        </Card>
        <Card>
          <h2 className="text-xl">Economics</h2>
          {!b.financials ? <p className="mt-2 text-muted">Not finalised yet. Figures are written when the visit is completed or a late cancellation is charged.</p> : (
            <dl className="mt-3 grid gap-2 text-small">
              {[["Cash taken", b.financials.gross_paid_pence], ["Service value (commission basis)", b.financials.service_value_pence], ["Commission", b.financials.commission_pence], ["Booking fee", b.financials.fee_pence], ["Promotion cost (platform funded)", b.financials.promo_cost_pence], ["Provider earning", b.financials.provider_earning_pence], [`Processing fee (${b.financials.processing_fee_source})`, b.financials.processing_fee_pence], ["Refunded", b.financials.refunded_pence]].map(([k, v]) => <div key={k as string} className="flex justify-between gap-4"><dt className="text-muted">{k}</dt><dd className="tabular-nums">{money(v as number)}</dd></div>)}
            </dl>
          )}
        </Card>
        <Card>
          <h2 className="text-xl">Status history</h2>
          <ol className="mt-3 space-y-2 text-small">{b.history.map((h: any, i: number) => <li key={i}><strong>{STATUS_LABEL[h.status]}</strong> <span className="text-muted">{dateTime(h.at)}{h.note ? ` · ${h.note}` : ""}</span></li>)}</ol>
        </Card>
        <Card>
          <h2 className="text-xl">Conversation (read only)</h2>
          <div className="mt-3 space-y-2 max-h-64 overflow-y-auto">{msgs?.length === 0 && <p className="text-muted text-sm">No messages.</p>}{msgs?.map((m: any) => <p key={m.id} className="text-small"><strong>{m.sender_role === "customer" ? "Customer" : "Professional"}:</strong> {m.body}</p>)}</div>
        </Card>
        {can("bookings.manage") && ["awaiting_provider", "confirmed"].includes(b.status) && (
          <Card>
            <h2 className="text-xl">Assign a professional</h2>
            <p className="text-sm text-muted mt-1">Only professionals who are approved, verified for this service, cover the area and are free at this time are listed.</p>
            <ErrorAlert error={assign.error} className="mt-3" />
            <div className="mt-3 flex flex-wrap items-end gap-3">
              <Select label="Professional" value={pick} onChange={(e) => setPick(e.target.value)} className="min-w-56">
                <option value="">Choose…</option>{cands?.map((c: any) => <option key={c.id} value={c.id}>{c.display_name} ({c.rating_avg ? c.rating_avg.toFixed(1) : "new"}, {c.jobs_completed} jobs)</option>)}
              </Select>
              <Button disabled={!pick} loading={assign.loading} onClick={async () => { await assign.run(() => api(`/admin/bookings/${id}/assign`, { body: { provider_id: pick } })); mutate(); }}>Assign</Button>
            </div>
            {cands?.length === 0 && <Alert tone="warn" className="mt-3">Nobody is available. Contact the customer to move the visit, or cancel with a full refund.</Alert>}
          </Card>
        )}
        {can("refunds.manage") && can("bookings.manage") && !["completed", "cancelled", "expired"].includes(b.status) && (
          <Card>
            <h2 className="text-xl">Cancel for the customer</h2>
            <p className="text-sm text-muted mt-1">Full refund, whatever the notice.</p>
            <ErrorAlert error={cancel.error} className="mt-3" />
            <TextArea label="Reason" rows={2} value={reason} onChange={(e) => setReason(e.target.value)} className="mt-3" />
            <Button variant="danger" className="mt-3" disabled={reason.length < 3} loading={cancel.loading} onClick={async () => { if (confirm("Cancel and refund in full?")) { await cancel.run(() => api(`/admin/bookings/${id}/cancel`, { body: { reason } })); mutate(); } }}>Cancel and refund</Button>
          </Card>
        )}
        {can("refunds.manage") && ["completed", "cancelled"].includes(b.status) && (
          <Card>
            <h2 className="text-xl">Issue a refund</h2>
            <form className="mt-3 grid gap-3" onSubmit={async (e) => { e.preventDefault(); if (await refund.run(() => api(`/admin/bookings/${id}/refund`, { body: { amount_pence: Math.round(parseFloat(rf.amount) * 100), reason: rf.reason, funded_by: rf.funded_by, note: rf.note } }))) { setRf({ ...rf, amount: "", note: "" }); mutate(); } }}>
              <ErrorAlert error={refund.error} />
              <Field label="Amount in pounds" type="number" step="0.01" min="0.01" required value={rf.amount} onChange={(e) => setRf({ ...rf, amount: e.target.value })} />
              <Select label="Reason" value={rf.reason} onChange={(e) => setRf({ ...rf, reason: e.target.value })}><option value="goodwill">Goodwill</option><option value="complaint">Complaint</option><option value="other">Other</option></Select>
              <Select label="Who bears the cost?" value={rf.funded_by} onChange={(e) => setRf({ ...rf, funded_by: e.target.value })} hint="Provider-funded refunds reduce a payout that has not been paid yet."><option value="platform">Platform (reduces our contribution)</option><option value="provider">Professional (reduces their payout)</option></Select>
              <Field label="Note for the audit log" required value={rf.note} onChange={(e) => setRf({ ...rf, note: e.target.value })} />
              <Button type="submit" loading={refund.loading} className="justify-self-start">Issue refund</Button>
            </form>
          </Card>
        )}
      </div>
    </div>
  );
}
