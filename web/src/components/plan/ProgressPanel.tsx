import type { GroupProgress, PlanOut } from "@/lib/api";
import { credits, units } from "@/lib/format";
import { ChevronDownIcon, LayersIcon, ListChecksIcon } from "@/components/icons";
import { Card, CheckIcon, ProgressBar, StatusBadge } from "@/components/ui";

type Progress = PlanOut["progress"];
type Counted = GroupProgress["courses"][number];

/** F1.7: a course that counts toward another program too, or that another requirement also lists. */
function flagged(course: Counted): boolean {
  return course.also_counts_toward.length > 0 || course.also_listed.length > 0;
}

export function countedNote(course: Counted): string {
  const parts: string[] = [];
  if (course.also_counts_toward.length > 0) {
    parts.push(`${course.code} also counts toward ${course.also_counts_toward.join(", ")}.`);
  }
  if (course.also_listed.length > 0) {
    parts.push(`${course.also_listed.join(", ")} also list${course.also_listed.length === 1 ? "s" : ""} ${course.code}; it counts here only.`);
  }
  return parts.join(" ");
}

/** F1.2 and F4: progress per requirement group and the "what's left" checklist, for the major and any minor. */
export function ProgressPanel({ id, plan }: { id: string; plan: PlanOut }) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="space-y-4">
      <div className="space-y-1">
        <h2 id={`${id}-title`} className="font-heading text-xl font-bold tracking-tight">
          Requirements
        </h2>
        <p className="text-sm text-text-muted">
          Completed, in progress and planned credits for each requirement group, as counted by this app. Open a group
          to see the courses that count toward it.
        </p>
      </div>
      <Requirements progress={plan.progress} withPlan={plan.progress_with_plan} />
      {plan.minor && (
        <div className="space-y-4 pt-4">
          <div className="space-y-1">
            <h3 className="font-heading text-lg font-bold tracking-tight">Minor in {plan.minor.name}</h3>
            <p className="text-sm text-text-muted">
              A course can count toward your major and your minor at the same time.
            </p>
          </div>
          <Requirements progress={plan.minor.progress} withPlan={plan.minor.progress_with_plan} />
        </div>
      )}
    </section>
  );
}

function Requirements({ progress, withPlan }: { progress: Progress; withPlan: GroupProgress }) {
  const planned = new Map(flatten(withPlan).map((group) => [group.key, group.planned]));
  return (
    <div className="grid items-start gap-4 lg:grid-cols-[1.4fr_1fr]">
      <Card className="space-y-4">
        <Legend />
        <ul className="divide-y divide-border">
          {progress.root.children.map((group) => (
            <GroupRow key={group.key} group={group} planned={planned} />
          ))}
        </ul>
      </Card>
      <WhatsLeft progress={progress} />
    </div>
  );
}

