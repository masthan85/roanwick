"use client";
import { CloseIcon, StarIcon } from "./icons";
import * as Dialog from "@radix-ui/react-dialog";
import Link from "next/link";
import { useId, useState } from "react";
import { ApiError } from "@/lib/api";

const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");

type Variant = "primary" | "secondary" | "ghost" | "danger";
const variants: Record<Variant, string> = {
  primary: "bg-brand text-brand-fg hover:bg-brand-hover",
  secondary: "bg-surface text-ink border border-line hover:bg-sunken",
  ghost: "text-brand hover:bg-brand-soft",
  danger: "bg-danger text-white hover:opacity-90",
};
const base = "inline-flex items-center justify-center gap-2 rounded-control px-4 min-h-11 text-small font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed";

export function Button({ variant = "primary", loading, className, children, disabled, ...rest }: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; loading?: boolean }) {
  return (
    <button {...rest} disabled={disabled || loading} aria-busy={loading || undefined} className={cx(base, variants[variant], className)}>
      {loading && <Spinner small />}
      {children}
    </button>
  );
}

export function LinkButton({ href, variant = "primary", className, children, ...rest }: { href: string; variant?: Variant; className?: string; children: React.ReactNode } & Omit<React.ComponentProps<typeof Link>, "href">) {
  return (
    <Link href={href} {...rest} className={cx(base, variants[variant], className)}>
      {children}
    </Link>
  );
}

export function Spinner({ small }: { small?: boolean }) {
  const s = small ? "h-4 w-4" : "h-6 w-6";
  return (
    <svg role="status" aria-label="Loading" className={cx(s, "animate-spin")} viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity=".25" strokeWidth="3" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cx("skeleton", className ?? "h-5 w-full")} />;
}

export function PageLoading({ label = "Loading" }: { label?: string }) {
  return (
    <div className="py-16 flex flex-col items-center gap-3 text-muted" role="status" aria-live="polite">
      <Spinner />
      <span>{label}…</span>
    </div>
  );
}

export function Card({ className, children, ...rest }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div data-card {...rest} className={cx("rounded-card border border-line bg-surface p-5 md:p-6", className)}>
      {children}
    </div>
  );
}

const tones = {
  neutral: "bg-sunken text-ink border-line",
  brand: "bg-brand-soft text-brand border-transparent",
  success: "bg-success-soft text-success border-transparent",
  warn: "bg-warn-soft text-warn border-transparent",
  danger: "bg-danger-soft text-danger border-transparent",
  accent: "bg-accent-soft text-accent border-transparent",
};
export function Badge({ tone = "neutral", children }: { tone?: keyof typeof tones; children: React.ReactNode }) {
  return <span className={cx("inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium whitespace-nowrap", tones[tone])}>{children}</span>;
}

export const statusTone = (s: string): keyof typeof tones =>
  ({ confirmed: "success", completed: "success", approved: "success", paid: "success", succeeded: "success", resolved: "success", in_progress: "brand", awaiting_provider: "warn", pending_payment: "warn", submitted: "warn", pending: "warn", open: "warn", investigating: "brand", held: "warn", cancelled: "neutral", expired: "neutral", rejected: "danger", suspended: "danger", failed: "danger", draft: "neutral" })[s] as keyof typeof tones ?? "neutral";

export function Alert({ tone = "danger", title, children, className }: { tone?: "danger" | "success" | "warn" | "info"; title?: string; children?: React.ReactNode; className?: string }) {
  const t = tone === "info" ? "bg-brand-soft text-ink border-line" : tone === "danger" ? "bg-danger-soft text-ink border-danger/40" : tone === "success" ? "bg-success-soft text-ink border-success/40" : "bg-warn-soft text-ink border-warn/40";
  return (
    <div role={tone === "danger" ? "alert" : "status"} className={cx("rounded-control border px-4 py-3 text-small", t, className)}>
      {title && <p className="font-semibold">{title}</p>}
      {children && <div className={title ? "mt-1" : ""}>{children}</div>}
    </div>
  );
}

export function ErrorAlert({ error, className }: { error: unknown; className?: string }) {
  if (!error) return null;
  const msg = error instanceof ApiError ? error.message : "Something went wrong. Please try again.";
  return <Alert className={className}>{msg}</Alert>;
}

