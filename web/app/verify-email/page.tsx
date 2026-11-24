"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Container } from "@/components/shell";
import { Alert, PageLoading } from "@/components/ui";

export default function Verify() {
  const token = useSearchParams().get("token");
  const [state, setState] = useState<"working" | "ok" | "bad">("working");
  useEffect(() => {
    if (!token) return setState("bad");
    api("/auth/verify-email", { body: { token } }).then(() => setState("ok"), () => setState("bad"));
  }, [token]);
  return (
    <Container narrow className="py-14">
      <h1 className="text-3xl">Email confirmation</h1>
      <div className="mt-6">
        {state === "working" && <PageLoading label="Confirming your email" />}
        {state === "ok" && <Alert tone="success" title="Thank you, your email is confirmed.">You can <Link className="underline" href="/account">go to your account</Link>.</Alert>}
        {state === "bad" && <Alert title="This link is not valid or has expired.">Sign in and we can send you a new one from your profile.</Alert>}
      </div>
    </Container>
  );
}
