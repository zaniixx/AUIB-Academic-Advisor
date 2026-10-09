"use client";

import { useId, useState, type CSSProperties } from "react";
import type { AttemptIn, PlanOut, PreferencesIn } from "@/lib/api";
import { termOrder } from "@/lib/build";
import { credits, pluralize } from "@/lib/format";
import { CalendarCheckIcon } from "@/components/icons";
import { AlertIcon, Button, StatusBadge } from "@/components/ui";
import { TermBuilder } from "./TermBuilder";
import { TermCard, TermHeader, courseTitles, type PlanActions } from "./TermParts";

export type { PlanActions } from "./TermParts";

/**
 * The plan, term by term (F1.4), built by the student one term at a time (F1.9): the terms they
 * have built, the term they are building, and the app's suggestion for the rest, folded away.
 * F1.5 what-if, F1.6 locks and "replace with" start from here.
 */
export function TermPlan({
  id,
  plan,
  inProgress,
  locks,
  preferences,
  actions,
}: {
  id: string;
  plan: PlanOut;
  inProgress: AttemptIn[];
  locks: { code: string; term: string }[];
  preferences: PreferencesIn;
  actions: PlanActions;
}) {
  const locked = new Set(locks.map((lock) => lock.code));
  const titles = courseTitles(plan.progress.root);
  const buildingLabel = plan.building?.term.label ?? null;
  const at = buildingLabel ? plan.terms.findIndex((term) => term.term.label === buildingLabel) : -1;
  const split = at >= 0 ? at : plan.terms.length;
  const done = plan.terms.slice(0, split);
  const building = at >= 0 ? plan.terms[at] : null;
  const later = plan.terms.slice(split + 1);

  // Terms the student chose to take no courses in show as a short row among their terms.
  const listed = new Set(plan.terms.map((term) => term.term.label));
  const start = termOrder(plan.start_term.label);
  const empty = (preferences.built_terms ?? [])
    .filter((label) => !listed.has(label) && termOrder(label) >= start)
    .sort((a, b) => termOrder(a) - termOrder(b));
  const yours = [
    ...done.map((term) => ({ order: termOrder(term.term.label), term, label: term.term.label })),
    ...empty.map((label) => ({ order: termOrder(label), term: null, label })),
  ].sort((a, b) => a.order - b.order);

  return (
    <section id={id} aria-labelledby={`${id}-title`} className="space-y-5">
      <div className="space-y-1">
        <h2 id={`${id}-title`} className="font-heading text-xl font-bold tracking-tight">
          Term by term
        </h2>
        <p className="max-w-3xl text-sm text-text-muted">
          Build your plan one term at a time. Add courses from the recommendations, or press Auto-fill to take them all,
          then press Done. The app suggests the terms after that, and its suggestions change as you build.
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

      {(inProgress.length > 0 || yours.length > 0) && (
        <ol aria-label="Your terms" className="stagger grid grid-cols-1 items-start gap-4 md:grid-cols-2 xl:grid-cols-3">
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
          {yours.map((entry, index) =>
            entry.term ? (
              <TermCard
                key={entry.label}
                term={entry.term}
                index={index + 1}
                mode="built"
                locked={locked}
                actions={actions}
              />
            ) : (
              <EmptyTerm key={entry.label} label={entry.label} index={index + 1} actions={actions} />
            ),
          )}
        </ol>
      )}

      {building && plan.building ? (
        <TermBuilder
          term={building}
          choices={plan.building.choices}
          preferences={preferences}
          first={done.length === 0}
          actions={actions}
        />
      ) : (
        plan.terms.length > 0 && (
          <p className="flex items-center gap-3 rounded-card border border-status-done/35 bg-status-done/8 px-5 py-4 text-sm">
            <CalendarCheckIcon className="h-5 w-5 shrink-0 text-status-done" />
            <span>
              You have built every term to graduation in {plan.graduation_term?.label}. Use Change on a term to adjust
              it.
            </span>
          </p>
        )
      )}

      <LaterTerms terms={later} graduation={plan.graduation_term?.label ?? null} locked={locked} actions={actions} />
    </section>
  );
}

/** A term the student chose to take no courses in. */
function EmptyTerm({ label, index, actions }: { label: string; index: number; actions: PlanActions }) {
  return (
    <li
      style={{ "--i": Math.min(index, 8) } as CSSProperties}
      className="flex min-w-0 items-center justify-between gap-3 rounded-card border border-dashed border-border-strong bg-surface px-4 py-3"
    >
      <div>
        <p className="text-[0.7rem] font-semibold uppercase tracking-[0.12em] text-text-muted">No courses</p>
        <h3 className="font-heading text-lg font-bold">{label}</h3>
      </div>
      <Button
        variant="quiet"
        size="sm"
        className="min-h-8 px-2.5 text-xs"
        onClick={() => actions.reopen(label)}
        aria-label={`Change ${label}`}
      >
        Change
      </Button>
    </li>
  );
}

/** The app's suggestion for the terms after the one being built, folded away until asked for. */
function LaterTerms({
  terms,
  graduation,
  locked,
  actions,
}: {
  terms: PlanOut["terms"];
  graduation: string | null;
  locked: Set<string>;
  actions: PlanActions;
}) {
  const [open, setOpen] = useState(false);
  const listId = useId();
  if (terms.length === 0) return null;
  const total = terms.reduce((sum, term) => sum + term.units, 0);
  return (
    <section aria-labelledby={`${listId}-title`} className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-card border border-dashed border-border-strong bg-surface px-5 py-4">
        <div className="min-w-0 flex-1 basis-72">
          <h3 id={`${listId}-title`} className="font-heading text-lg font-bold">
            Later terms
          </h3>
          <p className="text-sm text-text-muted">
            The app suggests {pluralize(terms.length, "more term")} ({credits(total)})
            {graduation ? `, finishing in ${graduation}` : ""}. You build them one at a time, so they can still
            change.
          </p>
        </div>
        <Button variant="secondary" size="sm" aria-expanded={open} aria-controls={listId} onClick={() => setOpen(!open)}>
          {open ? "Hide the suggested terms" : "Show the suggested terms"}
        </Button>
      </div>
      <div id={listId} hidden={!open}>
        {open && (
          <ol aria-label="Suggested later terms" className="stagger grid grid-cols-1 items-start gap-4 md:grid-cols-2 xl:grid-cols-3">
            {terms.map((term, index) => (
              <TermCard
                key={term.term.label}
                term={term}
                index={index}
                mode={term.built ? "built" : "suggested"}
                locked={locked}
                actions={actions}
              />
            ))}
          </ol>
        )}
      </div>
    </section>
  );
}
