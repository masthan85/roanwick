"use client";
import { useState } from "react";
import useSWR from "swr";
import { api, fetcher } from "@/lib/api";
import { hours, money, shortDate } from "@/lib/format";
import { PageHeader } from "@/components/admin";
import { Alert, Badge, Button, Card, Check, DataTable, ErrorAlert, Field, PageLoading, Panel, Select, Tabs, TextArea, useAsync } from "@/components/ui";

export default function Catalogue() {
  const [tab, setTab] = useState("services");
  return (
    <div>
      <PageHeader title="Catalogue and promotions" />
      <Tabs label="Catalogue sections" value={tab} onChange={setTab} tabs={[{ id: "services", label: "Services and prices" }, { id: "bundles", label: "Bundles" }, { id: "coverage", label: "Coverage" }, { id: "promos", label: "Promotions" }]} />
      <Panel id={tab}>
        {tab === "services" && <Services />}
        {tab === "bundles" && <Bundles />}
        {tab === "coverage" && <Coverage />}
        {tab === "promos" && <Promos />}
      </Panel>
    </div>
  );
}

function Services() {
  const { data, error, mutate } = useSWR("/admin/catalogue", fetcher);
  const a = useAsync();
  const [edit, setEdit] = useState<Record<string, any>>({});
  const [confirmed, setConfirmed] = useState<Record<string, boolean>>({});
  if (error) return <ErrorAlert error={error} />;
  if (!data) return <PageLoading />;
  return (
    <div className="grid gap-6">
      <ErrorAlert error={a.error} />
      <NewService categories={data} onDone={() => mutate()} />
      {data.map((c: any) => (
        <Card key={c.slug}>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div><h2 className="text-xl">{c.name}</h2><p className="text-sm text-muted">Required documents: {c.requirements.length ? c.requirements.map((r: any) => `${r.document_type.replace(/_/g, " ")}${r.is_mandatory ? "" : " (optional)"}`).join(", ") : "None defined"}</p></div>
            <div className="flex items-center gap-3">
              <Badge tone={c.is_active ? "success" : "neutral"}>{c.is_active ? "Live" : "Not live"}</Badge>
              {c.requires_compliance_review && !c.is_active && <Badge tone="warn">Compliance review required</Badge>}
            </div>
          </div>
          {c.requires_compliance_review && !c.is_active && (
            <div className="mt-4 rounded-control bg-warn-soft p-4">
              <p className="text-small">Regulated or specialist trades stay off until their verification requirements are defined in the system and someone qualified has reviewed them.</p>
              <Check className="mt-3" checked={!!confirmed[c.slug]} onChange={(e) => setConfirmed({ ...confirmed, [c.slug]: e.target.checked })} label="I confirm the compliance requirements for this category have been reviewed." />
              <Button className="mt-3" variant="secondary" loading={a.loading} onClick={async () => { await a.run(() => api(`/admin/categories/${c.slug}`, { method: "PATCH", body: { is_active: true, confirm_compliance_reviewed: !!confirmed[c.slug] } })); mutate(); }}>Try to switch on</Button>
            </div>
          )}
          {c.is_active && <Button className="mt-3" variant="secondary" onClick={async () => { if (confirm(`Switch ${c.name} off? Customers will no longer be able to book it.`)) { await a.run(() => api(`/admin/categories/${c.slug}`, { method: "PATCH", body: { is_active: false } })); mutate(); } }}>Switch off</Button>}
          {c.offerings.map((o: any) => {
            const e = edit[o.id] ?? { rate: (o.hourly_rate_pence ?? 0) / 100, min: o.min_minutes / 60, buffer: o.buffer_minutes, tiers: o.tiers, addons: o.addons };
            const set = (p: object) => setEdit({ ...edit, [o.id]: { ...e, ...p } });
            return (
              <div key={o.id} className="mt-6 border-t border-line pt-5">
                <h3 className="text-lg">{o.name} <span className="text-sm text-muted font-sans">({o.pricing_model})</span></h3>
                <div className="mt-3 grid gap-4 sm:grid-cols-3">
                  {o.pricing_model === "hourly" && <Field label="Hourly rate in pounds" type="number" step="0.5" min="5" value={e.rate} onChange={(x) => set({ rate: x.target.value })} />}
                  {o.pricing_model === "hourly" && <Field label="Minimum hours" type="number" step="0.5" min="0.5" value={e.min} onChange={(x) => set({ min: x.target.value })} />}
                  <Field label="Gap between jobs (minutes)" type="number" min="0" max="120" value={e.buffer} onChange={(x) => set({ buffer: x.target.value })} />
                </div>
                {o.pricing_model === "tiered" && (
                  <div className="mt-4"><p className="text-sm font-medium mb-2">Fixed prices by property size</p>
                    <div className="grid gap-2">{e.tiers.map((t: any, i: number) => <div key={t.bedrooms} className="flex flex-wrap items-end gap-3"><span className="w-28">{t.label}</span><Field label={`${t.label} price in pounds`} type="number" step="1" value={t.price_pence / 100} onChange={(x) => set({ tiers: e.tiers.map((q: any, j: number) => (j === i ? { ...q, price_pence: Math.round(parseFloat(x.target.value || "0") * 100) } : q)) })} /><span className="text-sm text-muted pb-3">{hours(t.duration_minutes)}</span></div>)}</div>
                  </div>
                )}
                <div className="mt-4"><p className="text-sm font-medium mb-2">Extras</p>
                  <div className="grid gap-2">{e.addons.map((ad: any, i: number) => <div key={ad.code} className="flex flex-wrap items-end gap-3"><span className="w-40">{ad.name}</span><Field label={`${ad.name} price in pounds`} type="number" step="0.5" value={ad.price_pence / 100} onChange={(x) => set({ addons: e.addons.map((q: any, j: number) => (j === i ? { ...q, price_pence: Math.round(parseFloat(x.target.value || "0") * 100) } : q)) })} /><Check checked={ad.is_active} onChange={(x) => set({ addons: e.addons.map((q: any, j: number) => (j === i ? { ...q, is_active: x.target.checked } : q)) })} label="Offered" /></div>)}</div>
                </div>
                <Button className="mt-4" loading={a.loading} onClick={async () => {
                  const body: any = { buffer_minutes: Number(e.buffer), addons: e.addons };
                  if (o.pricing_model === "hourly") { body.hourly_rate_pence = Math.round(parseFloat(e.rate) * 100); body.min_minutes = Math.round(parseFloat(e.min) * 60); } else body.tiers = e.tiers;
                  await a.run(() => api(`/admin/offerings/${o.id}`, { method: "PATCH", body })); setEdit({ ...edit, [o.id]: undefined }); mutate();
                }}>Save prices (audited)</Button>
              </div>
            );
          })}
        </Card>
      ))}
    </div>
  );
}

