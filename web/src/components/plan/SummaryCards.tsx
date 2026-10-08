import type { PlanOut } from "@/lib/api";
import { percent, units } from "@/lib/format";
import { ProgressBar, StatusBadge } from "@/components/ui";
import { GpaCard } from "./GpaCard";

export function SummaryCards({ plan }: { plan: PlanOut }) {
  const { progress } = plan;
  const total = progress.root.units_required;
  const remaining = Math.max(0, total - progress.root.completed - progress.root.in_progress);
  // Whole percents; the in-progress share is the difference so the two always add up.
  const donePercent = percent(progress.root.completed, total);
  const nowPercent = percent(progress.root.completed + progress.root.in_progress, total) - donePercent;
  const graduation = plan.graduation_term;
  const onTime = plan.on_time_term;
  const late = graduation && onTime && (graduation.year > onTime.year || (graduation.year === onTime.year && seasonRank(graduation.season) > seasonRank(onTime.season)));

  return (
    <div className="grid gap-3 lg:grid-cols-[2fr_1fr]">
    <section aria-label="Summary" className="grid content-start gap-3 sm:grid-cols-2">
      <div className="rounded-card border border-border bg-surface p-4">
        <p className="text-sm text-text-muted">Expected graduation</p>
        <p className="mt-1 font-heading text-2xl font-bold">{graduation?.label ?? "All done"}</p>
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
      <div className="rounded-card border border-border bg-surface p-4">
        <p className="text-sm text-text-muted">Degree progress</p>
        <p className="mt-1 font-heading text-2xl font-bold">
          {donePercent}%
          {nowPercent > 0 && (
            <span className="ms-2 text-sm font-semibold text-status-in-progress">+{nowPercent}% in progress</span>
          )}
        </p>
        <div className="mt-2">
          <ProgressBar
            total={total}
            done={progress.root.completed}
            inProgress={progress.root.in_progress}
            label={`${units(progress.root.completed)} of ${units(total)} units completed, ${units(progress.root.in_progress)} in progress`}
          />
        </div>
      </div>
      <div className="rounded-card border border-border bg-surface p-4">
        <p className="text-sm text-text-muted">Units</p>
        <dl className="mt-1 grid grid-cols-3 gap-1 text-center">
          <div>
            <dt className="text-xs text-text-muted">Done</dt>
            <dd className="font-heading text-xl font-bold text-status-done">{units(progress.root.completed)}</dd>
          </div>
          <div>
            <dt className="text-xs text-text-muted">Now</dt>
            <dd className="font-heading text-xl font-bold text-status-in-progress">{units(progress.root.in_progress)}</dd>
          </div>
          <div>
            <dt className="text-xs text-text-muted">Left</dt>
            <dd className="font-heading text-xl font-bold">{units(remaining)}</dd>
          </div>
        </dl>
      </div>
      <div className="rounded-card border border-border bg-surface p-4">
        <p className="text-sm text-text-muted">Longest prerequisite chain</p>
        {plan.critical_chain.length > 0 ? (
          <>
            <p className="mt-1 text-sm font-medium">{plan.critical_chain.map((course) => course.code).join(" → ")}</p>
            <p className="mt-1 text-xs text-text-muted">
              {plan.critical_chain.length} terms at least. Delaying any of these delays graduation.
            </p>
          </>
        ) : (
          <p className="mt-1 text-sm">No chains left</p>
        )}
      </div>
    </section>
    <GpaCard gpa={plan.gpa ?? null} />
    </div>
  );
}

function seasonRank(season: string): number {
  return { Spring: 1, Summer: 2, Fall: 3 }[season] ?? 0;
}
