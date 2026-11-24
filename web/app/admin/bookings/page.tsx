"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import useSWR from "swr";
import { fetcher, qs } from "@/lib/api";
import { STATUS_LABEL, dateTime, money } from "@/lib/format";
import { PageHeader } from "@/components/admin";
import { Badge, Button, DataTable, ErrorAlert, Field, PageLoading, Pager, Select, statusTone } from "@/components/ui";

export default function Bookings() {
  const sp = useSearchParams();
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const unassigned = sp.get("unassigned") === "1";
  const { data, error, isLoading } = useSWR(`/admin/bookings${qs({ status, q, page, unassigned: unassigned || undefined, page_size: 20 })}`, fetcher);
  return (
    <div>
      <PageHeader title={unassigned ? "Bookings without a professional" : "Bookings"} />
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <Select label="Status" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
          <option value="">All</option>{Object.entries(STATUS_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </Select>
        <Field label="Reference" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} placeholder="RW-" />
      </div>
      <ErrorAlert error={error} />
      {isLoading && <PageLoading />}
      {data && <DataTable caption="Bookings" empty="No bookings match." rows={data.items} columns={[
        { key: "ref", header: "Reference", render: (b) => <Link className="underline underline-offset-4" href={`/admin/bookings/${b.id}`}>{b.reference}</Link> },
        { key: "when", header: "Starts", render: (b) => dateTime(b.starts_at) },
        { key: "svc", header: "Service", render: (b) => b.offering.name },
        { key: "cust", header: "Customer", render: (b) => b.customer.name },
        { key: "pro", header: "Professional", render: (b) => b.professional?.display_name ?? <Badge tone="warn">Unassigned</Badge> },
        { key: "tot", header: "Total", render: (b) => money(b.total_pence) },
        { key: "st", header: "Status", render: (b) => <Badge tone={statusTone(b.status)}>{STATUS_LABEL[b.status]}</Badge> },
      ]} />}
      {data && <Pager page={data.page} pageSize={data.page_size} total={data.total} onChange={setPage} />}
    </div>
  );
}
