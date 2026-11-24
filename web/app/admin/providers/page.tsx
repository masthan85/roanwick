"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import useSWR from "swr";
import { fetcher, qs } from "@/lib/api";
import { shortDate } from "@/lib/format";
import { PageHeader } from "@/components/admin";
import { Badge, DataTable, ErrorAlert, Field, PageLoading, Pager, Select, statusTone } from "@/components/ui";

export default function Providers() {
  const sp = useSearchParams();
  const [status, setStatus] = useState(sp.get("status") ?? "");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const { data, error, isLoading } = useSWR(`/admin/providers${qs({ status, q, page, page_size: 20 })}`, fetcher);
  return (
    <div>
      <PageHeader title="Professionals" />
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <Select label="Status" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
          <option value="">All</option>{["draft", "submitted", "approved", "rejected", "suspended"].map((s) => <option key={s} value={s}>{s}</option>)}
        </Select>
        <Field label="Name" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />
      </div>
      <ErrorAlert error={error} />
      {isLoading && <PageLoading />}
      {data && <DataTable caption="Professionals" rows={data.items} empty="No professionals match." columns={[
        { key: "n", header: "Name", render: (p) => <Link className="underline underline-offset-4" href={`/admin/providers/${p.id}`}>{p.display_name}</Link> },
        { key: "e", header: "Email", render: (p) => p.email },
        { key: "s", header: "Status", render: (p) => <Badge tone={statusTone(p.status)}>{p.status}</Badge> },
        { key: "r", header: "Rating", render: (p) => (p.rating_count ? `${p.rating_avg.toFixed(1)} (${p.rating_count})` : "None yet") },
        { key: "j", header: "Jobs", render: (p) => p.jobs_completed },
        { key: "c", header: "Late / cancelled", render: (p) => `${p.late_count} / ${p.cancel_count}` },
        { key: "d", header: "Applied", render: (p) => shortDate(p.created_at) },
      ]} />}
      {data && <Pager page={data.page} pageSize={data.page_size} total={data.total} onChange={setPage} />}
    </div>
  );
}