function Coverage() {
  const { data, mutate } = useSWR("/admin/areas", fetcher);
  const [f, setF] = useState({ outward_code: "", name: "" });
  const a = useAsync();
  return (
    <div className="grid gap-6 max-w-2xl">
      <Alert tone="info">Customers can only book, and professionals can only sign up for, districts marked active.</Alert>
      <DataTable caption="Service areas" rows={(data ?? []).map((x: any) => ({ ...x, id: x.outward_code }))} columns={[{ key: "outward_code", header: "District" }, { key: "name", header: "Name" }, { key: "st", header: "Status", render: (x) => <Badge tone={x.is_active ? "success" : "neutral"}>{x.is_active ? "Active" : "Paused"}</Badge> }, { key: "x", header: "", render: (x) => <Button variant="secondary" onClick={async () => { await a.run(() => api("/admin/areas", { method: "PUT", body: { outward_code: x.outward_code, name: x.name, is_active: !x.is_active } })); mutate(); }}>{x.is_active ? "Pause" : "Activate"}</Button> }]} />
      <Card>
        <h2 className="text-xl">Add a district</h2>
        <ErrorAlert error={a.error} className="mt-3" />
        <form className="mt-3 flex flex-wrap items-end gap-3" onSubmit={async (e) => { e.preventDefault(); if (await a.run(() => api("/admin/areas", { method: "PUT", body: { ...f, is_active: true } }))) { setF({ outward_code: "", name: "" }); mutate(); } }}>
          <Field label="Postcode district" placeholder="SW6" required value={f.outward_code} onChange={(e) => setF({ ...f, outward_code: e.target.value })} />
          <Field label="Name" required value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />
          <Button type="submit" loading={a.loading}>Add</Button>
        </form>
      </Card>
    </div>
  );
}

