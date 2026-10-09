"use client";

import { useState, type ReactNode } from "react";
import { ChevronDownIcon } from "@/components/icons";

/** Shows the first ``limit`` items; a button reveals the rest, so long lists stay scannable. */
export function ShowMore<T>({
  items,
  limit,
  noun,
  children,
}: {
  items: T[];
  limit: number;
  noun: string;
  children: (shown: T[]) => ReactNode;
}) {
  const [all, setAll] = useState(false);
  const hidden = items.length - limit;
  return (
    <>
      {children(all || hidden <= 0 ? items : items.slice(0, limit))}
      {hidden > 0 && (
        <button
          type="button"
          onClick={() => setAll(!all)}
          aria-expanded={all}
          className="mt-2 inline-flex min-h-10 cursor-pointer items-center gap-1.5 rounded-full px-3 text-sm font-medium text-primary transition hover:bg-tint"
        >
          {all ? "Show fewer" : `Show ${hidden} more ${noun}`}
          <ChevronDownIcon className={`h-4 w-4 transition-transform duration-200 ${all ? "rotate-180" : ""}`} />
        </button>
      )}
    </>
  );
}
