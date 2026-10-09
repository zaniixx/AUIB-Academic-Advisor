import { describe, expect, it } from "vitest";
import type { CourseRef, PlanItem, PlannedTerm, TermChoice } from "./api";
import { autoFillCodes, chosenItems, groupChoices, recommendedItems, termLoad, termOrder } from "./build";
import { DEFAULT_PREFERENCES } from "./profile";

const course = (code: string): CourseRef => ({ code, title: `${code} title`, units: 3 });

function item(overrides: Partial<PlanItem>): PlanItem {
  return {
    kind: "course",
    key: overrides.code ?? "slot",
    code: null,
    title: "",
    units: 3,
    reason: "",
    group_key: null,
    group_label: null,
    locked: false,
    unlocks: 0,
    advisories: [],
    suggestions: [],
    alternatives: [],
    ...overrides,
  };
}

function term(label: string, items: PlanItem[]): PlannedTerm {
  const [season, year] = label.split(" ");
  return {
    term: { label, year: Number(year), season: season as PlannedTerm["term"]["season"] },
    units: items.reduce((sum, each) => sum + each.units, 0),
    items,
    schedule_published: false,
    built: false,
  };
}

const choice = (code: string, group: string): TermChoice => ({
  course: course(code),
  group_key: group,
  group_label: group,
  unlocks: 0,
  advisories: [],
  take_with: [],
  planned_for: null,
});

describe("building a term (F1.9)", () => {
  const spring = term("Spring 2027", [
    item({ code: "CSC 231", locked: true }),
    item({ code: "MAT 130" }),
    item({
      kind: "slot",
      key: "hum-1",
      suggestions: [course("ART 999"), course("PHI 101")],
      alternatives: [course("HIS 101"), course("PHI 101")],
    }),
    item({ kind: "slot", key: "hum-2", suggestions: [course("PHI 101")], alternatives: [course("PHI 101")] }),
    item({ kind: "slot", key: "free-1", alternatives: [] }),
  ]);

  it("tells the student's own courses from the app's recommendations", () => {
    expect(chosenItems(spring).map((each) => each.code)).toEqual(["CSC 231"]);
    expect(recommendedItems(spring).map((each) => each.key)).toEqual(["MAT 130", "hum-1", "hum-2", "free-1"]);
  });

  it("auto-fills recommended courses and the first suggestion that fits each open choice", () => {
    // ART 999 does not fit the term, so PHI 101 fills the first slot. The second slot's only course is
    // then taken and the last slot has none, so both are left for a later term.
    expect(autoFillCodes(recommendedItems(spring))).toEqual(["MAT 130", "PHI 101"]);
  });

  it("uses the summer limit in summer and the usual load otherwise", () => {
    expect(termLoad(spring, DEFAULT_PREFERENCES)).toEqual({ limit: 18, usual: 15 });
    expect(termLoad(term("Summer 2027", []), DEFAULT_PREFERENCES)).toEqual({ limit: 6, usual: null });
    expect(termLoad(spring, { ...DEFAULT_PREFERENCES, preferred_units: 21, max_units: 12 })).toEqual({
      limit: 12,
      usual: 12,
    });
  });

  it("groups other courses by requirement in the order given", () => {
    const groups = groupChoices([choice("ENL 201", "Communication"), choice("HIS 101", "Humanities"), choice("ENL 210", "Communication")]);
    expect(groups.map((group) => [group.label, group.choices.map((each) => each.course.code)])).toEqual([
      ["Communication", ["ENL 201", "ENL 210"]],
      ["Humanities", ["HIS 101"]],
    ]);
  });

  it("sorts term labels in calendar order", () => {
    const labels = ["Fall 2027", "Spring 2028", "Summer 2027", "Spring 2027"];
    expect(labels.sort((a, b) => termOrder(a) - termOrder(b))).toEqual([
      "Spring 2027",
      "Summer 2027",
      "Fall 2027",
      "Spring 2028",
    ]);
    expect(termOrder("Someday")).toBeNaN();
  });
});
