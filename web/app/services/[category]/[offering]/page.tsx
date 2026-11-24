import { CheckIcon } from "@/components/icons";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Container } from "@/components/shell";
import { PostcodeCheck } from "@/components/postcode-check";
import { LivePricing } from "@/components/live-pricing";
import { Card } from "@/components/ui";
import { OFFERINGS } from "@/lib/content";

export function generateStaticParams() {
  return OFFERINGS.map((o) => ({ category: o.category, offering: o.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ offering: string }> }): Promise<Metadata> {
  const { offering } = await params;
  const o = OFFERINGS.find((x) => x.slug === offering);
  return o ? { title: o.name, description: o.tagline } : {};
}

export default async function OfferingPage({ params }: { params: Promise<{ category: string; offering: string }> }) {
  const { offering } = await params;
  const o = OFFERINGS.find((x) => x.slug === offering);
  if (!o) notFound();
  const ld = {
    "@context": "https://schema.org",
    "@type": "Service",
    name: o.name,
    description: o.tagline,
    areaServed: "South-west London",
    provider: { "@type": "Organization", name: "Roanwick" },
  };
  return (
    <Container className="py-12">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(ld) }} />
      <div className="grid gap-10 lg:grid-cols-[1.4fr_1fr]">
        <div>
          <h1 className="text-4xl md:text-5xl">{o.name}</h1>
          <p className="mt-4 text-lg text-muted">{o.intro}</p>
          <div className="mt-8 grid gap-6 sm:grid-cols-2">
            <Card>
              <h2 className="text-xl">Included</h2>
              <ul className="mt-3 space-y-2 text-small">{o.included.map((i) => <li key={i} className="flex gap-2"><CheckIcon className="mt-1 shrink-0 text-brand" size={18} />{i}</li>)}</ul>
            </Card>
            <Card>
              <h2 className="text-xl">Not included</h2>
              <ul className="mt-3 space-y-2 text-small text-muted">{o.excluded.map((i) => <li key={i} className="flex gap-2"><span aria-hidden>–</span>{i}</li>)}</ul>
            </Card>
          </div>
          <h2 className="mt-12 text-2xl">Pricing</h2>
          <LivePricing slug={o.slug} />
          <h2 className="mt-12 text-2xl">Questions</h2>
          <div className="mt-4 divide-y divide-line rounded-card border border-line bg-surface">
            {o.faqs.map((f) => (
              <details key={f.q} className="group p-5">
                <summary className="cursor-pointer font-medium list-none flex justify-between gap-4 min-h-6">{f.q}<span aria-hidden className="text-muted group-open:rotate-45 transition-transform">+</span></summary>
                <p className="mt-3 text-muted">{f.a}</p>
              </details>
            ))}
          </div>
        </div>
        <aside aria-label="Check availability" className="lg:sticky lg:top-24 self-start rounded-panel border border-line bg-surface p-5">
          <h2 className="text-xl mb-3">Check your postcode</h2>
          <PostcodeCheck service={o.slug} compact />
        </aside>
      </div>
    </Container>
  );
}
