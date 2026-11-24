"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { Container } from "@/components/shell";
import { Alert, Button, ErrorAlert, Field, fieldErr, useAsync } from "@/components/ui";

export default function Reset() {
  const token = useSearchParams().get("token") ?? "";
  const [pw, setPw] = useState("");
  const [done, setDone] = useState(false);
  const { loading, error, run } = useAsync();
  return (
    <Container narrow className="py-14 max-w-md">
      <h1 className="text-3xl">Choose a new password</h1>
      {done ? (
        <Alert tone="success" className="mt-6" title="Password changed">You can now <Link className="underline" href="/login">sign in</Link> with your new password.</Alert>
      ) : (
        <form className="mt-6 grid gap-5" onSubmit={async (e) => { e.preventDefault(); if ((await run(() => api("/auth/reset-password", { body: { token, new_password: pw } }))) !== undefined) setDone(true); }}>
          <ErrorAlert error={error} />
          <Field label="New password" type="password" autoComplete="new-password" required minLength={10} value={pw} onChange={(e) => setPw(e.target.value)} hint="At least 10 characters." error={fieldErr(error, "new_password")} />
          <Button type="submit" loading={loading} disabled={!token}>Change password</Button>
          {!token && <Alert tone="warn">This link is missing its token. Please use the link from your email.</Alert>}
        </form>
      )}
    </Container>
  );
}
