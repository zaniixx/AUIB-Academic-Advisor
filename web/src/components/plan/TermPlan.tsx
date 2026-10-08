"use client";

import Link from "next/link";
import { useId } from "react";
import type { AttemptIn, ChangeAction, CourseRef, GroupProgress, PlanItem, PlanOut } from "@/lib/api";
import { units } from "@/lib/format";
import { Badge, Button, Heading, LockIcon, StatusBadge } from "@/components/ui";

export interface PlanActions {
  lock: (code: string, term: string) => void;
  unlock: (code: string) => void;
  include: (code: string) => void;
  exclude: (code: string) => void;
  /** Put ``next`` in ``term`` instead of ``previous`` (null when filling an open-choice slot). */
  replace: (previous: string | null, next: string, term: string) => void;
  whatIf: (code: string, action: ChangeAction) => void;
}

/** F1.4 term-by-term plan; F1.5 what-if, F1.6 locks and "replace with" start from here. */
export function TermPlan({
  id,
  plan,
  inProgress,
  locks,
  actions,
}: {
  id: string;
  plan: PlanOut;
  inProgress: AttemptIn[];
  locks: { code: string; term: string }[];
  actions: PlanActions;
}) {
  const locked = new Set(locks.map((lock) => lock.code));
  const titles = courseTitles(plan.progress.root);
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="space-y-3">
      <Heading>
        <span id={`${id}-title`}>Term by term</span>
      </Heading>
      <p className="text-sm text-text-muted">
        Where a requirement lets you choose, use &ldquo;Replace with&rdquo; to swap a course for another that
        fits the same term: its prerequisites are done in earlier terms and its corequisites are in the same term.
      </p>
      {plan.unscheduled.length > 0 && (
        <p className="text-sm text-status-blocked">
          {plan.unscheduled.length} item(s) could not be scheduled. See &ldquo;Things to check&rdquo;.
        </p>
      )}
      <ol className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {inProgress.length > 0 && (
          <li className="min-w-0 self-start rounded-card border-2 border-status-in-progress bg-surface p-3">
            <div className="flex items-baseline justify-between">
              <h3 className="font-semibold">This term</h3>
              <span className="text-sm text-text-muted">
                {units(inProgress.reduce((sum, a) => sum + (a.units ?? 3), 0))} units
              </span>
            </div>
            <ul className="mt-2 space-y-2">
              {inProgress.map((attempt) => (
                <li key={attempt.code} className="rounded-card border border-border p-2 text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusBadge status="in-progress" />
                    <span className="font-medium">{attempt.code}</span>
                    {titles.get(attempt.code) && <span>{titles.get(attempt.code)}</span>}
                  </div>
                  <Button
                    variant="ghost"
                    className="mt-1 px-0 py-1 text-xs print:hidden"
                    onClick={() => actions.whatIf(attempt.code, "drop")}
                  >
                    What if I don&apos;t pass?
                  </Button>
                </li>
              ))}
            </ul>
          </li>
        )}
        {plan.terms.map((term) => (
          <li
            key={term.term.label}
            className={`min-w-0 self-start rounded-card border bg-surface p-3 ${
              term.term.season === "Summer" ? "border-dashed border-accent" : "border-border"
            }`}
          >
            <div className="flex items-baseline justify-between">
              <h3 className="font-semibold">{term.term.label}</h3>
              <span className="text-sm text-text-muted">{units(term.units)} units</span>
            </div>
            <ul className="mt-2 space-y-2">
              {term.items.map((item) =>
                item.kind === "slot" ? (
                  <SlotItem key={item.key} item={item} term={term.term.label} actions={actions} />
                ) : (
                  <CourseItem
                    key={item.key}
                    item={item}
                    term={term.term.label}
                    locked={locked.has(item.code ?? "")}
                    actions={actions}
                  />
                ),
              )}
            </ul>
          </li>
        ))}
      </ol>
    </section>
  );
}

function courseTitles(group: GroupProgress, found = new Map<string, string>()): Map<string, string> {
  for (const course of group.courses) found.set(course.code, course.title);
  for (const child of group.children) courseTitles(child, found);
  return found;
}