function Promos() {
  const { data, mutate } = useSWR("/admin/promotions", fetcher);
  const [f, setF] = useState({ code: "", description: "", kind: "percent", value: "", min_spend: "", max_discount: "", first_booking_only: false, max_redemptions: "", valid_to: "", channel: "" });
  const a = useAsync();
  return (
    <div className="grid gap-6">
      <DataTable caption="Promotions" rows={data ?? []} empty="No promotions yet." columns={[
        { key: "code", header: "Code", render: (p) => <strong>{p.code}</strong> },
        { key: "d", header: "Offer", render: (p) => `${p.kind === "percent" ? `${p.value / 100}% off` : `${money(p.value)} off`}${p.max_discount_pence ? ` (max ${money(p.max_discount_pence)})` : ""}${p.first_booking_only ? ", first booking only" : ""}` },
        { key: "u", header: "Used", render: (p) => `${p.redemption_count}${p.max_redemptions ? ` of ${p.max_redemptions}` : ""}` },
        { key: "v", header: "Valid to", render: (p) => (p.valid_to ? shortDate(p.valid_to) : "No end date") },
        { key: "ch", header: "Channel", render: (p) => p.channel ?? "" },
        { key: "s", header: "Active", render: (p) => <Check checked={p.is_active} aria-label={`${p.code} active`} onChange={async (e) => { const { id, redemption_count, ...rest } = p; await api(`/admin/promotions/${p.id}`, { method: "PUT", body: { ...rest, is_active: e.target.checked } }); mutate(); }} label="" /> },
      ]} />
      <Card className="max-w-3xl">
        <h2 className="text-xl">Create a promotion</h2>
        <p className="text-sm text-muted mt-1">The platform bears the cost of promotions. Professionals are paid on the full service value.</p>
        <form className="mt-4 grid gap-4 sm:grid-cols-2" onSubmit={async (e) => { e.preventDefault(); const pct = f.kind === "percent"; if (await a.run(() => api("/admin/promotions", { body: { code: f.code, description: f.description, kind: f.kind, value: pct ? Math.round(parseFloat(f.value) * 100) : Math.round(parseFloat(f.value) * 100), min_spend_pence: f.min_spend ? Math.round(parseFloat(f.min_spend) * 100) : 0, max_discount_pence: f.max_discount ? Math.round(parseFloat(f.max_discount) * 100) : null, first_booking_only: f.first_booking_only, max_redemptions: f.max_redemptions ? Number(f.max_redemptions) : null, valid_to: f.valid_to || null, channel: f.channel || null } }))) { setF({ ...f, code: "", description: "", value: "" }); mutate(); } }}>
          <div className="sm:col-span-2"><ErrorAlert error={a.error} /></div>
          <Field label="Code" required value={f.code} onChange={(e) => setF({ ...f, code: e.target.value.toUpperCase() })} />
          <Field label="Description" value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} />
          <Select label="Type" value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })}><option value="percent">Percentage</option><option value="fixed">Fixed amount</option></Select>
          <Field label={f.kind === "percent" ? "Percentage off" : "Amount off in pounds"} type="number" step="0.01" required value={f.value} onChange={(e) => setF({ ...f, value: e.target.value })} />
          <Field label="Minimum spend in pounds" optional type="number" step="0.01" value={f.min_spend} onChange={(e) => setF({ ...f, min_spend: e.target.value })} />
          <Field label="Maximum discount in pounds" optional type="number" step="0.01" value={f.max_discount} onChange={(e) => setF({ ...f, max_discount: e.target.value })} />
          <Field label="Maximum redemptions" optional type="number" value={f.max_redemptions} onChange={(e) => setF({ ...f, max_redemptions: e.target.value })} />
          <Field label="Valid until" optional type="date" value={f.valid_to} onChange={(e) => setF({ ...f, valid_to: e.target.value })} />
          <Field label="Marketing channel" optional value={f.channel} onChange={(e) => setF({ ...f, channel: e.target.value })} hint="For tracking only." />
          <Check checked={f.first_booking_only} onChange={(e) => setF({ ...f, first_booking_only: e.target.checked })} label="First booking only" />
          <Button type="submit" loading={a.loading} className="justify-self-start">Create promotion</Button>
        </form>
      </Card>
    </div>
  );
}

