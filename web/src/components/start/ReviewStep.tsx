"use client";

import { useState } from "react";
import type { AttemptStatus } from "@/lib/api";
import { STATUS_OPTIONS, normalizeCode, normalizeTerm, pluralize } from "@/lib/format";
import { ArrowLeftIcon, ArrowRightIcon, ListChecksIcon, PlusIcon, TrashIcon } from "@/components/icons";
import { Alert, AlertIcon, Button, Disclosure, FIELD, Select } from "@/components/ui";
import { StepCard } from "./StepCard";
import { newRow, type EditableRow } from "./rows";

// A dot beside each course echoes its status at a glance; the select beside it carries the word.
const STATUS_DOT: Record<AttemptStatus, string> = {
  completed: "bg-status-done",
  in_progress: "bg-status-in-progress",
  failed: "bg-status-blocked",
  withdrawn: "bg-border-strong",
  incomplete: "bg-status-warning",
  not_counted: "bg-border-strong",
};

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
  const counts = STATUS_OPTIONS.map(([value, label]) => [label, rows.filter((row) => row.status === value).length] as const).filter(
    ([, count]) => count > 0,
  );

  return (
    <StepCard
      icon={<ListChecksIcon />}
      title="Check your courses"
      description={
        <>
          {pluralize(rows.length, "course attempt")} found. Fix anything that looks wrong; nothing here is sent
          anywhere until you plan.
        </>
      }
      footer={
        <>
          <Button variant="secondary" onClick={onBack}>
            <ArrowLeftIcon className="h-4 w-4" />
            Back
          </Button>
          <Button onClick={onNext} disabled={missingStatus > 0}>
            Next
            <ArrowRightIcon className="h-4 w-4" />
          </Button>
        </>
      }
    >
      {counts.length > 0 && (
        <ul aria-label="Courses by status" className="flex flex-wrap gap-2">
          {counts.map(([label, count]) => (
            <li key={label} className="rounded-full bg-surface-sunken px-3 py-1 text-sm">
              <span className="font-semibold">{count}</span> <span className="text-text-muted">{label.toLowerCase()}</span>
            </li>
          ))}
        </ul>
      )}

      {missingStatus > 0 && (
        <Alert tone="warning" title={`Choose a status for ${pluralize(missingStatus, "course")}`}>
          SIS did not show whether these were completed or are still in progress.
        </Alert>
      )}

      {/* A list rather than a table, so every field (especially Status) fits a 380px phone without sideways scrolling. */}
      <ul aria-label="Your course attempts" className="space-y-2">
        {rows.map((row) => (
          <li
            key={row.id}
            className={`flex flex-wrap items-center gap-x-4 gap-y-3 rounded-xl border p-3 text-sm transition ${
              row.status ? "border-border bg-surface" : "border-status-warning/60 bg-status-warning/5"
            }`}
          >
            <div className="flex min-w-0 flex-1 basis-56 items-start gap-3">
              <span
                aria-hidden
                className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${row.status ? STATUS_DOT[row.status] : "bg-status-warning"}`}
              />
              <div className="min-w-0">
                <p>
                  <span className="font-semibold">{row.code}</span>
                  {row.title && <span className="text-text-muted"> · {row.title}</span>}
                </p>
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
            </div>
            <div className="flex items-center gap-2">
              <label className="text-xs text-text-muted" htmlFor={`status-${row.id}`}>
                Status<span className="sr-only"> of {row.code}</span>
              </label>
              <Select
                id={`status-${row.id}`}
                value={row.status ?? ""}
                onChange={(event) => update(row.id, { status: (event.target.value || null) as AttemptStatus | null })}
                wrapperClassName="w-40"
                className={`min-h-10 py-1.5 text-sm ${row.status ? "" : "border-status-warning"}`}
              >
                <option value="">Choose…</option>
                {STATUS_OPTIONS.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </Select>
              <Button
                variant="quiet"
                size="sm"
                className="h-10 w-10 px-0"
                onClick={() => onChange(rows.filter((other) => other.id !== row.id))}
                aria-label={`Remove ${row.code}`}
                title="Remove"
              >
                <TrashIcon className="h-4 w-4" />
              </Button>
            </div>
          </li>
        ))}
      </ul>

      <AddCourse onAdd={(row) => onChange([...rows, row])} />

      {(unread.length > 0 || ignored > 0) && (
        <Disclosure
          className="rounded-xl border border-border px-4 py-1 text-sm"
          summary={
            unread.length > 0
              ? `${pluralize(unread.length, "line")} mention a course but could not be read`
              : "Page text that was skipped"
          }
        >
          <div className="space-y-2 pb-3">
            {unread.length > 0 && (
              <ul className="space-y-1">
                {unread.map((line) => (
                  <li key={line.line} className="rounded-lg bg-surface-sunken px-2 py-1 font-mono text-xs">
                    Line {line.line}: {line.text}
                  </li>
                ))}
              </ul>
            )}
            <p className="text-xs text-text-muted">
              {pluralize(ignored, "other line")} (menus and headings) had no course code and were skipped. If a
              course is missing, add it above.
            </p>
          </div>
        </Disclosure>
      )}
    </StepCard>
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
    <fieldset className="space-y-3 rounded-xl border border-dashed border-border-strong p-4">
      <legend className="px-1 text-sm font-semibold">Add a missing course</legend>
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm">
          <span className="mb-1 block text-text-muted">Code</span>
          <input
            value={code}
            onChange={(event) => setCode(event.target.value)}
            placeholder="CSC 231"
            className={`${FIELD} w-32`}
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-text-muted">Term (optional)</span>
          <input
            value={term}
            onChange={(event) => setTerm(event.target.value)}
            placeholder="Fall 2025"
            className={`${FIELD} w-36`}
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-text-muted">Status</span>
          <Select
            value={status}
            onChange={(event) => setStatus(event.target.value as AttemptStatus)}
            wrapperClassName="w-40"
          >
            {STATUS_OPTIONS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
        </label>
        <Button variant="secondary" onClick={add}>
          <PlusIcon className="h-4 w-4" />
          Add
        </Button>
      </div>
      {error && (
        <p role="alert" className="text-sm text-status-blocked">
          {error}
        </p>
      )}
    </fieldset>
  );
}
