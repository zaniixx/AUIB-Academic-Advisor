"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";
import type { PlanItem, PlannedTerm, PreferencesIn, TermChoice } from "@/lib/api";
import { autoFillCodes, chosenItems, groupChoices, recommendedItems, termLoad } from "@/lib/build";
import { pluralize, units } from "@/lib/format";
import { ArrowRightIcon, PlusIcon, SearchIcon, SparklesIcon } from "@/components/icons";
import { AlertIcon, Badge, Button, Disclosure, FIELD, StatusBadge } from "@/components/ui";
import { ShowMore } from "./ShowMore";
import { ChooseCourse, CourseItem, UnconfirmedMark, type PlanActions } from "./TermParts";
import { DropHint, dropClasses, useDraggable, useDropTarget } from "./MoveCourse";

/**
 * F1.9: the student builds one term at a time. They add courses from the app's recommendations
 * (or all of them with "Auto-fill") and from the other courses they can take, then finish the term.
 */
export function TermBuilder({
  term,
  choices,
  preferences,
  first,
  actions,
}: {
  term: PlannedTerm;
  choices: TermChoice[];
  preferences: PreferencesIn;
  /** True for the student's next term (nothing built before it yet). */
  first: boolean;
  actions: PlanActions;
}) {
  const label = term.term.label;
  const mine = chosenItems(term);
  const recommended = recommendedItems(term);
  const chosen = mine.reduce((sum, item) => sum + item.units, 0);
  const { limit, usual } = termLoad(term, preferences);
  const room = limit - chosen;
  const auto = autoFillCodes(recommended);
  const over = chosen > limit;
  const titleId = useId();
  const target = useDropTarget(label);

  // When the student finishes a term, bring the next one into view.
  const panel = useRef<HTMLElement>(null);
  const shown = useRef(label);
  useEffect(() => {
    if (shown.current !== label) {
      shown.current = label;
      panel.current?.scrollIntoView({ block: "start", behavior: "smooth" });
    }
  }, [label]);

  return (
    <section
      ref={panel}
      {...target.props}
      aria-labelledby={titleId}
      className={`scroll-mt-36 overflow-hidden rounded-card border border-primary/40 bg-surface shadow-card ring-4 ring-tint transition print:hidden ${dropClasses(target.state, target.over)}`}
    >
      <header className="flex flex-wrap items-center justify-between gap-4 bg-tint px-5 py-4">
        <div className="min-w-0">
          <p className="text-[0.7rem] font-semibold uppercase tracking-[0.12em] text-primary">
            {first ? "Build your next term" : "Build the next term"}
          </p>
          <h3 id={titleId} className="font-heading text-2xl font-bold tracking-tight">
            <span className="sr-only">Build </span>
            {label}
          </h3>
        </div>
        <div className="flex items-center gap-3">
          {!term.schedule_published && <UnconfirmedMark term={label} />}
          <CreditMeter chosen={chosen} usual={usual} limit={limit} />
        </div>
      </header>
      <DropHint state={target.state} option={target.option} />

      <div className="grid gap-6 p-5 lg:grid-cols-2">
        <div className="space-y-2">
          <h4 className="text-sm font-semibold">Your courses for {label}</h4>
          {mine.length === 0 ? (
            <p className="rounded-xl border border-dashed border-border-strong px-4 py-6 text-center text-sm text-text-muted">
              Nothing here yet. Add courses from the recommendations, or press Auto-fill to add them all.
            </p>
          ) : (
            <ul className="space-y-1.5">
              {mine.map((item) => (
                <CourseItem key={item.key} item={item} term={label} mode="building" locked actions={actions} />
              ))}
            </ul>
          )}
        </div>

        <div className="space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h4 className="flex items-center gap-1.5 text-sm font-semibold">
              <SparklesIcon className="h-4 w-4 text-primary" />
              Recommended for you
            </h4>
            {auto.length > 0 && (
              <Button
                variant={mine.length === 0 ? "primary" : "secondary"}
                size="sm"
                onClick={() => actions.addAll(auto, label)}
              >
                <SparklesIcon className="h-4 w-4" />
                Auto-fill {label}
              </Button>
            )}
          </div>
          {recommended.length === 0 ? (
            <p className="rounded-xl bg-surface-sunken px-4 py-3 text-sm text-text-muted">
              {mine.length > 0
                ? "You have added everything the app recommends for this term."
                : "The app has nothing more to recommend for this term."}
            </p>
          ) : (
            <ul className="space-y-1.5">
              {recommended.map((item) =>
                item.kind === "slot" ? (
                  <ChoiceSlot key={item.key} item={item} term={label} actions={actions} />
                ) : (
                  <Recommendation key={item.key} item={item} term={label} room={room} actions={actions} />
                ),
              )}
            </ul>
          )}
        </div>
      </div>

      {choices.length > 0 && (
        <div className="border-t border-border px-5 py-3">
          <OtherCourses choices={choices} term={label} room={room} actions={actions} />
        </div>
      )}

      <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-border bg-surface-sunken/50 px-5 py-4">
        <p className="min-w-0 flex-1 basis-60 text-sm text-text-muted" aria-live="polite">
          {doneHint(mine.length, chosen, usual, limit)}
        </p>
        <div className="flex flex-wrap gap-2">
          {mine.length === 0 && (
            <Button variant="quiet" size="sm" onClick={() => actions.finish(label, true)}>
              No courses this term
            </Button>
          )}
          <Button disabled={mine.length === 0 || over} onClick={() => actions.finish(label)}>
            Done with {label}
            <ArrowRightIcon className="h-4 w-4" />
          </Button>
        </div>
      </footer>
    </section>
  );
}

