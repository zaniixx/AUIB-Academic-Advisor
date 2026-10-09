import { describe, expect, it } from "vitest";
import type { AttemptIn, CourseRef, PlanItem, PlanOut } from "./api";
import {
  DEFAULT_PAPER,
  NOTICE_TEXT,
  defaultTerm,
  formatDate,
  formatIsoDate,
  isLate,
  loadSummary,
  overviewRows,
  pageStyle,
  planNotes,
  requirementRows,
  termDetail,
  unconfirmedNote,
} from "./advisor";
import { DEFAULT_PREFERENCES } from "./profile";

const course = (code: string, title = `${code} title`): CourseRef => ({ code, title, units: 3 });

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

const group = (label: string, codes: string[], units: Partial<Record<"completed" | "in_progress" | "planned", number>> = {}) => ({
  key: label,
  label,
  role: "core",
  units_required: 12,
  completed: units.completed ?? 0,
  in_progress: units.in_progress ?? 0,
  planned: units.planned ?? 0,
  remaining: 0,
  courses: codes.map((code) => ({ code, title: code, units: 3, state: "planned" as const })),
  children: [],
});

// The fields of a plan the advisor document reads; the rest of PlanOut is not needed here.
const plan = {
  start_term: { label: "Spring 2027", year: 2027, season: "Spring" },
  graduation_term: { label: "Fall 2029", year: 2029, season: "Fall" },
  on_time_term: { label: "Spring 2029", year: 2029, season: "Spring" },
  terms: [
    {
      term: { label: "Spring 2027", year: 2027, season: "Spring" },
      units: 9,
      schedule_published: true,
      items: [
        item({ code: "CSC 231", title: "Data Structure", reason: "Required: Major core courses", unlocks: 20 }),
        item({
          code: "MAT 130",
          title: "Linear Algebra",
          reason: "Needed before CSC 313",
          advisories: ["Placement: Mathematics Assessment Test"],
          alternatives: ["MAT 140", "MAT 150", "MAT 160", "MAT 170", "MAT 180"].map((code) => course(code)),
        }),
        item({
          kind: "slot",
          key: "hum-1",
          title: "Humanities electives (your choice)",
          group_label: "Humanities electives",
          suggestions: [course("PHI 101", "Introduction to Philosophy"), course("ART 999", "Not offered then")],
          alternatives: [course("PHI 101", "Introduction to Philosophy"), course("HIS 101"), course("LIT 101")],
        }),
      ],
    },
    {
      term: { label: "Summer 2027", year: 2027, season: "Summer" },
      units: 3,
      schedule_published: false,
      items: [item({ code: "CSC 390", title: "Internship I in Computer Science", locked: true, reason: "You placed this course" })],
    },
  ],
  issues: [
    { severity: "warning", message: "The standard finish would be Spring 2029.", code: null },
    { severity: "warning", message: "CSC 231 is over the unit limit.", code: "CSC 231" },
    { severity: "info", message: "MAT 130: Placement: Mathematics Assessment Test", code: "MAT 130" },
    { severity: "info", message: "CSC 390: Instructor consent", code: "CSC 390" },
  ],
  critical_chain: [course("CSC 231"), course("CSC 313")],
  progress_with_plan: {
    ...group("Computer Science", []),
    units_required: 126,
    completed: 18,
    in_progress: 6,
    planned: 90,
    children: [
      group("Major core courses", ["CSC 231", "MAT 130", "CSC 390"], { completed: 6, planned: 6 }),
      group("Humanities electives", [], { completed: 3, in_progress: 3 }),
    ],
  },
  eligible_next_term: [
    { course: course("CSC 231"), group_key: "core", group_label: "Major core courses", unlocks: 20, advisories: [], take_with: [] },
    { course: course("CSC 337"), group_key: "core", group_label: "Major core courses", unlocks: 0, advisories: [], take_with: [] },
    ...["A", "B", "C", "D", "E", "F", "G", "H"].map((letter) => ({
      course: course(`HUM 10${letter}`),
      group_key: "hum",
      group_label: "Humanities electives",
      unlocks: 0,
      advisories: [],
      take_with: [],
    })),
  ],
  degree_map: {
    columns: [],
    edges: [],
    nodes: [{ key: "CSC 230", code: "CSC 230", title: "Object-Oriented Computing", units: 3, status: "in_progress", column: 0, group_label: null }],
  },
} as unknown as PlanOut;

