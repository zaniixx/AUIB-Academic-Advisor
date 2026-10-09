import { describe, expect, it } from "vitest";
import { credits, joinTermOptions, normalizeCode, normalizeTerm, percent, pluralize, units } from "./format";

describe("normalizeCode", () => {
  it.each([
    ["csc231", "CSC 231"],
    ["CSC-231", "CSC 231"],
    [" bio 101l ", "BIO 101L"],
    ["HUM XXX", "HUM XXX"],
  ])("reads %s as %s", (raw, expected) => {
    expect(normalizeCode(raw)).toBe(expected);
  });

  it("rejects text that is not a course code", () => {
    expect(normalizeCode("Introduction")).toBeNull();
    expect(normalizeCode("ASP 6")).toBeNull();
  });
});

describe("normalizeTerm", () => {
  it.each([
    ["fall 2027", "Fall 2027"],
    ["2027 Spring", "Spring 2027"],
    ["2024/2025 Fall", "Fall 2024"],
    ["2024/2025 Spring", "Spring 2025"],
  ])("reads %s as %s", (raw, expected) => {
    expect(normalizeTerm(raw)).toBe(expected);
  });

  it("rejects unknown terms", () => {
    expect(normalizeTerm("Winter 2027")).toBeNull();
  });
});

describe("numbers", () => {
  it("formats credits and percentages", () => {
    expect(units(3)).toBe("3");
    expect(units(0.5)).toBe("0.5");
    expect(credits(3)).toBe("3 credits");
    expect(credits(1)).toBe("1 credit");
    expect(credits(1.5)).toBe("1.5 credits");
    expect(percent(30, 126)).toBe(24);
    expect(percent(5, 0)).toBe(0);
    expect(pluralize(1, "course")).toBe("1 course");
    expect(pluralize(2, "course")).toBe("2 courses");
  });
});

describe("join terms", () => {
  it("lists terms newest first, from next year back to 2010", () => {
    const terms = joinTermOptions(new Date(2026, 9, 9));
    expect(terms.slice(0, 4)).toEqual(["Fall 2027", "Summer 2027", "Spring 2027", "Fall 2026"]);
    expect(terms.at(-1)).toBe("Spring 2010");
  });
});