function doneHint(count: number, chosen: number, usual: number | null, limit: number): string {
  if (count === 0) return "Add at least one course to finish this term.";
  if (chosen > limit) return `That is over your ${units(limit)}-credit limit. Remove a course to finish.`;
  if (usual !== null && chosen < usual) {
    return `${units(usual - chosen)} credits below your usual ${units(usual)}. You can still finish the term.`;
  }
  return "Looks good. Press Done to move on to the next term.";
}

/** Credits chosen so far, against the student's usual load and their limit. */
function CreditMeter({ chosen, usual, limit }: { chosen: number; usual: number | null; limit: number }) {
  const share = (value: number) => `${Math.min(100, (value / limit) * 100)}%`;
  return (
    <div className="w-44 space-y-1">
      <p className="flex items-baseline justify-between gap-2 text-sm">
        <span>
          <span className="font-heading text-xl font-bold tabular-nums">{units(chosen)}</span>{" "}
          <span className="text-text-muted">{usual !== null ? `of ${units(usual)} credits` : "credits"}</span>
        </span>
        <span className="text-xs text-text-muted">max {units(limit)}</span>
      </p>
      <div
        role="meter"
        aria-label="Credits chosen for this term"
        aria-valuemin={0}
        aria-valuemax={limit}
        aria-valuenow={chosen}
        aria-valuetext={`${units(chosen)} of up to ${units(limit)} credits`}
        className="relative h-2 overflow-hidden rounded-full bg-surface"
      >
        <div
          className={`h-full rounded-full transition-[width] duration-500 ease-out ${chosen > limit ? "bg-status-blocked" : "bg-primary"}`}
          style={{ width: share(chosen) }}
        />
        {usual !== null && usual < limit && (
          <span aria-hidden className="absolute inset-y-0 w-0.5 bg-text/40" style={{ left: share(usual) }} />
        )}
      </div>
    </div>
  );
}

function Recommendation({
  item,
  term,
  room,
  actions,
}: {
  item: PlanItem;
  term: string;
  room: number;
  actions: PlanActions;
}) {
  const code = item.code ?? "";
  const fits = item.units <= room;
  const drag = useDraggable(code, term);
  return (
    <li
      {...drag}
      className={`flex items-start gap-3 rounded-xl border border-dashed border-border-strong bg-surface px-3 py-2.5 text-sm ${
        drag.draggable ? "cursor-grab active:cursor-grabbing" : ""
      }`}
    >
      <div className="min-w-0 flex-1">
        <p>
          <Link href={`/courses/${encodeURIComponent(code)}`} className="font-semibold text-primary hover:underline">
            {code}
          </Link>{" "}
          <span>{item.title}</span>
        </p>
        {item.reason && <p className="mt-0.5 text-xs text-text-muted">{item.reason}</p>}
        {(item.unlocks >= 3 || item.advisories.length > 0) && (
          <div className="mt-1 flex flex-wrap gap-1">
            {item.unlocks >= 3 && <Badge>Opens {item.unlocks} later courses</Badge>}
            {item.advisories.length > 0 && <StatusBadge status="warning" label="Check requirement" />}
          </div>
        )}
      </div>
      <span className="mt-0.5 shrink-0 text-xs text-text-muted">{units(item.units)} cr</span>
      <AddButton code={code} term={term} fits={fits} onAdd={() => actions.lock(code, term)} />
    </li>
  );
}

