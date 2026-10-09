"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { credits } from "@/lib/format";
import {
  ArrowLeftIcon,
  BookOpenIcon,
  CalendarIcon,
  LayersIcon,
  ListChecksIcon,
  NoteIcon,
  RouteIcon,
} from "@/components/icons";
import { Alert, Badge, Skeleton, StatusBadge } from "@/components/ui";

const KIND_LABELS: Record<string, string> = {
  pre: "Prerequisite",
  co: "Corequisite (same term or earlier)",
  pre_or_co: "Prerequisite or corequisite",
};

export function CourseDetailSkeleton() {
  return (
    <div role="status" aria-label="Loading course" className="space-y-6">
      <Skeleton className="h-4 w-28" />
      <Skeleton className="h-40 rounded-card" />
      <div className="grid gap-4 lg:grid-cols-[1.5fr_1fr]">
        <Skeleton className="h-64 rounded-card" />
        <Skeleton className="h-64 rounded-card" />
      </div>
    </div>
  );
}

function Panel({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <section className="space-y-3 rounded-card border border-border bg-surface p-5 shadow-soft">
      <h2 className="flex items-center gap-2 font-heading text-base font-bold">
        <span className="text-primary">{icon}</span>
        {title}
      </h2>
      {children}
    </section>
  );
}

export function CourseDetail({ code }: { code: string }) {
  const result = useAsync(`course:${code}`, () => api.course(code));
  if (result.loading) return <CourseDetailSkeleton />;
  if (result.error || !result.data) return <Alert tone="error">{result.error ?? "Course not found."}</Alert>;
  const course = result.data;

  return (
    <div className="space-y-6">
      <Link
        href="/courses"
        className="inline-flex min-h-11 items-center gap-2 rounded-full text-sm font-medium text-primary hover:underline"
      >
        <ArrowLeftIcon className="h-4 w-4" />
        All courses
      </Link>

      <header className="relative overflow-hidden rounded-card border border-border bg-surface p-6 shadow-card sm:p-8 animate-fade-up">
        <span
          aria-hidden
          className="absolute -end-20 -top-20 h-56 w-56 rounded-full bg-[radial-gradient(closest-side,var(--brand-tint-strong),transparent)]"
        />
        <div className="relative space-y-4">
          <h1 className="font-heading text-3xl font-bold tracking-tight">
            <span className="block text-base font-semibold tracking-normal text-primary">{course.code}</span>{" "}
            {course.title}
          </h1>
          <p className="flex flex-wrap gap-2 text-sm">
            <Badge>
              <BookOpenIcon className="h-3.5 w-3.5" />
              {credits(course.units)}
            </Badge>
            {course.component && <Badge>{course.component}</Badge>}
            {course.offered_terms && (
              <Badge tone="brand">
                <CalendarIcon className="h-3.5 w-3.5" />
                Runs in {course.offered_terms.map((t) => t.charAt(0).toUpperCase() + t.slice(1)).join(" and ")} only
              </Badge>
            )}
            {course.notices.map((notice) => (
              <Badge key={notice}>{notice}</Badge>
            ))}
          </p>
        </div>
      </header>

      <div className="grid items-start gap-4 lg:grid-cols-[1.5fr_1fr]">
        <div className="space-y-4">
          <Panel icon={<NoteIcon className="h-5 w-5" />} title="Description">
            <p className="text-[0.95rem] leading-relaxed">{course.description || "No description in SIS."}</p>
          </Panel>

          <Panel icon={<ListChecksIcon className="h-5 w-5" />} title="Requirements to take it">
            {course.rules.length === 0 ? (
              <p className="text-sm">No prerequisites or corequisites are listed.</p>
            ) : (
              <ul className="space-y-3">
                {course.rules.map((rule) => (
                  <li key={rule.kind} className="space-y-2 rounded-xl bg-surface-sunken p-4 text-sm">
                    <p className="text-xs font-semibold uppercase tracking-wider text-text-muted">
                      {KIND_LABELS[rule.kind] ?? rule.kind}
                    </p>
                    <p className="font-heading text-lg font-bold">{rule.english}</p>
                    <p className="border-s-2 border-border-strong ps-3 text-xs text-text-muted">
                      From the SIS description: &ldquo;{rule.source_text}&rdquo;
                    </p>
                    <p>
                      {rule.reviewed ? (
                        <StatusBadge status="done" label="Checked by an admin" />
                      ) : (
                        <StatusBadge status="warning" label="Read automatically, not yet checked" />
                      )}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>

        <div className="space-y-4">
          {course.offerings && course.offerings.length > 0 && (
            <Panel icon={<CalendarIcon className="h-5 w-5" />} title="Sections">
              <div className="space-y-3">
                {course.offerings.map((term) => (
                  <div key={term.term.label} className="space-y-1.5">
                    <p className="text-xs font-semibold uppercase tracking-wider text-text-muted">{term.term.label}</p>
                    <ul className="space-y-1.5 text-sm">
                      {term.sections.map((section, index) => (
                        <li key={index} className="rounded-xl bg-surface-sunken px-3 py-2">
                          <span className="font-semibold">{section.section ? `Section ${section.section}` : "Section"}</span>
                          {[section.days, section.time].filter(Boolean).length > 0 && (
                            <span className="text-text-muted"> · {[section.days, section.time].filter(Boolean).join(" ")}</span>
                          )}
                          {(section.instructor || section.room) && (
                            <span className="block text-xs text-text-muted">
                              {[section.instructor, section.room].filter(Boolean).join(" · ")}
                            </span>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
              <p className="text-xs text-text-muted">From the published schedule. Register in SIS.</p>
            </Panel>
          )}
          <Panel icon={<RouteIcon className="h-5 w-5" />} title="Opens">
            {course.unlocks.length === 0 ? (
              <p className="text-sm">No course lists this one as a prerequisite.</p>
            ) : (
              <ul className="flex flex-wrap gap-1.5">
                {course.unlocks.map((next) => (
                  <li key={next.code}>
                    <Link
                      href={`/courses/${encodeURIComponent(next.code)}`}
                      className="inline-flex min-h-8 items-center rounded-full border border-border bg-surface px-3 text-xs transition hover:border-primary hover:text-primary"
                    >
                      <span className="font-semibold">{next.code}</span>&nbsp;{next.title}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
          <Panel icon={<LayersIcon className="h-5 w-5" />} title="Counts toward">
            {course.groups.length === 0 ? (
              <p className="text-sm">Free elective only.</p>
            ) : (
              <ul className="space-y-2 text-sm">
                {course.groups.map((group) => (
                  <li key={`${group.program_id}-${group.group_key}`} className="rounded-xl border border-border p-3">
                    <span className="block text-xs text-text-muted">{group.program_name}</span>
                    <span className="font-medium">{group.group_label}</span>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}
