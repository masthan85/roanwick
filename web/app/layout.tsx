import type { Metadata, Viewport } from "next";
import { Suspense } from "react";
import { AuthProvider } from "@/lib/auth";
import { Footer, Header } from "@/components/shell";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000"),
  title: { default: "Roanwick: trusted home cleaning in south-west London", template: "%s | Roanwick" },
  description: "Book regular and end-of-tenancy cleaning with the same professional every visit. See the full price, the cancellation terms and which documents we have checked before you pay.",
  openGraph: { type: "website", locale: "en_GB", siteName: "Roanwick" },
  robots: { index: true, follow: true },
};
export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: [{ media: "(prefers-color-scheme: light)", color: "#fbf9f5" }, { media: "(prefers-color-scheme: dark)", color: "#0d1613" }] };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-GB">
      <body className="min-h-screen flex flex-col">
        <a href="#main" className="skip-link">Skip to main content</a>
        <AuthProvider>
          <Suspense fallback={<div className="h-16 border-b border-line" aria-hidden />}>
            <Header />
          </Suspense>
          <main id="main" className="flex-1">{children}</main>
          <Footer />
        </AuthProvider>
      </body>
    </html>
  );
}
