import type { Metadata } from "next";
import { Container } from "@/components/shell";
import { LinkButton } from "@/components/ui";
import { FAQ_GROUPS } from "@/lib/content";

export const metadata: Metadata = { title: "Help centre", description: "Answers about booking, pricing, cancellations, trust and your data." };

export default function Help() {
  const ld = { "@context": "https://schema.org", "@type": "FAQPage", mainEntity: FAQ_GROUPS.flatMap((g) => g.items).map((f) => ({ "@type": "Question", name: f.q, acceptedAnswer: { "@type": "Answer", text: f.a } })) };
  return (
    <Container narrow className="py-14">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(ld) }} />
      <h1 className="text-4xl">Help centre</h1>
      {FAQ_GROUPS.map((g) => (
        <section key={g.title} className="mt-10" aria-labelledby={g.title.replace(/\W+/g, "-")}>
          <h2 id={g.title.replace(/\W+/g, "-")} className="text-2xl">{g.title}</h2>
          <div className="mt-4 divide-y divide-line rounded-card border border-line bg-surface">
            {g.items.map((f) => (
              <details key={f.q} className="group p-5">
                <summary className="cursor-pointer font-medium list-none flex justify-between gap-4">{f.q}<span aria-hidden className="text-muted group-open:rotate-45 transition-transform">+</span></summary>
                <p className="mt-3 text-muted">{f.a}</p>
              </details>
            ))}
          </div>
        </section>
      ))}
      <div className="mt-12 rounded-card bg-sunken border border-line p-6">
        <h2 className="text-xl">Still need help?</h2>
        <p className="text-muted mt-1">If you have a booking, the quickest route is Report a problem inside it. Otherwise, write to us.</p>
        <div className="mt-4"><LinkButton href="/contact" variant="secondary">Contact us</LinkButton></div>
      </div>
    </Container>
  );
}
