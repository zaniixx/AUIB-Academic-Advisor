"use client";

import { useId, useState, type FormEvent, type ReactNode } from "react";
import { api, type Comparison, type PlanOut, type ProgramChange, type ProgramSide, type ScenarioPlan } from "@/lib/api";
import { termRows, versusFirst } from "@/lib/compare";
import { credits, pluralize, units } from "@/lib/format";
import { useAsync, useScenarios } from "@/lib/hooks";
import {
  MAX_SCENARIOS,
  applyScenario,
  freshPreferences,
  makeScenario,
  removeScenario,
  saveProfile,
  saveScenario,
  toScenarioIn,
  toStudent,
  type Profile,
  type Scenario,
} from "@/lib/profile";
import { ArrowRightIcon, LayersIcon, SwapIcon, TrashIcon } from "@/components/icons";
import { Alert, Button, Card, FIELD, ProgressBar, Select, Skeleton, StatusBadge } from "@/components/ui";

/**
 * F6.2 and F6.3: the current plan beside up to three saved ones, and what a change of major or
 * minor would do. Saved plans stay in this browser; the courses are always the student's latest.
 */
export function ComparePanel({ id, profile, plan }: { id: string; profile: Profile; plan: PlanOut }) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="space-y-12">
      <SavedPlans titleId={`${id}-title`} profile={profile} />
      <ProgramChangePanel profile={profile} plan={plan} />
    </section>
  );
}

// ---------------------------------------------------------------------------
// F6.2: saved plans side by side
// ---------------------------------------------------------------------------

function SavedPlans({ titleId, profile }: { titleId: string; profile: Profile }) {
  const scenarios = useScenarios();
  const [name, setName] = useState("");
  const nameId = useId();
  const full = scenarios.length >= MAX_SCENARIOS;
  const requests = [toScenarioIn("Your current plan", profile), ...scenarios.map((each) => toScenarioIn(each.name, each))];
  const key = scenarios.length > 0 ? JSON.stringify({ attempts: profile.attempts, requests }) : null;
  const comparison = useAsync<Comparison>(key, () => api.compare(profile.attempts, requests), { keepPrevious: true });

  function save(event: FormEvent) {
    event.preventDefault();
    if (saveScenario(makeScenario(profile, name || `Plan ${scenarios.length + 1}`))) setName("");
  }

  function use(scenario: Scenario) {
    const message =
      `Make "${scenario.name}" your plan? It replaces your current plan's major, minor, settings and the courses ` +
      "you placed. Save your current plan first if you want to come back to it.";
    if (window.confirm(message)) applyScenario(profile, scenario);
  }

  return (
    <div className="space-y-5">
      <div className="space-y-1">
        <h2 id={titleId} className="font-heading text-xl font-bold tracking-tight">
          Compare plans
        </h2>
        <p className="max-w-3xl text-sm text-text-muted">
          Save your plan as it is now, then change it (summers, a lighter load, another minor) and compare. You can
          save {MAX_SCENARIOS} plans. They all use your latest courses, and they are kept only in this browser.
        </p>
      </div>

      <form onSubmit={save} className="flex flex-wrap items-end gap-3">
        <div className="min-w-0 flex-1 basis-64 space-y-1.5">
          <label htmlFor={nameId} className="block text-sm font-semibold">
            Name for this plan
          </label>
          <input
            id={nameId}
            value={name}
            maxLength={60}
            onChange={(event) => setName(event.target.value)}
            placeholder={`Plan ${scenarios.length + 1}`}
            disabled={full}
            className={FIELD}
          />
        </div>
        <Button type="submit" disabled={full}>
          <LayersIcon className="h-4 w-4" />
          Save this plan
        </Button>
      </form>
      {full && (
        <p className="text-sm text-text-muted">
          You have saved {MAX_SCENARIOS} plans. Delete one to save another.
        </p>
      )}

      {scenarios.length === 0 ? (
        <p className="rounded-card border border-dashed border-border-strong px-5 py-6 text-center text-sm text-text-muted">
          No saved plans yet. Save this one, change your plan, and its side-by-side comparison appears here.
        </p>
      ) : (
        <>
          {comparison.error && <Alert tone="error">{comparison.error}</Alert>}
          {!comparison.data && !comparison.error && <Skeleton className="h-72 rounded-card" />}
          {comparison.data && (
            <ComparisonTable
              data={comparison.data}
              scenarios={scenarios}
              loading={comparison.loading}
              onUse={use}
              onDelete={(scenario) => removeScenario(scenario.id)}
            />
          )}
        </>
      )}
    </div>
  );
}

