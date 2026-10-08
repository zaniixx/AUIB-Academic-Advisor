"use client";

import Link from "next/link";
import { useDeferredValue, useState } from "react";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { units } from "@/lib/format";
import { Alert, Card, Spinner } from "@/components/ui";

export function CourseSearch() {
  const [query, setQuery] = useState("");
  const deferred = useDeferredValue(query.trim());
  const results = useAsync(`courses:${deferred}`, () => api.courses(deferred, 0, 50));

  return (
    <div className="space-y-4">
      <h1 className="font-heading text-2xl font-bold">Courses</h1>
      <Card>
        <label htmlFor="course-search" className="block font-semibold">
          Search by code or title
        </label>
        <input
          id="course-search"
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="e.g. CSC 231 or machine learning"
          className="mt-2 w-full rounded-button border border-border bg-surface px-3 py-2"
          maxLength={60}
        />
      </Card>
      {results.error && <Alert tone="error">{results.error}</Alert>}
      {results.loading && <Spinner label="Searching" />}
      {results.data && (
        <section aria-live="polite">
          <p className="mb-2 text-sm text-text-muted">
            {results.data.total} course{results.data.total === 1 ? "" : "s"}
            {results.data.total > results.data.courses.length && `, showing the first ${results.data.courses.length}`}
          </p>
          <ul className="divide-y divide-border rounded-card border border-border bg-surface">
            {results.data.courses.map((course) => (
              <li key={course.code}>
                <Link
                  href={`/courses/${encodeURIComponent(course.code)}`}
                  className="flex items-baseline justify-between gap-3 px-4 py-2 hover:bg-background"
                >
                  <span>
                    <span className="font-medium">{course.code}</span> {course.title}
                  </span>
                  <span className="shrink-0 text-sm text-text-muted">{units(course.units)} units</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
