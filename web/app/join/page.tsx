"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { Container } from "@/components/shell";
import { Button, Card, Check, ErrorAlert, Field, fieldErr, useAsync } from "@/components/ui";

export default function Join() {
  const { register } = useAuth();
  const router = useRouter();
  const [f, setF] = useState({ full_name: "", display_name: "", email: "", phone: "", password: "", accept_terms: false });
  const { loading, error, run } = useAsync();
  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  return (
    <Container className="py-14 grid gap-12 lg:grid-cols-2">
      <div>
        <h1 className="text-4xl md:text-5xl">Work with Roanwick</h1>
        <p className="mt-4 text-lg text-muted">Build a regular round of clients near you. You choose your hours and areas, you see your commission before you accept a job, and you are paid after each completed visit.</p>
        <dl className="mt-8 grid gap-5">
          {[
            ["How much you keep", "A flat commission on the service value, shown on every job before you accept. The current rate is on your earnings page."],
            ["How you are paid", "Payouts are released a few days after each visit, once any problem has had a chance to be raised."],
            ["What we ask for", "Photo identity, evidence of your right to work in the UK and your public liability insurance certificate. Our team reviews each one before you can take bookings."],
            ["Your independence", "You are in business for yourself. You set your availability, can decline jobs and can substitute where the booking allows. We are taking legal advice on the working relationship and will update these terms."],
          ].map(([t, d]) => <div key={t}><dt className="font-medium">{t}</dt><dd className="text-muted mt-1">{d}</dd></div>)}
        </dl>
      </div>
      <Card className="self-start">
        <h2 className="text-2xl">Apply</h2>
        <form className="mt-5 grid gap-4" onSubmit={async (e) => { e.preventDefault(); const u = await run(() => register(f, "provider")); if (u) router.push("/pro"); }}>
          <ErrorAlert error={error} />
          <Field label="Full name" autoComplete="name" required value={f.full_name} onChange={set("full_name")} error={fieldErr(error, "full_name")} />
          <Field label="Name shown to customers" required value={f.display_name} onChange={set("display_name")} hint="For example, Elena K." error={fieldErr(error, "display_name")} />
          <Field label="Email address" type="email" autoComplete="email" required value={f.email} onChange={set("email")} error={fieldErr(error, "email")} />
          <Field label="Mobile number" type="tel" autoComplete="tel" required value={f.phone} onChange={set("phone")} error={fieldErr(error, "phone")} />
          <Field label="Password" type="password" autoComplete="new-password" required minLength={10} value={f.password} onChange={set("password")} hint="At least 10 characters." error={fieldErr(error, "password")} />
          <Check checked={f.accept_terms} onChange={set("accept_terms")} required label={<>I accept the <Link className="underline" href="/legal/terms">terms</Link> and the <Link className="underline" href="/legal/privacy">privacy notice</Link>.</>} />
          <Button type="submit" loading={loading}>Start my application</Button>
        </form>
        <p className="mt-4 text-sm text-muted">Already applied? <Link className="underline" href="/login">Sign in</Link></p>
      </Card>
    </Container>
  );
}