function ComparisonTable({
  data,
  scenarios,
  loading,
  onUse,
  onDelete,
}: {
  data: Comparison;
  scenarios: Scenario[];
  loading: boolean;
  onUse: (scenario: Scenario) => void;
  onDelete: (scenario: Scenario) => void;
}) {
  const plans = data.scenarios.map((each) => each.plan);
  const rows = termRows(plans);
  // The first column is the current plan; the others are the saved scenarios, in order. While a
  // new comparison loads the columns may not match the saved plans, so they offer no actions.
  const saved = (index: number) => (index > 0 && !loading ? scenarios[index - 1] : undefined);
  const cell = "border-t border-border px-3 py-2.5 align-top";
  return (
    // On a phone the table scrolls sideways; the region can take focus so a keyboard can scroll it.
    <div
      role="region"
      aria-label="Plans side by side"
      tabIndex={0}
      aria-busy={loading}
      className={`overflow-x-auto rounded-card border border-border bg-surface shadow-soft transition-opacity ${loading ? "opacity-60" : ""}`}
    >
      <table className="w-full min-w-[40rem] text-sm">
        <caption className="sr-only">Your current plan and your saved plans, side by side</caption>
        <thead>
          <tr className="bg-surface-sunken/60">
            <th scope="col" className="w-36 px-3 py-3 text-start text-xs font-medium text-text-muted">
              <span className="sr-only">Plan</span>
            </th>
            {data.scenarios.map((scenario, index) => {
              const own = saved(index);
              return (
                <th key={index} scope="col" className="min-w-48 px-3 py-3 text-start align-top">
                  <span className="block font-heading text-base font-bold">{scenario.name}</span>
                  {scenario.plan && (
                    <span className="block text-xs font-normal text-text-muted">
                      {scenario.plan.program_name}
                      {scenario.plan.minor_name && ` · Minor in ${scenario.plan.minor_name}`}
                    </span>
                  )}
                  {own && (
                    <span className="mt-2 flex flex-wrap gap-1.5 font-normal">
                      <Button size="sm" variant="secondary" className="min-h-8 px-2.5 text-xs" onClick={() => onUse(own)}>
                        <SwapIcon className="h-3.5 w-3.5" />
                        Use this plan
                      </Button>
                      <Button
                        size="sm"
                        variant="quiet"
                        className="min-h-8 px-2.5 text-xs"
                        onClick={() => onDelete(own)}
                        aria-label={`Delete ${own.name}`}
                      >
                        <TrashIcon className="h-3.5 w-3.5" />
                        Delete
                      </Button>
                    </span>
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          <SummaryRow label="Graduation" plans={data.scenarios} cell={cell}>
            {(plan) => (
              <>
                <span className="block font-heading text-lg font-bold">{plan.graduation_term?.label ?? "All done"}</span>
                <FinishBadge plan={plan} />
              </>
            )}
          </SummaryRow>
          <SummaryRow label="Credits left" plans={data.scenarios} cell={cell}>
            {(plan) => `${units(plan.credits_left)} (${plan.percent_complete}% done)`}
          </SummaryRow>
          <SummaryRow label="Planned credits" plans={data.scenarios} cell={cell}>
            {(plan) => `${units(plan.planned_credits)} in ${pluralize(plan.terms.length, "term")}`}
          </SummaryRow>
          <SummaryRow label="To check" plans={data.scenarios} cell={cell}>
            {(plan) =>
              plan.warnings > 0 ? (
                <StatusBadge status="warning" label={pluralize(plan.warnings, "note")} />
              ) : (
                <span className="text-text-muted">Nothing</span>
              )
            }
          </SummaryRow>
          <tr>
            <th scope="colgroup" colSpan={data.scenarios.length + 1} className="border-t border-border bg-surface-sunken/40 px-3 py-2 text-start text-xs font-semibold uppercase tracking-[0.08em] text-text-muted">
              Credits per term
            </th>
          </tr>
          {rows.map((row) => (
            <tr key={row.label}>
              <th scope="row" className={`${cell} text-start font-medium`}>
                {row.label}
              </th>
              {row.cells.map((term, index) => (
                <td key={index} className={cell}>
                  {term ? (
                    <>
                      <span className="font-semibold">{credits(term.units)}</span>
                      <span className="mt-0.5 block text-xs text-text-muted">
                        {[
                          ...term.courses.map((course) => course.code),
                          ...(term.open_choices.length > 0 ? [`${pluralize(term.open_choices.length, "choice")} to make`] : []),
                        ].join(", ")}
                      </span>
                    </>
                  ) : (
                    <span className="text-text-muted">—</span>
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SummaryRow({
  label,
  plans,
  cell,
  children,
}: {
  label: string;
  plans: Comparison["scenarios"];
  cell: string;
  children: (plan: ScenarioPlan) => ReactNode;
}) {
  return (
    <tr>
      <th scope="row" className={`${cell} text-start font-medium`}>
        {label}
      </th>
      {plans.map((scenario, index) => (
        <td key={index} className={cell}>
          {scenario.plan ? (
            children(scenario.plan)
          ) : (
            <span className="text-status-blocked">{label === "Graduation" ? `Can't plan: ${scenario.error}` : "—"}</span>
          )}
        </td>
      ))}
    </tr>
  );
}

function FinishBadge({ plan }: { plan: ScenarioPlan }) {
  const difference = plan.semesters_vs_first;
  if (difference === null) return <span className="text-xs text-text-muted">{versusFirst(null)}</span>;
  const status = difference > 0 ? "warning" : difference < 0 ? "done" : "planned";
  return <StatusBadge status={status} label={versusFirst(difference)} />;
}

// ---------------------------------------------------------------------------
// F6.3: what a change of major or minor would do
// ---------------------------------------------------------------------------

function ProgramChangePanel({ profile, plan }: { profile: Profile; plan: PlanOut }) {
  const majors = useAsync("majors", () => api.programs("major"));
  const minors = useAsync("minors", () => api.programs("minor"));
  const currentMajor = plan.catalog.family_id;
  const currentMinor = profile.minorId ?? "";
  const [major, setMajor] = useState(currentMajor);
  const [minor, setMinor] = useState(currentMinor);
  const changed = major !== currentMajor || minor !== currentMinor;
  const student = toStudent(profile);
  const key = changed ? JSON.stringify({ student, major, minor }) : null;
  const result = useAsync<ProgramChange>(key, () => api.changeProgram(student, major, minor || null));
  const majorId = useId();
  const minorId = useId();
  const scenarios = useScenarios();

  const choices = {
    programId: major,
    minorId: minor || null,
    entryTerm: profile.entryTerm ?? null,
    programVersion: null,
    preferences: freshPreferences(profile.preferences),
  };

  function saveAsPlan(data: ProgramChange) {
    const name = data.target.minor_name ? `${data.target.name} + ${data.target.minor_name}` : data.target.name;
    saveScenario(makeScenario(choices, name));
  }

  function switchTo(data: ProgramChange) {
    const message =
      `Switch your plan to ${data.target.name}${data.target.minor_name ? ` with a minor in ${data.target.minor_name}` : ""}? ` +
      "The courses you placed and the terms you built are left behind; your courses and settings stay.";
    if (window.confirm(message)) saveProfile({ ...profile, ...choices });
  }

  return (
    <div className="space-y-5">
      <div className="space-y-1">
        <h2 className="font-heading text-xl font-bold tracking-tight">Try another major or minor</h2>
        <p className="max-w-3xl text-sm text-text-muted">
          See which of your courses would count, what would be left, and when you would graduate. Nothing changes
          until you switch.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <label htmlFor={majorId} className="block text-sm font-semibold">
            Major
          </label>
          <Select id={majorId} value={major} onChange={(event) => setMajor(event.target.value)}>
            {!majors.data && <option value={currentMajor}>{plan.catalog.program_name}</option>}
            {majors.data?.map((program) => (
              <option key={program.id} value={program.id}>
                {program.name}
                {program.id === currentMajor ? " (yours)" : ""}
              </option>
            ))}
          </Select>
        </div>
        <div className="space-y-1.5">
          <label htmlFor={minorId} className="block text-sm font-semibold">
            Minor
          </label>
          <Select id={minorId} value={minor} onChange={(event) => setMinor(event.target.value)}>
            <option value="">No minor{currentMinor === "" ? " (yours)" : ""}</option>
            {!minors.data && currentMinor && <option value={currentMinor}>{plan.minor?.name ?? currentMinor}</option>}
            {minors.data?.map((program) => (
              <option key={program.id} value={program.id}>
                {program.name}
                {program.id === currentMinor ? " (yours)" : ""}
              </option>
            ))}
          </Select>
        </div>
      </div>

      {!changed && (
        <p className="rounded-card border border-dashed border-border-strong px-5 py-6 text-center text-sm text-text-muted">
          Choose another major or minor to compare it with your own.
        </p>
      )}
      {changed && result.error && <Alert tone="error">{result.error}</Alert>}
      {changed && result.loading && <Skeleton className="h-80 rounded-card" />}
      {changed && result.data && (
        <ChangeResult
          key={key}
          data={result.data}
          canSave={scenarios.length < MAX_SCENARIOS}
          onSave={() => saveAsPlan(result.data!)}
          onSwitch={() => switchTo(result.data!)}
        />
      )}
    </div>
  );
}

function ChangeResult({
  data,
  canSave,
  onSave,
  onSwitch,
}: {
  data: ProgramChange;
  canSave: boolean;
  onSave: () => void;
  onSwitch: () => void;
}) {
  const [saved, setSaved] = useState(false);
  const graduation = data.target.graduation_term?.label ?? "your last planned term";
  const counting = data.courses.filter((course) => course.after || course.after_minor);
  const minorColumn = data.target.minor_name !== null;
  return (
    <div className="space-y-5">
      <Alert
        tone={data.terms_later > 0 ? "warning" : "success"}
        title={
          data.terms_later > 0
            ? `You would graduate in ${graduation}, ${pluralize(data.terms_later, "term")} later`
            : data.terms_later < 0
              ? `You would graduate in ${graduation}, ${pluralize(-data.terms_later, "term")} sooner`
              : `You would still graduate in ${graduation}`
        }
      >
        {counting.length} of your {pluralize(data.courses.length, "course")} would count.
        {data.lost_credits > 0
          ? ` ${credits(data.lost_credits)} would no longer count toward your degree.`
          : " None of your credits would be lost."}
      </Alert>

      <div className="grid gap-4 md:grid-cols-[1fr_auto_1fr] md:items-center">
        <ProgramCard side={data.current} label="Now" />
        <ArrowRightIcon aria-hidden className="mx-auto hidden h-6 w-6 text-text-muted md:block" />
        <ProgramCard side={data.target} label="After the change" />
      </div>

      {data.courses.length > 0 && (
        <div
          role="region"
          aria-label="Where your courses count"
          tabIndex={0}
          className="overflow-x-auto rounded-card border border-border bg-surface shadow-soft"
        >
          <table className="w-full min-w-[36rem] text-sm">
            <caption className="sr-only">Where each of your courses counts now and after the change</caption>
            <thead>
              <tr className="bg-surface-sunken/60 text-xs text-text-muted">
                <th scope="col" className="px-3 py-2.5 text-start font-medium">
                  Course
                </th>
                <th scope="col" className="px-3 py-2.5 text-start font-medium">
                  Counts toward now
                </th>
                <th scope="col" className="px-3 py-2.5 text-start font-medium">
                  In {data.target.name}
                </th>
                {minorColumn && (
                  <th scope="col" className="px-3 py-2.5 text-start font-medium">
                    In the {data.target.minor_name} minor
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {data.courses.map((course) => {
                const lost = course.now && !course.after && !course.after_minor;
                return (
                  <tr key={course.course.code} className="border-t border-border">
                    <th scope="row" className="px-3 py-2 text-start font-normal">
                      <span className="font-semibold">{course.course.code}</span>{" "}
                      <span className="text-text-muted">{course.course.title}</span>
                      {course.state === "in_progress" && <span className="text-xs text-status-in-progress"> (now)</span>}
                    </th>
                    <td className="px-3 py-2">{course.now ?? <span className="text-text-muted">Does not count</span>}</td>
                    <td className="px-3 py-2">
                      {course.after ?? (
                        <span className={lost ? "font-medium text-status-blocked" : "text-text-muted"}>
                          Does not count
                        </span>
                      )}
                    </td>
                    {minorColumn && (
                      <td className="px-3 py-2">{course.after_minor ?? <span className="text-text-muted">—</span>}</td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <ul className="space-y-1 text-xs text-text-muted">
        <li>{data.version_note}</li>
        {data.notes.map((note) => (
          <li key={note}>{note}</li>
        ))}
      </ul>

      <div className="flex flex-wrap gap-2">
        <Button
          variant="secondary"
          disabled={!canSave || saved}
          onClick={() => {
            onSave();
            setSaved(true);
          }}
          title={canSave ? undefined : `You have saved ${MAX_SCENARIOS} plans already`}
        >
          <LayersIcon className="h-4 w-4" />
          {saved ? "Saved to compare" : "Save as a plan to compare"}
        </Button>
        <Button onClick={onSwitch}>
          <SwapIcon className="h-4 w-4" />
          Switch my plan to {data.target.name}
        </Button>
      </div>
    </div>
  );
}

function ProgramCard({ side, label }: { side: ProgramSide; label: string }) {
  return (
    <Card className="space-y-3">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-text-muted">{label}</p>
        <h3 className="font-heading text-lg font-bold">{side.name}</h3>
        {side.minor_name && <p className="text-sm text-text-muted">Minor in {side.minor_name}</p>}
      </div>
      <div className="space-y-1.5">
        <ProgressBar
          total={side.total_credits}
          done={side.counted_credits}
          label={`${units(side.counted_credits)} of ${units(side.total_credits)} credits count`}
        />
        <p className="text-sm">
          <span className="font-semibold">{units(side.counted_credits)}</span> of {units(side.total_credits)} credits
          count · {units(side.credits_left)} left
        </p>
      </div>
      <p className="text-sm">
        Graduation: <span className="font-semibold">{side.graduation_term?.label ?? "All done"}</span>
      </p>
    </Card>
  );
}
