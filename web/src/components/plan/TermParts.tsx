"use client";

import Link from "next/link";
import { useEffect, useId, useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import type { ChangeAction, CourseRef, GroupProgress, PlanItem, PlannedTerm } from "@/lib/api";
import { credits, units } from "@/lib/format";
import { CalendarIcon, ChevronDownIcon, ClockIcon, CloseIcon, LayersIcon, LightbulbIcon, SwapIcon } from "@/components/icons";
import { AlertIcon, Badge, Button, CheckIcon, LockIcon, StatusBadge } from "@/components/ui";
import { DropHint, dropClasses, useDraggable, useDropTarget, useMoveDialog } from "./MoveCourse";

export interface PlanActions {
  lock: (code: string, term: string) => void;
  unlock: (code: string) => void;
  include: (code: string) => void;
  exclude: (code: string) => void;
  /** Put ``next`` in ``term`` instead of ``previous`` (null when filling an open-choice slot). */
  replace: (previous: string | null, next: string, term: string) => void;
  whatIf: (code: string, action: ChangeAction) => void;
  /** F1.9: put several courses in a term at once ("Auto-fill", or a course with its corequisites). */
  addAll: (codes: string[], term: string) => void;
  /** F1.9: the student has finished building ``term``; with ``empty`` they take no courses then. */
  finish: (term: string, empty?: boolean) => void;
  /** F1.9: open a term the student built so they can change it. */
  reopen: (term: string) => void;
  /** F6.1: put ``code`` in ``to`` instead of ``from`` (dragged there, or from the move dialog). */
  move: (code: string, from: string, to: string) => void;
}

/** How a course row behaves: in a term the student built, the one being built, or a later suggestion. */
export type ItemMode = "built" | "building" | "suggested";

const HEADER_TONES = {
  now: "bg-status-in-progress/8 text-status-in-progress",
  next: "bg-tint text-primary",
  built: "bg-status-done/8 text-status-done",
  summer: "bg-surface-sunken text-text-muted",
  plain: "bg-surface-sunken/60 text-text-muted",
};

export function TermHeader({
  eyebrow,
  title,
  unitCount,
  tone,
  unconfirmed = false,
  action,
}: {
  eyebrow: ReactNode;
  title: string;
  unitCount: number;
  tone: keyof typeof HEADER_TONES;
  unconfirmed?: boolean;
  action?: ReactNode;
}) {
  return (
    <div className={`flex items-end justify-between gap-2 px-4 py-3 ${HEADER_TONES[tone]}`}>
      <div>
        <p className="flex items-center gap-1 text-[0.7rem] font-semibold uppercase tracking-[0.12em]">{eyebrow}</p>
        <h3 className="font-heading text-lg font-bold text-text">{title}</h3>
      </div>
      <div className="flex items-center gap-1.5">
        {unconfirmed && <UnconfirmedMark term={title} />}
        <span className="rounded-full bg-surface px-2.5 py-0.5 text-xs font-semibold text-text shadow-soft">
          {credits(unitCount)}
        </span>
        {action}
      </div>
    </div>
  );
}

/** One planned term as a card: a term the student built, or one the app suggests for later. */
export function TermCard({
  term,
  index,
  mode,
  locked,
  actions,
}: {
  term: PlannedTerm;
  index: number;
  mode: "built" | "suggested";
  locked: Set<string>;
  actions: PlanActions;
}) {
  const label = term.term.label;
  const summer = term.term.season === "Summer";
  const built = mode === "built";
  const target = useDropTarget(label);
  return (
    <li
      {...target.props}
      style={{ "--i": Math.min(index, 8) } as CSSProperties}
      className={`min-w-0 overflow-hidden rounded-card border bg-surface shadow-soft transition ${
        built ? "border-status-done/35" : summer ? "border-dashed border-accent" : "border-dashed border-border-strong"
      } ${dropClasses(target.state, target.over)}`}
    >
      <TermHeader
        eyebrow={
          built ? (
            <>
              <CheckIcon />
              Your term
            </>
          ) : summer ? (
            "Suggested summer"
          ) : (
            "Suggested"
          )
        }
        title={label}
        unitCount={term.units}
        tone={built ? "built" : summer ? "summer" : "plain"}
        unconfirmed={!term.schedule_published}
        action={
          built ? (
            <Button
              variant="quiet"
              size="sm"
              className="min-h-8 px-2.5 text-xs print:hidden"
              onClick={() => actions.reopen(label)}
              aria-label={`Change ${label}`}
            >
              Change
            </Button>
          ) : undefined
        }
      />
      <DropHint state={target.state} option={target.option} />
      <ul className="space-y-1.5 p-3">
        {term.items.map((item) =>
          item.kind === "slot" ? (
            <SlotItem key={item.key} item={item} term={label} actions={actions} />
          ) : (
            <CourseItem
              key={item.key}
              item={item}
              term={label}
              mode={mode}
              locked={locked.has(item.code ?? "")}
              actions={actions}
            />
          ),
        )}
      </ul>
    </li>
  );
}

/**
 * F1.8: a quiet mark on a term whose courses are not checked against a published schedule. Its
 * explanation shows on hover or keyboard focus, or on a tap on a phone. The popup is fixed to the
 * window because the term cards clip their content.
 */
export function UnconfirmedMark({ term }: { term: string }) {
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

export function courseTitles(group: GroupProgress, found = new Map<string, string>()): Map<string, string> {
  for (const course of group.courses) found.set(course.code, course.title);
  for (const child of group.children) courseTitles(child, found);
  return found;
}

export function CourseItem({
  item,
  term,
  mode,
  locked,
  actions,
}: {
  item: PlanItem;
  term: string;
  mode: ItemMode;
  locked: boolean;
  actions: PlanActions;
}) {
  const code = item.code ?? "";
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const gateway = item.unlocks >= 3;
  const check = item.advisories.length > 0;
  const kept = locked && mode === "suggested";
  const twice = item.also_counts_toward.length > 0;
  const listed = item.also_listed.length > 0;
  const drag = useDraggable(code, term);
  const openMove = useMoveDialog();
  return (
    <li
      {...drag}
      className={`rounded-xl border bg-surface transition-colors ${open ? "border-border-strong" : "border-border"} ${
        mode === "building" ? "animate-fade-up" : ""
      } ${drag.draggable ? "cursor-grab active:cursor-grabbing" : ""}`}
    >
      <div className="flex items-start gap-2 py-2 ps-3 pe-1.5">
        <span
          aria-hidden
          className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${mode === "suggested" ? "bg-status-planned/70" : "bg-primary"}`}
        />
        <div className="min-w-0 flex-1 text-sm">
          <p>
            <Link href={`/courses/${encodeURIComponent(code)}`} className="font-semibold text-primary hover:underline">
              {code}
            </Link>{" "}
            <span>{item.title}</span>
          </p>
          {(kept || gateway || check || twice || listed) && (
            <div className="mt-1 flex flex-wrap gap-1">
              {kept && (
                <Badge tone="brand">
                  <LockIcon />
                  Kept here
                </Badge>
              )}
              {twice && (
                <Badge tone="brand">
                  <LayersIcon className="h-3.5 w-3.5" />
                  Counts twice
                </Badge>
              )}
              {listed && <Badge>Fits {item.also_listed.length + 1} requirements</Badge>}
              {gateway && <Badge>Opens {item.unlocks} later courses</Badge>}
              {check && <StatusBadge status="warning" label="Check requirement" />}
            </div>
          )}
        </div>
        <span className="mt-0.5 shrink-0 text-xs text-text-muted">{units(item.units)} cr</span>
        {mode === "building" && (
          <button
            type="button"
            aria-label={`Remove ${code} from ${term}`}
            onClick={() => actions.unlock(code)}
            className="-my-1.5 grid h-10 w-10 shrink-0 cursor-pointer place-items-center rounded-full text-text-muted transition hover:bg-status-blocked/8 hover:text-status-blocked print:hidden"
          >
            <CloseIcon className="h-4 w-4" />
          </button>
        )}
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
            {(twice || listed) && (
              <p className="flex gap-1.5 text-text-muted">
                <LayersIcon className="h-4 w-4 shrink-0" />
                <span>{countsNote(item)}</span>
              </p>
            )}
            {item.advisories.map((note) => (
              <p key={note} className="flex gap-1.5 text-status-warning">
                <AlertIcon className="mt-0.5 h-3.5 w-3.5" />
                <span>{note}</span>
              </p>
            ))}
            <div className="flex flex-wrap gap-2 print:hidden">
              {mode === "built" && (
                <Button variant="secondary" size="sm" onClick={() => actions.unlock(code)}>
                  <CloseIcon className="h-3.5 w-3.5" />
                  Remove from {term}
                </Button>
              )}
              {mode === "suggested" &&
                (locked ? (
                  <Button variant="secondary" size="sm" onClick={() => actions.unlock(code)}>
                    Let the planner move it
                  </Button>
                ) : (
                  <Button variant="secondary" size="sm" onClick={() => actions.lock(code, term)}>
                    <LockIcon />
                    Keep in {term}
                  </Button>
                ))}
              {openMove && (
                <Button variant="secondary" size="sm" onClick={() => openMove(code, term)}>
                  <CalendarIcon className="h-3.5 w-3.5" />
                  Move to another term
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

/**
 * F1.7: where a course counts when more than one requirement could use it. Within a program a
 * course counts once; toward a major and a minor it counts for both.
 */
export function countsNote(item: Pick<PlanItem, "counts_toward" | "also_listed" | "also_counts_toward">): string {
  const parts: string[] = [];
  if (item.counts_toward) {
    const also = item.also_counts_toward.length > 0 ? ` and ${item.also_counts_toward.join(", ")}` : "";
    parts.push(`Counts toward ${item.counts_toward}${also}.`);
  }
  if (item.also_listed.length > 0) {
    parts.push(
      `${item.also_listed.join(", ")} also list${item.also_listed.length === 1 ? "s" : ""} it, but a course counts ` +
        "toward one requirement only: the first, in SIS order, that still needs it. The registrar's audit decides.",
    );
  }
  return parts.join(" ");
}

export function SlotItem({ item, term, actions }: { item: PlanItem; term: string; actions: PlanActions }) {
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
export function ChooseCourse({
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
