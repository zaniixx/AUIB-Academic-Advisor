"use client";

import Link from "next/link";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { units } from "@/lib/format";
import { Alert, Badge, Card, Heading, Spinner, StatusBadge } from "@/components/ui";

const KIND_LABELS: Record<string, string> = {
  pre: "Prerequisite",
  co: "Corequisite (same term or earlier)",
  pre_or_co: "Prerequisite or corequisite",
};

export function CourseDetail({ code }: { code: string }) {
  const result = useAsync(`course:${code}`, () => api.course(code));
  if (result.loading) return <Spinner label="Loading course" />;
  if (result.error || !result.data) return <Alert tone="error">{result.error ?? "Course not found."}</Alert>;
  const course = result.data;

  return (
    <div className="space-y-4">
      <Link href="/courses" className="text-sm text-primary hover:underline">
        ← All courses
      </Link>
      <div>
        <h1 className="font-heading text-2xl font-bold">
          {course.code} {course.title}
        </h1>
        <p className="mt-1 flex flex-wrap gap-2 text-sm text-text-muted">
          <Badge>{units(course.units)} units</Badge>
          {course.component && <Badge>{course.component}</Badge>}
          {course.offered_terms && (
            <Badge className="border border-accent text-text">
              Runs in {course.offered_terms.map((t) => t.charAt(0).toUpperCase() + t.slice(1)).join(" and ")} only
            </Badge>
          )}
          {course.notices.map((notice) => (
            <Badge key={notice}>{notice}</Badge>
          ))}
        </p>
      </div>

      <Card>
        <Heading level={3}>Description</Heading>
        <p className="mt-2 text-sm leading-relaxed">{course.description || "No description in SIS."}</p>
      </Card>

      <Card>
        <Heading level={3}>Requirements to take it</Heading>
        {course.rules.length === 0 ? (
          <p className="mt-2 text-sm">No prerequisites or corequisites are listed.</p>
        ) : (
          <ul className="mt-2 space-y-3">
            {course.rules.map((rule) => (
              <li key={rule.kind} className="text-sm">
                <p className="font-medium">{KIND_LABELS[rule.kind] ?? rule.kind}</p>
                <p className="mt-1">{rule.english}</p>
                <p className="mt-1 text-xs text-text-muted">
                  From the SIS description: &ldquo;{rule.source_text}&rdquo;
                </p>
                <p className="mt-1">
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
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <Heading level={3}>Opens</Heading>
          {course.unlocks.length === 0 ? (
            <p className="mt-2 text-sm">No course lists this one as a prerequisite.</p>
          ) : (
            <ul className="mt-2 flex flex-wrap gap-1">
              {course.unlocks.map((next) => (
                <li key={next.code}>
                  <Link
                    href={`/courses/${encodeURIComponent(next.code)}`}
                    className="inline-block rounded-full border border-border px-2 py-0.5 text-xs hover:bg-background"
                  >
                    {next.code} {next.title}
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card>
          <Heading level={3}>Counts toward</Heading>
          {course.groups.length === 0 ? (
            <p className="mt-2 text-sm">Free elective only.</p>
          ) : (
            <ul className="mt-2 list-disc ps-5 text-sm">
              {course.groups.map((group) => (
                <li key={`${group.program_id}-${group.group_key}`}>
                  {group.program_name}: {group.group_label}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