describe("termDetail", () => {
  const detail = termDetail(plan, "Spring 2027")!;

  it("says what each course counts toward and why it matters", () => {
    const [core, math] = detail.rows;
    expect(core.countsToward).toEqual(["Major core courses"]);
    expect(core.notes).toContain("On the longest prerequisite chain: a delay here delays graduation.");
    expect(core.notes).toContain("Prerequisite for 20 later courses.");
    expect(math.notes).toEqual([
      "Needed before CSC 313.",
      "To confirm: Placement: Mathematics Assessment Test",
      "If it is not available: MAT 140, MAT 150, MAT 160, MAT 170 and 1 more.",
    ]);
  });

  it("names the minor's requirement too when a course counts toward both", () => {
    const withMinor = {
      ...plan,
      minor: { name: "Psychology", progress_with_plan: group("Psychology minor: 5 of 8 courses", ["MAT 130"]) },
    } as unknown as PlanOut;
    const [core, math] = termDetail(withMinor, "Spring 2027")!.rows;
    expect(core.countsToward).toEqual(["Major core courses"]);
    expect(math.countsToward).toEqual(["Major core courses", "Psychology minor: 5 of 8 courses"]);
  });

  it("lists suggestions that fit the term for an open choice", () => {
    const choice = detail.rows[2];
    expect(choice.choice).toBe(true);
    expect(choice.countsToward).toEqual(["Humanities electives"]);
    expect(choice.notes).toEqual([
      "Suggested for the student: PHI 101.",
      "Or one of 2 other courses that fit this term.",
    ]);
  });

  it("keeps only this term's warnings and lists other eligible courses by requirement", () => {
    expect(detail.warnings).toEqual(["CSC 231 is over the unit limit."]);
    expect(detail.otherOptions).toEqual([
      { requirement: "Major core courses", courses: [course("CSC 337")], more: 0 },
      {
        requirement: "Humanities electives",
        courses: ["A", "B", "C", "D", "E", "F"].map((letter) => course(`HUM 10${letter}`)),
        more: 2,
      },
    ]);
  });

  it("has no eligibility list for later terms and no detail for unknown terms", () => {
    const summer = termDetail(plan, "Summer 2027")!;
    expect(summer.otherOptions).toEqual([]);
    expect(summer.rows[0].notes).toEqual(["Placed in this term by the student."]);
    expect(termDetail(plan, "Fall 2040")).toBeNull();
  });
});

describe("the rest of the document", () => {
  const inProgress: AttemptIn[] = [
    { code: "CSC 230", status: "in_progress", term: "2026/2027 Fall" },
    { code: "CSC 132", status: "in_progress", term: "2026/2027 Fall", units: 4 },
  ];

  it("starts with the first planned term", () => {
    expect(defaultTerm(plan)).toBe("Spring 2027");
  });

  it("shows the current term, then every planned term", () => {
    const rows = overviewRows(plan, inProgress);
    expect(rows.map((row) => [row.label, row.current, row.units])).toEqual([
      ["Fall 2026", true, 7],
      ["Spring 2027", false, 9],
      ["Summer 2027", false, 3],
    ]);
    expect(rows[0].courses[0]).toMatchObject({ code: "CSC 230", title: "Object-Oriented Computing" });
  });

  it("marks planned terms that no published schedule confirms (F1.8)", () => {
    const rows = overviewRows(plan, inProgress);
    expect(rows.map((row) => [row.label, row.confirmed])).toEqual([
      ["Fall 2026", true],
      ["Spring 2027", true],
      ["Summer 2027", false],
    ]);
    expect(unconfirmedNote("Summer 2027")).toBe(
      "Course offerings for Summer 2027 are not published yet, so it is not known whether these courses will " +
        "run. Check the schedule in SIS before registering.",
    );
  });

  it("counts what is left of each requirement after the plan", () => {
    expect(requirementRows(plan.progress_with_plan)).toEqual([
      { label: "Major core courses", required: 12, completed: 6, inProgress: 0, planned: 6, left: 0 },
      { label: "Humanities electives", required: 12, completed: 3, inProgress: 3, planned: 0, left: 6 },
      { label: "Total", required: 126, completed: 18, inProgress: 6, planned: 90, left: 12 },
    ]);
  });

  it("puts warnings and checks about other terms in the plan notes", () => {
    expect(planNotes(plan, "Spring 2027")).toEqual({
      warnings: ["The standard finish would be Spring 2029."],
      checks: ["CSC 390: Instructor consent"],
    });
  });

  it("describes the timing, the load and the date plainly", () => {
    expect(isLate(plan)).toBe(true);
    expect(loadSummary(DEFAULT_PREFERENCES)).toBe(
      "Usual load 15 credits a term, at most 18. Summer terms are used only for courses that run in summer only, " +
        "such as internships. Pace: aim for the standard finish.",
    );
    expect(formatDate(new Date(2026, 9, 8))).toBe("8 October 2026");
    expect(formatIsoDate("2026-10-08")).toBe("8 October 2026");
  });

  it("prints on A4 unless another paper size is chosen", () => {
    expect(DEFAULT_PAPER.id).toBe("a4");
    expect(pageStyle(DEFAULT_PAPER)).toBe("@page { size: A4; }");
  });

  it("states that approval is not a promise of courses", () => {
    expect(NOTICE_TEXT).toContain(
      "Even if an advisor reviews, approves or signs this plan, that is not a promise that these classes will be " +
        "scheduled in upcoming terms.",
    );
  });
});
