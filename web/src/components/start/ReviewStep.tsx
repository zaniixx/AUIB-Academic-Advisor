"use client";

import { useState } from "react";
import type { AttemptStatus } from "@/lib/api";
import { STATUS_OPTIONS, normalizeCode, normalizeTerm, pluralize } from "@/lib/format";
import { Alert, AlertIcon, Button, Card } from "@/components/ui";
import { newRow, type EditableRow } from "./rows";

/** F11.4: the student confirms or fixes every course before it is used for planning. */
export function ReviewStep({
  rows,
  unread,
  ignored,
  onChange,
  onBack,
  onNext,
}: {
  rows: EditableRow[];
  unread: { line: number; text: string }[];
  ignored: number;
  onChange: (rows: EditableRow[]) => void;
  onBack: () => void;
  onNext: () => void;
}) {
  const missingStatus = rows.filter((row) => row.status === null).length;
  const update = (id: string, changes: Partial<EditableRow>) =>
    onChange(rows.map((row) => (row.id === id ? { ...row, ...changes } : row)));

  return (
    <Card className="space-y-4">
      <div>
        <h2 className="font-heading text-lg font-semibold">Check your courses</h2>
        <p className="mt-1 text-sm text-text-muted">
          {pluralize(rows.length, "course attempt")} found. Fix anything that looks wrong; nothing here is
          sent anywhere until you plan.
        </p>
      </div>

      {missingStatus > 0 && (
        <Alert tone="warning" title={`Choose a status for ${pluralize(missingStatus, "course")}`}>
          SIS did not show whether these were completed or are still in progress.
        </Alert>
      )}

      {/* A list rather than a table, so every field (especially Status) fits a 380px phone without sideways scrolling. */}
      <ul aria-label="Your course attempts" className="divide-y divide-border border-y border-border">
        {rows.map((row) => (
          <li key={row.id} className="flex flex-wrap items-start gap-x-4 gap-y-2 py-3 text-sm">
            <div className="min-w-0 flex-1 basis-56">
              <p className="font-medium">{row.code}</p>
              {row.title && <p className="text-xs text-text-muted">{row.title}</p>}
              <p className="text-xs text-text-muted">
                {row.term ?? "Term not shown"}
                {row.grade ? ` · Grade ${row.grade}` : ""}
              </p>
              {row.issues.map((issue) => (
                <p key={issue} className="mt-1 flex items-start gap-1 text-xs text-status-warning">
                  <AlertIcon />
                  {issue}
                </p>
              ))}
            </div>
            <div className="flex items-center gap-2">
              <label className="text-xs text-text-muted" htmlFor={`status-${row.id}`}>
                Status<span className="sr-only"> of {row.code}</span>
              </label>
              <select
                id={`status-${row.id}`}
                value={row.status ?? ""}
                onChange={(event) =>
                  update(row.id, { status: (event.target.value || null) as AttemptStatus | null })
                }
                className={`rounded-button border bg-surface px-2 py-1 ${row.status ? "border-border" : "border-status-warning"}`}
              >
                <option value="">Choose…</option>
                {STATUS_OPTIONS.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
              <Button
                variant="ghost"
                onClick={() => onChange(rows.filter((other) => other.id !== row.id))}
                aria-label={`Remove ${row.code}`}
              >
                Remove
              </Button>
            </div>
          </li>
        ))}
      </ul>

      <AddCourse onAdd={(row) => onChange([...rows, row])} />

      {(unread.length > 0 || ignored > 0) && (
        <details className="rounded-card border border-border p-3 text-sm">
          <summary className="cursor-pointer font-medium">
            {unread.length > 0
              ? `${pluralize(unread.length, "line")} mention a course but could not be read`
              : "Page text that was skipped"}
          </summary>
          {unread.length > 0 && (
            <ul className="mt-2 space-y-1">
              {unread.map((line) => (
                <li key={line.line} className="font-mono text-xs">
                  Line {line.line}: {line.text}
                </li>
              ))}
            </ul>
          )}
          <p className="mt-2 text-xs text-text-muted">
            {pluralize(ignored, "other line")} (menus and headings) had no course code and were skipped. If a course
            is missing, add it above.
          </p>
        </details>
      )}

      <div className="flex justify-between gap-2">
        <Button variant="secondary" onClick={onBack}>
          Back
        </Button>
        <Button onClick={onNext} disabled={missingStatus > 0}>
          Next
        </Button>
      </div>
    </Card>
  );
}

function AddCourse({ onAdd }: { onAdd: (row: EditableRow) => void }) {
  const [code, setCode] = useState("");
  const [term, setTerm] = useState("");
  const [status, setStatus] = useState<AttemptStatus>("completed");
  const [error, setError] = useState<string | null>(null);

  function add() {
    const normalCode = normalizeCode(code);
    const normalTerm = term.trim() ? normalizeTerm(term) : null;
    if (!normalCode) return setError("Enter a course code like CSC 231.");
    if (term.trim() && !normalTerm) return setError("Enter the term like Fall 2025.");
    onAdd(newRow(normalCode, normalTerm, status));
    setCode("");
    setTerm("");
    setError(null);
  }

  return (
    <fieldset className="space-y-2 rounded-card border border-dashed border-border p-3">
      <legend className="px-1 text-sm font-medium">Add a course</legend>
      <div className="flex flex-wrap items-end gap-2">
        <label className="text-sm">
          <span className="block text-text-muted">Code</span>
          <input
            value={code}
            onChange={(event) => setCode(event.target.value)}
            placeholder="CSC 231"
            className="w-28 rounded-button border border-border bg-surface px-2 py-1"
          />
        </label>
        <label className="text-sm">
          <span className="block text-text-muted">Term (optional)</span>
          <input
            value={term}
            onChange={(event) => setTerm(event.target.value)}
            placeholder="Fall 2025"
            className="w-32 rounded-button border border-border bg-surface px-2 py-1"
          />
        </label>
        <label className="text-sm">
          <span className="block text-text-muted">Status</span>
          <select
            value={status}
            onChange={(event) => setStatus(event.target.value as AttemptStatus)}
            className="rounded-button border border-border bg-surface px-2 py-1"
          >
            {STATUS_OPTIONS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <Button variant="secondary" onClick={add}>
          Add
        </Button>
      </div>
      {error && <p className="text-sm text-status-blocked">{error}</p>}
    </fieldset>
  );
}
