"use client";

import Link from "next/link";
import type { Recommendations } from "@/lib/api";
import { credits } from "@/lib/format";
import { CloseIcon, PlusIcon, SparklesIcon } from "@/components/icons";
import { Alert, Button, Card, CheckIcon, Skeleton, StatusBadge } from "@/components/ui";
import { ShowMore } from "./ShowMore";
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
    <section id={id} aria-labelledby={`${id}-title`} className="space-y-4">
      <div className="flex items-start gap-3">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-tint text-primary">
          <SparklesIcon />
        </span>
        <div className="space-y-1">
          <h2 id={`${id}-title`} className="font-heading text-xl font-bold tracking-tight">
            Electives for you
          </h2>
          <p className="max-w-3xl text-sm text-text-muted">
            Ranked by your interests and goals. Choose &ldquo;Plan this&rdquo; to put a course in your plan. Course
            reviews will refine these once students start sharing them.
          </p>
        </div>
      </div>
      {error && <Alert tone="error">{error}</Alert>}
      {!data && !error && (
        <div role="status" aria-label="Finding electives" className="grid gap-4 lg:grid-cols-2">
          <Skeleton className="h-56 rounded-card" />
          <Skeleton className="h-56 rounded-card" />
        </div>
      )}
      {data && data.groups.length === 0 && (
        <Card>
          <p className="flex items-center gap-2 text-sm text-status-done">
            <CheckIcon /> All elective requirements are already covered.
          </p>
        </Card>
      )}
      <div className="grid items-start gap-4 lg:grid-cols-2">
        {data?.groups.map((group) => (
          <Card key={group.group_key} className="space-y-3">
            <h3 className="flex flex-wrap items-baseline justify-between gap-2 font-heading font-bold">
              {group.group_label}
              <span className="rounded-full bg-tint px-2 py-0.5 text-xs font-semibold text-primary">
                {credits(group.units_needed)} needed
              </span>
            </h3>
            <ShowMore
              items={group.suggestions}
              limit={3}
              noun={group.suggestions.length - 3 === 1 ? "suggestion" : "suggestions"}
            >
              {(shown) => (
                <ul className="space-y-2">
                  {shown.map((suggestion) => {
                    const chosen = included.includes(suggestion.course.code);
                    return (
                      <li
                        key={suggestion.course.code}
                        className={`rounded-xl border p-3 text-sm transition ${
                          chosen ? "border-status-planned/40 bg-status-planned/5" : "border-border"
                        }`}
                      >
                        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                          <Link
                            href={`/courses/${encodeURIComponent(suggestion.course.code)}`}
                            className="font-semibold text-primary hover:underline"
                          >
                            {suggestion.course.code}
                          </Link>
                          <span>{suggestion.course.title}</span>
                          {chosen && <StatusBadge status="planned" label="In your plan" />}
                        </div>
                        <ul className="mt-2 flex flex-wrap gap-1.5">
                          {suggestion.reasons.map((reason) => (
                            <li
                              key={reason}
                              className="rounded-full bg-surface-sunken px-2.5 py-0.5 text-xs text-text-muted"
                            >
                              {reason}
                            </li>
                          ))}
                        </ul>
                        {!chosen && (
                          <div className="mt-2.5 flex flex-wrap gap-2 print:hidden">
                            <Button
                              variant="secondary"
                              size="sm"
                              onClick={() => actions.include(suggestion.course.code)}
                            >
                              <PlusIcon className="h-4 w-4" />
                              Plan this
                            </Button>
                            <Button variant="quiet" size="sm" onClick={() => actions.exclude(suggestion.course.code)}>
                              <CloseIcon className="h-4 w-4" />
                              Not interested
                            </Button>
                          </div>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
            </ShowMore>
          </Card>
        ))}
      </div>
    </section>
  );
}