export function Empty({ title, children, action }: { title: string; children?: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="rounded-card border border-dashed border-line bg-sunken px-6 py-10 text-center">
      <p className="font-display text-lg">{title}</p>
      {children && <p className="mt-1 text-muted max-w-md mx-auto">{children}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

interface FieldProps {
  label: string;
  hint?: string;
  error?: string;
  optional?: boolean;
}
const inputCls = "w-full rounded-control border border-line bg-surface px-3 min-h-11 text-[16px] placeholder:text-muted/70 focus:border-brand";

export function Field({ label, hint, error, optional, className, ...rest }: FieldProps & React.InputHTMLAttributes<HTMLInputElement>) {
  const id = useId();
  return (
    <div className={className}>
      <label htmlFor={id} className="block text-sm font-medium mb-1.5">
        {label}
        {optional && <span className="text-muted font-normal"> (optional)</span>}
      </label>
      <input id={id} {...rest} aria-invalid={!!error || undefined} aria-describedby={error ? `${id}-err` : hint ? `${id}-hint` : undefined} className={cx(inputCls, error && "border-danger")} />
      {hint && !error && <p id={`${id}-hint`} className="mt-1 text-sm text-muted">{hint}</p>}
      {error && <p id={`${id}-err`} className="mt-1 text-sm text-danger" role="alert">{error}</p>}
    </div>
  );
}

export function TextArea({ label, hint, error, optional, className, ...rest }: FieldProps & React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const id = useId();
  return (
    <div className={className}>
      <label htmlFor={id} className="block text-sm font-medium mb-1.5">
        {label}
        {optional && <span className="text-muted font-normal"> (optional)</span>}
      </label>
      <textarea id={id} rows={4} {...rest} aria-invalid={!!error || undefined} aria-describedby={error ? `${id}-err` : hint ? `${id}-hint` : undefined} className={cx(inputCls, "py-2.5", error && "border-danger")} />
      {hint && !error && <p id={`${id}-hint`} className="mt-1 text-sm text-muted">{hint}</p>}
      {error && <p id={`${id}-err`} className="mt-1 text-sm text-danger" role="alert">{error}</p>}
    </div>
  );
}

export function Select({ label, hint, error, optional, className, children, ...rest }: FieldProps & React.SelectHTMLAttributes<HTMLSelectElement>) {
  const id = useId();
  return (
    <div className={className}>
      <label htmlFor={id} className="block text-sm font-medium mb-1.5">
        {label}
        {optional && <span className="text-muted font-normal"> (optional)</span>}
      </label>
      <select id={id} {...rest} aria-invalid={!!error || undefined} aria-describedby={error ? `${id}-err` : hint ? `${id}-hint` : undefined} className={cx(inputCls, error && "border-danger")}>
        {children}
      </select>
      {hint && !error && <p id={`${id}-hint`} className="mt-1 text-sm text-muted">{hint}</p>}
      {error && <p id={`${id}-err`} className="mt-1 text-sm text-danger" role="alert">{error}</p>}
    </div>
  );
}

export function Check({ label, className, ...rest }: { label: React.ReactNode } & React.InputHTMLAttributes<HTMLInputElement>) {
  const id = useId();
  return (
    <div className={cx("flex items-start gap-3", className)}>
      <input id={id} type="checkbox" {...rest} className="mt-1 h-5 w-5 shrink-0 accent-[var(--brand)]" />
      <label htmlFor={id} className="text-small">{label}</label>
    </div>
  );
}

export function Modal({ open, onOpenChange, title, description, children }: { open: boolean; onOpenChange: (o: boolean) => void; title: string; description?: string; children: React.ReactNode }) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/50 z-40" />
        <Dialog.Content className="fixed z-50 left-1/2 top-1/2 w-[calc(100%-32px)] max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-panel bg-surface border border-line p-6 max-h-[88vh] overflow-y-auto">
          <Dialog.Title className="font-display text-xl">{title}</Dialog.Title>
          <Dialog.Description className={description ? "mt-1 text-muted" : "sr-only"}>{description ?? title}</Dialog.Description>
          <div className="mt-4">{children}</div>
          <Dialog.Close asChild>
            <button aria-label="Close" className="absolute right-3 top-3 h-10 w-10 rounded-control hover:bg-sunken grid place-items-center"><CloseIcon /></button>
          </Dialog.Close>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export function Tabs({ tabs, value, onChange, label }: { tabs: { id: string; label: string; badge?: number }[]; value: string; onChange: (id: string) => void; label: string }) {
  return (
    <div role="tablist" aria-label={label} className="flex gap-1 overflow-x-auto border-b border-line -mx-1 px-1">
      {tabs.map((t) => (
        <button
          key={t.id}
          role="tab"
          id={`tab-${t.id}`}
          aria-selected={value === t.id}
          aria-controls={`panel-${t.id}`}
          onClick={() => onChange(t.id)}
          className={cx("px-4 min-h-11 whitespace-nowrap text-small font-medium border-b-2 -mb-px", value === t.id ? "border-brand text-brand" : "border-transparent text-muted hover:text-ink")}
        >
          {t.label}
          {t.badge ? <span className="ml-2 rounded-full bg-accent-soft text-accent px-2 text-xs">{t.badge}</span> : null}
        </button>
      ))}
    </div>
  );
}
export const Panel = ({ id, children }: { id: string; children: React.ReactNode }) => (
  <div role="tabpanel" id={`panel-${id}`} aria-labelledby={`tab-${id}`} className="pt-6">{children}</div>
);

export function Stars({ value, count }: { value: number; count?: number }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-sm">
      <span aria-hidden className="inline-flex text-accent">{[1, 2, 3, 4, 5].map((n) => <StarIcon key={n} filled={n <= Math.round(value)} className={n <= Math.round(value) ? "" : "text-line"} />)}</span>
      <span className="font-medium">{value ? value.toFixed(1) : "New"}</span>
      {count !== undefined && <span className="text-muted">({count})</span>}
      <span className="sr-only">{value ? `${value.toFixed(1)} out of 5` : "No ratings yet"}</span>
    </span>
  );
}

export function Stat({ label, value, note, basis }: { label: string; value: React.ReactNode; note?: string; basis?: string }) {
  return (
    <div className="rounded-card border border-line bg-surface p-4">
      <p className="text-sm text-muted">{label}</p>
      <p className="mt-1 font-display text-2xl">{value}</p>
      {basis && <Badge tone={basis === "actual" ? "success" : basis === "manual" ? "accent" : "warn"}>{basis === "actual" ? "Actual" : basis === "manual" ? "Manual entry" : "Estimate"}</Badge>}
      {note && <p className="mt-2 text-xs text-muted">{note}</p>}
    </div>
  );
}

export function DataTable({ columns, rows, empty = "Nothing to show yet.", caption }: { columns: { key: string; header: string; render?: (row: any) => React.ReactNode; className?: string }[]; rows: any[]; empty?: string; caption: string }) {
  if (!rows.length) return <Empty title={empty} />;
  return (
    <div className="overflow-x-auto rounded-card border border-line bg-surface">
      <table className="w-full text-left text-small">
        <caption className="sr-only">{caption}</caption>
        <thead className="bg-sunken text-sm text-muted">
          <tr>
            {columns.map((c) => (
              <th key={c.key} scope="col" className={cx("px-4 py-3 font-medium whitespace-nowrap", c.className)}>{c.header}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {rows.map((r, i) => (
            <tr key={r.id ?? i} className="align-top">
              {columns.map((c) => (
                <td key={c.key} className={cx("px-4 py-3", c.className)}>{c.render ? c.render(r) : r[c.key]}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Pager({ page, pageSize, total, onChange }: { page: number; pageSize: number; total: number; onChange: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (pages <= 1) return null;
  return (
    <nav aria-label="Pagination" className="mt-4 flex items-center justify-between text-sm">
      <span className="text-muted">Page {page} of {pages} ({total} results)</span>
      <div className="flex gap-2">
        <Button variant="secondary" disabled={page <= 1} onClick={() => onChange(page - 1)}>Previous</Button>
        <Button variant="secondary" disabled={page >= pages} onClick={() => onChange(page + 1)}>Next</Button>
      </div>
    </nav>
  );
}

export function useAsync() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);
  async function run<T>(fn: () => Promise<T>): Promise<T | undefined> {
    setLoading(true);
    setError(null);
    try {
      return await fn();
    } catch (e) {
      setError(e);
      return undefined;
    } finally {
      setLoading(false);
    }
  }
  return { loading, error, run, setError };
}

export const fieldErr = (e: unknown, name: string) => (e instanceof ApiError ? e.fields[name] : undefined);
