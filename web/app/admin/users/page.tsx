"use client";
import Link from "next/link";
import { useState } from "react";
import useSWR from "swr";
import { api, fetcher, qs } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { shortDate } from "@/lib/format";
import { PageHeader } from "@/components/admin";
import { Badge, Button, Card, DataTable, ErrorAlert, Field, PageLoading, Pager, Select, useAsync } from "@/components/ui";

export default function Users() {
  const { can, user } = useAuth();
  const [role, setRole] = useState("customer");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const { data, error, isLoading, mutate } = useSWR(`/admin/users${qs({ role, q, page, page_size: 20 })}`, fetcher);
  const act = useAsync();
  const [staff, setStaff] = useState({ email: "", full_name: "", password: "", role: "operations" });
  const add = useAsync();
  return (
    <div>
      <PageHeader title="Customers and staff" />
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <Select label="Account type" value={role} onChange={(e) => { setRole(e.target.value); setPage(1); }}>{["customer", "provider", "super_admin", "operations", "support", "finance"].map((r) => <option key={r} value={r}>{r.replace("_", " ")}</option>)}</Select>
        <Field label="Search name or email" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />
      </div>
      <ErrorAlert error={error || act.error} />
      {isLoading && <PageLoading />}
      {data && <DataTable caption="Accounts" rows={data.items} empty="No accounts match." columns={[
        { key: "n", header: "Name", render: (u) => <Link className="underline underline-offset-4" href={`/admin/users/${u.id}`}>{u.full_name}</Link> },
        { key: "e", header: "Email", render: (u) => u.email },
        { key: "r", header: "Roles", render: (u) => u.roles.join(", ") },
        { key: "c", header: "Joined", render: (u) => shortDate(u.created_at) },
        { key: "s", header: "Status", render: (u) => <Badge tone={u.is_active ? "success" : "danger"}>{u.is_active ? "Active" : "Suspended"}</Badge> },
        { key: "x", header: "", render: (u) => can("users.manage") && u.id !== user?.id ? <Button variant="secondary" onClick={async () => { const reason = prompt(u.is_active ? "Why are you suspending this account?" : "Why are you reactivating it?"); if (reason && reason.length >= 3) { await act.run(() => api(`/admin/users/${u.id}/status`, { body: { is_active: !u.is_active, reason } })); mutate(); } }}>{u.is_active ? "Suspend" : "Reactivate"}</Button> : null },
      ]} />}
      {data && <Pager page={data.page} pageSize={data.page_size} total={data.total} onChange={setPage} />}
      {can("staff.manage") && (
        <Card className="mt-10 max-w-xl">
          <h2 className="text-xl">Add a staff account</h2>
          <p className="text-sm text-muted mt-1">Staff roles carry fixed permissions. Share the temporary password securely; staff should change it at first sign-in.</p>
          <form className="mt-4 grid gap-4" onSubmit={async (e) => { e.preventDefault(); if (await add.run(() => api("/admin/staff", { body: staff }))) { setStaff({ ...staff, email: "", full_name: "", password: "" }); mutate(); } }}>
            <ErrorAlert error={add.error} />
            <Field label="Full name" required value={staff.full_name} onChange={(e) => setStaff({ ...staff, full_name: e.target.value })} />
            <Field label="Email address" type="email" required value={staff.email} onChange={(e) => setStaff({ ...staff, email: e.target.value })} />
            <Select label="Role" value={staff.role} onChange={(e) => setStaff({ ...staff, role: e.target.value })}><option value="operations">Operations</option><option value="support">Customer support</option><option value="finance">Finance</option><option value="super_admin">Super administrator</option></Select>
            <Field label="Temporary password" type="password" autoComplete="new-password" required minLength={10} value={staff.password} onChange={(e) => setStaff({ ...staff, password: e.target.value })} />
            <Button type="submit" loading={add.loading} className="justify-self-start">Create account</Button>
          </form>
        </Card>
      )}
    </div>
  );
}
