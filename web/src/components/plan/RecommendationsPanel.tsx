"use client";

import Link from "next/link";
import type { Recommendations } from "@/lib/api";
import { units } from "@/lib/format";
import { Alert, Button, Card, Heading, Spinner, StatusBadge } from "@/components/ui";
import type { PlanActions } from "./TermPlan";

/** F2.2: ranked electives for each open requirement, each with the reasons it was suggested. */
export function RecommendationsPanel({
  id,
  data,
  error,
  included,
  actions,
}: {
  id: string;
  data: Recommendations | undefined;
  error: string | undefined;
  included: string[];
  actions: PlanActions;
}) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="space-y-3">
      <Heading>
        <span id={`${id}-title`}>Electives for you</span>
      </Heading>
      <p className="text-sm text-text-muted">
        Ranked by your interests and goals. Choose &ldquo;Plan this&rdquo; to put a course in your plan. Course
        reviews will refine these once students start sharing them.
      </p>
      {error && <Alert tone="error">{error}</Alert>}
      {!data && !error && <Spinner label="Finding electives" />}
      {data && data.groups.length === 0 && (
        <Card>
          <p className="text-sm">All elective requirements are already covered.</p>
        </Card>
      )}
      <div className="grid items-start gap-3 lg:grid-cols-2">
        {data?.groups.map((group) => (
          <Card key={group.group_key}>
            <Heading level={3}>
              {group.group_label}{" "}
              <span className="font-normal text-text-muted">({units(group.units_needed)} units needed)</span>
            </Heading>
            <ul className="mt-2 space-y-3">
              {group.suggestions.map((suggestion) => {
                const chosen = included.includes(suggestion.course.code);
                return (
                  <li key={suggestion.course.code} className="text-sm">
                    <div className="flex flex-wrap items-center gap-2">
                      <Link href={`/courses/${encodeURIComponent(suggestion.course.code)}`}
                        className="font-medium text-primary hover:underline"
                      >
                        {suggestion.course.code}
                      </Link>
                      <span>{suggestion.course.title}</span>
                      {chosen && <StatusBadge status="planned" label="In your plan" />}
                    </div>
                    <ul className="mt-1 list-disc ps-5 text-xs text-text-muted">
                      {suggestion.reasons.map((reason) => (
                        <li key={reason}>{reason}</li>
                      ))}
                    </ul>
                    {!chosen && (
                      <div className="mt-1 flex gap-3 print:hidden">
                        <Button variant="ghost" className="px-0 py-1 text-xs" onClick={() => actions.include(suggestion.course.code)}>
                          Plan this
                        </Button>
                        <Button variant="ghost" className="px-0 py-1 text-xs" onClick={() => actions.exclude(suggestion.course.code)}>
                          Not interested
                        </Button>
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          </Card>
        ))}
      </div>
    </section>
  );
}