function NewService({ categories, onDone }: { categories: any[]; onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ category_slug: "home-cleaning", slug: "", name: "", summary: "", pricing_model: "hourly", rate: "", min: "2", max: "8", recurring: false, tiers: "" });
  const a = useAsync();
  if (!open) return <div><Button variant="secondary" onClick={() => setOpen(true)}>Add a new service</Button></div>;
  return (
    <Card>
      <h2 className="text-xl">Add a new service</h2>
      <p className="text-sm text-muted mt-1">A service in a category that is not live stays hidden from customers until the category is switched on.</p>
      <form className="mt-4 grid gap-4 sm:grid-cols-2" onSubmit={async (e) => {
        e.preventDefault();
        const tiers = f.tiers.split("\n").map((l) => l.trim()).filter(Boolean).map((l) => { const [bed, label, price, mins] = l.split(",").map((x) => x.trim()); return { bedrooms: Number(bed), label, price_pence: Math.round(parseFloat(price) * 100), duration_minutes: Math.round(parseFloat(mins) * 60) }; });
        const body: any = { category_slug: f.category_slug, slug: f.slug, name: f.name, summary: f.summary, pricing_model: f.pricing_model, supports_recurring: f.recurring, min_minutes: Math.round(parseFloat(f.min) * 60), max_minutes: Math.round(parseFloat(f.max) * 60) };
        if (f.pricing_model === "hourly") body.hourly_rate_pence = Math.round(parseFloat(f.rate) * 100); else body.tiers = tiers;
        if (await a.run(() => api("/admin/offerings", { body }))) { setOpen(false); onDone(); }
      }}>
        <div className="sm:col-span-2"><ErrorAlert error={a.error} /></div>
        <Select label="Category" value={f.category_slug} onChange={(e) => setF({ ...f, category_slug: e.target.value })}>{categories.map((c) => <option key={c.slug} value={c.slug}>{c.name}{c.is_active ? "" : " (not live)"}</option>)}</Select>
        <Select label="Pricing" value={f.pricing_model} onChange={(e) => setF({ ...f, pricing_model: e.target.value })}><option value="hourly">Hourly rate</option><option value="tiered">Fixed price by size</option></Select>
        <Field label="Name" required value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />
        <Field label="Web address" required value={f.slug} onChange={(e) => setF({ ...f, slug: e.target.value.toLowerCase() })} hint="Lower case letters, numbers and hyphens." />
        <Field label="Summary" className="sm:col-span-2" value={f.summary} onChange={(e) => setF({ ...f, summary: e.target.value })} />
        {f.pricing_model === "hourly" ? (
          <>
            <Field label="Hourly rate in pounds" type="number" step="0.5" required value={f.rate} onChange={(e) => setF({ ...f, rate: e.target.value })} />
            <Field label="Minimum hours" type="number" step="0.5" value={f.min} onChange={(e) => setF({ ...f, min: e.target.value })} />
            <Field label="Maximum hours" type="number" step="0.5" value={f.max} onChange={(e) => setF({ ...f, max: e.target.value })} />
            <Check checked={f.recurring} onChange={(e) => setF({ ...f, recurring: e.target.checked })} label="Can be booked as a recurring plan" />
          </>
        ) : <TextArea label="Sizes, one per line" className="sm:col-span-2" value={f.tiers} onChange={(e) => setF({ ...f, tiers: e.target.value })} hint="bedrooms, label, price in pounds, hours. For example: 2, 2 bedrooms, 250, 6" />}
        <div className="flex gap-2 sm:col-span-2"><Button type="submit" loading={a.loading}>Create service</Button><Button variant="secondary" onClick={() => setOpen(false)}>Cancel</Button></div>
      </form>
    </Card>
  );
}

