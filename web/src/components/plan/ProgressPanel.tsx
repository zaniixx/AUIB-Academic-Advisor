import type { GroupProgress, PlanOut } from "@/lib/api";
import { units } from "@/lib/format";
import { Card, CheckIcon, Heading, ProgressBar, StatusBadge } from "@/components/ui";

type Progress = PlanOut["progress"];

/** F1.2 and F4: progress per requirement group and the "what's left" checklist, for the major and any minor. */
export function ProgressPanel({ id, plan }: { id: string; plan: PlanOut }) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="space-y-3">
      <Heading>
        <span id={`${id}-title`}>Requirements</span>
      </Heading>
      <Requirements progress={plan.progress} withPlan={plan.progress_with_plan} />
      {plan.minor && (
        <>
          <Heading level={3} className="pt-2">
            Minor in {plan.minor.name}
          </Heading>
          <p className="text-sm text-text-muted">
            A course can count toward your major and your minor at the same time.
          </p>
          <Requirements progress={plan.minor.progress} withPlan={plan.minor.progress_with_plan} />
        </>
      )}
    </section>
  );
}

function Requirements({ progress, withPlan }: { progress: Progress; withPlan: GroupProgress }) {
  const planned = new Map(flatten(withPlan).map((group) => [group.key, group.planned]));
  return (
    <div className="grid items-start gap-3 lg:grid-cols-2">
      <Card className="space-y-4">
        <p className="text-sm text-text-muted">
          Completed, in progress and planned units for each requirement group, as counted by this app.
        </p>
        <ul className="space-y-4">
          {progress.root.children.map((group) => (
            <GroupRow key={group.key} group={group} planned={planned} />
          ))}
        </ul>
        <Legend />
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
      <details>
        <summary className="cursor-pointer list-none">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="font-medium">{group.label}</span>
            <span className="text-sm text-text-muted">
              {units(group.completed)} of {units(group.units_required)} units
              {group.in_progress > 0 && `, ${units(group.in_progress)} in progress`}
            </span>
          </div>
          <div className="mt-1">
            <ProgressBar
              total={group.units_required}
              done={group.completed}
              inProgress={group.in_progress}
              planned={planned.get(group.key) ?? 0}
              label={`${group.label}: ${units(group.completed)} of ${units(group.units_required)} units completed`}
            />
          </div>
          {done && (
            <span className="mt-1 inline-block">
              <StatusBadge status="done" label="Complete" />
            </span>
          )}
        </summary>
        <ul className="mt-2 space-y-2 border-s-2 border-border ps-3">
          {leaves.map((leaf) => (
            <li key={leaf.key} className="text-sm">
              <p className="font-medium">
                {leaf.label}{" "}
                <span className="font-normal text-text-muted">
                  ({units(leaf.completed + leaf.in_progress)} of {units(leaf.units_required)})
                </span>
              </p>
              {leaf.courses.length > 0 ? (
                <ul className="mt-1 flex flex-wrap gap-1">
                  {leaf.courses.map((course) => (
                    <li key={course.code} className="rounded-full border border-border px-2 py-0.5 text-xs">
                      {course.code} {course.state === "in_progress" ? "(now)" : ""}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-text-muted">Nothing counted yet</p>
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
    <Card className="space-y-3">
      <Heading level={3}>What&apos;s left</Heading>
      {left.length === 0 ? (
        <p className="flex items-center gap-2 text-sm text-status-done">
          <CheckIcon /> Every requirement is covered by completed or in-progress courses.
        </p>
      ) : (
        <ul className="space-y-3 text-sm">
          {left.map((item) => (
            <li key={item.group_key}>
              <p className="font-medium">
                {item.group_label}: {units(item.units_needed)} units
              </p>
              {item.required_courses.length > 0 ? (
                <ul className="mt-1 space-y-0.5">
                  {item.required_courses.map((course) => (
                    <li key={course.code} className="flex gap-2">
                      <span aria-hidden>☐</span>
                      <span>
                        <span className="font-medium">{course.code}</span> {course.title}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-text-muted">
                  {item.open_pool
                    ? "Any course counts. Pick ones you enjoy."
                    : `Choose from ${item.options.length} listed courses. See "Electives for you".`}
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
    <ul className="flex flex-wrap gap-3 text-xs text-text-muted" aria-label="Legend">
      <li className="flex items-center gap-1">
        <span className="h-2 w-4 rounded-sm bg-status-done" aria-hidden /> Completed
      </li>
      <li className="flex items-center gap-1">
        <span className="h-2 w-4 rounded-sm bg-status-in-progress" aria-hidden /> In progress
      </li>
      <li className="flex items-center gap-1">
        <span className="h-2 w-4 rounded-sm bg-status-planned opacity-50" aria-hidden /> Planned
      </li>
    </ul>
  );
}

function flatten(group: GroupProgress): GroupProgress[] {
  return [group, ...group.children.flatMap(flatten)];
}
