import type { AttemptStatus } from "./api";

export function units(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

export function percent(part: number, whole: number): number {
  if (whole <= 0) return 0;
  return Math.max(0, Math.min(100, Math.round((part / whole) * 100)));
}

export const STATUS_LABELS: Record<AttemptStatus, string> = {
  completed: "Completed",
  in_progress: "In progress",
  failed: "Failed",
  withdrawn: "Withdrawn",
  incomplete: "Incomplete",
  not_counted: "Not counted",
};

export const STATUS_OPTIONS = Object.entries(STATUS_LABELS) as [AttemptStatus, string][];

/** "CSC 231" from inputs like "csc231" or "CSC-231"; null if it is not a course code. */
export function normalizeCode(raw: string): string | null {
  const match = raw.trim().match(/^([A-Za-z]{2,4})\s*-?\s*(\d{3}[A-Za-z]?|\d[Xx]{2}|[Xx]{3})$/);
  return match ? `${match[1].toUpperCase()} ${match[2].toUpperCase()}` : null;
}

/** "Fall 2027" from "fall 2027", "2027 Fall" or "2027/2028 Fall"; null if unrecognised. */
export function normalizeTerm(raw: string): string | null {
  const text = raw.trim();
  const academic = text.match(/^(\d{4})\s*[/-]\s*\d{4}\s+(fall|spring|summer)$/i);
  if (academic) {
    const season = capitalize(academic[2]);
    const year = season === "Fall" ? Number(academic[1]) : Number(academic[1]) + 1;
    return `${season} ${year}`;
  }
  const seasonFirst = text.match(/^(fall|spring|summer)\s+(\d{4})$/i);
  if (seasonFirst) return `${capitalize(seasonFirst[1])} ${seasonFirst[2]}`;
  const yearFirst = text.match(/^(\d{4})\s+(fall|spring|summer)$/i);
  if (yearFirst) return `${capitalize(yearFirst[2])} ${yearFirst[1]}`;
  return null;
}

function capitalize(word: string): string {
  return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
}

export function pluralize(count: number, singular: string, plural = `${singular}s`): string {
  return `${count} ${count === 1 ? singular : plural}`;
}
