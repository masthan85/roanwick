"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { homeFor, useAuth } from "@/lib/auth";
import { Container } from "@/components/shell";
import { Button, Check, ErrorAlert, Field, fieldErr, useAsync } from "@/components/ui";

export default function Signup() {
  const { register } = useAuth();
  const router = useRouter();
  const sp = useSearchParams();
  const next = sp.get("next");
  const [f, setF] = useState({ full_name: "", email: "", phone: "", password: "", accept_terms: false, marketing_consent: false, referral_code: sp.get("ref") ?? "" });
  const { loading, error, run } = useAsync();
  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  return (
    <Container narrow className="py-14 max-w-md">
      <h1 className="text-3xl">Create your account</h1>
      <form
        className="mt-6 grid gap-5"
        onSubmit={async (e) => {
          e.preventDefault();
          const body = { ...f, phone: f.phone || null, referral_code: f.referral_code || null, source: sp.get("utm_source") ?? "direct" };
          const u = await run(() => register(body));
          if (u) router.push(next && next.startsWith("/") ? next : homeFor(u));
        }}
      >
        <ErrorAlert error={error} />
        <Field label="Full name" autoComplete="name" required value={f.full_name} onChange={set("full_name")} error={fieldErr(error, "full_name")} />
        <Field label="Email address" type="email" autoComplete="email" required value={f.email} onChange={set("email")} error={fieldErr(error, "email")} />
        <Field label="Mobile number" type="tel" autoComplete="tel" optional value={f.phone} onChange={set("phone")} hint="Used for booking reminders, for example 07700 900123." error={fieldErr(error, "phone")} />
        <Field label="Password" type="password" autoComplete="new-password" required minLength={10} value={f.password} onChange={set("password")} hint="At least 10 characters." error={fieldErr(error, "password")} />
        <Field label="Referral code" optional value={f.referral_code} onChange={set("referral_code")} />
        <Check checked={f.accept_terms} onChange={set("accept_terms")} required label={<>I accept the <Link className="underline" href="/legal/terms">terms of service</Link> and have read the <Link className="underline" href="/legal/privacy">privacy notice</Link>.</>} />
        <Check checked={f.marketing_consent} onChange={set("marketing_consent")} label="Send me occasional offers by email. You can opt out at any time." />
        <Button type="submit" loading={loading}>Create account</Button>
      </form>
      <p className="mt-6 text-small text-muted">Already registered? <Link className="underline underline-offset-4 text-ink" href="/login">Sign in</Link></p>
    </Container>
  );
}
