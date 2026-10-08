import { describe, expect, it } from "vitest";
import { DEFAULT_PREFERENCES, parseProfile, toStudent } from "./profile";

const saved = {
  version: 1,
  programId: "casc-computer-science",
  attempts: [{ code: "CSC 101", status: "completed", term: "Fall 2025", grade: "A", units: 3 }],
  preferences: { interests: ["ai"] },
  updatedAt: "2026-10-08T10:00:00.000Z",
};

describe("parseProfile", () => {
  it("reads a saved profile and fills in missing preferences with defaults", () => {
    const profile = parseProfile(JSON.stringify(saved));
    expect(profile?.programId).toBe("casc-computer-science");
    expect(profile?.preferences.interests).toEqual(["ai"]);
    expect(profile?.preferences.max_units).toBe(DEFAULT_PREFERENCES.max_units);
  });

  it("ignores anything that is not a valid profile", () => {
    expect(parseProfile(null)).toBeNull();
    expect(parseProfile("not json")).toBeNull();
    expect(parseProfile(JSON.stringify({ ...saved, version: 99 }))).toBeNull();
    expect(parseProfile(JSON.stringify({ ...saved, attempts: "CSC 101" }))).toBeNull();
  });
});

describe("toStudent", () => {
  it("builds the request the planner expects", () => {
    const profile = parseProfile(JSON.stringify(saved));
    expect(profile).not.toBeNull();
    const student = toStudent(profile!);
    expect(student.program_id).toBe("casc-computer-science");
    expect(student.attempts).toHaveLength(1);
  });
});
