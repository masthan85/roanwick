"use client";
import { useState } from "react";
import useSWR from "swr";
import { fetcher, qs } from "@/lib/api";
import { dateTime } from "@/lib/format";
import { PageHeader } from "@/components/admin";
import { DataTable, ErrorAlert, Field, PageLoading, Pager } from "@/components/ui";

export default function Audit() {
  const [action, setAction] = useState("");
  const [page, setPage] = useState(1);
  const { data, error, isLoading } = useSWR(`/admin/audit${qs({ action, page, page_size: 25 })}`, fetcher);
  return (
    <div>
      <PageHeader title="Audit log" />
      <Field label="Action starts with" value={action} onChange={(e) => { setAction(e.target.value); setPage(1); }} placeholder="provider, setting, refund" className="max-w-xs mb-4" />
      <ErrorAlert error={error} />
      {isLoading && <PageLoading />}
      {data && <DataTable caption="Audit events" rows={data.items} empty="No events match." columns={[
        { key: "at", header: "When", render: (e) => dateTime(e.at) },
        { key: "actor", header: "Who", render: (e) => e.actor ?? "System" },
        { key: "action", header: "Action", render: (e) => <code className="text-sm">{e.action}</code> },
        { key: "entity", header: "Record", render: (e) => `${e.entity_type} ${e.entity_id ? e.entity_id.slice(0, 8) : ""}` },
        { key: "chg", header: "Change", render: (e) => <details><summary className="cursor-pointer text-sm underline">View</summary><pre className="mt-2 max-w-md overflow-auto text-xs">{JSON.stringify({ before: e.before, after: e.after }, null, 2)}</pre></details> },
      ]} />}
      {data && <Pager page={data.page} pageSize={data.page_size} total={data.total} onChange={setPage} />}
    </div>
  );
}
