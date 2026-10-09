/**
 * The document a student prints or saves as a PDF for their advisor (F5.3): one term in
 * detail, then every term at a glance. Pure functions over the plan, so they are unit-tested.
 */
import type { AttemptIn, CourseRef, GroupProgress, PlanItem, PlanOut, PlannedTerm, PreferencesIn } from "./api";
import { normalizeTerm } from "./format";

export const NOTICE_TITLE = "A planning aid, not a registration or a promise of courses";

export const NOTICE_TEXT =
  "Courses are not scheduled from this document, and it does not reserve a seat. The university sets each " +
  "term's schedule, so a course listed here may not be offered in that term, may be full, or may change. " +
  "Even if an advisor reviews, approves or signs this plan, that is not a promise that these classes will be " +
  "scheduled in upcoming terms. Class registration must always be completed through AUIB's official system (SIS).";

export const SIGN_OFF_NOTE =
  "A signature records that this plan was discussed. It does not register the student, reserve a seat, or " +
  "promise that any course will be scheduled in an upcoming term.";

export interface PaperSize {
  id: string;
  label: string;
  /** The CSS page size, as written in `@page { size: … }`. */
  css: string;
  /** Sheet width for the on-screen preview. */
  width: string;
}

/** Paper the document can be printed on; the first is the default. */
export const PAPER_SIZES: readonly PaperSize[] = [{ id: "a4", label: "A4 (210 × 297 mm)", css: "A4", width: "210mm" }];

export const DEFAULT_PAPER = PAPER_SIZES[0];

export function pageStyle(paper: PaperSize): string {
  return `@page { size: ${paper.css}; }`;
}

/** How many replacement courses to name before "and N more". */
const ALTERNATIVES_SHOWN = 4;
/** How many other eligible courses to name per requirement before "and N more". */
const OPTIONS_SHOWN = 6;

export interface DetailRow {
  key: string;
  code: string | null;
  title: string;
  units: number;
  /** The requirements the course counts toward in the plan: the major's, and the minor's if it counts there too. */
  countsToward: string[];
  notes: string[];
  choice: boolean;
}

export interface OptionGroup {
  requirement: string;
  courses: CourseRef[];
  more: number;
}

export interface TermDetail {
  term: PlannedTerm;
  rows: DetailRow[];
  /** Warnings about this term's courses. Conditions to confirm are in each row's notes. */
  warnings: string[];
  /** Other courses whose prerequisites are met; only known for the plan's first term. */
  otherOptions: OptionGroup[];
}

export interface OverviewRow {
  label: string;
  current: boolean;
  /** False when no published schedule confirms the term's courses will be offered (F1.8). */
  confirmed: boolean;
  /** True when the student chose the term's courses; false for the app's suggestion (F1.9). */
  chosen: boolean;
  courses: { key: string; code: string | null; title: string; units: number; choice: boolean }[];
  units: number;
}

export interface RequirementRow {
  label: string;
  required: number;
  completed: number;
  inProgress: number;
  planned: number;
  left: number;
}

/** The leaf requirement each course counts toward, by course code. */
export function requirementByCourse(group: GroupProgress, found = new Map<string, string>()): Map<string, string> {
  for (const course of group.courses) found.set(course.code, group.label);
  for (const child of group.children) requirementByCourse(child, found);
  return found;
}

/** Course titles for every course on the student's path, including the ones in progress. */
export function courseTitles(plan: PlanOut): Map<string, string> {
  const titles = new Map<string, string>();
  for (const node of plan.degree_map.nodes) if (node.code) titles.set(node.code, node.title);
  return titles;
}

/** The term the document starts with: the first planned term unless the student chose another. */
export function defaultTerm(plan: PlanOut): string | null {
  return plan.terms[0]?.term.label ?? null;
}

