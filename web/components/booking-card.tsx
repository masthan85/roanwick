import Link from "next/link";
import { STATUS_LABEL, dateTime, hours, money } from "@/lib/format";
import { Badge, statusTone } from "./ui";

export function BookingCard({ b, href }: { b: any; href: string }) {
  const mins = Math.round((new Date(b.ends_at).getTime() - new Date(b.starts_at).getTime()) / 60000);
  return (
    <Link href={href} className="block rounded-card border border-line bg-surface p-5 hover:border-brand">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-display text-lg">{b.offering.name}</p>
          <p className="text-small text-muted">{dateTime(b.starts_at)} · {hours(mins)}</p>
        </div>
        <Badge tone={statusTone(b.status)}>{STATUS_LABEL[b.status] ?? b.status}</Badge>
      </div>
      <p className="mt-2 text-sm text-muted">
        {b.reference} · {b.professional ? `with ${b.professional.display_name}` : b.customer ? `for ${b.customer.first_name ?? b.customer.name}` : "professional being assigned"} · {money(b.total_pence)}
      </p>
    </Link>
  );
}
