"use client";

import { useEffect, useState } from "react";
import { api, type ExpectedGrade, type GpaPlan, type PlanOut, type StudentIn } from "@/lib/api";
import { courseTitles } from "@/lib/advisor";
import { credits, units } from "@/lib/format";
import { TargetIcon, TrendingUpIcon } from "@/components/icons";
import { Alert, Button, Dialog, Disclosure, FIELD, Select, Skeleton, Switch } from "@/components/ui";

const GRADES = ["A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-", "F"] as const;

interface Row {
  code: string;
  title: string;
  units: number;
  next: boolean; // a course planned for next term, not one in progress
}

/** F7.2 and F7.3: "where will my CGPA land?" and "what do I need for my target?" */
export function GpaPlanner({ plan, student }: { plan: PlanOut; student: StudentIn }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button variant="secondary" size="sm" onClick={() => setOpen(true)}>
        <TargetIcon className="h-4 w-4" />
        Plan my grades
      </Button>
      {open && <PlannerDialog plan={plan} student={student} onClose={() => setOpen(false)} />}
    </>
  );
}

function PlannerDialog({ plan, student, onClose }: { plan: PlanOut; student: StudentIn; onClose: () => void }) {
  const titles = courseTitles(plan);
  const next = plan.terms[0];
  const current: Row[] = (student.attempts ?? [])
    .filter((attempt) => attempt.status === "in_progress")
    .map((attempt) => ({ code: attempt.code, title: titles.get(attempt.code) ?? "", units: attempt.units ?? 3, next: false }));
  const upcoming: Row[] = (next?.items ?? [])
    .filter((item) => item.code)
    .map((item) => ({ code: item.code!, title: item.title, units: item.units, next: true }));
  const [withNext, setWithNext] = useState(current.length === 0);
  const [grades, setGrades] = useState<Record<string, string>>({});
  const [target, setTarget] = useState("");
  const rows = withNext ? [...current, ...upcoming] : current;

  // Ask again shortly after the student stops changing things.
  const courses: ExpectedGrade[] = rows.map((row) => ({ code: row.code, grade: (grades[row.code] || null) as ExpectedGrade["grade"] }));
  const targetValue = Number(target);
  const validTarget = target.trim() !== "" && targetValue > 0 && targetValue <= 4 ? targetValue : null;
  const query = JSON.stringify({ courses, target: validTarget });
  const [result, setResult] = useState<{ query: string; data?: GpaPlan; error?: string } | null>(null);
  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(() => {
      api.gpaPlan(student, courses, validTarget).then(
        (data) => active && setResult({ query, data }),
        (error: unknown) => active && setResult({ query, error: error instanceof Error ? error.message : "Try again." }),
      );
    }, 250);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
    // `query` captures everything the request depends on.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);
  const data = result?.data;

  return (
    <Dialog open wide title="Plan my grades" onClose={onClose}>
      <div className="space-y-5">
        <p className="text-sm text-text-muted">
          Pick the grade you expect in each course to see where your CGPA would land. Leave a course on
          &ldquo;Not sure&rdquo; and set a target to see what it needs.
        </p>
        {upcoming.length > 0 && current.length > 0 && (
          <Switch
            id="gpa-with-next"
            checked={withNext}
            onChange={setWithNext}
            label={`Also include next term (${next!.term.label})`}
            description={`${credits(upcoming.reduce((sum, row) => sum + row.units, 0))} of planned courses`}
          />
        )}
        {rows.length === 0 ? (
          <Alert tone="info">There are no in-progress or planned courses to project.</Alert>
        ) : (
          <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border">
            {rows.map((row) => (
              <li key={row.code} className="flex flex-wrap items-center gap-x-4 gap-y-2 px-3 py-2.5 text-sm">
                <div className="min-w-0 flex-1 basis-48">
                  <span className="font-semibold">{row.code}</span> <span>{row.title}</span>
                  <span className="block text-xs text-text-muted">
                    {row.next ? `Planned for ${next!.term.label}` : "In progress"} · {credits(row.units)}
                  </span>
                </div>
                <label className="flex items-center gap-2 text-xs text-text-muted">
                  <span>
                    Grade<span className="sr-only"> expected in {row.code}</span>
                  </span>
                  <Select
                    value={grades[row.code] ?? ""}
                    onChange={(event) => setGrades({ ...grades, [row.code]: event.target.value })}
                    wrapperClassName="w-32"
                    className="min-h-10 py-1.5 text-sm"
                  >
                    <option value="">Not sure</option>
                    {GRADES.map((grade) => (
                      <option key={grade} value={grade}>
                        {grade}
                      </option>
                    ))}
                  </Select>
                </label>
              </li>
            ))}
          </ul>
        )}

        <div className="grid gap-4 md:grid-cols-2">
          <section aria-labelledby="projection-title" className="rounded-xl bg-surface-sunken p-4" aria-live="polite">
            <h3 id="projection-title" className="flex items-center gap-2 text-sm font-semibold">
              <TrendingUpIcon className="h-4 w-4 text-status-done" />
              Projected CGPA
            </h3>
            {!data && !result?.error && <Skeleton className="mt-3 h-10 w-24" />}
            {result?.error && <p className="mt-2 text-sm text-status-blocked">{result.error}</p>}
            {data && (
              <div className="mt-2 space-y-1">
                <p className="font-heading text-3xl font-bold tracking-tight text-primary">
                  {data.projected !== null ? data.projected.toFixed(2) : "—"}
                </p>
                <p className="text-sm text-text-muted">
                  {data.projected === null
                    ? "Choose a grade for at least one course."
                    : `Now ${data.current !== null ? data.current.toFixed(2) : "no CGPA yet"}${
                        data.courses_gpa !== null ? ` · these grades alone: ${data.courses_gpa.toFixed(2)}` : ""
                      }`}
                </p>
              </div>
            )}
          </section>

          <section aria-labelledby="target-title" className="space-y-2 rounded-xl bg-surface-sunken p-4" aria-live="polite">
            <h3 id="target-title" className="flex items-center gap-2 text-sm font-semibold">
              <TargetIcon className="h-4 w-4 text-primary" />
              Aim for a CGPA
            </h3>
            <label className="flex items-center gap-2 text-sm">
              <span>Target</span>
              <input
                type="number"
                inputMode="decimal"
                min={0.1}
                max={4}
                step={0.05}
                value={target}
                placeholder="3.00"
                onChange={(event) => setTarget(event.target.value)}
                className={`${FIELD} w-28`}
              />
            </label>
            {data?.target && <p className="text-sm">{targetSentence(data.target)}</p>}
          </section>
        </div>

        {data && (
          <Disclosure summary={<span className="text-xs font-normal text-text-muted">How this is calculated</span>}>
            <ul className="list-disc space-y-1 ps-4 text-xs text-text-muted">
              {data.assumptions.map((assumption) => (
                <li key={assumption}>{assumption}</li>
              ))}
              <li>An expected grade in a course you took before replaces the earlier grade, as a retake does.</li>
            </ul>
          </Disclosure>
        )}
      </div>
    </Dialog>
  );
}

function targetSentence(target: NonNullable<GpaPlan["target"]>): string {
  const goal = target.target.toFixed(2);
  switch (target.status) {
    case "met":
      return `You stay at or above ${goal} whatever grades the courses marked "Not sure" get.`;
    case "reachable":
      return (
        `To reach ${goal}, the ${units(target.open_credits)} credits marked "Not sure" need about ` +
        `${target.grade_needed} on average (${target.average_needed!.toFixed(2)} grade points).`
      );
    case "out_of_reach":
      return (
        `Even with an A in every course marked "Not sure", your CGPA would be ${target.best_possible!.toFixed(2)}. ` +
        "Include more courses, or aim a little lower for now."
      );
    default:
      return 'Mark at least one course "Not sure" to see what it needs.';
  }
}