function CourseItem({
  item,
  term,
  locked,
  actions,
}: {
  item: PlanItem;
  term: string;
  locked: boolean;
  actions: PlanActions;
}) {
  const code = item.code ?? "";
  return (
    <li className="rounded-card border border-border p-2 text-sm">
      <div className="flex items-start justify-between gap-2">
        <div>
          <Link href={`/courses/${encodeURIComponent(code)}`} className="font-medium text-primary hover:underline">
            {code}
          </Link>{" "}
          <span>{item.title}</span>
        </div>
        <span className="shrink-0 text-text-muted">{units(item.units)}u</span>
      </div>
      <div className="mt-1 flex flex-wrap gap-1">
        <StatusBadge status="planned" />
        {locked && (
          <Badge>
            <LockIcon />
            <span className="ms-1">Kept here</span>
          </Badge>
        )}
        {item.unlocks >= 3 && <Badge>Gateway: {item.unlocks} later courses need it</Badge>}
        {item.advisories.length > 0 && <StatusBadge status="warning" label="Check requirement" />}
      </div>
      {item.reason && <p className="mt-1 text-xs text-text-muted">{item.reason}</p>}
      {item.advisories.map((note) => (
        <p key={note} className="mt-1 text-xs text-status-warning">
          {note}
        </p>
      ))}
      {item.alternatives.length > 0 && (
        <ChooseCourse
          label="Replace with"
          placeholder="Another course…"
          options={item.alternatives}
          suggested={[]}
          onPick={(next) => actions.replace(code, next, term)}
          describedBy={`${item.group_label ?? "this requirement"} in ${term}`}
        />
      )}
      <div className="mt-1 flex flex-wrap gap-x-3 print:hidden">
        {locked ? (
          <Button variant="ghost" className="px-0 py-1 text-xs" onClick={() => actions.unlock(code)}>
            Let the planner move it
          </Button>
        ) : (
          <Button variant="ghost" className="px-0 py-1 text-xs" onClick={() => actions.lock(code, term)}>
            Keep in {term}
          </Button>
        )}
        <Button variant="ghost" className="px-0 py-1 text-xs" onClick={() => actions.whatIf(code, "delay")}>
          What if I delay it?
        </Button>
      </div>
    </li>
  );
}

function SlotItem({ item, term, actions }: { item: PlanItem; term: string; actions: PlanActions }) {
  const available = new Set(item.alternatives.map((course) => course.code));
  const suggested = item.suggestions.filter((course) => available.has(course.code));
  return (
    <li className="rounded-card border border-dashed border-border p-2 text-sm">
      <div className="flex items-start justify-between gap-2">
        <span className="font-medium">{item.title}</span>
        <span className="shrink-0 text-text-muted">{units(item.units)}u</span>
      </div>
      {item.suggestions.length > 0 && (
        <p className="mt-1 text-xs text-text-muted">
          Suggested for you: {item.suggestions.map((course) => `${course.code} ${course.title}`).join(" · ")}
        </p>
      )}
      {item.alternatives.length > 0 ? (
        <ChooseCourse
          label="Pick"
          placeholder="Choose a course…"
          options={item.alternatives}
          suggested={suggested}
          onPick={(next) => actions.replace(null, next, term)}
          describedBy={`${item.group_label ?? "this requirement"} in ${term}`}
        />
      ) : (
        <p className="mt-1 text-xs text-text-muted">Any course from {item.group_label} can go here.</p>
      )}
    </li>
  );
}

/** The small "replace with" selector: choosing an option re-plans with that course in this term. */
function ChooseCourse({
  label,
  placeholder,
  options,
  suggested,
  onPick,
  describedBy,
}: {
  label: string;
  placeholder: string;
  options: CourseRef[];
  suggested: CourseRef[];
  onPick: (code: string) => void;
  describedBy: string;
}) {
  const id = useId();
  const suggestedCodes = new Set(suggested.map((course) => course.code));
  const others = options.filter((course) => !suggestedCodes.has(course.code));
  const option = (course: CourseRef) => (
    <option key={course.code} value={course.code}>
      {course.code} {course.title}
      {course.units !== 3 ? ` (${units(course.units)}u)` : ""}
    </option>
  );
  return (
    <div className="mt-2 flex items-center gap-2 print:hidden">
      <label htmlFor={id} className="shrink-0 text-xs font-medium text-text-muted">
        {label}
        <span className="sr-only"> for {describedBy}</span>
      </label>
      <select
        id={id}
        value=""
        onChange={(event) => event.target.value && onPick(event.target.value)}
        className="w-0 min-w-0 flex-1 rounded-button border border-border bg-surface px-3 py-1 text-xs"
      >
        <option value="">{placeholder}</option>
        {suggested.length > 0 && <optgroup label="Suggested for you">{suggested.map(option)}</optgroup>}
        <optgroup label={suggested.length > 0 ? "Other courses that fit" : "Courses that fit"}>
          {others.map(option)}
        </optgroup>
      </select>
    </div>
  );
}
