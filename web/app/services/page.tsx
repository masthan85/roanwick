import type { Metadata } from "next";
import Link from "next/link";
import { Container } from "@/components/shell";
import { Badge, Card } from "@/components/ui";
import { COMING_LATER, OFFERINGS } from "@/lib/content";

export const metadata: Metadata = { title: "Services", description: "Regular home cleaning and end-of-tenancy cleaning in south-west London, with itemised prices." };

export default function Services() {
  return (
    <Container className="py-14">
      <h1 className="text-4xl">Services</h1>
      <p className="mt-3 text-muted max-w-2xl">We are starting with two services and doing them well. We will add others once we are sure we can check and support them properly.</p>
      <div className="mt-10 grid gap-6 md:grid-cols-2">
        {OFFERINGS.map((o) => (
          <Link key={o.slug} href={`/services/${o.category}/${o.slug}`} className="rounded-card border border-line bg-surface p-6 hover:border-brand">
            <Badge tone="success">Available now</Badge>
            <h2 className="mt-3 text-2xl">{o.name}</h2>
            <p className="mt-2 text-muted">{o.tagline}</p>
          </Link>
        ))}
      </div>
      <h2 className="mt-14 text-2xl">Not yet available</h2>
      <p className="mt-2 text-muted max-w-2xl">Some trades are regulated, and a professional needs specific qualifications or registrations. We will not open these until we know exactly what to check.</p>
      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {COMING_LATER.map((c) => (
          <Card key={c.name}>
            <h3 className="text-lg">{c.name}</h3>
            <p className="text-muted text-sm mt-1">{c.note}</p>
          </Card>
        ))}
      </div>
    </Container>
  );
}
