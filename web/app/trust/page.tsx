import type { Metadata } from "next";
import { Container } from "@/components/shell";
import { Card } from "@/components/ui";

export const metadata: Metadata = { title: "Trust and safety", description: "Exactly what Roanwick checks before a professional can take bookings, what we do not claim, and how we handle problems." };

export default function Trust() {
  return (
    <Container narrow className="py-14">
      <h1 className="text-4xl">Trust and safety</h1>
      <p className="mt-4 text-lg text-muted">We would rather tell you precisely what we do than use a word like &quot;vetted&quot; and leave you to guess. This page is kept in step with our actual process.</p>

      <h2 className="mt-10 text-2xl">What we check before a professional can take bookings</h2>
      <div className="mt-4 grid gap-4">
        <Card><h3 className="text-lg">Identity</h3><p className="text-muted mt-1">A member of our team reviews a government-issued photo document supplied by the professional.</p></Card>
        <Card><h3 className="text-lg">Right to work in the UK</h3><p className="text-muted mt-1">We review the evidence the professional provides, such as a Home Office share code check result.</p></Card>
        <Card><h3 className="text-lg">Public liability insurance</h3><p className="text-muted mt-1">We review the certificate and record its expiry date. We remind professionals before it runs out, and a professional with an expired certificate does not appear in search or receive new bookings.</p></Card>
      </div>
      <p className="mt-4 text-muted">Professionals can also upload an enhanced DBS certificate. If they do and we approve it, their profile says so, with its date. It is optional during the pilot.</p>

      <h2 className="mt-10 text-2xl">What we do not claim</h2>
      <ul className="mt-3 list-disc pl-5 space-y-2 text-muted">
        <li>We do not run our own criminal record checks. A DBS certificate shown on a profile was obtained by the professional.</li>
        <li>We do not guarantee the quality of any individual visit, though we will put things right where we agree it fell short.</li>
        <li>We do not currently operate an insurance policy covering damage to your property that replaces the professional&apos;s own cover. The professional&apos;s insurance certificate is what we have seen.</li>
        <li>Badges on a profile appear only when a document has been approved and is in date.</li>
      </ul>

      <h2 className="mt-10 text-2xl">If something goes wrong</h2>
      <p className="mt-3 text-muted">Use Report a problem on any booking. We aim to give a first response within 48 hours. Depending on what we find, we can arrange a re-clean or a refund, or stop a professional receiving bookings. Payments to professionals are held for a few days after each visit so there is time to raise an issue.</p>
    </Container>
  );
}
