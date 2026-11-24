"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { homeFor, useAuth } from "@/lib/auth";
import { Button, LinkButton } from "./ui";

export function Logo({ className = "" }: { className?: string }) {
  return (
    <Link href="/" className={`inline-flex items-center gap-2 font-display text-[22px] font-semibold ${className}`} aria-label="Roanwick home">
      <svg width="26" height="26" viewBox="0 0 26 26" aria-hidden><path d="M3 12.5 13 4l10 8.5V22a1 1 0 0 1-1 1h-6v-7h-6v7H4a1 1 0 0 1-1-1v-9.5Z" fill="var(--brand)" /></svg>
      Roanwick
    </Link>
  );
}

const nav = [
  { href: "/services", label: "Services" },
  { href: "/how-it-works", label: "How it works" },
  { href: "/trust", label: "Trust and safety" },
  { href: "/help", label: "Help" },
];

export function Header() {
  const { user, logout, loading } = useAuth();
  const [open, setOpen] = useState(false);
  const path = usePathname();
  const router = useRouter();
  useEffect(() => setOpen(false), [path]);
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-bg/95 backdrop-blur">
      <div className="mx-auto max-w-6xl px-4 flex items-center justify-between h-16">
        <Logo />
        <nav aria-label="Main" className="hidden md:flex items-center gap-1">
          {nav.map((n) => (
            <Link key={n.href} href={n.href} aria-current={path.startsWith(n.href) ? "page" : undefined} className="px-3 min-h-11 inline-flex items-center rounded-control text-small hover:bg-sunken aria-[current=page]:text-brand aria-[current=page]:font-medium">
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="hidden md:flex items-center gap-2">
          {loading ? null : user ? (
            <>
              <LinkButton href={homeFor(user)} variant="ghost">{user.full_name.split(" ")[0]}</LinkButton>
              <Button variant="secondary" onClick={async () => { await logout(); router.push("/"); }}>Sign out</Button>
            </>
          ) : (
            <>
              <LinkButton href="/login" variant="ghost">Sign in</LinkButton>
              <LinkButton href="/book/regular-cleaning">Book a clean</LinkButton>
            </>
          )}
        </div>
        <button className="md:hidden min-h-11 min-w-11 rounded-control border border-line" aria-expanded={open} aria-controls="mobile-nav" onClick={() => setOpen(!open)}>
          <span className="sr-only">{open ? "Close menu" : "Open menu"}</span>
          <svg width="22" height="22" viewBox="0 0 22 22" className="mx-auto" aria-hidden>
            {open ? <path d="M5 5l12 12M17 5 5 17" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /> : <path d="M3 6h16M3 11h16M3 16h16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />}
          </svg>
        </button>
      </div>
      {open && (
        <div id="mobile-nav" className="md:hidden border-t border-line bg-bg px-4 pb-4">
          <nav aria-label="Mobile" className="flex flex-col py-2">
            {nav.map((n) => (
              <Link key={n.href} href={n.href} className="min-h-12 flex items-center border-b border-line/60">{n.label}</Link>
            ))}
          </nav>
          <div className="flex flex-col gap-2 pt-2">
            {user ? (
              <>
                <LinkButton href={homeFor(user)} variant="secondary">My account</LinkButton>
                <Button variant="ghost" onClick={async () => { await logout(); router.push("/"); }}>Sign out</Button>
              </>
            ) : (
              <>
                <LinkButton href="/book/regular-cleaning">Book a clean</LinkButton>
                <LinkButton href="/login" variant="secondary">Sign in</LinkButton>
              </>
            )}
          </div>
        </div>
      )}
    </header>
  );
}

export function Footer() {
  return (
    <footer className="mt-16 border-t border-line bg-sunken">
      <div className="mx-auto max-w-6xl px-4 py-12 grid gap-10 md:grid-cols-4 text-small">
        <div className="md:col-span-1">
          <Logo />
          <p className="mt-3 text-muted max-w-xs">Home cleaning from professionals whose documents we have checked, at a price you see before you book.</p>
        </div>
        <FooterCol title="Services" links={[["/services/home-cleaning/regular-cleaning", "Regular home cleaning"], ["/services/home-cleaning/end-of-tenancy-cleaning", "End of tenancy cleaning"], ["/services", "Coming later"]]} />
        <FooterCol title="Company" links={[["/how-it-works", "How it works"], ["/trust", "Trust and safety"], ["/join", "Work with us"], ["/contact", "Contact"], ["/help", "Help centre"]]} />
        <FooterCol title="Legal" links={[["/legal/terms", "Terms of service"], ["/legal/privacy", "Privacy notice"], ["/legal/cancellation", "Cancellation and refunds"], ["/legal/cookies", "Cookies"], ["/legal/accessibility", "Accessibility"]]} />
      </div>
      <div className="border-t border-line">
        <p className="mx-auto max-w-6xl px-4 py-5 text-sm text-muted">
          Roanwick is a pilot service in south-west London. Company details and registration numbers will be shown here before public launch.
        </p>
      </div>
    </footer>
  );
}

function FooterCol({ title, links }: { title: string; links: [string, string][] }) {
  return (
    <nav aria-label={title}>
      <p className="font-medium mb-3">{title}</p>
      <ul className="space-y-2">
        {links.map(([h, l]) => (
          <li key={h + l}><Link href={h} className="text-muted hover:text-ink underline-offset-4 hover:underline">{l}</Link></li>
        ))}
      </ul>
    </nav>
  );
}

export function Container({ children, className = "", narrow }: { children: React.ReactNode; className?: string; narrow?: boolean }) {
  return <div className={`mx-auto px-4 ${narrow ? "max-w-3xl" : "max-w-6xl"} ${className}`}>{children}</div>;
}
