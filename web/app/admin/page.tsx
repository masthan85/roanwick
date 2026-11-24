"use client";
import Link from "next/link";
import useSWR from "swr";
import { fetcher, qs } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { money, percent } from "@/lib/format";
import { PageHeader, useRange } from "@/components/admin";
import { Alert, Badge, Card, ErrorAlert, PageLoading, Stat } from "@/components/ui";

export default function Overview() {
  const { can } = useAuth();
  const r = useRange(30);
  const { data: ops, error } = useSWR(`/admin/reports/operations${qs({ from: r.from, to: r.to })}`, fetcher);
  const { data: fin } = useSWR(can("finance.read") ? `/admin/reports/finance${qs({ from: r.from, to: r.to })}` : null, fetcher);
  if (error) return <ErrorAlert error={error} />;
  if (!ops) return <PageLoading />;
  const todo = [
    [ops.providers_by_status?.submitted ?? 0, "professional applications to review", "/admin/providers?status=submitted"],
    [ops.unassigned_bookings, "paid bookings with no professional", "/admin/bookings?unassigned=1"],
    [ops.open_refund_requests, "open refund requests", "/admin/support"],
    [ops.complaints_past_sla, "complaints past the response target", "/admin/support"],
    [ops.quality_reviews_open, "professional quality reviews open", "/admin/support"],
    [ops.documents_expiring_30_days, "documents expiring in 30 days", "/admin/providers"],
  ].filter(([n]) => (n as number) > 0);
  return (
    <div>
      <PageHeader title="Overview">{r.picker}</PageHeader>
      <Card className="mb-6">
        <h2 className="text-xl">Needs attention</h2>
        {todo.length === 0 ? <p className="mt-2 text-muted">Nothing is waiting. </p> : <ul className="mt-3 divide-y divide-line">{todo.map(([n, l, h]) => <li key={l as string}><Link href={h as string} className="flex min-h-11 items-center justify-between gap-3 hover:text-brand"><span>{l}</span><Badge tone="warn">{n}</Badge></Link></li>)}</ul>}
      </Card>
      <h2 className="text-xl mb-3">Operations</h2>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Bookings created" value={Object.entries(ops.bookings_by_status).filter(([k]) => !["expired", "pending_payment"].includes(k)).reduce((a, [, v]) => a + (v as number), 0)} />
        <Stat label="Completed" value={ops.bookings_by_status.completed ?? 0} />
        <Stat label="Cancellation rate" value={percent(ops.cancellation_rate)} note={`Provider-caused: ${percent(ops.provider_cancellation_rate)}`} />
        <Stat label="On-time start rate" value={percent(ops.on_time_rate)} />
        <Stat label="Average rating" value={ops.average_rating ?? "No reviews"} />
        <Stat label="Complaints per 100 completed" value={ops.complaints_per_100_completed ?? "Not enough data"} />
        <Stat label="Approved professionals" value={ops.providers_by_status?.approved ?? 0} />
        <Stat label="Awaiting review" value={ops.providers_by_status?.submitted ?? 0} />
      </div>
      {fin && (
        <>
          <h2 className="text-xl mt-8 mb-3">Money, for the same period</h2>
          <Alert tone="info" className="mb-4">Gross booking value is cash taken from customers. It is not our revenue. <Link className="underline" href="/admin/finance">See the full breakdown.</Link></Alert>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Gross booking value" value={money(fin.gross_booking_value.value)} basis={fin.gross_booking_value.basis} />
            <Stat label="Platform revenue" value={money(fin.platform_revenue.value)} basis={fin.platform_revenue.basis} />
            <Stat label="Contribution" value={money(fin.contribution.value)} basis={fin.contribution.basis} />
            <Stat label="Contribution per booking" value={money(fin.contribution_per_booking.value)} basis={fin.contribution_per_booking.basis} />
          </div>
        </>
      )}
    </div>
  );
}