function Bundles() {
  const { data, mutate } = useSWR("/admin/bundles", fetcher);
  const { data: cat } = useSWR("/admin/catalogue", fetcher);
  const offerings = (cat ?? []).flatMap((c: any) => c.offerings);
  const [f, setF] = useState({ slug: "", name: "", description: "", offering_id: "", addons: [] as string[], pct: "10" });
  const a = useAsync();
  const current = offerings.find((o: any) => o.id === f.offering_id);
  return (
    <div className="grid gap-6 max-w-3xl">
      <Alert tone="info">A bundle ticks a set of extras for the customer and applies a percentage discount to labour and extras. The platform bears the discount, and professionals are paid on the full value. It is reported as promotion cost.</Alert>
      <DataTable caption="Bundles" rows={data ?? []} empty="No bundles yet." columns={[
        { key: "n", header: "Bundle", render: (b) => <span><strong>{b.name}</strong><br /><span className="text-sm text-muted">{b.offering}</span></span> },
        { key: "a", header: "Extras", render: (b) => b.addon_codes.join(", ") },
        { key: "d", header: "Discount", render: (b) => `${b.discount_bps / 100}%` },
        { key: "s", header: "Active", render: (b) => <Check checked={b.is_active} aria-label={`${b.name} active`} label="" onChange={async (e) => { await api(`/admin/bundles/${b.id}`, { method: "PUT", body: { slug: b.slug, name: b.name, description: b.description, offering_id: b.offering_id, addon_codes: b.addon_codes, discount_bps: b.discount_bps, is_active: e.target.checked } }); mutate(); }} /> },
      ]} />
      <Card>
        <h2 className="text-xl">Create a bundle</h2>
        <form className="mt-4 grid gap-4 sm:grid-cols-2" onSubmit={async (e) => { e.preventDefault(); if (await a.run(() => api("/admin/bundles", { body: { slug: f.slug, name: f.name, description: f.description, offering_id: f.offering_id, addon_codes: f.addons, discount_bps: Math.round(parseFloat(f.pct) * 100) } }))) { setF({ ...f, slug: "", name: "", description: "", addons: [] }); mutate(); } }}>
          <div className="sm:col-span-2"><ErrorAlert error={a.error} /></div>
          <Field label="Name" required value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />
          <Field label="Web address" required value={f.slug} onChange={(e) => setF({ ...f, slug: e.target.value.toLowerCase() })} />
          <Select label="Service" required value={f.offering_id} onChange={(e) => setF({ ...f, offering_id: e.target.value, addons: [] })}><option value="">Choose…</option>{offerings.map((o: any) => <option key={o.id} value={o.id}>{o.name}</option>)}</Select>
          <Field label="Discount percentage" type="number" step="0.5" min="0" max="50" value={f.pct} onChange={(e) => setF({ ...f, pct: e.target.value })} />
          <Field label="Description" className="sm:col-span-2" value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} />
          {current && <fieldset className="sm:col-span-2"><legend className="text-sm font-medium mb-2">Extras included</legend>{current.addons.map((x: any) => <Check key={x.code} className="py-1" checked={f.addons.includes(x.code)} onChange={(e) => setF({ ...f, addons: e.target.checked ? [...f.addons, x.code] : f.addons.filter((c) => c !== x.code) })} label={`${x.name} (${money(x.price_pence)})`} />)}</fieldset>}
          <Button type="submit" loading={a.loading} className="justify-self-start">Create bundle</Button>
        </form>
      </Card>
    </div>
  );
}
