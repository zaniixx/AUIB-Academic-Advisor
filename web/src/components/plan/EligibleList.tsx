import Link from "next/link";
import type { PlanOut } from "@/lib/api";
import { units } from "@/lib/format";
import { CalendarCheckIcon } from "@/components/icons";
import { AlertIcon, Badge, Card } from "@/components/ui";
import { ShowMore } from "./ShowMore";

/** F1.3: courses that count toward an open requirement and whose prerequisites are met. */
export function EligibleList({ id, plan }: { id: string; plan: PlanOut }) {
  const groups = new Map<string, PlanOut["eligible_next_term"]>();
  for (const course of plan.eligible_next_term) {
    groups.set(course.group_label, [...(groups.get(course.group_label) ?? []), course]);
  }
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="space-y-4">
      <div className="flex items-start gap-3">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-tint text-primary">
          <CalendarCheckIcon />
        </span>
        <div className="space-y-1">
          <h2 id={`${id}-title`} className="font-heading text-xl font-bold tracking-tight">
            You can take next term ({plan.start_term.label})
          </h2>
          <p className="max-w-3xl text-sm text-text-muted">
            Prerequisites are checked against your completed and in-progress courses (assuming you pass them). Whether a
            course actually runs next term depends on the schedule SIS publishes.
          </p>
        </div>
      </div>
      {groups.size === 0 ? (
        <Card>
          <p className="text-sm">No courses toward your open requirements can be taken next term.</p>
        </Card>
      ) : (
        <div className="grid items-start gap-4 md:grid-cols-2">
          {[...groups.entries()].map(([label, courses]) => (
            <Card key={label} className="space-y-3">
              <h3 className="flex items-center justify-between gap-2 font-heading font-bold">
                {label}
                <span className="shrink-0 rounded-full bg-surface-sunken px-2 py-0.5 text-xs font-medium text-text-muted">
                  {courses.length}
                </span>
              </h3>
              <ShowMore items={courses} limit={5} noun={courses.length - 5 === 1 ? "course" : "courses"}>
                {(shown) => (
                  <ul className="divide-y divide-border text-sm">
                    {shown.map((entry) => (
                      <li key={entry.course.code} className="py-2 first:pt-0 last:pb-0">
                        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                          <Link
                            href={`/courses/${encodeURIComponent(entry.course.code)}`}
                            className="font-semibold text-primary hover:underline"
                          >
                            {entry.course.code}
                          </Link>
                          <span>{entry.course.title}</span>
                          <span className="text-xs text-text-muted">{units(entry.course.units)} cr</span>
                          {entry.unlocks >= 3 && <Badge tone="brand">Opens {entry.unlocks} courses</Badge>}
                        </div>
                        {entry.take_with.length > 0 && (
                          <p className="mt-0.5 text-xs text-text-muted">
                            Take together with {entry.take_with.join(", ")}
                          </p>
                        )}
                        {entry.advisories.map((note) => (
                          <p key={note} className="mt-0.5 flex gap-1 text-xs text-status-warning">
                            <AlertIcon className="mt-0.5 h-3 w-3" />
                            {note}
                          </p>
                        ))}
                      </li>
                    ))}
                  </ul>
                )}
              </ShowMore>
            </Card>
          ))}
        </div>
      )}
    </section>
  );
}
