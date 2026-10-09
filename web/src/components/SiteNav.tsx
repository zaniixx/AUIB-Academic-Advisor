"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BookOpenIcon, RouteIcon, ShieldCheckIcon } from "./icons";

const NAV = [
  { href: "/plan", label: "My plan", Icon: RouteIcon },
  { href: "/courses", label: "Courses", Icon: BookOpenIcon },
  { href: "/privacy", label: "Privacy", Icon: ShieldCheckIcon },
];

/** The main navigation; the current section is marked for screen readers and with a soft pill. */
export function SiteNav() {
  return <NavList pathname={usePathname()} />;
}

/**
 * The same links with nothing marked current. The path is only known at request time, so the
 * layout shows this while it streams in (and prerendering is never blocked on it).
 */
export function SiteNavFallback() {
  return <NavList pathname={null} />;
}

function NavList({ pathname }: { pathname: string | null }) {
  return (
    <nav aria-label="Main">
      <ul className="flex items-center gap-0.5 sm:gap-1">
        {NAV.map(({ href, label, Icon }) => {
          const active = pathname !== null && (pathname === href || pathname.startsWith(`${href}/`));
          return (
            <li key={href}>
              <Link
                href={href}
                aria-current={active ? "page" : undefined}
                className={`relative inline-flex min-h-11 items-center gap-2 whitespace-nowrap rounded-full px-3 text-sm font-medium transition duration-200 ${
                  active ? "bg-white/14 text-white" : "text-ink-contrast/75 hover:bg-white/8 hover:text-white"
                }`}
              >
                <Icon className="hidden h-4 w-4 sm:block" />
                {label}
                {active && (
                  <span
                    aria-hidden
                    className="absolute inset-x-4 -bottom-[7px] h-[3px] rounded-full bg-primary animate-pop"
                  />
                )}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
