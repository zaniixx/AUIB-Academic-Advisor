"use client";

import Link from "next/link";
import { useEffect, useId, useLayoutEffect, useRef, useState, type CSSProperties } from "react";
import type { AttemptIn, ChangeAction, CourseRef, GroupProgress, PlanItem, PlanOut } from "@/lib/api";
import { credits, units } from "@/lib/format";
import { ChevronDownIcon, ClockIcon, LightbulbIcon, SwapIcon } from "@/components/icons";
import { AlertIcon, Badge, Button, LockIcon, StatusBadge } from "@/components/ui";

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
  const offset = inProgress.length > 0 ? 1 : 0;
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="space-y-4">
      <div className="space-y-1">
        <h2 id={`${id}-title`} className="font-heading text-xl font-bold tracking-tight">
          Term by term
        </h2>
        <p className="max-w-3xl text-sm text-text-muted">
          Open a course for more options. Where a requirement lets you choose, &ldquo;Replace with&rdquo; swaps it
          for another course that fits the same term: its prerequisites come in earlier terms and its corequisites in
          the same term.
        </p>
      </div>
      {plan.unscheduled.length > 0 && (
        <p className="flex items-center gap-2 rounded-xl border border-status-blocked/30 bg-status-blocked/5 px-3 py-2 text-sm text-status-blocked">
          <AlertIcon className="h-4 w-4" />
          {plan.unscheduled.length} item(s) could not be scheduled.{" "}
          <a href="#notes" className="font-semibold underline">
            See the notes
          </a>
        </p>
      )}
      <ol className="stagger grid grid-cols-1 items-start gap-4 md:grid-cols-2 xl:grid-cols-3">
        {inProgress.length > 0 && (
          <li
            style={{ "--i": 0 } as CSSProperties}
            className="min-w-0 overflow-hidden rounded-card border border-status-in-progress/40 bg-surface shadow-soft"
          >
            <TermHeader
              eyebrow="Now"
              title="This term"
              unitCount={inProgress.reduce((sum, a) => sum + (a.units ?? 3), 0)}
              tone="now"
            />
            <ul className="space-y-1.5 p-3">
              {inProgress.map((attempt) => (
                <li key={attempt.code} className="rounded-xl border border-border px-3 py-2 text-sm">
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                    <span className="font-semibold">{attempt.code}</span>
                    {titles.get(attempt.code) && <span className="min-w-0 text-text-muted">{titles.get(attempt.code)}</span>}
                  </div>
                  <div className="mt-1 flex flex-wrap items-center justify-between gap-2">
                    <StatusBadge status="in-progress" />
                    <Button
                      variant="ghost"
                      size="sm"
                      className="-me-2 min-h-8 px-2 text-xs print:hidden"
                      onClick={() => actions.whatIf(attempt.code, "drop")}
                    >
                      What if I don&apos;t pass?
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          </li>
        )}
        {plan.terms.map((term, index) => {
          const summer = term.term.season === "Summer";
          const next = index === 0;
          return (
            <li
              key={term.term.label}
              style={{ "--i": Math.min(index + offset, 8) } as CSSProperties}
              className={`min-w-0 overflow-hidden rounded-card border bg-surface shadow-soft ${
                next ? "border-primary/50 ring-2 ring-tint-strong" : summer ? "border-dashed border-accent" : "border-border"
              }`}
            >
              <TermHeader
                eyebrow={next ? "Up next" : summer ? "Summer term" : `Term ${index + 1}`}
                title={term.term.label}
                unitCount={term.units}
                tone={next ? "next" : summer ? "summer" : "plain"}
                unconfirmed={!term.schedule_published}
              />
              <ul className="space-y-1.5 p-3">
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
          );
        })}
      </ol>
    </section>
  );
}

const HEADER_TONES = {
  now: "bg-status-in-progress/8 text-status-in-progress",
  next: "bg-tint text-primary",
  summer: "bg-surface-sunken text-text-muted",
  plain: "bg-surface-sunken/60 text-text-muted",
};

function TermHeader({
  eyebrow,
  title,
  unitCount,
  tone,
  unconfirmed = false,
}: {
  eyebrow: string;
  title: string;
  unitCount: number;
  tone: keyof typeof HEADER_TONES;
  unconfirmed?: boolean;
}) {
  return (
    <div className={`flex items-end justify-between gap-2 px-4 py-3 ${HEADER_TONES[tone]}`}>
      <div>
        <p className="text-[0.7rem] font-semibold uppercase tracking-[0.12em]">{eyebrow}</p>
        <h3 className="font-heading text-lg font-bold text-text">{title}</h3>
      </div>
      <div className="flex items-center gap-1.5">
        {unconfirmed && <UnconfirmedMark term={title} />}
        <span className="rounded-full bg-surface px-2.5 py-0.5 text-xs font-semibold text-text shadow-soft">
          {credits(unitCount)}
        </span>
      </div>
    </div>
  );
}

/**
 * F1.8: a quiet mark on a term whose courses are not checked against a published schedule. Its
 * explanation shows on hover or keyboard focus, or on a tap on a phone. The popup is fixed to the
 * window because the term cards clip their content.
 */
function UnconfirmedMark({ term }: { term: string }) {
  const tipId = useId();
  const button = useRef<HTMLButtonElement>(null);
  const [hovered, setHovered] = useState(false);
  const [pinned, setPinned] = useState(false);
  const [place, setPlace] = useState<{ top: number; left: number } | null>(null);
  const open = hovered || pinned;

  // Keep the popup under the icon while the page scrolls or resizes.
  useLayoutEffect(() => {
    if (!open) return;
    const measure = () => {
      if (!button.current) return;
      const rect = button.current.getBoundingClientRect();
      const width = Math.min(288, window.innerWidth - 32);
      setPlace({ top: rect.bottom + 8, left: Math.max(16, Math.min(rect.right - width, window.innerWidth - 16 - width)) });
    };
    measure();
    window.addEventListener("scroll", measure, { passive: true });
    window.addEventListener("resize", measure);
    return () => {
      window.removeEventListener("scroll", measure);
      window.removeEventListener("resize", measure);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const close = () => {
      setHovered(false);
      setPinned(false);
    };
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && close();
    const onPointer = (event: PointerEvent) => {
      if (!button.current?.contains(event.target as Node)) close();
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("pointerdown", onPointer);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("pointerdown", onPointer);
    };
  }, [open]);

  return (
    <>
      <button
        ref={button}
        type="button"
        aria-label={`Course offerings for ${term} are not confirmed yet`}
        aria-describedby={open ? tipId : undefined}
        aria-expanded={open}
        onClick={() => setPinned((value) => !value)}
        onPointerEnter={(event) => event.pointerType === "mouse" && setHovered(true)}
        onPointerLeave={(event) => event.pointerType === "mouse" && setHovered(false)}
        onFocus={() => setHovered(true)}
        onBlur={() => {
          setHovered(false);
          setPinned(false);
        }}
        className="grid h-7 w-7 shrink-0 cursor-help place-items-center rounded-full bg-status-warning/10 text-status-warning transition-colors hover:bg-status-warning/20 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
      >
        <AlertIcon className="h-3.5 w-3.5" />
      </button>
      {open && place && (
        <span
          id={tipId}
          role="tooltip"
          style={{ top: place.top, left: place.left, width: Math.min(288, window.innerWidth - 32) }}
          className="fixed z-50 rounded-xl bg-ink px-3 py-2 text-xs font-normal normal-case leading-relaxed tracking-normal text-ink-contrast shadow-float animate-fade-up"
        >
          <strong className="font-semibold">Not confirmed yet.</strong> {term} has no published course schedule, so
          the app does not know whether these courses will be offered. Check the schedule in SIS before you
          register.
        </span>
      )}
    </>
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
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const gateway = item.unlocks >= 3;
  const check = item.advisories.length > 0;
  return (
    <li className={`rounded-xl border bg-surface transition-colors ${open ? "border-border-strong" : "border-border"}`}>
      <div className="flex items-start gap-2 py-2 ps-3 pe-1.5">
        <span aria-hidden className="mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full bg-status-planned/70" />
        <div className="min-w-0 flex-1 text-sm">
          <p>
            <Link href={`/courses/${encodeURIComponent(code)}`} className="font-semibold text-primary hover:underline">
              {code}
            </Link>{" "}
            <span>{item.title}</span>
          </p>
          {(locked || gateway || check) && (
            <div className="mt-1 flex flex-wrap gap-1">
              {locked && (
                <Badge tone="brand">
                  <LockIcon />
                  Kept here
                </Badge>
              )}
              {gateway && <Badge>Opens {item.unlocks} later courses</Badge>}
              {check && <StatusBadge status="warning" label="Check requirement" />}
            </div>
          )}
        </div>
        <span className="mt-0.5 shrink-0 text-xs text-text-muted">{units(item.units)} cr</span>
        <button
          type="button"
          aria-expanded={open}
          aria-controls={panelId}
          aria-label={`More about ${code}`}
          onClick={() => setOpen(!open)}
          className="-my-1.5 grid h-10 w-10 shrink-0 cursor-pointer place-items-center rounded-full text-text-muted transition hover:bg-surface-sunken hover:text-text print:hidden"
        >
          <ChevronDownIcon className={`h-4 w-4 transition-transform duration-200 ${open ? "rotate-180" : ""}`} />
        </button>
      </div>
      {item.alternatives.length > 0 && (
        <div className="px-3 pb-2.5">
          <ChooseCourse
            label="Replace with"
            placeholder="Another course…"
            options={item.alternatives}
            suggested={[]}
            onPick={(next) => actions.replace(code, next, term)}
            describedBy={`${item.group_label ?? "this requirement"} in ${term}`}
          />
        </div>
      )}
      <div id={panelId} hidden={!open} className="border-t border-border bg-surface-sunken/50 px-3 py-2.5 text-xs">
        {open && (
          <div className="space-y-2 animate-fade-in">
            {item.reason && (
              <p className="flex gap-1.5 text-text-muted">
                <LightbulbIcon className="h-4 w-4" />
                <span>{item.reason}</span>
              </p>
            )}
            {item.advisories.map((note) => (
              <p key={note} className="flex gap-1.5 text-status-warning">
                <AlertIcon className="mt-0.5 h-3.5 w-3.5" />
                <span>{note}</span>
              </p>
            ))}
            <div className="flex flex-wrap gap-2 print:hidden">
              {locked ? (
                <Button variant="secondary" size="sm" onClick={() => actions.unlock(code)}>
                  Let the planner move it
                </Button>
              ) : (
                <Button variant="secondary" size="sm" onClick={() => actions.lock(code, term)}>
                  <LockIcon />
                  Keep in {term}
                </Button>
              )}
              <Button variant="secondary" size="sm" onClick={() => actions.whatIf(code, "delay")}>
                <ClockIcon className="h-3.5 w-3.5" />
                What if I delay it?
              </Button>
            </div>
          </div>
        )}
      </div>
    </li>
  );
}

function SlotItem({ item, term, actions }: { item: PlanItem; term: string; actions: PlanActions }) {
  const available = new Set(item.alternatives.map((course) => course.code));
  const suggested = item.suggestions.filter((course) => available.has(course.code));
  return (
    <li className="rounded-xl border border-dashed border-border-strong bg-surface-sunken/40 px-3 py-2.5 text-sm">
      <div className="flex items-start justify-between gap-2">
        <span className="font-semibold">{item.title}</span>
        <span className="shrink-0 text-xs text-text-muted">{units(item.units)} cr</span>
      </div>
      {item.suggestions.length > 0 && (
        <p className="mt-1 text-xs text-text-muted">
          Suggested for you: {item.suggestions.map((course) => `${course.code} ${course.title}`).join(" · ")}
        </p>
      )}
      {item.alternatives.length > 0 ? (
        <div className="mt-2">
          <ChooseCourse
            label="Pick"
            placeholder="Choose a course…"
            options={item.alternatives}
            suggested={suggested}
            onPick={(next) => actions.replace(null, next, term)}
            describedBy={`${item.group_label ?? "this requirement"} in ${term}`}
          />
        </div>
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
      {course.units !== 3 ? ` (${credits(course.units)})` : ""}
    </option>
  );
  return (
    <div className="flex items-center gap-2 print:hidden">
      <label htmlFor={id} className="flex shrink-0 items-center gap-1 text-xs font-medium text-text-muted">
        <SwapIcon className="h-3.5 w-3.5" />
        {label}
        <span className="sr-only"> for {describedBy}</span>
      </label>
      <div className="relative w-0 min-w-0 flex-1">
        <select
          id={id}
          value=""
          onChange={(event) => event.target.value && onPick(event.target.value)}
          className="min-h-10 w-full cursor-pointer appearance-none rounded-lg border border-border bg-surface py-1 ps-2.5 pe-8 text-xs transition hover:border-primary"
        >
          <option value="">{placeholder}</option>
          {suggested.length > 0 && <optgroup label="Suggested for you">{suggested.map(option)}</optgroup>}
          <optgroup label={suggested.length > 0 ? "Other courses that fit" : "Courses that fit"}>
            {others.map(option)}
          </optgroup>
        </select>
        <ChevronDownIcon className="pointer-events-none absolute end-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-muted" />
      </div>
    </div>
  );
}
