import { describe, expect, it } from "vitest";
import { DEFAULT_PREFERENCES, freshPreferences, parseProfile, parseScenarios, toScenarioIn, toStudent } from "./profile";

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

describe("scenarios", () => {
  const scenario = {
    id: "a",
    name: "Summers",
    savedAt: "2026-10-08T10:00:00.000Z",
    programId: "casc-computer-science",
    minorId: null,
    entryTerm: null,
    programVersion: null,
    preferences: { include_summer: true },
  };

  it("reads saved scenarios, at most three, with default preferences", () => {
    const parsed = parseScenarios(JSON.stringify([scenario, scenario, scenario, scenario, { name: "broken" }]));
    expect(parsed).toHaveLength(3);
    expect(parsed[0].preferences.include_summer).toBe(true);
    expect(parsed[0].preferences.max_units).toBe(DEFAULT_PREFERENCES.max_units);
    expect(parseScenarios("not json")).toEqual([]);
  });

  it("starts a plan in another major without the old plan's placements", () => {
    const fresh = freshPreferences({ ...DEFAULT_PREFERENCES, max_units: 15, locks: [{ code: "CSC 231", term: "Fall 2027" }] });
    expect(fresh.locks).toEqual([]);
    expect(fresh.max_units).toBe(15);
  });

  it("turns a scenario into the planner's request", () => {
    const request = toScenarioIn("Summers", parseScenarios(JSON.stringify([scenario]))[0]);
    expect(request).toMatchObject({ name: "Summers", program_id: "casc-computer-science", minor_id: null });
  });
});
