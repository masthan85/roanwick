"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { PageHeader } from "@/components/admin";
import { Alert, Button, Card, ErrorAlert, Field, useAsync } from "@/components/ui";

export default function Security() {
  const { user, reload } = useAuth();
  const [setup, setSetup] = useState<{ secret: string; otpauth_uri: string } | null>(null);
  const [code, setCode] = useState("");
  const [pw, setPw] = useState("");
  const a = useAsync();
  if (!user) return null;
  return (
    <div className="max-w-2xl">
      <PageHeader title="My security" />
      <Card>
        <h2 className="text-xl">Two-step verification</h2>
        <p className="mt-2 text-small text-muted">Adds a 6-digit code from an authenticator app (such as Google Authenticator, 1Password or Authy) to sign-in. Strongly recommended for every staff account. Administrators can require it for all staff in Settings.</p>
        <ErrorAlert error={a.error} className="mt-4" />
        {user.mfa_enabled ? (
          <form className="mt-4 grid gap-4" onSubmit={async (e) => { e.preventDefault(); if ((await a.run(() => api("/auth/mfa/disable", { body: { password: pw, code } }))) !== undefined) { setPw(""); setCode(""); await reload(); } }}>
            <Alert tone="success" title="Two-step verification is on." />
            <Field label="Your password" type="password" autoComplete="current-password" required value={pw} onChange={(e) => setPw(e.target.value)} />
            <Field label="Current code" inputMode="numeric" maxLength={6} required value={code} onChange={(e) => setCode(e.target.value)} />
            <Button type="submit" variant="danger" loading={a.loading} className="justify-self-start">Turn off</Button>
          </form>
        ) : !setup ? (
          <Button className="mt-4" loading={a.loading} onClick={async () => { const r = await a.run(() => api<{ secret: string; otpauth_uri: string }>("/auth/mfa/setup", { method: "POST" })); if (r) setSetup(r); }}>Set up</Button>
        ) : (
          <form className="mt-4 grid gap-4" onSubmit={async (e) => { e.preventDefault(); if (await a.run(() => api("/auth/mfa/enable", { body: { code } }))) { setSetup(null); setCode(""); await reload(); } }}>
            <p className="text-small">In your authenticator app choose to add an account with a setup key, and enter this key. Keep it private.</p>
            <code className="rounded-control bg-sunken px-3 py-2 text-lg tracking-widest break-all">{setup.secret}</code>
            <p className="text-sm text-muted">Some apps accept this link instead: <a className="underline break-all" href={setup.otpauth_uri}>open in authenticator</a>.</p>
            <Field label="Code from the app" inputMode="numeric" autoComplete="one-time-code" maxLength={6} required value={code} onChange={(e) => setCode(e.target.value)} />
            <Button type="submit" loading={a.loading} className="justify-self-start">Turn on</Button>
          </form>
        )}
      </Card>
    </div>
  );
}
