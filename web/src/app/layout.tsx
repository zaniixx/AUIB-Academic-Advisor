import type { Metadata, Viewport } from "next";
import { Ubuntu } from "next/font/google";
import Link from "next/link";
import { Suspense } from "react";
import { GraduationCapIcon } from "@/components/icons";
import { SiteNav, SiteNavFallback } from "@/components/SiteNav";
import "./globals.css";

// AUIB's typeface. next/font serves it from this app, so browsers never contact Google.
const ubuntu = Ubuntu({ subsets: ["latin"], weight: ["400", "500", "700"], variable: "--font-ubuntu", display: "swap" });

export const metadata: Metadata = {
  title: { default: "AUIB Academic Advisor", template: "%s · AUIB Academic Advisor" },
  description:
    "Plan your AUIB degree: see what is left, what to take next, and what a change does to your graduation date.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#273237" },
    { media: "(prefers-color-scheme: dark)", color: "#10171a" },
  ],
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    // Browser extensions often add classes or attributes to <html> and <body> before React loads
    // (one adds "vc-init" to <body>). suppressHydrationWarning ignores attribute differences on these
    // two elements only; a mismatch anywhere inside the page is still reported.
    <html lang="en" dir="ltr" className={`h-full ${ubuntu.variable}`} suppressHydrationWarning>
      <body className="flex min-h-full flex-col bg-background text-text antialiased" suppressHydrationWarning>
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:start-3 focus:top-3 focus:z-50 focus:rounded-button focus:bg-surface focus:px-4 focus:py-2 focus:shadow-float"
        >
          Skip to content
        </a>
        <header className="sticky top-0 z-40 border-t-4 border-primary bg-ink/95 dark:border-b dark:border-b-white/8 text-ink-contrast shadow-[0_6px_20px_-12px_rgb(0_0_0/0.5)] backdrop-blur-md">
          <div className="mx-auto flex max-w-6xl items-center justify-between gap-2 px-4 py-2">
            <Link href="/" className="group flex min-h-11 items-center gap-2.5 rounded-xl">
              <span className="grid h-9 w-9 place-items-center rounded-xl bg-primary text-primary-contrast shadow-soft transition duration-300 ease-out group-hover:-rotate-6">
                <GraduationCapIcon className="h-5 w-5" />
              </span>
              <span className="leading-none whitespace-nowrap max-sm:sr-only">
                <span className="block text-[0.65rem] font-medium uppercase tracking-[0.18em] text-ink-contrast/70">
                  AUIB
                </span>{" "}
                <span className="mt-1 block font-heading text-[0.95rem] font-bold">Academic Advisor</span>
              </span>
            </Link>
            <Suspense fallback={<SiteNavFallback />}>
              <SiteNav />
            </Suspense>
          </div>
        </header>
        <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:py-10">
          {children}
        </main>
        <footer className="mt-12 bg-footer text-white/80">
          <div className="mx-auto flex max-w-6xl flex-wrap items-start justify-between gap-6 px-4 py-8">
            <div className="max-w-2xl space-y-2">
              <p className="flex items-center gap-2 font-heading font-bold text-white">
                <GraduationCapIcon className="h-5 w-5" />
                AUIB Academic Advisor
              </p>
              <p className="text-xs leading-relaxed">
                A student-built planning aid for American University of Iraq, Baghdad students. The registrar&apos;s
                degree audit in SIS is authoritative; confirm plans with your academic advisor. Not an official AUIB
                service.
              </p>
            </div>
            <nav aria-label="Footer">
              <ul className="flex gap-5 text-sm">
                <li>
                  <Link href="/courses" className="hover:text-white hover:underline">
                    Course catalog
                  </Link>
                </li>
                <li>
                  <Link href="/privacy" className="hover:text-white hover:underline">
                    Privacy
                  </Link>
                </li>
              </ul>
            </nav>
          </div>
        </footer>
      </body>
    </html>
  );
}
