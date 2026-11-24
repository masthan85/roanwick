import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Container } from "@/components/shell";
import { Alert } from "@/components/ui";

type Section = { h: string; p: string[] };
const DOCS: Record<string, { title: string; sections: Section[] }> = {
  terms: {
    title: "Terms of service",
    sections: [
      { h: "About these terms", p: ["These terms apply when you use Roanwick to book home services. Roanwick operates a platform that connects customers with independent service professionals. The contract for the service itself is between you and the professional; Roanwick takes payment and provides support as set out here."] },
      { h: "Bookings and prices", p: ["The quote you accept shows the price, any extras and fees and the total payable. We do not add charges after you confirm. A slot is held for 15 minutes while you pay."] },
      { h: "Your right to cancel", p: ["You can cancel a booking at any time. The refund depends on how far ahead you cancel, as set out in the cancellation policy. If you ask us to start the service within 14 days of booking, you agree that your statutory right to cancel is limited as the law provides once the service has been fully performed, and that you will pay for the service provided up to the point of cancelling."] },
      { h: "Access and conduct", p: ["Please provide safe access and accurate information about the property. Professionals may decline or leave a job if they feel unsafe."] },
      { h: "Problems and complaints", p: ["Tell us within 48 hours of a visit if something was not right and we will investigate. This does not affect your legal rights."] },
    ],
  },
  privacy: {
    title: "Privacy notice",
    sections: [
      { h: "Who we are", p: ["Roanwick is the data controller for the personal data described here. Contact details for data protection queries will be published here before public launch."] },
      { h: "What we collect and why", p: ["Account details, addresses and booking information, so we can provide the service. Payment information is handled by our payment provider; we store only references and amounts. For professionals, we also collect identity, right-to-work and insurance documents so we can approve them to work on the platform. Our lawful bases are contract, legal obligation and legitimate interests, and consent for marketing."] },
      { h: "How long we keep it", p: ["Booking and financial records are kept for the periods tax law requires. Identity documents are retained while a professional is active and for a limited period afterwards. Marketing preferences can be changed at any time."] },
      { h: "Your rights", p: ["You can ask for a copy of your data, correction, erasure, restriction or to object, and you can complain to the Information Commissioner's Office. In your account you can download your data and close your account."] },
    ],
  },
  cancellation: {
    title: "Cancellation and refunds",
    sections: [
      { h: "If you cancel", p: ["More than 48 hours before the start: full refund. Between 24 and 48 hours: 50% refunded. Less than 24 hours: no refund. These tiers are shown on every quote and in your booking. They can change over time but the terms in your booking at the time you booked are the terms that apply."] },
      { h: "If your professional cancels", p: ["You receive a full refund. We will try to offer the visit to another available professional and will tell you if we do."] },
      { h: "If the visit was not up to standard", p: ["Report a problem within 48 hours. Where we agree the service fell short we may arrange a re-clean or a full or partial refund."] },
      { h: "How refunds are paid", p: ["Refunds go back to the original card. Any part you paid with account credit is returned as credit. Card refunds usually reach your account within 5 to 10 working days."] },
    ],
  },
  cookies: {
    title: "Cookies",
    sections: [{ h: "What we use", p: ["We use one strictly necessary cookie to keep you signed in securely. We do not currently use advertising or analytics cookies. If that changes we will ask for your consent first and update this page."] }],
  },
  accessibility: {
    title: "Accessibility statement",
    sections: [
      { h: "Our commitment", p: ["We aim to meet WCAG 2.2 level AA. The site works with a keyboard and screen readers, respects reduced-motion settings and has been designed for small screens."] },
      { h: "Known limitations", p: ["This is a pilot and we have not yet had an independent accessibility audit. If you find a barrier, please contact us and we will fix it or offer another way to book, such as by phone."] },
    ],
  },
};

export function generateStaticParams() {
  return Object.keys(DOCS).map((doc) => ({ doc }));
}

export async function generateMetadata({ params }: { params: Promise<{ doc: string }> }): Promise<Metadata> {
  const { doc } = await params;
  return DOCS[doc] ? { title: DOCS[doc].title } : {};
}

export default async function Legal({ params }: { params: Promise<{ doc: string }> }) {
  const { doc } = await params;
  const d = DOCS[doc];
  if (!d) notFound();
  return (
    <Container narrow className="py-14">
      <h1 className="text-4xl">{d.title}</h1>
      <Alert tone="warn" className="mt-6" title="Draft for the pilot">
        This text has not yet been reviewed by a solicitor. It must be reviewed, and company and data protection details added, before any public launch.
      </Alert>
      <div className="prose-legal mt-6">
        {d.sections.map((s) => (
          <section key={s.h}><h2>{s.h}</h2>{s.p.map((t) => <p key={t}>{t}</p>)}</section>
        ))}
      </div>
    </Container>
  );
}
