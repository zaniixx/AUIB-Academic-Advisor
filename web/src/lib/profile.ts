/**
 * The guest's planning profile (F11). It lives only in this browser's storage and is
 * sent to the API with each planning request; the server never stores it (F11.5).
 */
import type { AttemptIn, PreferencesIn, ScenarioIn, StudentIn } from "./api";

export const PROFILE_KEY = "auib-advisor:profile";
export const SCENARIOS_KEY = "auib-advisor:scenarios";
/** F6.2: how many plans the student can save to compare with their current one. */
export const MAX_SCENARIOS = 3;
const VERSION = 1;

export interface Profile {
  version: typeof VERSION;
  programId: string;
  /** Optional; profiles saved before minors existed have none. */
  minorId?: string | null;
  /** When the student joined AUIB ("Fall 2025"); empty means "work it out from the history" (F0.4). */
  entryTerm?: string | null;
  /** A version of the major the student follows with the registrar's approval; empty means automatic. */
  programVersion?: string | null;
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
  built_terms: [],
  exclude: [],
  include: [],
  interests: [],
  goal: null,
  workload: "balanced",
  plans: null,
  avoid: [],
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

/** "Clear my data": the profile and every saved scenario. */
export function clearProfile(): void {
  storage()?.removeItem(PROFILE_KEY);
  storage()?.removeItem(SCENARIOS_KEY);
  notify();
}

export function toStudent(profile: Profile): StudentIn {
  return {
    program_id: profile.programId,
    minor_id: profile.minorId ?? null,
    entry_term: profile.entryTerm || null,
    program_version: profile.programVersion || null,
    attempts: profile.attempts,
    preferences: profile.preferences,
  };
}

/** Change when the student joined, or which version of the major they follow (F0.4). */
export function withRequirements(
  profile: Profile,
  changes: Partial<Pick<Profile, "entryTerm" | "programVersion">>,
): Profile {
  return saveProfile({ ...profile, ...changes });
}

export function withPreferences(profile: Profile, changes: Partial<PreferencesIn>): Profile {
  return saveProfile({ ...profile, preferences: { ...profile.preferences, ...changes } });
}

/**
 * F6.2: a plan saved to compare with others. It keeps a profile's programs and plan choices
 * (load, pace, placed courses, finished terms); the course history stays the profile's, so every
 * scenario uses the student's latest courses.
 */
export interface Scenario {
  id: string;
  name: string;
  savedAt: string;
  programId: string;
  minorId: string | null;
  entryTerm: string | null;
  programVersion: string | null;
  preferences: PreferencesIn;
}

function isScenario(value: unknown): value is Scenario {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<Scenario>;
  return (
    typeof candidate.id === "string" &&
    typeof candidate.name === "string" &&
    typeof candidate.programId === "string" &&
    typeof candidate.preferences === "object" &&
    candidate.preferences !== null
  );
}

export function parseScenarios(raw: string | null): Scenario[] {
  if (!raw) return [];
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter(isScenario)
      .slice(0, MAX_SCENARIOS)
      .map((scenario) => ({ ...scenario, preferences: { ...DEFAULT_PREFERENCES, ...scenario.preferences } }));
  } catch {
    return [];
  }
}

let cachedScenariosRaw: string | null | undefined;
let cachedScenarios: Scenario[] = [];

/** The saved scenarios; the same array until they change, as useSyncExternalStore needs. */
export function scenariosSnapshot(): Scenario[] {
  const raw = storage()?.getItem(SCENARIOS_KEY) ?? null;
  if (raw !== cachedScenariosRaw) {
    cachedScenariosRaw = raw;
    cachedScenarios = parseScenarios(raw);
  }
  return cachedScenarios;
}

function writeScenarios(scenarios: Scenario[]): void {
  storage()?.setItem(SCENARIOS_KEY, JSON.stringify(scenarios));
  notify();
}

/** A scenario holding ``choices`` (a profile, or a profile moved to another major) under ``name``. */
export function makeScenario(
  choices: Pick<Profile, "programId" | "minorId" | "entryTerm" | "programVersion" | "preferences">,
  name: string,
): Scenario {
  return {
    id: `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
    name: name.trim().slice(0, 60) || "Saved plan",
    savedAt: new Date().toISOString(),
    programId: choices.programId,
    minorId: choices.minorId ?? null,
    entryTerm: choices.entryTerm ?? null,
    programVersion: choices.programVersion ?? null,
    preferences: choices.preferences,
  };
}

/** Save ``scenario`` after the others; false when there are already MAX_SCENARIOS. */
export function saveScenario(scenario: Scenario): boolean {
  const saved = scenariosSnapshot();
  if (saved.length >= MAX_SCENARIOS) return false;
  writeScenarios([...saved, scenario]);
  return true;
}

export function removeScenario(id: string): void {
  writeScenarios(scenariosSnapshot().filter((scenario) => scenario.id !== id));
}

/** Make a scenario the student's plan: its programs and choices, with the profile's courses. */
export function applyScenario(profile: Profile, scenario: Scenario): Profile {
  return saveProfile({
    ...profile,
    programId: scenario.programId,
    minorId: scenario.minorId,
    entryTerm: scenario.entryTerm,
    programVersion: scenario.programVersion,
    preferences: scenario.preferences,
  });
}

export function toScenarioIn(
  name: string,
  choices: Pick<Profile, "programId" | "minorId" | "entryTerm" | "programVersion" | "preferences">,
): ScenarioIn {
  return {
    name: name.slice(0, 60) || "Plan",
    program_id: choices.programId,
    minor_id: choices.minorId ?? null,
    entry_term: choices.entryTerm || null,
    program_version: choices.programVersion || null,
    preferences: choices.preferences,
  };
}

/**
 * F6.3: the student's settings for a plan in another major. Courses they placed, terms they built
 * and courses they chose or ruled out belong to the current major's plan, so they are left behind.
 */
export function freshPreferences(preferences: PreferencesIn): PreferencesIn {
  return { ...preferences, locks: [], built_terms: [], include: [], exclude: [] };
}
