"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { homeFor, useAuth } from "@/lib/auth";
import { Container } from "@/components/shell";
import { ApiError } from "@/lib/api";
import { Alert, Button, ErrorAlert, Field, useAsync } from "@/components/ui";

export default function Login() {
  const { login } = useAuth();
  const router = useRouter();
  const next = useSearchParams().get("next");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const { loading, error, run } = useAsync();
  const needCode = (error instanceof ApiError && (error.code === "mfa_required" || error.code === "mfa_invalid")) || code !== "";
  return (
    <Container narrow className="py-14 max-w-md">
      <h1 className="text-3xl">Sign in</h1>
      <form
        className="mt-6 grid gap-5"
        onSubmit={async (e) => {
          e.preventDefault();
          const u = await run(() => login(email, password, code));
          if (u) router.push(next && next.startsWith("/") ? next : homeFor(u));
        }}
      >
        {error instanceof ApiError && error.code === "mfa_required" ? <Alert tone="info" title="Two-step verification">Enter the 6-digit code from your authenticator app.</Alert> : <ErrorAlert error={error} />}
        <Field label="Email address" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        <Field label="Password" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
        {needCode && <Field label="Authenticator code" inputMode="numeric" autoComplete="one-time-code" maxLength={6} pattern="[0-9]{6}" required value={code} onChange={(e) => setCode(e.target.value)} />}
        <Button type="submit" loading={loading}>Sign in</Button>
      </form>
      <p className="mt-6 text-small"><Link className="underline underline-offset-4" href="/forgot-password">Forgotten your password?</Link></p>
      <p className="mt-2 text-small text-muted">New here? <Link className="underline underline-offset-4 text-ink" href="/signup">Create an account</Link>. Cleaner? <Link className="underline underline-offset-4 text-ink" href="/join">Apply to work with us</Link>.</p>
    </Container>
  );
}
