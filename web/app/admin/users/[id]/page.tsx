"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import useSWR from "swr";
import { fetcher } from "@/lib/api";
import { STATUS_LABEL, dateTime, money, shortDate } from "@/lib/format";
import { PageHeader } from "@/components/admin";
import { Badge, Card, DataTable, ErrorAlert, PageLoading, statusTone } from "@/components/ui";

export default function UserDetail() {
  const { id } = useParams<{ id: string }>();
  const { data: u, error } = useSWR(`/admin/users/${id}`, fetcher);
  if (error) return <ErrorAlert error={error} />;
  if (!u) return <PageLoading />;
  return (
    <div>
      <PageHeader title={u.full_name}><Badge tone={u.is_active ? "success" : "danger"}>{u.anonymised ? "Erased" : u.is_active ? "Active" : "Suspended"}</Badge></PageHeader>
      <p className="mb-6"><Link className="underline underline-offset-4" href="/admin/users">Back to accounts</Link></p>
      <div className="grid gap-6 lg:grid-cols-2 items-start">
        <Card>
          <h2 className="text-xl">Account</h2>
          <dl className="mt-3 grid gap-2 text-small">
            {[["Email", u.email], ["Phone", u.phone ?? "None"], ["Roles", u.roles.join(", ")], ["Joined", shortDate(u.created_at)], ["Last sign-in", u.last_login_at ? dateTime(u.last_login_at) : "Never"], ["Email confirmed", u.email_verified ? "Yes" : "No"], ["Two-step verification", u.mfa_enabled ? "On" : "Off"], ["Marketing consent", u.marketing_consent ? "Yes" : "No"]].map(([k, v]) => <div key={k} className="flex justify-between gap-4"><dt className="text-muted">{k}</dt><dd className="text-right">{v}</dd></div>)}
          </dl>
        </Card>
        {u.customer && (
          <Card>
            <h2 className="text-xl">Customer</h2>
            <dl className="mt-3 grid gap-2 text-small">
              {[["Source", u.customer.acquisition_source], ["Referral code", u.customer.referral_code], ["Account credit", money(u.customer.credit_pence)], ["Completed spend", money(u.completed_spend_pence)], ["Areas", u.customer.addresses.map((a: any) => a.postcode).join(", ") || "None"]].map(([k, v]) => <div key={k} className="flex justify-between gap-4"><dt className="text-muted">{k}</dt><dd className="text-right">{v}</dd></div>)}
            </dl>
          </Card>
        )}
        <div className="lg:col-span-2 grid gap-3">
          <h2 className="text-xl">Bookings</h2>
          <DataTable caption="Customer bookings" rows={u.bookings} empty="No bookings." columns={[{ key: "r", header: "Reference", render: (b) => <Link className="underline underline-offset-4" href={`/admin/bookings/${b.id}`}>{b.reference}</Link> }, { key: "w", header: "Starts", render: (b) => dateTime(b.starts_at) }, { key: "t", header: "Total", render: (b) => money(b.total_pence) }, { key: "s", header: "Status", render: (b) => <Badge tone={statusTone(b.status)}>{STATUS_LABEL[b.status]}</Badge> }]} />
          {u.complaints.length > 0 && (<><h2 className="text-xl mt-4">Complaints</h2><DataTable caption="Customer complaints" rows={u.complaints} columns={[{ key: "c", header: "Category", render: (c) => c.category }, { key: "s", header: "Status", render: (c) => c.status }, { key: "d", header: "Raised", render: (c) => shortDate(c.created_at) }]} /></>)}
          {u.customer?.credit_history.length > 0 && (<><h2 className="text-xl mt-4">Credit history</h2><DataTable caption="Credit history" rows={u.customer.credit_history} columns={[{ key: "d", header: "Date", render: (t) => shortDate(t.at) }, { key: "r", header: "Reason", render: (t) => t.reason.replace(/_/g, " ") }, { key: "a", header: "Amount", render: (t) => money(t.amount_pence) }]} /></>)}
        </div>
      </div>
    </div>
  );
}
