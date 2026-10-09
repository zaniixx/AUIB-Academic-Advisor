/**
 * F1.9: building the plan one term at a time. The student's own courses in a term are the ones
 * locked there; the rest of the term is what the app recommends.
 */
import type { PlanItem, PlannedTerm, PreferencesIn, TermChoice } from "./api";

/** The courses the student put in this term themselves. */
export function chosenItems(term: PlannedTerm): PlanItem[] {
  return term.items.filter((item) => item.kind === "course" && item.locked);
}

/** What the app recommends for the rest of the term: its courses and open choices. */
export function recommendedItems(term: PlannedTerm): PlanItem[] {
  return term.items.filter((item) => !(item.kind === "course" && item.locked));
}

/**
 * The courses "Auto-fill" adds: every recommended course, and for each open choice the first
 * course suggested for it that fits the term (or, failing that, the first that fits at all).
 */
export function autoFillCodes(items: PlanItem[]): string[] {
  const codes: string[] = [];
  for (const item of items) {
    if (item.kind === "course" && item.code) {
      codes.push(item.code);
      continue;
    }
    const fits = item.alternatives.map((course) => course.code).filter((code) => !codes.includes(code));
    const pick = item.suggestions.map((course) => course.code).find((code) => fits.includes(code)) ?? fits[0];
    if (pick) codes.push(pick);
  }
  return codes;
}

/** The credit limit and the usual load for a term; summers have their own limit and no usual load. */
export function termLoad(term: PlannedTerm, preferences: PreferencesIn): { limit: number; usual: number | null } {
  if (term.term.season === "Summer") return { limit: preferences.summer_max_units ?? 6, usual: null };
  const limit = preferences.max_units ?? 18;
  return { limit, usual: Math.min(preferences.preferred_units ?? 15, limit) };
}

/** Choices grouped by the requirement they count toward, in the order the API lists them. */
export function groupChoices(choices: TermChoice[]): { label: string; choices: TermChoice[] }[] {
  const groups = new Map<string, TermChoice[]>();
  for (const choice of choices) {
    const list = groups.get(choice.group_label) ?? [];
    list.push(choice);
    groups.set(choice.group_label, list);
  }
  return [...groups].map(([label, list]) => ({ label, choices: list }));
}

const SEASON_ORDER: Record<string, number> = { Spring: 0, Summer: 1, Fall: 2 };

/** A number that sorts term labels such as "Fall 2027" in calendar order; NaN when it is not a term. */
export function termOrder(label: string): number {
  const match = /^(Spring|Summer|Fall) (\d{4})$/.exec(label.trim());
  return match ? Number(match[2]) * 3 + SEASON_ORDER[match[1]] : Number.NaN;
}
