"use client";
import { useState } from "react";
import useSWR from "swr";
import { api, fetcher, qs } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { money, percent, shortDate } from "@/lib/format";
import { PageHeader, useRange } from "@/components/admin";
import { Alert, Badge, Button, Card, DataTable, ErrorAlert, Field, PageLoading, Panel, Select, Stat, Tabs, useAsync } from "@/components/ui";

export default function Finance() {
  const [tab, setTab] = useState("finance");
  const r = useRange(30);
  return (
    <div>
      <PageHeader title="Finance and growth">{r.picker}</PageHeader>
      <Tabs label="Reports" value={tab} onChange={setTab} tabs={[{ id: "finance", label: "Revenue and margin" }, { id: "growth", label: "Acquisition and retention" }, { id: "costs", label: "Manual costs" }]} />
      <Panel id={tab}>
        {tab === "finance" && <Money from={r.from} to={r.to} />}
        {tab === "growth" && <Growth from={r.from} to={r.to} />}
        {tab === "costs" && <Costs />}
      </Panel>
    </div>
  );
}

function Money({ from, to }: { from: string; to: string }) {
  const { data: d, error, isLoading } = useSWR(`/admin/reports/finance${qs({ from, to })}`, fetcher);
  if (error) return <ErrorAlert error={error} />;
  if (isLoading || !d) return <PageLoading />;
  const m = (x: any, fmt: (v: any) => string = money) => fmt(x.value);
  return (
    <div className="grid gap-8">
      <Alert tone="info" title="How to read this page">
        Each figure is labelled Actual (from transactions), Estimate (calculated from configured assumptions) or Manual entry (typed in by staff). Gross booking value is money we collect; most of it belongs to professionals, so it is not revenue.
      </Alert>
      <section aria-labelledby="flow"><h2 id="flow" className="text-xl mb-3">From customer payment to contribution</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label="Gross booking value" value={m(d.gross_booking_value)} basis={d.gross_booking_value.basis} note={d.gross_booking_value.note} />
          <Stat label="Platform revenue" value={m(d.platform_revenue)} basis={d.platform_revenue.basis} note={d.platform_revenue.note} />
          <Stat label="Processing costs" value={m(d.processing_costs)} basis={d.processing_costs.basis} note={d.processing_costs.note} />
          <Stat label="Contribution" value={m(d.contribution)} basis={d.contribution.basis} note={d.contribution.note} />
          <Stat label="Contribution per booking" value={m(d.contribution_per_booking)} basis={d.contribution_per_booking.basis} note={`${d.finalised_bookings.value} finalised bookings`} />
          <Stat label="Commission" value={m(d.commission)} basis="actual" />
          <Stat label="Promotion cost" value={m(d.promotion_cost)} basis="actual" note="Platform-funded discounts" />
          <Stat label="Platform-funded refunds" value={m(d.platform_funded_refunds)} basis="actual" />
        </div>
      </section>
      <section aria-labelledby="prov"><h2 id="prov" className="text-xl mb-3">Professionals and refunds</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label="Provider earnings" value={m(d.provider_earnings)} basis="actual" note={d.provider_earnings.note} />
          <Stat label="Payouts paid" value={m(d.provider_payouts_paid)} basis="actual" />
          <Stat label="Payouts owed" value={m(d.provider_payouts_owed)} basis="actual" note={d.provider_payouts_owed.note} />
          <Stat label="Refunds issued" value={m(d.refunds_issued)} basis="actual" />
        </div>
      </section>
      <section aria-labelledby="unit"><h2 id="unit" className="text-xl mb-3">Customers and unit economics</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label="New paying customers" value={d.new_paying_customers.value} basis="actual" />
          <Stat label="Customer acquisition cost" value={m(d.customer_acquisition_cost)} basis="manual" note={d.customer_acquisition_cost.note} />
          <Stat label="Repeat booking rate" value={m(d.repeat_booking_rate, percent)} basis="actual" note={d.repeat_booking_rate.note} />
          <Stat label="Lifetime value estimate" value={m(d.lifetime_value_estimate)} basis="estimated" note={d.lifetime_value_estimate.note} />
        </div>
      </section>
      <section aria-labelledby="svc"><h2 id="svc" className="text-xl mb-3">By service</h2>
        <DataTable caption="Revenue and contribution by service" rows={d.by_service.map((x: any) => ({ ...x, id: x.key }))} empty="No finalised bookings in this period." columns={[{ key: "key", header: "Service" }, { key: "bookings", header: "Bookings" }, { key: "sv", header: "Service value", render: (x) => money(x.service_value_pence) }, { key: "rev", header: "Revenue", render: (x) => money(x.revenue_pence) }, { key: "con", header: "Contribution", render: (x) => money(x.contribution_pence) }]} />
      </section>
      <section aria-labelledby="area"><h2 id="area" className="text-xl mb-3">By postcode district</h2>
        <DataTable caption="Revenue and contribution by area" rows={d.by_area.map((x: any) => ({ ...x, id: x.key }))} empty="No finalised bookings in this period." columns={[{ key: "key", header: "District" }, { key: "bookings", header: "Bookings" }, { key: "sv", header: "Service value", render: (x) => money(x.service_value_pence) }, { key: "rev", header: "Revenue", render: (x) => money(x.revenue_pence) }, { key: "con", header: "Contribution", render: (x) => money(x.contribution_pence) }]} />
      </section>
    </div>
  );
}

