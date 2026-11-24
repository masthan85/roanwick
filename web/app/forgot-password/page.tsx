"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { Container } from "@/components/shell";
import { Alert, Button, ErrorAlert, Field, useAsync } from "@/components/ui";

export default function Forgot() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const { loading, error, run } = useAsync();
  return (
    <Container narrow className="py-14 max-w-md">
      <h1 className="text-3xl">Reset your password</h1>
      {sent ? (
        <Alert tone="success" className="mt-6" title="Check your inbox">If an account exists for that address, we have sent a link that works for one hour.</Alert>
      ) : (
        <form className="mt-6 grid gap-5" onSubmit={async (e) => { e.preventDefault(); if ((await run(() => api("/auth/forgot-password", { body: { email } }))) !== undefined) setSent(true); }}>
          <ErrorAlert error={error} />
          <Field label="Email address" type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          <Button type="submit" loading={loading}>Send reset link</Button>
        </form>
      )}
    </Container>
  );
}
