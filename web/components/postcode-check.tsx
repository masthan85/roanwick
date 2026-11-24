"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { api, qs } from "@/lib/api";
import { normalisePostcode, POSTCODE_RE } from "@/lib/format";
import { Alert, Button, ErrorAlert, Field, useAsync } from "./ui";

export function PostcodeCheck({ service = "regular-cleaning", compact }: { service?: string; compact?: boolean }) {
  const [postcode, setPostcode] = useState("");
  const [result, setResult] = useState<{ covered: boolean; postcode: string; area_name: string | null; outward_code: string } | null>(null);
  const [email, setEmail] = useState("");
  const [joined, setJoined] = useState(false);
  const [localErr, setLocalErr] = useState("");
  const check = useAsync();
  const continueLink = useRef<HTMLAnchorElement>(null);
  // After a successful check, move focus to the next step so keyboard and screen reader users do not have to hunt for it.
  useEffect(() => { if (result?.covered) continueLink.current?.focus(); }, [result]);
  const wait = useAsync();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setJoined(false);
    if (!POSTCODE_RE.test(postcode.trim())) {
      setLocalErr("Enter a full UK postcode, for example SW11 1AB.");
      setResult(null);
      return;
    }
    setLocalErr("");
    const r = await check.run(() => api(`/public/coverage${qs({ postcode })}`));
    if (r) setResult(r);
  }

  return (
    <div>
      <form onSubmit={submit} className="flex flex-col sm:flex-row gap-3 sm:items-end" noValidate>
        <Field label="Your postcode" placeholder="SW11 1AB" autoComplete="postal-code" value={postcode} onChange={(e) => setPostcode(e.target.value)} error={localErr} className="flex-1" />
        <Button type="submit" loading={check.loading} className="sm:mb-0">Check availability</Button>
      </form>
      <div aria-live="polite" className="mt-4">
        <ErrorAlert error={check.error} />
        {result?.covered && (
          <Alert tone="success" title={`Good news: we cover ${result.area_name ?? result.outward_code}.`}>
            <Link ref={continueLink} className="font-medium underline underline-offset-4" href={`/book/${service}?postcode=${encodeURIComponent(normalisePostcode(result.postcode))}`}>
              Continue to book and see your price
            </Link>
          </Alert>
        )}
        {result && !result.covered && !joined && (
          <Alert tone="warn" title={`We do not cover ${result.outward_code} yet.`}>
            <p>We are growing street by street. Leave your email and we will tell you when we arrive.</p>
            <form
              className="mt-3 flex flex-col sm:flex-row gap-3 sm:items-end"
              onSubmit={async (e) => {
                e.preventDefault();
                const r = await wait.run(() => api("/public/waitlist", { body: { email, postcode: result.postcode } }));
                if (r) setJoined(true);
              }}
            >
              <Field label="Email address" type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} className="flex-1" />
              <Button type="submit" variant="secondary" loading={wait.loading}>Join the waiting list</Button>
            </form>
            <ErrorAlert error={wait.error} className="mt-3" />
          </Alert>
        )}
        {joined && <Alert tone="success" title="You are on the list.">We will email you when we start in your area.</Alert>}
      </div>
      {!compact && <p className="mt-3 text-sm text-muted">Pilot areas: SW4, SW11, SW12, SW15, SW17, SW18 and SW19.</p>}
    </div>
  );
}