function GroupRow({ group, planned }: { group: GroupProgress; planned: Map<string, number> }) {
  const done = group.remaining <= 0 && group.in_progress <= 0;
  const leaves = group.children.length ? group.children : [group];
  return (
    <li>
      <details className="group py-3">
        <summary className="cursor-pointer rounded-lg">
          <div className="flex items-center justify-between gap-2">
            <span className="flex min-w-0 items-center gap-2 font-medium">
              {done && (
                <span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-status-done text-surface">
                  <CheckIcon className="h-3 w-3" />
                </span>
              )}
              {group.label}
            </span>
            <span className="flex shrink-0 items-center gap-1 text-sm text-text-muted">
              {units(group.completed)} / {units(group.units_required)}
              <ChevronDownIcon className="h-4 w-4 transition-transform duration-200 group-open:rotate-180" />
            </span>
          </div>
          <div className="mt-2">
            <ProgressBar
              total={group.units_required}
              done={group.completed}
              inProgress={group.in_progress}
              planned={planned.get(group.key) ?? 0}
              label={`${group.label}: ${units(group.completed)} of ${units(group.units_required)} credits completed`}
            />
          </div>
          <p className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-text-muted">
            {units(group.completed)} of {units(group.units_required)} credits
            {group.in_progress > 0 && `, ${units(group.in_progress)} in progress`}
            {done && <StatusBadge status="done" label="Complete" />}
          </p>
        </summary>
        <ul className="disclosure-body mt-3 space-y-3 border-s-2 border-tint-strong ps-4">
          {leaves.map((leaf) => (
            <li key={leaf.key} className="text-sm">
              <p className="font-medium">
                {leaf.label}{" "}
                <span className="font-normal text-text-muted">
                  ({units(leaf.completed + leaf.in_progress)} of {units(leaf.units_required)})
                </span>
              </p>
              {leaf.courses.length > 0 ? (
                <ul className="mt-1.5 flex flex-wrap gap-1.5">
                  {leaf.courses.map((course) => (
                    <li
                      key={course.code}
                      className={`rounded-full border px-2.5 py-0.5 text-xs ${
                        course.state === "in_progress"
                          ? "border-status-in-progress/40 text-status-in-progress"
                          : "border-status-done/40 text-status-done"
                      }`}
                    >
                      {flagged(course) && <LayersIcon className="me-1 inline h-3 w-3 align-[-1px]" />}
                      {course.code} {course.state === "in_progress" ? "(now)" : ""}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-text-muted">Nothing counted yet</p>
              )}
              {leaf.courses.some(flagged) && (
                <ul className="mt-1.5 space-y-0.5 text-xs text-text-muted">
                  {leaf.courses.filter(flagged).map((course) => (
                    <li key={course.code} className="flex gap-1.5">
                      <LayersIcon className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                      <span>{countedNote(course)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      </details>
    </li>
  );
}

function WhatsLeft({ progress }: { progress: Progress }) {
  const left = progress.whats_left;
  return (
    <Card className="space-y-4">
      <h3 className="flex items-center gap-2 font-heading text-base font-bold">
        <ListChecksIcon className="h-5 w-5 text-primary" />
        What&apos;s left
      </h3>
      {left.length === 0 ? (
        <p className="flex items-center gap-2 rounded-xl bg-status-done/8 p-3 text-sm text-status-done">
          <CheckIcon /> Every requirement is covered by completed or in-progress courses.
        </p>
      ) : (
        <ul className="space-y-4 text-sm">
          {left.map((item) => (
            <li key={item.group_key}>
              <p className="flex items-baseline justify-between gap-2 font-medium">
                <span>{item.group_label}</span>
                <span className="shrink-0 rounded-full bg-tint px-2 py-0.5 text-xs font-semibold text-primary">
                  {credits(item.units_needed)}
                </span>
              </p>
              {item.required_courses.length > 0 ? (
                <ul className="mt-1.5 space-y-1">
                  {item.required_courses.map((course) => (
                    <li key={course.code} className="flex items-start gap-2">
                      <span aria-hidden className="mt-1 h-3.5 w-3.5 shrink-0 rounded border-2 border-border-strong" />
                      <span>
                        <span className="font-medium">{course.code}</span> {course.title}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-1 text-text-muted">
                  {item.open_pool
                    ? "Any course counts. Pick ones you enjoy."
                    : `Choose from ${item.options.length} listed courses. See "Explore courses".`}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function Legend() {
  return (
    <ul className="flex flex-wrap gap-4 text-xs text-text-muted" aria-label="Legend">
      <li className="flex items-center gap-1.5">
        <span className="h-2 w-4 rounded-full bg-status-done" aria-hidden /> Completed
      </li>
      <li className="flex items-center gap-1.5">
        <span className="h-2 w-4 rounded-full bg-status-in-progress" aria-hidden /> In progress
      </li>
      <li className="flex items-center gap-1.5">
        <span className="h-2 w-4 rounded-full bg-status-planned/45" aria-hidden /> Planned
      </li>
    </ul>
  );
}

function flatten(group: GroupProgress): GroupProgress[] {
  return [group, ...group.children.flatMap(flatten)];
}
