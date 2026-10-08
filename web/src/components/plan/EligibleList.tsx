import Link from "next/link";
import type { PlanOut } from "@/lib/api";
import { units } from "@/lib/format";
import { Badge, Card, Heading } from "@/components/ui";

/** F1.3: courses that count toward an open requirement and whose prerequisites are met. */
export function EligibleList({ id, plan }: { id: string; plan: PlanOut }) {
  const groups = new Map<string, PlanOut["eligible_next_term"]>();
  for (const course of plan.eligible_next_term) {
    groups.set(course.group_label, [...(groups.get(course.group_label) ?? []), course]);
  }
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="space-y-3">
      <Heading>
        <span id={`${id}-title`}>You can take next term ({plan.start_term.label})</span>
      </Heading>
      <p className="text-sm text-text-muted">
        Prerequisites are checked against your completed and in-progress courses (assuming you pass them).
        Whether a course actually runs next term depends on the schedule SIS publishes.
      </p>
      {groups.size === 0 ? (
        <Card>
          <p className="text-sm">No courses toward your open requirements can be taken next term.</p>
        </Card>
      ) : (
        <div className="grid items-start gap-3 md:grid-cols-2">
          {[...groups.entries()].map(([label, courses]) => (
            <Card key={label}>
              <Heading level={3}>{label}</Heading>
              <ul className="mt-2 space-y-2 text-sm">
                {courses.map((entry) => (
                  <li key={entry.course.code}>
                    <div className="flex flex-wrap items-center gap-2">
                      <Link href={`/courses/${encodeURIComponent(entry.course.code)}`} className="font-medium text-primary hover:underline">
                        {entry.course.code}
                      </Link>
                      <span>{entry.course.title}</span>
                      <span className="text-text-muted">{units(entry.course.units)}u</span>
                      {entry.unlocks >= 3 && <Badge>Opens {entry.unlocks} courses</Badge>}
                    </div>
                    {entry.take_with.length > 0 && (
                      <p className="text-xs text-text-muted">Take together with {entry.take_with.join(", ")}</p>
                    )}
                    {entry.advisories.map((note) => (
                      <p key={note} className="text-xs text-status-warning">
                        {note}
                      </p>
                    ))}
                  </li>
                ))}
              </ul>
            </Card>
          ))}
        </div>
      )}
    </section>
  );
}
