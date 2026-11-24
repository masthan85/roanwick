"use client";
import { useState } from "react";
import useSWR from "swr";
import { api, fetcher } from "@/lib/api";
import { PageHeader } from "@/components/admin";
import { Alert, Button, Card, Check, ErrorAlert, Field, PageLoading, TextArea, useAsync } from "@/components/ui";

const MONEY_KEYS = new Set(["customer_booking_fee_pence", "referral_reward_pence", "referral_welcome_pence", "processing_fee_fixed_pence"]);

export default function Settings() {
  const { data: settings, error, mutate } = useSWR("/admin/settings", fetcher);
  const { data: flags, mutate: reloadFlags } = useSWR("/admin/flags", fetcher);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const a = useAsync();
  if (error) return <ErrorAlert error={error} />;
  if (!settings || !flags) return <PageLoading />;
  const show = (s: any) => (draft[s.key] ?? (typeof s.value === "object" ? JSON.stringify(s.value) : String(s.value)));
  return (
    <div className="grid gap-8">
      <PageHeader title="Business configuration" />
      <Alert tone="info">Commercial assumptions live here, not in code. Every change is recorded in the audit log with the old and new value. Rates in basis points: 100 basis points is 1%. Money values are in pence.</Alert>
      <ErrorAlert error={a.error} />
      <Card>
        <h2 className="text-xl">Settings</h2>
        <div className="mt-4 divide-y divide-line">
          {settings.map((s: any) => (
            <form key={s.key} className="py-4 grid gap-2 md:grid-cols-[1fr_auto] items-end" onSubmit={async (e) => {
              e.preventDefault();
              const raw = show(s);
              let value: any = raw;
              if (typeof s.value === "boolean") value = raw === "true";
              else if (typeof s.value === "number") value = Number(raw);
              else if (typeof s.value === "object") { try { value = JSON.parse(raw); } catch { alert("That is not valid JSON."); return; } }
              await a.run(() => api(`/admin/settings/${s.key}`, { method: "PUT", body: { value } }));
              setDraft({ ...draft, [s.key]: undefined as any }); mutate();
            }}>
              {typeof s.value === "object" ? <TextArea label={s.key} rows={4} value={show(s)} onChange={(e) => setDraft({ ...draft, [s.key]: e.target.value })} hint={s.description} /> : typeof s.value === "boolean" ? (
                <div><label htmlFor={s.key} className="block text-sm font-medium mb-1.5">{s.key}</label><select id={s.key} className="w-full rounded-control border border-line bg-surface px-3 min-h-11" value={show(s)} onChange={(e) => setDraft({ ...draft, [s.key]: e.target.value })}><option value="true">On</option><option value="false">Off</option></select><p className="mt-1 text-sm text-muted">{s.description}</p></div>
              ) : <Field label={s.key} value={show(s)} onChange={(e) => setDraft({ ...draft, [s.key]: e.target.value })} hint={`${s.description}${MONEY_KEYS.has(s.key) ? ` Currently £${(Number(s.value) / 100).toFixed(2)}.` : ""}`} />}
              <Button type="submit" variant="secondary" disabled={draft[s.key] === undefined} loading={a.loading}>Save</Button>
            </form>
          ))}
        </div>
      </Card>
      <Card>
        <h2 className="text-xl">Feature flags</h2>
        <ul className="mt-4 divide-y divide-line">
          {flags.map((f: any) => (
            <li key={f.key} className="py-3 flex items-start justify-between gap-4">
              <div><p className="font-medium">{f.key}</p><p className="text-sm text-muted">{f.description}</p></div>
              <Check checked={f.enabled} aria-label={`${f.key} enabled`} label="" onChange={async (e) => { await a.run(() => api(`/admin/flags/${f.key}`, { method: "PUT", body: { enabled: e.target.checked } })); reloadFlags(); }} />
            </li>
          ))}
        </ul>
      </Card>
      <Card>
        <h2 className="text-xl">Scheduled jobs</h2>
        <p className="text-sm text-muted mt-1">These run automatically in production (every five minutes). Run them now to expire unpaid holds, re-match unaccepted jobs, generate plan visits, release due payouts, send document reminders and deliver queued emails.</p>
        <RunJobs />
      </Card>
    </div>
  );
}

function RunJobs() {
  const a = useAsync();
  const [out, setOut] = useState<any>(null);
  return (
    <div className="mt-3">
      <ErrorAlert error={a.error} className="mb-3" />
      <Button variant="secondary" loading={a.loading} onClick={async () => setOut(await a.run(() => api("/admin/jobs/run", { method: "POST" })))}>Run jobs now</Button>
      {out && <pre className="mt-3 rounded-control bg-sunken p-3 text-xs overflow-auto">{JSON.stringify(out, null, 2)}</pre>}
    </div>
  );
}