export function termDetail(plan: PlanOut, label: string): TermDetail | null {
  const term = plan.terms.find((entry) => entry.term.label === label);
  if (!term) return null;
  const counts = requirementByCourse(plan.progress_with_plan);
  const minorCounts = plan.minor ? requirementByCourse(plan.minor.progress_with_plan) : new Map<string, string>();
  const chain = new Set(plan.critical_chain.map((course) => course.code));
  const codes = new Set(term.items.flatMap((item) => (item.code ? [item.code] : [])));
  const rows = term.items.map((item) =>
    item.kind === "slot"
      ? choiceRow(item)
      : courseRow(item, [counts.get(item.code ?? "") ?? item.group_label, minorCounts.get(item.code ?? "")], chain),
  );
  const warnings = plan.issues
    .filter((issue) => issue.severity === "warning" && issue.code !== null && codes.has(issue.code))
    .map((issue) => issue.message);
  return { term, rows, warnings, otherOptions: label === plan.start_term.label ? otherOptions(plan, codes) : [] };
}

function courseRow(item: PlanItem, countsToward: (string | null | undefined)[], chain: Set<string>): DetailRow {
  const notes: string[] = [];
  if (item.locked) notes.push("Placed in this term by the student.");
  const reason = describeReason(item.reason);
  if (reason) notes.push(reason);
  if (item.code && chain.has(item.code)) notes.push("On the longest prerequisite chain: a delay here delays graduation.");
  if (item.unlocks >= 3) notes.push(`Prerequisite for ${item.unlocks} later courses.`);
  for (const advisory of item.advisories) notes.push(`To confirm: ${advisory}`);
  if (item.alternatives.length > 0) notes.push(`If it is not available: ${listCodes(item.alternatives)}.`);
  return {
    key: item.key,
    code: item.code,
    title: item.title,
    units: item.units,
    countsToward: [...new Set(countsToward.filter((label): label is string => Boolean(label)))],
    notes,
    choice: false,
  };
}

function choiceRow(item: PlanItem): DetailRow {
  const fits = new Set(item.alternatives.map((course) => course.code));
  const suggested = item.suggestions.filter((course) => fits.has(course.code));
  const notes: string[] = [];
  if (suggested.length > 0) {
    notes.push(`Suggested for the student: ${suggested.map((course) => course.code).join(", ")}.`);
  }
  const others = item.alternatives.length - suggested.length;
  if (others > 0) {
    notes.push(`${suggested.length > 0 ? "Or one of" : "One of"} ${others} other courses that fit this term.`);
  } else if (item.alternatives.length === 0) {
    notes.push("Any course that counts toward this requirement.");
  }
  return {
    key: item.key,
    code: null,
    title: item.title,
    units: item.units,
    countsToward: item.group_label ? [item.group_label] : [],
    notes,
    choice: true,
  };
}

/** The planner's reason in the advisor's terms; "Required: …" repeats the requirement column. */
function describeReason(reason: string): string | null {
  if (!reason || reason.startsWith("Required:") || reason === "You placed this course") return null;
  if (reason === "You chose this course") return "Chosen by the student.";
  return reason.endsWith(".") ? reason : `${reason}.`;
}

function listCodes(courses: CourseRef[]): string {
  const shown = courses.slice(0, ALTERNATIVES_SHOWN).map((course) => course.code);
  const more = courses.length - shown.length;
  return more > 0 ? `${shown.join(", ")} and ${more} more` : shown.join(", ");
}

function otherOptions(plan: PlanOut, planned: Set<string>): OptionGroup[] {
  const groups = new Map<string, CourseRef[]>();
  for (const entry of plan.eligible_next_term) {
    if (planned.has(entry.course.code)) continue;
    groups.set(entry.group_label, [...(groups.get(entry.group_label) ?? []), entry.course]);
  }
  return [...groups.entries()].map(([requirement, courses]) => ({
    requirement,
    courses: courses.slice(0, OPTIONS_SHOWN),
    more: Math.max(0, courses.length - OPTIONS_SHOWN),
  }));
}

/** F1.8: said wherever a planned term is not checked against a published schedule. */
export function unconfirmedNote(label: string): string {
  return (
    `Course offerings for ${label} are not published yet, so it is not known whether these courses will run. ` +
    "Check the schedule in SIS before registering."
  );
}

