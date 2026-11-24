"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { RequireRole } from "@/components/guard";
import { useAuth } from "@/lib/auth";

const NAV: { href: string; label: string; perm: string }[] = [
  { href: "/admin", label: "Overview", perm: "bookings.read" },
  { href: "/admin/bookings", label: "Bookings", perm: "bookings.read" },
  { href: "/admin/providers", label: "Professionals", perm: "users.read" },
  { href: "/admin/support", label: "Complaints and refunds", perm: "complaints.manage" },
  { href: "/admin/payouts", label: "Payouts", perm: "payouts.read" },
  { href: "/admin/finance", label: "Finance and growth", perm: "finance.read" },
  { href: "/admin/catalogue", label: "Catalogue and promotions", perm: "catalogue.manage" },
  { href: "/admin/users", label: "Customers and staff", perm: "users.read" },
  { href: "/admin/settings", label: "Settings and flags", perm: "settings.manage" },
  { href: "/admin/audit", label: "Audit log", perm: "audit.read" },
  { href: "/admin/security", label: "My security", perm: "" },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const { can } = useAuth();
  return (
    <RequireRole roles={["super_admin", "operations", "support", "finance"]}>
      <div className="mx-auto max-w-7xl px-4 py-8 grid gap-8 lg:grid-cols-[230px_1fr]">
        <nav aria-label="Administration" className="lg:sticky lg:top-24 self-start">
          <ul className="flex lg:flex-col gap-1 overflow-x-auto pb-2 lg:pb-0">
            {NAV.filter((n) => !n.perm || can(n.perm)).map((n) => {
              const active = n.href === "/admin" ? path === "/admin" : path.startsWith(n.href);
              return (
                <li key={n.href}>
                  <Link href={n.href} aria-current={active ? "page" : undefined} className={`flex min-h-11 items-center whitespace-nowrap rounded-control px-3 text-small ${active ? "bg-brand-soft text-brand font-medium" : "hover:bg-sunken"}`}>{n.label}</Link>
                </li>
              );
            })}
          </ul>
        </nav>
        <div className="min-w-0">{children}</div>
      </div>
    </RequireRole>
  );
}
