/**
 * The guest's planning profile (F11). It lives only in this browser's storage and is
 * sent to the API with each planning request; the server never stores it (F11.5).
 */
import type { AttemptIn, PreferencesIn, StudentIn } from "./api";

export const PROFILE_KEY = "auib-advisor:profile";
const VERSION = 1;

export interface Profile {
  version: typeof VERSION;
  programId: string;
  /** Optional; profiles saved before minors existed have none. */
  minorId?: string | null;
  attempts: AttemptIn[];
  preferences: PreferencesIn;
  updatedAt: string;
}

export const DEFAULT_PREFERENCES: PreferencesIn = {
  preferred_units: 15,
  max_units: 18,
  pace: "on_time",
  include_summer: false,
  summer_max_units: 6,
  locks: [],
  exclude: [],
  include: [],
  interests: [],
  goal: null,
  workload: "balanced",
};

function storage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null; // storage can be blocked (private mode, strict settings)
  }
}

export function isProfile(value: unknown): value is Profile {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<Profile>;
  return (
    candidate.version === VERSION &&
    typeof candidate.programId === "string" &&
    Array.isArray(candidate.attempts) &&
    typeof candidate.preferences === "object" &&
    candidate.preferences !== null
  );
}

export function parseProfile(raw: string | null): Profile | null {
  if (!raw) return null;
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!isProfile(parsed)) return null;
    return { ...parsed, preferences: { ...DEFAULT_PREFERENCES, ...parsed.preferences } };
  } catch {
    return null;
  }
}

export function loadProfile(): Profile | null {
  return parseProfile(storage()?.getItem(PROFILE_KEY) ?? null);
}

// A tiny external store so components re-render when the profile changes, in this tab
// (save/clear below) or another one (the "storage" event).
const listeners = new Set<() => void>();
let cachedRaw: string | null | undefined;
let cachedProfile: Profile | null = null;

export function subscribeProfile(listener: () => void): () => void {
  listeners.add(listener);
  window.addEventListener("storage", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", listener);
  };
}

export function profileSnapshot(): Profile | null {
  const raw = storage()?.getItem(PROFILE_KEY) ?? null;
  if (raw !== cachedRaw) {
    cachedRaw = raw;
    cachedProfile = parseProfile(raw);
  }
  return cachedProfile;
}

function notify() {
  listeners.forEach((listener) => listener());
}

export function saveProfile(profile: Omit<Profile, "version" | "updatedAt">): Profile {
  const full: Profile = { ...profile, version: VERSION, updatedAt: new Date().toISOString() };
  storage()?.setItem(PROFILE_KEY, JSON.stringify(full));
  notify();
  return full;
}

export function clearProfile(): void {
  storage()?.removeItem(PROFILE_KEY);
  notify();
}

export function toStudent(profile: Profile): StudentIn {
  return {
    program_id: profile.programId,
    minor_id: profile.minorId ?? null,
    attempts: profile.attempts,
    preferences: profile.preferences,
  };
}

export function withPreferences(profile: Profile, changes: Partial<PreferencesIn>): Profile {
  return saveProfile({ ...profile, preferences: { ...profile.preferences, ...changes } });
}