/** F1.9: said of a planned term whose courses the student has not chosen yet. */
export function suggestedNote(label: string): string {
  return `The app suggested these courses for ${label}; the student has not chosen them yet.`;
}

/** The term the in-progress courses belong to, such as "Fall 2026"; null if none says. */
export function currentTermLabel(inProgress: AttemptIn[]): string | null {
  const counts = new Map<string, number>();
  for (const attempt of inProgress) {
    const label = attempt.term ? normalizeTerm(attempt.term) : null;
    if (label) counts.set(label, (counts.get(label) ?? 0) + 1);
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? null;
}

export function overviewRows(plan: PlanOut, inProgress: AttemptIn[]): OverviewRow[] {
  const titles = courseTitles(plan);
  const rows: OverviewRow[] = [];
  if (inProgress.length > 0) {
    rows.push({
      label: currentTermLabel(inProgress) ?? "This term",
      current: true,
      confirmed: true, // the student is registered in these
      chosen: true,
      courses: inProgress.map((attempt) => ({
        key: attempt.code,
        code: attempt.code,
        title: titles.get(attempt.code) ?? "",
        units: attempt.units ?? 3,
        choice: false,
      })),
      units: inProgress.reduce((sum, attempt) => sum + (attempt.units ?? 3), 0),
    });
  }
  for (const term of plan.terms) {
    rows.push({
      label: term.term.label,
      current: false,
      confirmed: term.schedule_published,
      chosen: term.built,
      courses: term.items.map((item) => ({
        key: item.key,
        code: item.code,
        title: item.title,
        units: item.units,
        choice: item.kind === "slot",
      })),
      units: term.units,
    });
  }
  return rows;
}

/** Units per top-level requirement of a program once the plan is done, then the total. */
export function requirementRows(root: GroupProgress, totalLabel = "Total"): RequirementRow[] {
  const row = (group: GroupProgress, label = group.label): RequirementRow => ({
    label,
    required: group.units_required,
    completed: group.completed,
    inProgress: group.in_progress,
    planned: group.planned,
    left: Math.max(0, group.units_required - group.completed - group.in_progress - group.planned),
  });
  return [...root.children.map((group) => row(group)), row(root, totalLabel)];
}

/** Notes about the plan as a whole: warnings and conditions outside the term shown in detail. */
export function planNotes(plan: PlanOut, label: string | null): { warnings: string[]; checks: string[] } {
  const term = plan.terms.find((entry) => entry.term.label === label);
  const shown = new Set(term?.items.flatMap((item) => (item.code ? [item.code] : [])) ?? []);
  const elsewhere = plan.issues.filter((issue) => issue.code === null || !shown.has(issue.code));
  return {
    warnings: elsewhere.filter((issue) => issue.severity === "warning").map((issue) => issue.message),
    checks: elsewhere.filter((issue) => issue.severity === "info").map((issue) => issue.message),
  };
}

export function isLate(plan: PlanOut): boolean {
  const { graduation_term: graduation, on_time_term: onTime } = plan;
  if (!graduation || !onTime) return false;
  const rank = { Spring: 1, Summer: 2, Fall: 3 } as const;
  return graduation.year * 10 + rank[graduation.season] > onTime.year * 10 + rank[onTime.season];
}

export function loadSummary(preferences: PreferencesIn): string {
  const usual = preferences.preferred_units ?? 15;
  const most = preferences.max_units ?? 18;
  const summer = preferences.include_summer
    ? `Summer terms are used, up to ${preferences.summer_max_units ?? 6} credits.`
    : "Summer terms are used only for courses that run in summer only, such as internships.";
  const pace = preferences.pace === "fastest" ? "finish as early as possible" : "aim for the standard finish";
  return `Usual load ${usual} credits a term, at most ${most}. ${summer} Pace: ${pace}.`;
}

/** "8 October 2026": day, month name and year, so it reads the same everywhere. */
export function formatDate(date: Date): string {
  return new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "long", year: "numeric" }).format(date);
}

/** "2026-10-08" as "8 October 2026"; anything else is returned as it is. */
export function formatIsoDate(iso: string): string {
  const match = iso.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  return match ? formatDate(new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]))) : iso;
}
