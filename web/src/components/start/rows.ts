import type { AttemptIn, AttemptStatus, HistoryRow } from "@/lib/api";

/** One editable line of the "check your courses" table (F11.4). */
export interface EditableRow {
  id: string;
  code: string;
  title: string | null;
  term: string | null;
  grade: string | null;
  units: number | null;
  status: AttemptStatus | null;
  issues: string[];
}

let counter = 0;
const nextId = () => `row-${++counter}`;

export function fromHistory(rows: HistoryRow[]): EditableRow[] {
  return rows.map((row) => ({
    id: nextId(),
    code: row.code,
    title: row.title ?? null,
    term: row.term ?? null,
    grade: row.grade ?? null,
    units: row.units ?? null,
    status: row.status ?? null,
    issues: row.issues,
  }));
}

export function fromAttempts(attempts: AttemptIn[]): EditableRow[] {
  return attempts.map((attempt) => ({
    id: nextId(),
    code: attempt.code,
    title: null,
    term: attempt.term ?? null,
    grade: attempt.grade ?? null,
    units: attempt.units ?? null,
    status: attempt.status,
    issues: [],
  }));
}

export function newRow(code: string, term: string | null, status: AttemptStatus): EditableRow {
  return { id: nextId(), code, title: null, term, grade: null, units: null, status, issues: [] };
}

export function toAttempts(rows: EditableRow[]): AttemptIn[] {
  return rows
    .filter((row): row is EditableRow & { status: AttemptStatus } => row.status !== null)
    .map((row) => ({
      code: row.code,
      status: row.status,
      term: row.term,
      grade: row.grade,
      units: row.units,
    }));
}
