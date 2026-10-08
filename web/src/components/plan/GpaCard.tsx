import type { Schemas } from "@/lib/api";
import { units } from "@/lib/format";
import { Badge } from "@/components/ui";

type Gpa = Schemas["GpaOut"];

/** CGPA, then last term's GPA, then the retakes that would raise the CGPA most (F7). */
export function GpaCard({ gpa }: { gpa: Gpa | null }) {
  if (!gpa) {
    return (
      <section aria-label="GPA" className="rounded-card border border-border bg-surface p-4">
        <p className="text-sm text-text-muted">Cumulative GPA (CGPA)</p>
        <p className="mt-1 font-heading text-2xl font-bold">No grades yet</p>
        <p className="mt-1 text-sm text-text-muted">Your CGPA appears here once you have graded courses.</p>
      </section>
    );
  }
  const last = gpa.last_term;
  // The retake that raises the CGPA most is shown; the others wait behind a toggle.
  const [best, ...others] = gpa.retakes;
  return (
    <section aria-label="GPA" className="divide-y divide-border rounded-card border border-border bg-surface">
      <div className="p-4">
        <p className="text-sm text-text-muted">Cumulative GPA (CGPA)</p>
        <p className="mt-1 font-heading text-3xl font-bold text-primary">{gpa.cumulative.toFixed(2)}</p>
        <p className="text-xs text-text-muted">Over {units(gpa.units)} graded units</p>
      </div>
      {last && (
        <div className="p-4">
          <p className="text-sm text-text-muted">Last term GPA</p>
          <p className="mt-1 font-heading text-2xl font-bold">
            {last.gpa.toFixed(2)} <span className="text-sm font-normal text-text-muted">{last.term.label}</span>
          </p>
        </div>
      )}
      <div className="p-4">
        <p className="text-sm text-text-muted">Retake to raise your CGPA</p>
        {best ? (
          <>
            <div className="mt-2 text-sm">
              <RetakeSuggestion retake={best} />
            </div>
            {others.length > 0 && (
              <details className="mt-3 text-sm">
                <summary className="cursor-pointer font-medium text-primary">
                  Other retake options ({others.length})
                </summary>
                <ol className="mt-2 space-y-3">
                  {others.map((retake) => (
                    <li key={retake.course.code}>
                      <RetakeSuggestion retake={retake} />
                    </li>
                  ))}
                </ol>
              </details>
            )}
          </>
        ) : (
          <p className="mt-1 text-sm">No course is below a B, so a retake would not help much.</p>
        )}
        <details className="mt-3 text-xs text-text-muted">
          <summary className="cursor-pointer">How this is calculated</summary>
          <ul className="mt-1 list-disc space-y-1 ps-4">
            {gpa.assumptions.map((assumption) => (
              <li key={assumption}>{assumption}</li>
            ))}
          </ul>
        </details>
      </div>
    </section>
  );
}

function RetakeSuggestion({ retake }: { retake: Gpa["retakes"][number] }) {
  return (
    <>
      <p>
        <span className="font-medium">{retake.course.code}</span> {retake.course.title}{" "}
        <Badge>Grade {retake.grade}</Badge>
      </p>
      <p className="text-text-muted">
        CGPA becomes <span className="font-semibold text-text">{retake.with_a.toFixed(2)}</span> with an A, or{" "}
        {retake.with_b.toFixed(2)} with a B.
      </p>
      {retake.in_plan && <p className="text-xs text-status-done">Already in your plan</p>}
    </>
  );
}
