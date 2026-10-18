import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { OWNER_KEY, auibAddress, claimBrowserData, nameForBox } from "./auth";
import { PROFILE_KEY, SCENARIOS_KEY } from "./profile";

/** A browser's localStorage, enough for these tests. */
function fakeStorage(): Storage {
  const items = new Map<string, string>();
  return {
    get length() {
      return items.size;
    },
    clear: () => items.clear(),
    getItem: (key) => items.get(key) ?? null,
    key: (index) => [...items.keys()][index] ?? null,
    removeItem: (key) => void items.delete(key),
    setItem: (key, value) => void items.set(key, String(value)),
  };
}

describe("a shared computer (F9.1)", () => {
  let storage: Storage;

  beforeEach(() => {
    storage = fakeStorage();
    vi.stubGlobal("window", { localStorage: storage, addEventListener: () => undefined, removeEventListener: () => undefined });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("keeps a student's own courses and plan when they sign in again", () => {
    claimBrowserData("a@auib.edu.iq");
    storage.setItem(PROFILE_KEY, "{}");
    claimBrowserData("a@auib.edu.iq");
    expect(storage.getItem(PROFILE_KEY)).toBe("{}");
  });

  it("deletes the previous student's courses and saved plans when someone else signs in", () => {
    claimBrowserData("a@auib.edu.iq");
    storage.setItem(PROFILE_KEY, "{}");
    storage.setItem(SCENARIOS_KEY, "[]");
    claimBrowserData("b@auib.edu.iq");
    expect(storage.getItem(PROFILE_KEY)).toBeNull();
    expect(storage.getItem(SCENARIOS_KEY)).toBeNull();
    expect(storage.getItem(OWNER_KEY)).toBe("b@auib.edu.iq");
  });

  it("lets the first student to sign in keep data saved before sign-in existed", () => {
    storage.setItem(PROFILE_KEY, "{}");
    claimBrowserData("a@auib.edu.iq");
    expect(storage.getItem(PROFILE_KEY)).toBe("{}");
  });
});

describe("the sign-in address (F9.1)", () => {
  it("adds @auib.edu.iq to the name the student types", () => {
    expect(auibAddress("  Ali.Hassan ")).toEqual({ address: "ali.hassan@auib.edu.iq" });
  });

  it("keeps only the name when a full AUIB address is pasted or autofilled", () => {
    expect(nameForBox("ali.hassan@AUIB.edu.iq")).toBe("ali.hassan");
    expect(auibAddress("ali.hassan@auib.edu.iq")).toEqual({ address: "ali.hassan@auib.edu.iq" });
  });

  it("explains an empty box, another domain and characters an address cannot have", () => {
    expect(auibAddress("")).toEqual({ problem: "Type the first part of your AUIB email address." });
    expect(auibAddress("someone@gmail.com")).toEqual({
      problem: "Only AUIB addresses can sign in: type the part before @auib.edu.iq.",
    });
    expect(auibAddress("ali hassan")).toHaveProperty("problem");
    expect(auibAddress(".ali")).toHaveProperty("problem");
  });
});