function Growth({ from, to }: { from: string; to: string }) {
  const { data: d, error, isLoading } = useSWR(`/admin/reports/growth${qs({ from, to })}`, fetcher);
  if (error) return <ErrorAlert error={error} />;
  if (isLoading || !d) return <PageLoading />;
  const f = d.funnel;
  return (
    <div className="grid gap-8">
      <section><h2 className="text-xl mb-3">Booking funnel</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {[["Quotes", f.quotes], ["Bookings started", f.bookings_started], ["Paid", f.bookings_paid], ["Completed", f.bookings_completed], ["Waiting-list sign-ups", f.waitlist_signups]].map(([l, v]) => <Stat key={l as string} label={l as string} value={v as number} basis="actual" />)}
        </div>
        {f.bookings_started > 0 && <p className="mt-2 text-sm text-muted">{percent(f.bookings_paid / f.bookings_started)} of started bookings were paid.</p>}
      </section>
      <section><h2 className="text-xl mb-3">Acquisition by channel</h2>
        <DataTable caption="Acquisition by channel" rows={d.acquisition_by_channel.map((c: any) => ({ ...c, id: c.channel }))} empty="No sign-ups in this period." columns={[{ key: "channel", header: "Channel" }, { key: "signups", header: "Sign-ups" }, { key: "paying", header: "Paying customers", render: (c) => c.paying_customers }, { key: "conv", header: "Conversion", render: (c) => percent(c.conversion) }, { key: "spend", header: "Marketing spend", render: (c) => <span>{money(c.marketing_spend_pence)} <Badge tone="accent">Manual</Badge></span> }, { key: "cac", header: "CAC", render: (c) => (c.cac_pence == null ? "Not available" : money(c.cac_pence)) }]} />
      </section>
      <section><h2 className="text-xl mb-3">Retention by first-visit month</h2>
        <DataTable caption="Repeat booking by cohort" rows={d.retention_cohorts.map((c: any) => ({ ...c, id: c.cohort }))} empty="Retention appears once customers complete a first booking." columns={[{ key: "cohort", header: "Cohort" }, { key: "customers", header: "Customers" }, { key: "d30", header: "Rebooked within 30 days", render: (c) => `${c.d30} (${percent(c.d30_rate)})` }, { key: "d60", header: "Within 60 days", render: (c) => `${c.d60} (${percent(c.d60_rate)})` }, { key: "d90", header: "Within 90 days", render: (c) => `${c.d90} (${percent(c.d90_rate)})` }]} />
        <p className="mt-2 text-sm text-muted">{d.note}</p>
      </section>
    </div>
  );
}

function Costs() {
  const { can } = useAuth();
  const { data, error, mutate } = useSWR("/admin/costs", fetcher);
  const [f, setF] = useState({ category: "marketing", channel: "", period_start: "", period_end: "", amount: "", note: "" });
  const a = useAsync();
  return (
    <div className="grid gap-6 max-w-3xl">
      <Alert tone="info">These costs are typed in by staff and shown separately from transaction data. Marketing spend entered here drives customer acquisition cost. Use the same channel names as the sign-up source (for example google_ads).</Alert>
      <ErrorAlert error={error} />
      {can("finance.manage") && (
        <Card>
          <h2 className="text-xl">Add a cost</h2>
          <form className="mt-4 grid gap-4 sm:grid-cols-2" onSubmit={async (e) => { e.preventDefault(); if (await a.run(() => api("/admin/costs", { body: { category: f.category, channel: f.channel || null, period_start: f.period_start, period_end: f.period_end, amount_pence: Math.round(parseFloat(f.amount) * 100), note: f.note || null } }))) { setF({ ...f, amount: "", note: "" }); mutate(); } }}>
            <div className="sm:col-span-2"><ErrorAlert error={a.error} /></div>
            <Select label="Category" value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })}>{["marketing", "support", "insurance", "tools", "other"].map((c) => <option key={c} value={c}>{c}</option>)}</Select>
            <Field label="Channel" optional value={f.channel} onChange={(e) => setF({ ...f, channel: e.target.value })} />
            <Field label="Period start" type="date" required value={f.period_start} onChange={(e) => setF({ ...f, period_start: e.target.value })} />
            <Field label="Period end" type="date" required value={f.period_end} onChange={(e) => setF({ ...f, period_end: e.target.value })} />
            <Field label="Amount in pounds" type="number" step="0.01" min="0.01" required value={f.amount} onChange={(e) => setF({ ...f, amount: e.target.value })} />
            <Field label="Note" optional value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })} />
            <Button type="submit" loading={a.loading} className="justify-self-start">Add cost</Button>
          </form>
        </Card>
      )}
      <DataTable caption="Manual costs" rows={data ?? []} empty="No costs entered yet." columns={[{ key: "p", header: "Period", render: (c) => `${shortDate(c.period_start)} to ${shortDate(c.period_end)}` }, { key: "c", header: "Category", render: (c) => c.category }, { key: "ch", header: "Channel", render: (c) => c.channel ?? "" }, { key: "a", header: "Amount", render: (c) => money(c.amount_pence) }, { key: "n", header: "Note", render: (c) => c.note ?? "" }, { key: "x", header: "", render: (c) => can("finance.manage") ? <Button variant="ghost" onClick={async () => { if (confirm("Delete this cost?")) { await api(`/admin/costs/${c.id}`, { method: "DELETE" }); mutate(); } }}>Delete</Button> : null }]} />
    </div>
  );
}
