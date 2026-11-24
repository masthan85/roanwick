"use client";
import { useState } from "react";
import useSWR from "swr";
import { api, fetcher, qs } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { money, shortDate } from "@/lib/format";
import { PageHeader } from "@/components/admin";
import { Alert, Badge, Button, DataTable, ErrorAlert, PageLoading, Pager, Select, statusTone, useAsync } from "@/components/ui";

export default function Payouts() {
  const { can } = useAuth();
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const { data, error, isLoading, mutate } = useSWR(`/admin/payouts${qs({ status, page, page_size: 20 })}`, fetcher);
  const { data: adj } = useSWR("/admin/adjustments", fetcher);
  const act = useAsync();
  const run = async (id: string, action: string) => {
    const note = prompt(action === "hold" ? "Why are you holding this payout?" : "Note for the audit log");
    if (!note || note.length < 3) return;
    await act.run(() => api(`/admin/payouts/${id}/action`, { body: { action, note } }));
    mutate();
  };
  return (
    <div>
      <PageHeader title="Provider payouts" />
      <Alert tone="info" className="mb-4">Payouts are created when a visit is completed and released after the hold period, unless a complaint or refund request is open. Sandbox payouts are simulated; no money moves until live payment credentials are connected.</Alert>
      <Select label="Status" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} className="max-w-xs mb-4"><option value="">All</option>{["pending", "held", "paid", "cancelled"].map((s) => <option key={s} value={s}>{s}</option>)}</Select>
      <ErrorAlert error={error || act.error} />
      {isLoading && <PageLoading />}
      {data && <DataTable caption="Payouts" rows={data.items} empty="No payouts yet." columns={[
        { key: "p", header: "Professional", render: (p) => p.provider },
        { key: "b", header: "Booking", render: (p) => p.booking_reference },
        { key: "g", header: "Service value", render: (p) => money(p.gross_pence) },
        { key: "c", header: "Commission", render: (p) => money(p.commission_pence) },
        { key: "a", header: "Payout", render: (p) => <strong>{money(p.amount_pence)}</strong> },
        { key: "s", header: "Status", render: (p) => <div><Badge tone={statusTone(p.status)}>{p.status}</Badge><p className="text-xs text-muted mt-1">{p.status === "paid" ? shortDate(p.paid_at) : `Due ${shortDate(p.release_at)}`}{p.note ? ` · ${p.note}` : ""}</p></div> },
        { key: "x", header: "", render: (p) => can("payouts.manage") && p.status !== "paid" && p.status !== "cancelled" ? <div className="flex gap-2">{p.status !== "held" && <Button variant="secondary" onClick={() => run(p.id, "hold")}>Hold</Button>}<Button variant="secondary" onClick={() => run(p.id, "release")}>Release</Button></div> : null },
      ]} />}
      {data && <Pager page={data.page} pageSize={data.page_size} total={data.total} onChange={setPage} />}
      {adj && adj.length > 0 && (
        <section className="mt-10" aria-labelledby="adj">
          <h2 id="adj" className="text-xl mb-2">Owed to us by professionals</h2>
          <p className="text-sm text-muted mb-3">Refunds a professional funded after their payout was paid. These are netted off their next payouts automatically.</p>
          <DataTable caption="Professional adjustments" rows={adj} columns={[{ key: "p", header: "Professional", render: (a) => a.provider }, { key: "o", header: "Owed", render: (a) => money(a.owed_pence) }, { key: "r", header: "Still to recover", render: (a) => money(a.remaining_pence) }, { key: "n", header: "Reason", render: (a) => a.note }]} />
        </section>
      )}
    </div>
  );
}
