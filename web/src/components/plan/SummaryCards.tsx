import type { PlanOut, StudentIn } from "@/lib/api";
import { percent, units } from "@/lib/format";
import { CalendarCheckIcon, ChevronRightIcon, LayersIcon } from "@/components/icons";
import { CountUp, ProgressRing, StatusBadge } from "@/components/ui";
import { GpaCard } from "./GpaCard";
import { GpaPlanner } from "./GpaPlanner";

/** The plan at a glance: degree progress, expected graduation, the longest chain, and the GPA card. */
export function SummaryCards({ plan, student }: { plan: PlanOut; student: StudentIn }) {
  const { progress } = plan;
  const total = progress.root.units_required;
  const remaining = Math.max(0, total - progress.root.completed - progress.root.in_progress);
  // Whole percents; the in-progress share is the difference so the two always add up.
  const donePercent = percent(progress.root.completed, total);
  const nowPercent = percent(progress.root.completed + progress.root.in_progress, total) - donePercent;
  const graduation = plan.graduation_term;
  const onTime = plan.on_time_term;
  const late =
    graduation &&
    onTime &&
    (graduation.year > onTime.year ||
      (graduation.year === onTime.year && seasonRank(graduation.season) > seasonRank(onTime.season)));

  return (
    <div className="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
      <section aria-label="Summary" className="rounded-card border border-border bg-surface p-5 shadow-card sm:p-6">
        <div className="flex flex-wrap items-center gap-6">
          <ProgressRing
            done={total > 0 ? progress.root.completed / total : 0}
            inProgress={total > 0 ? progress.root.in_progress / total : 0}
            label={`Degree progress: ${donePercent}% completed, ${nowPercent}% in progress`}
          >
            <span aria-hidden>
              <span className="block font-heading text-4xl font-bold tracking-tight">
                <CountUp value={donePercent} />%
              </span>
              {nowPercent > 0 && (
                <span className="block text-xs font-semibold text-status-in-progress">+{nowPercent}% in progress</span>
              )}
            </span>
          </ProgressRing>
          <div className="min-w-0 flex-1 basis-56 space-y-4">
            <div>
              <p className="text-sm text-text-muted">Degree progress</p>
              <p className="font-heading text-lg font-bold">
                {units(progress.root.completed)} of {units(total)} credits completed
              </p>
            </div>
            <dl className="grid grid-cols-3 gap-2 text-center">
              <Stat label="Done" value={progress.root.completed} className="text-status-done" />
              <Stat label="Now" value={progress.root.in_progress} className="text-status-in-progress" />
              <Stat label="Left" value={remaining} />
            </dl>
          </div>
        </div>

        <div className="mt-6 grid gap-5 border-t border-border pt-5 sm:grid-cols-2">
          <div className="flex gap-3">
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-tint text-primary">
              <CalendarCheckIcon />
            </span>
            <div className="min-w-0">
              <p className="text-sm text-text-muted">Expected graduation</p>
              <p className="font-heading text-2xl font-bold tracking-tight">{graduation?.label ?? "All done"}</p>
              {onTime && graduation && (
                <p className="mt-1">
                  {late ? (
                    <StatusBadge status="warning" label={`Standard finish: ${onTime.label}`} />
                  ) : (
                    <StatusBadge status="done" label="On time" />
                  )}
                </p>
              )}
            </div>
          </div>
          <div className="flex gap-3">
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-surface-sunken text-text">
              <LayersIcon />
            </span>
            <div className="min-w-0">
              <p className="text-sm text-text-muted">Longest prerequisite chain</p>
              {plan.critical_chain.length > 0 ? (
                <>
                  <ol className="mt-1 flex flex-wrap items-center gap-1 text-sm font-medium">
                    {plan.critical_chain.map((course, index) => (
                      <li key={course.code} className="flex items-center gap-1">
                        {index > 0 && <ChevronRightIcon aria-hidden className="h-3.5 w-3.5 text-text-muted" />}
                        <span className="rounded-md bg-surface-sunken px-1.5 py-0.5">{course.code}</span>
                      </li>
                    ))}
                  </ol>
                  <p className="mt-1.5 text-xs text-text-muted">
                    {plan.critical_chain.length} terms at least. Delaying any of these delays graduation.
                  </p>
                </>
              ) : (
                <p className="mt-1 text-sm">No chains left</p>
              )}
            </div>
          </div>
        </div>
      </section>
      <GpaCard gpa={plan.gpa ?? null} planner={<GpaPlanner plan={plan} student={student} />} />
    </div>
  );
}

function Stat({ label, value, className = "" }: { label: string; value: number; className?: string }) {
  return (
    <div className="rounded-xl bg-surface-sunken px-2 py-2.5">
      <dt className="text-xs text-text-muted">{label}</dt>
      <dd className={`font-heading text-xl font-bold ${className}`}>{units(value)}</dd>
    </div>
  );
}

function seasonRank(season: string): number {
  return { Spring: 1, Summer: 2, Fall: 3 }[season] ?? 0;
}
