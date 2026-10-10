import { describe, expect, it } from "vitest";
import type { ScenarioPlan } from "./api";
import { termRows, versusFirst } from "./compare";

function plan(terms: [string, number][]): ScenarioPlan {
  return {
    program_name: "Computer Science",
    minor_name: null,
    catalog_year: null,
    graduation_term: null,
    on_time_term: null,
    semesters_vs_first: null,
    percent_complete: 0,
    counted_credits: 0,
    credits_left: 0,
    planned_credits: 0,
    warnings: 0,
    terms: terms.map(([label, units]) => {
      const [season, year] = label.split(" ");
      return {
        term: { label, year: Number(year), season: season as "Spring" | "Summer" | "Fall" },
        units,
        built: false,
        courses: [],
        open_choices: [],
      };
    }),
  };
}

describe("termRows", () => {
  it("has a row for every term any plan uses, in calendar order", () => {
    const rows = termRows([
      plan([["Spring 2027", 15], ["Fall 2027", 15]]),
      plan([["Spring 2027", 18], ["Summer 2027", 6]]),
      null,
    ]);
    expect(rows.map((row) => row.label)).toEqual(["Spring 2027", "Summer 2027", "Fall 2027"]);
    expect(rows[1].cells.map((cell) => cell?.units ?? null)).toEqual([null, 6, null]);
    expect(rows[2].cells[0]?.units).toBe(15);
  });
});

describe("versusFirst", () => {
  it("words the difference from the first plan", () => {
    expect(versusFirst(null)).toBe("Your current plan");
    expect(versusFirst(0)).toBe("Same finish");
    expect(versusFirst(1)).toBe("1 semester later");
    expect(versusFirst(-2)).toBe("2 semesters sooner");
  });
});
