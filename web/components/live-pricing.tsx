"use client";
import useSWR from "swr";
import { fetcher } from "@/lib/api";
import { hours, money } from "@/lib/format";
import { Alert, DataTable, Skeleton } from "./ui";

export function LivePricing({ slug }: { slug: string }) {
  const { data, error, isLoading } = useSWR(`/catalogue/offerings/${slug}`, fetcher);
  const { data: cfg } = useSWR("/public/config", fetcher);
  const { data: bundles } = useSWR(`/catalogue/bundles?offering=${slug}`, fetcher);
  if (isLoading) return <div className="mt-4 space-y-3"><Skeleton className="h-6 w-1/2" /><Skeleton className="h-24" /></div>;
  if (error || !data) return <Alert tone="warn" className="mt-4">Live prices could not be loaded just now. Enter your postcode to see an exact quote.</Alert>;
  return (
    <div className="mt-4 space-y-4">
      {data.pricing_model === "hourly" ? (
        <p className="text-lg">
          <strong>{money(data.hourly_rate_pence)}</strong> per hour, with a {hours(data.min_minutes)} minimum. Weekly plans save 10% on labour and fortnightly plans save 5%.
        </p>
      ) : (
        <DataTable caption="Fixed prices by property size" columns={[{ key: "label", header: "Property" }, { key: "price", header: "Fixed price", render: (t) => money(t.price_pence) }, { key: "dur", header: "Typical visit", render: (t) => hours(t.duration_minutes) }]} rows={data.tiers} />
      )}
      {data.addons.length > 0 && (
        <div>
          <p className="font-medium">Optional extras</p>
          <ul className="mt-2 grid gap-1 text-small">{data.addons.map((a: any) => <li key={a.code} className="flex justify-between border-b border-line py-1.5"><span>{a.name}</span><span className="tabular-nums">{money(a.price_pence)}</span></li>)}</ul>
        </div>
      )}
      {bundles && bundles.length > 0 && (
        <div>
          <p className="font-medium">Bundles</p>
          <ul className="mt-2 grid gap-2">
            {bundles.map((b: any) => (
              <li key={b.slug} className="rounded-control border border-line bg-surface p-3 text-small">
                <span className="font-medium">{b.name}</span> <span className="text-success text-sm">{b.discount_bps / 100}% off</span>
                <span className="block text-muted text-sm">{b.description}</span>
                <a className="text-sm underline underline-offset-4" href={`/book/${slug}?bundle=${b.slug}`}>Book this bundle</a>
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="text-sm text-muted">
        Booking fee: {cfg ? money(cfg.booking_fee_pence) : "shown on your quote"}. {cfg?.cancellation_terms?.summary?.join(" ")}
      </p>
    </div>
  );
}
