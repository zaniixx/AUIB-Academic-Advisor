import type { ReactNode } from "react";
import type { Schemas } from "@/lib/api";
import { units } from "@/lib/format";
import { AwardIcon, TrendingUpIcon } from "@/components/icons";
import { Badge, CountUp, Disclosure } from "@/components/ui";

type Gpa = Schemas["GpaOut"];

/** CGPA, then last term's GPA, then the retakes that would raise the CGPA most (F7); ``planner`` opens
 * the grade projection (F7.2, F7.3). */
export function GpaCard({ gpa, planner = null }: { gpa: Gpa | null; planner?: ReactNode }) {
  if (!gpa) {
    return (
      <section aria-label="GPA" className="rounded-card border border-border bg-surface p-5 shadow-card sm:p-6">
        <span className="grid h-10 w-10 place-items-center rounded-xl bg-tint text-primary">
          <AwardIcon />
        </span>
        <p className="mt-3 text-sm text-text-muted">Cumulative GPA (CGPA)</p>
        <p className="font-heading text-2xl font-bold">No grades yet</p>
        <p className="mt-1 text-sm text-text-muted">Your CGPA appears here once you have graded courses.</p>
        {planner && <div className="mt-4">{planner}</div>}
      </section>
    );
  }
  const last = gpa.last_term;
  // The retake that raises the CGPA most is shown; the others wait behind a toggle.
  const [best, ...others] = gpa.retakes;
  return (
    <section aria-label="GPA" className="flex flex-col rounded-card border border-border bg-surface shadow-card">
      <div className="grid grid-cols-2 gap-4 p-5 sm:p-6">
        <div>
          <p className="text-sm text-text-muted">Cumulative GPA (CGPA)</p>
          <p className="font-heading text-4xl font-bold tracking-tight text-primary">
            <CountUp value={gpa.cumulative} decimals={2} />
          </p>
          <p className="text-xs text-text-muted">Over {units(gpa.units)} graded credits</p>
        </div>
        {last && (
          <div className="border-s border-border ps-4">
            <p className="text-sm text-text-muted">Last term GPA</p>
            <p className="font-heading text-2xl font-bold">
              <CountUp value={last.gpa} decimals={2} />{" "}
              <span className="block text-sm font-normal text-text-muted">{last.term.label}</span>
            </p>
          </div>
        )}
        {planner && <div className="col-span-2">{planner}</div>}
      </div>
      <div className="flex-1 space-y-3 rounded-b-card border-t border-border bg-surface-sunken/60 p-5 sm:px-6">
        <p className="flex items-center gap-2 text-sm font-semibold">
          <TrendingUpIcon className="h-4 w-4 text-status-done" />
          Retake to raise your CGPA
        </p>
        {best ? (
          <>
            <div className="rounded-xl border border-border bg-surface p-3 text-sm shadow-soft">
              <RetakeSuggestion retake={best} />
            </div>
            {others.length > 0 && (
              <Disclosure summary={<span className="text-sm text-primary">Other retake options ({others.length})</span>}>
                <ol className="space-y-2 pt-1">
                  {others.map((retake) => (
                    <li key={retake.course.code} className="rounded-xl border border-border bg-surface p-3 text-sm">
                      <RetakeSuggestion retake={retake} />
                    </li>
                  ))}
                </ol>
              </Disclosure>
            )}
          </>
        ) : (
          <p className="text-sm">No course is below a B, so a retake would not help much.</p>
        )}
        <Disclosure summary={<span className="text-xs font-normal text-text-muted">How this is calculated</span>}>
          <ul className="list-disc space-y-1 ps-4 text-xs text-text-muted">
            {gpa.assumptions.map((assumption) => (
              <li key={assumption}>{assumption}</li>
            ))}
          </ul>
        </Disclosure>
      </div>
    </section>
  );
}

function RetakeSuggestion({ retake }: { retake: Gpa["retakes"][number] }) {
  return (
    <>
      <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <span className="font-semibold">{retake.course.code}</span>
        <span>{retake.course.title}</span>
        <Badge>Grade {retake.grade}</Badge>
      </p>
      <p className="mt-1 text-text-muted">
        CGPA becomes <span className="font-semibold text-status-done">{retake.with_a.toFixed(2)}</span> with an A, or{" "}
        {retake.with_b.toFixed(2)} with a B.
      </p>
      {retake.in_plan && <p className="mt-1 text-xs font-medium text-status-done">Already in your plan</p>}
    </>
  );
}
