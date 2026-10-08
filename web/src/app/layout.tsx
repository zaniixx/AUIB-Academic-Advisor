import type { Metadata, Viewport } from "next";
import { Ubuntu } from "next/font/google";
import Link from "next/link";
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
    { media: "(prefers-color-scheme: dark)", color: "#0f1416" },
  ],
};

const NAV = [
  { href: "/plan", label: "My plan" },
  { href: "/courses", label: "Courses" },
  { href: "/privacy", label: "Privacy" },
];

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" dir="ltr" className={`h-full ${ubuntu.variable}`}>
      <body className="flex min-h-full flex-col bg-background text-text antialiased">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:start-2 focus:top-2 focus:z-50 focus:rounded-button focus:bg-surface focus:px-3 focus:py-2"
        >
          Skip to content
        </a>
        <header className="border-t-4 border-primary bg-ink text-ink-contrast shadow-[0_3px_6px_rgba(0,0,0,0.16)]">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2 px-4 py-3">
            <Link href="/" className="font-heading text-lg font-bold tracking-tight">
              AUIB <span className="font-medium">Academic Advisor</span>
            </Link>
            <nav aria-label="Main">
              <ul className="flex gap-1 text-sm font-medium">
                {NAV.map((item) => (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      className="inline-block border-b-2 border-transparent px-3 py-2 hover:border-primary"
                    >
                      {item.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </nav>
          </div>
        </header>
        <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">
          {children}
        </main>
        <footer className="bg-footer text-white">
          <div className="mx-auto max-w-6xl px-4 py-4 text-xs leading-relaxed">
            A student-built planning aid for American University of Iraq, Baghdad students. The registrar&apos;s
            degree audit in SIS is authoritative; confirm plans with your academic advisor. Not an official AUIB
            service.
          </div>
        </footer>
      </body>
    </html>
  );
}
