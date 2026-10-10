/**
 * F6.2: the side-by-side comparison of saved plans. Each plan has its own terms, so the table has
 * a row for every term any of them plans, in calendar order.
 */
import type { ScenarioPlan } from "./api";
import { termOrder } from "./build";
import { pluralize } from "./format";

export type ScenarioTerm = ScenarioPlan["terms"][number];

export interface TermRow {
  label: string;
  /** One cell per plan: its courses that term, or null when it plans nothing then. */
  cells: (ScenarioTerm | null)[];
}

export function termRows(plans: (ScenarioPlan | null)[]): TermRow[] {
  const labels = new Set(plans.flatMap((plan) => plan?.terms.map((term) => term.term.label) ?? []));
  return [...labels]
    .sort((a, b) => termOrder(a) - termOrder(b))
    .map((label) => ({
      label,
      cells: plans.map((plan) => plan?.terms.find((term) => term.term.label === label) ?? null),
    }));
}

/** How a plan's finish compares with the first plan's. */
export function versusFirst(semesters: number | null): string {
  if (semesters === null) return "Your current plan";
  if (semesters === 0) return "Same finish";
  return `${pluralize(Math.abs(semesters), "semester")} ${semesters > 0 ? "later" : "sooner"}`;
}
