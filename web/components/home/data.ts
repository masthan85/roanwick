"use client";
import useSWR from "swr";
import { fetcher } from "@/lib/api";

export interface Offering {
  slug: string;
  name: string;
  hourly_rate_pence: number | null;
  min_minutes: number;
  pricing_model: "hourly" | "tiered";
  addons: { code: string; name: string; price_pence: number; extra_minutes: number }[];
  tiers: { bedrooms: number; label: string; price_pence: number }[];
  frequency_discounts: Record<string, number>;
}

/** Everything the landing page shows about money comes from here, so it cannot drift from the real prices. */
export function useHome() {
  const regular = useSWR<Offering>("/catalogue/offerings/regular-cleaning", fetcher);
  const eot = useSWR<Offering>("/catalogue/offerings/end-of-tenancy-cleaning", fetcher);
  const config = useSWR("/public/config", fetcher);
  const areas = useSWR<{ outward_code: string; name: string }[]>("/public/areas", fetcher);
  const bundles = useSWR<{ slug: string; name: string; offering: string; discount_bps: number; addons: { name: string }[] }[]>("/catalogue/bundles", fetcher);
  return { regular: regular.data, eot: eot.data, config: config.data, areas: areas.data, bundles: bundles.data };
}

/** A worked example: three hours, the oven, a fortnightly plan. Same arithmetic as the API's quote builder. */
export function exampleQuote(o: Offering, feePence: number) {
  const hours = 3;
  const labour = Math.round(((o.hourly_rate_pence ?? 0) * hours * 60) / 60);
  const oven = o.addons.find((a) => a.code === "oven");
  const bps = o.frequency_discounts.fortnightly ?? 0;
  const discount = Math.round((labour * bps) / 10000);
  const lines = [
    { label: `Cleaning, ${hours} hours at £${((o.hourly_rate_pence ?? 0) / 100).toFixed(2)}/hour`, pence: labour },
    ...(oven ? [{ label: oven.name, pence: oven.price_pence }] : []),
    ...(bps ? [{ label: `Fortnightly plan discount (${bps / 100}% off labour)`, pence: -discount }] : []),
    { label: "Booking fee", pence: feePence },
  ];
  return { lines, total: lines.reduce((a, l) => a + l.pence, 0) };
}
