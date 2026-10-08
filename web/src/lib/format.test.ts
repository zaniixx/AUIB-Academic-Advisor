import { describe, expect, it } from "vitest";
import { normalizeCode, normalizeTerm, percent, pluralize, units } from "./format";

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
  it("formats units and percentages", () => {
    expect(units(3)).toBe("3");
    expect(units(0.5)).toBe("0.5");
    expect(percent(30, 126)).toBe(24);
    expect(percent(5, 0)).toBe(0);
    expect(pluralize(1, "course")).toBe("1 course");
    expect(pluralize(2, "course")).toBe("2 courses");
  });
});
