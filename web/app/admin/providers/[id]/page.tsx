"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import useSWR from "swr";
import { api, fetcher, getToken } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { shortDate } from "@/lib/format";
import { PageHeader } from "@/components/admin";
import { Alert, Badge, Button, Card, ErrorAlert, Field, PageLoading, Select, TextArea, statusTone, useAsync } from "@/components/ui";

export default function ProviderReview() {
  const { id } = useParams<{ id: string }>();
  const { can } = useAuth();
  const { data: p, error, mutate } = useSWR(`/admin/providers/${id}`, fetcher);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [reason, setReason] = useState("");
  const [bps, setBps] = useState("");
  const rev = useAsync();
  const dec = useAsync();
  const com = useAsync();
  if (error) return <ErrorAlert error={error} />;
  if (!p) return <PageLoading />;
  const gaps = Object.entries(p.verification_gaps as Record<string, string[]>).filter(([, g]) => g.length);

  async function viewDoc(docId: string) {
    const r = await fetch(`/api/v1/admin/documents/${docId}/download`, { headers: { Authorization: `Bearer ${getToken()}` } });
    if (!r.ok) return alert("The file could not be opened.");
    const url = URL.createObjectURL(await r.blob());
    window.open(url, "_blank", "noopener");
  }

  return (
    <div>
      <PageHeader title={p.display_name}><Badge tone={statusTone(p.status)}>{p.status}</Badge></PageHeader>
      <p className="mb-6"><Link className="underline underline-offset-4" href="/admin/providers">Back to professionals</Link></p>
      <div className="grid gap-6 lg:grid-cols-2 items-start">
        <Card>
          <h2 className="text-xl">Profile</h2>
          <dl className="mt-3 grid gap-2 text-small">
            {[["Email", p.email], ["Phone", p.phone], ["Experience", p.years_experience ? `${p.years_experience} years` : "Not stated"], ["Areas", p.areas.join(", ") || "None"], ["Auto-accept", p.auto_accept ? "Yes" : "No"], ["Jobs completed", p.jobs_completed], ["Late starts / withdrawals", `${p.late_count} / ${p.cancel_count}`], ["Commission override", p.commission_override_bps == null ? "Default rate" : `${p.commission_override_bps / 100}%`]].map(([k, v]) => <div key={k as string} className="flex justify-between gap-4"><dt className="text-muted">{k}</dt><dd className="text-right">{v}</dd></div>)}
          </dl>
          <p className="mt-4 text-small">{p.bio || <span className="text-muted">No bio yet.</span>}</p>
          {p.status_reason && <Alert tone="warn" className="mt-3">Last reason recorded: {p.status_reason}</Alert>}
        </Card>

        <Card>
          <h2 className="text-xl">Verification status</h2>
          {gaps.length === 0 ? <Alert tone="success" className="mt-3" title="All mandatory documents are approved and in date.">This professional meets the requirements for every service they offer.</Alert>
            : <Alert tone="warn" className="mt-3" title="Cannot be approved yet">{gaps.map(([cat, g]) => <p key={cat}>{cat}: missing or expired {g.join(", ").replace(/_/g, " ")}</p>)}</Alert>}
          <ErrorAlert error={dec.error} className="mt-3" />
          {can("providers.review") && (
            <div className="mt-4 grid gap-3">
              <TextArea label="Reason or note" optional rows={2} value={reason} onChange={(e) => setReason(e.target.value)} hint="Required to reject or suspend. Shown to the professional." />
              <div className="flex flex-wrap gap-2">
                {["submitted", "rejected", "suspended"].includes(p.status) && <Button loading={dec.loading} onClick={async () => { await dec.run(() => api(`/admin/providers/${id}/decision`, { body: { action: p.status === "suspended" ? "reinstate" : "approve", reason } })); mutate(); }}>{p.status === "suspended" ? "Reinstate" : "Approve"}</Button>}
                {p.status === "submitted" && <Button variant="danger" loading={dec.loading} onClick={async () => { await dec.run(() => api(`/admin/providers/${id}/decision`, { body: { action: "reject", reason } })); mutate(); }}>Reject</Button>}
                {p.status === "approved" && <Button variant="danger" loading={dec.loading} onClick={async () => { await dec.run(() => api(`/admin/providers/${id}/decision`, { body: { action: "suspend", reason } })); mutate(); }}>Suspend</Button>}
              </div>
            </div>
          )}
        </Card>

        <Card className="lg:col-span-2">
          <h2 className="text-xl">Documents</h2>
          <ErrorAlert error={rev.error} className="mt-3" />
          <ul className="mt-3 divide-y divide-line">
            {p.documents.length === 0 && <li className="py-3 text-muted">No documents uploaded.</li>}
            {p.documents.map((d: any) => {
              const expired = d.expires_on && new Date(d.expires_on) < new Date();
              return (
                <li key={d.id} className="py-4 grid gap-3 md:grid-cols-[1fr_auto] items-start">
                  <div>
                    <p className="font-medium">{d.title} <Badge tone={statusTone(d.status)}>{d.status}</Badge> {expired && <Badge tone="danger">expired</Badge>}</p>
                    <p className="text-sm text-muted">{d.doc_type.replace(/_/g, " ")} · uploaded {shortDate(d.uploaded_at)}{d.reference ? ` · reference ${d.reference}` : ""}{d.expires_on ? ` · expires ${shortDate(d.expires_on)}` : ""}</p>
                    {d.review_notes && <p className="text-sm">Note: {d.review_notes}</p>}
                  </div>
                  {can("providers.review") && (
                    <div className="grid gap-2 md:w-72">
                      <Button variant="secondary" onClick={() => viewDoc(d.id)}>Open file (logged)</Button>
                      {d.status === "pending" && <>
                        <Field label="Review note" value={notes[d.id] ?? ""} onChange={(e) => setNotes({ ...notes, [d.id]: e.target.value })} hint="Required to reject." />
                        <div className="flex gap-2">
                          <Button loading={rev.loading} onClick={async () => { await rev.run(() => api(`/admin/documents/${d.id}/review`, { body: { decision: "approve", notes: notes[d.id] || null } })); mutate(); }}>Approve</Button>
                          <Button variant="danger" loading={rev.loading} onClick={async () => { await rev.run(() => api(`/admin/documents/${d.id}/review`, { body: { decision: "reject", notes: notes[d.id] || null } })); mutate(); }}>Reject</Button>
                        </div>
                      </>}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </Card>

        {can("payouts.manage") && (
          <Card>
            <h2 className="text-xl">Commission</h2>
            <p className="text-sm text-muted mt-1">Leave blank to use the platform default. Enter basis points: 2000 means 20%.</p>
            <ErrorAlert error={com.error} className="mt-3" />
            <form className="mt-3 flex items-end gap-3" onSubmit={async (e) => { e.preventDefault(); await com.run(() => api(`/admin/providers/${id}/commission`, { method: "PATCH", body: { commission_override_bps: bps === "" ? null : Number(bps) } })); mutate(); }}>
              <Field label="Override (basis points)" type="number" min={0} max={5000} value={bps} onChange={(e) => setBps(e.target.value)} />
              <Button type="submit" loading={com.loading}>Save</Button>
            </form>
          </Card>
        )}
      </div>
    </div>
  );
}
