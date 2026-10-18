import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { OWNER_KEY, claimBrowserData } from "./auth";
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
