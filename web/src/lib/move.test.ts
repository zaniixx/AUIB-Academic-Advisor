import { describe, expect, it } from "vitest";
import type { MoveOption } from "./api";
import { graduationEffect, otherShifts } from "./move";

const term = (label: string) => {
  const [season, year] = label.split(" ");
  return { label, year: Number(year), season: season as "Spring" | "Summer" | "Fall" };
};

function option(changes: Partial<MoveOption>): MoveOption {
  return {
    term: term("Spring 2029"),
    valid: true,
    problems: [],
    graduation_term: term("Spring 2029"),
    terms_later: 0,
    shifts: [],
    ...changes,
  };
}

describe("graduationEffect", () => {
  it("says whether graduation moves", () => {
    expect(graduationEffect(option({}))).toBe("Graduation stays Spring 2029");
    expect(graduationEffect(option({ graduation_term: term("Fall 2029"), terms_later: 1 }))).toBe(
      "Graduation Fall 2029, 1 term later",
    );
    expect(graduationEffect(option({ graduation_term: term("Fall 2028"), terms_later: -1 }))).toBe(
      "Graduation Fall 2028, 1 term earlier",
    );
    expect(graduationEffect(option({ graduation_term: null, valid: false }))).toBe("Not checked");
  });
});

describe("otherShifts", () => {
  it("lists the courses that move along with the one moved", () => {
    const moved = option({
      shifts: [
        { code: "CSC 313", title: "", before: term("Fall 2027"), after: term("Spring 2029") },
        { code: "CSC 422", title: "", before: term("Fall 2028"), after: term("Fall 2029") },
      ],
    });
    expect(otherShifts(moved, "CSC 313")).toEqual(["CSC 422 → Fall 2029"]);
  });
});