/** An open choice (such as a humanities elective): the student picks the course. */
function ChoiceSlot({ item, term, actions }: { item: PlanItem; term: string; actions: PlanActions }) {
  const fits = new Set(item.alternatives.map((course) => course.code));
  const suggested = item.suggestions.filter((course) => fits.has(course.code));
  return (
    <li className="rounded-xl border border-dashed border-border-strong bg-surface-sunken/40 px-3 py-2.5 text-sm">
      <div className="flex items-start justify-between gap-2">
        <span className="font-semibold">{item.title}</span>
        <span className="shrink-0 text-xs text-text-muted">{units(item.units)} cr</span>
      </div>
      {suggested.length > 0 && (
        <p className="mt-0.5 text-xs text-text-muted">
          Suggested for you: {suggested.map((course) => `${course.code} ${course.title}`).join(" · ")}
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
        <p className="mt-1 text-xs text-text-muted">No course from {item.group_label} fits this term.</p>
      )}
    </li>
  );
}

function AddButton({ code, term, fits, onAdd }: { code: string; term: string; fits: boolean; onAdd: () => void }) {
  return (
    <Button
      variant="secondary"
      size="sm"
      className="-my-0.5 shrink-0"
      disabled={!fits}
      title={fits ? undefined : "Over your credit limit for this term"}
      aria-label={`Add ${code} to ${term}`}
      onClick={onAdd}
    >
      <PlusIcon className="h-4 w-4" />
      Add
    </Button>
  );
}

/** Everything else the student could take that term, grouped by requirement, with a filter. */
function OtherCourses({
  choices,
  term,
  room,
  actions,
}: {
  choices: TermChoice[];
  term: string;
  room: number;
  actions: PlanActions;
}) {
  const [query, setQuery] = useState("");
  const filterId = useId();
  const words = query.trim().toLowerCase();
  const matching = words
    ? choices.filter((choice) => `${choice.course.code} ${choice.course.title}`.toLowerCase().includes(words))
    : choices;
  const groups = groupChoices(matching);
  return (
    <Disclosure
      summary={
        <span className="text-sm">
          Other courses you can take in {term}{" "}
          <span className="font-normal text-text-muted">({choices.length})</span>
        </span>
      }
    >
      <div className="space-y-4 pb-2 pt-1">
        <p className="text-xs text-text-muted">
          They count toward a requirement you still need, and their prerequisites are done before {term}. Adding one
          can move a recommended course to a later term.
        </p>
        {choices.length > 8 && (
          <div className="relative max-w-sm">
            <label htmlFor={filterId} className="sr-only">
              Filter the other courses by code or title
            </label>
            <SearchIcon className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
            <input
              id={filterId}
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Filter by code or title"
              className={`${FIELD} ps-9`}
            />
          </div>
        )}
        {groups.length === 0 && <p className="text-sm text-text-muted">No course matches &ldquo;{query}&rdquo;.</p>}
        {groups.map((group) => (
          <div key={group.label} className="space-y-1.5">
            <h5 className="text-xs font-semibold uppercase tracking-[0.08em] text-text-muted">
              {group.label} <span className="font-normal normal-case">· {pluralize(group.choices.length, "course")}</span>
            </h5>
            <ShowMore items={group.choices} limit={words ? 50 : 4} noun="courses">
              {(shown) => (
                <ul className="grid gap-1.5 md:grid-cols-2">
                  {shown.map((choice) => (
                    <OtherCourse key={choice.course.code} choice={choice} term={term} room={room} actions={actions} />
                  ))}
                </ul>
              )}
            </ShowMore>
          </div>
        ))}
      </div>
    </Disclosure>
  );
}

function OtherCourse({
  choice,
  term,
  room,
  actions,
}: {
  choice: TermChoice;
  term: string;
  room: number;
  actions: PlanActions;
}) {
  const { course } = choice;
  return (
    <li className="flex items-start gap-3 rounded-xl border border-border px-3 py-2 text-sm">
      <div className="min-w-0 flex-1">
        <p>
          <Link
            href={`/courses/${encodeURIComponent(course.code)}`}
            className="font-semibold text-primary hover:underline"
          >
            {course.code}
          </Link>{" "}
          <span>{course.title}</span>
        </p>
        <p className="mt-0.5 flex flex-wrap gap-x-2 text-xs text-text-muted">
          <span>{units(course.units)} cr</span>
          {choice.planned_for && <span>Suggested for {choice.planned_for.label}</span>}
          {choice.take_with.length > 0 && <span>Take with {choice.take_with.join(", ")}</span>}
          {choice.unlocks >= 3 && <span>Opens {choice.unlocks} later courses</span>}
        </p>
        {choice.advisories.length > 0 && (
          <p className="mt-0.5 flex items-start gap-1 text-xs text-status-warning">
            <AlertIcon className="mt-0.5 h-3 w-3 shrink-0" />
            {choice.advisories[0]}
          </p>
        )}
      </div>
      <AddButton
        code={course.code}
        term={term}
        fits={course.units <= room}
        onAdd={() => actions.addAll([course.code, ...choice.take_with], term)}
      />
    </li>
  );
}
