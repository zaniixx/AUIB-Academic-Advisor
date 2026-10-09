"use client";

import Link from "next/link";
import { useDeferredValue, useState, type CSSProperties } from "react";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { credits } from "@/lib/format";
import { ArrowRightIcon, SearchIcon } from "@/components/icons";
import { Alert, FIELD, PageHeader, Skeleton } from "@/components/ui";

export function CourseSearch() {
  const [query, setQuery] = useState("");
  const deferred = useDeferredValue(query.trim());
  // Earlier results stay on screen while a new search runs, so the list does not flash.
  const results = useAsync(`courses:${deferred}`, () => api.courses(deferred, 0, 50), { keepPrevious: true });

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Course catalog"
        title="Courses"
        description="Every AUIB course in the catalog, with its prerequisites, what it opens, and the requirements it counts toward."
      />
      <div className="space-y-2">
        <label htmlFor="course-search" className="block font-semibold">
          Search by code or title
        </label>
        <div className="relative">
          <SearchIcon className="pointer-events-none absolute start-4 top-1/2 h-5 w-5 -translate-y-1/2 text-text-muted" />
          <input
            id="course-search"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="e.g. CSC 231 or machine learning"
            className={`${FIELD} min-h-13 rounded-full ps-12 text-base shadow-card`}
            maxLength={60}
          />
        </div>
      </div>
      {results.error && <Alert tone="error">{results.error}</Alert>}
      {!results.data && !results.error && (
        <div role="status" aria-label="Searching" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 9 }, (_, index) => (
            <Skeleton key={index} className="h-24 rounded-card" />
          ))}
        </div>
      )}
      {results.data && (
        <section aria-live="polite" aria-busy={results.loading} className="space-y-3">
          <p className="text-sm text-text-muted">
            {results.data.total} course{results.data.total === 1 ? "" : "s"}
            {results.data.total > results.data.courses.length && `, showing the first ${results.data.courses.length}`}
          </p>
          {results.data.courses.length === 0 ? (
            <p className="rounded-card border border-dashed border-border-strong p-8 text-center text-text-muted">
              No course matches &ldquo;{deferred}&rdquo;. Try a course code like CSC 231 or one word from the title.
            </p>
          ) : (
            <ul
              key={deferred}
              className={`stagger grid gap-3 transition-opacity sm:grid-cols-2 lg:grid-cols-3 ${results.loading ? "opacity-60" : ""}`}
            >
              {results.data.courses.map((course, index) => (
                <li key={course.code} style={{ "--i": Math.min(index, 12) } as CSSProperties}>
                  <Link
                    href={`/courses/${encodeURIComponent(course.code)}`}
                    className="group flex h-full items-center justify-between gap-3 rounded-card border border-border bg-surface px-4 py-3 shadow-soft transition duration-300 ease-out hover:-translate-y-0.5 hover:border-tint-strong hover:shadow-card"
                  >
                    <span className="min-w-0">
                      <span className="flex items-center gap-2">
                        <span className="font-heading font-bold text-primary">{course.code}</span>
                        <span className="rounded-full bg-surface-sunken px-2 py-0.5 text-xs text-text-muted">
                          {credits(course.units)}
                        </span>
                      </span>
                      <span className="mt-0.5 block text-sm">{course.title}</span>
                    </span>
                    <ArrowRightIcon className="h-4 w-4 shrink-0 text-text-muted transition-transform duration-300 group-hover:translate-x-1 group-hover:text-primary" />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}
