"use client";
import { useState } from "react";
import { today, daysAgo } from "@/lib/dates";
import { Field } from "./ui";

export function useRange(defaultDays = 30) {
  const [from, setFrom] = useState(daysAgo(defaultDays - 1));
  const [to, setTo] = useState(today());
  const picker = (
    <div className="flex flex-wrap items-end gap-3">
      <Field label="From" type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
      <Field label="To" type="date" value={to} onChange={(e) => setTo(e.target.value)} />
    </div>
  );
  return { from, to, picker };
}

export function PageHeader({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <h1 className="text-3xl">{title}</h1>
      {children}
    </div>
  );
}
