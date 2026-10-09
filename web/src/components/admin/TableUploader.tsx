"use client";

import { useId, useState, type ReactNode } from "react";
import { ApiError, type TableUpload, type UploadRow } from "@/lib/api";
import { CheckIcon, ClipboardIcon, FileIcon } from "@/components/icons";
import { Alert, Button, FIELD } from "@/components/ui";

/** What a preview or a save answered: counts, the columns it understood, and rows worth showing. */
export interface UploadResult {
  applied: boolean;
  counts: Record<string, number>;
  columns: string[];
  ignored_columns: string[];
  rows: UploadRow[];
}

export function errorText(caught: unknown, fallback = "The change was not saved."): string {
  return caught instanceof ApiError ? caught.message : fallback;
}

const ACTION_LABELS: Record<string, string> = {
  create: "New",
  update: "Changes",
  unchanged: "No change",
  error: "Problem",
  skip: "Skipped",
};

const ACTION_STYLES: Record<string, string> = {
  create: "bg-status-done/8 text-status-done",
  update: "bg-status-in-progress/8 text-status-in-progress",
  error: "bg-status-blocked/8 text-status-blocked",
  skip: "bg-status-warning/8 text-status-warning",
};

/** A file's bytes as base64, converted in chunks so large files do not overflow the call stack. */
export async function fileToBase64(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  for (let start = 0; start < bytes.length; start += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(start, start + 0x8000));
  }
  return btoa(binary);
}

async function fileToUpload(file: File): Promise<Omit<TableUpload, "dry_run">> {
  if (/\.xlsx$/i.test(file.name)) return { xlsx_base64: await fileToBase64(file) };
  return { text: await file.text() };
}

/**
 * Paste cells from Excel or Google Sheets, or choose a .csv or .xlsx file; "Check" previews every
 * row without saving, and "Save" applies the same upload.
 */
export function TableUploader({
  columnsHelp,
  saveLabel,
  extra,
  disabled = false,
  onSubmit,
  summary,
}: {
  columnsHelp: ReactNode;
  saveLabel: (result: UploadResult) => string;
  extra?: ReactNode;
  disabled?: boolean;
  onSubmit: (upload: TableUpload, dryRun: boolean) => Promise<UploadResult>;
  summary: (result: UploadResult) => ReactNode;
}) {
  const pasteId = useId();
  const fileId = useId();
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(dryRun: boolean) {
    setBusy(true);
    setError(null);
    try {
      const upload = file ? await fileToUpload(file) : { text };
      setResult(await onSubmit({ ...upload, dry_run: dryRun }, dryRun));
    } catch (caught) {
      setError(errorText(caught, "The table could not be read."));
    } finally {
      setBusy(false);
    }
  }

  const ready = !disabled && (file !== null || text.trim().length > 0);
  const blocked = result !== null && (result.counts.error ?? 0) > 0;

  return (
    <div className="space-y-4">
      {extra}
      <div className="grid gap-4 lg:grid-cols-[1fr_16rem]">
        <div className="space-y-2">
          <label htmlFor={pasteId} className="flex items-center gap-2 text-sm font-semibold">
            <ClipboardIcon className="h-4 w-4 text-primary" />
            Paste from a spreadsheet, or type CSV
          </label>
          <textarea
            id={pasteId}
            value={text}
            disabled={file !== null}
            onChange={(event) => {
              setText(event.target.value);
              setResult(null);
            }}
            rows={7}
            placeholder={"Select the cells in Excel or Google Sheets (with the header row), copy, and paste here."}
            className={`${FIELD} resize-y font-mono text-xs leading-relaxed disabled:opacity-50`}
          />
        </div>
        <div className="space-y-2">
          <label htmlFor={fileId} className="flex items-center gap-2 text-sm font-semibold">
            <FileIcon className="h-4 w-4 text-primary" />
            Or choose a file
          </label>
          <input
            id={fileId}
            type="file"
            accept=".csv,.tsv,.txt,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            onChange={(event) => {
              setFile(event.target.files?.[0] ?? null);
              setResult(null);
            }}
            className="block w-full cursor-pointer rounded-field border border-dashed border-border-strong bg-surface-sunken p-3 text-sm file:me-3 file:cursor-pointer file:rounded-button file:border-0 file:bg-primary file:px-3 file:py-1.5 file:text-primary-contrast"
          />
          <p className="text-xs text-text-muted">.csv, .tsv or .xlsx (the first sheet is read).</p>
        </div>
      </div>
      <div className="rounded-xl bg-surface-sunken p-3 text-xs leading-relaxed text-text-muted">{columnsHelp}</div>

      <div className="flex flex-wrap gap-2">
        <Button variant="secondary" disabled={!ready || busy} onClick={() => run(true)}>
          {busy ? "Reading…" : "Check"}
        </Button>
        {result && !result.applied && (
          <Button disabled={busy || blocked} onClick={() => run(false)}>
            <CheckIcon className="h-4 w-4" />
            {saveLabel(result)}
          </Button>
        )}
      </div>

      {error && <Alert tone="error">{error}</Alert>}
      {result && (
        <div className="space-y-3 animate-fade-in">
          {result.applied ? (
            <Alert tone="success" title="Saved">
              {summary(result)}
            </Alert>
          ) : blocked ? (
            <Alert tone="error" title="Fix the rows marked Problem, then check again">
              {summary(result)} Nothing is saved until every row reads.
            </Alert>
          ) : (
            <Alert tone="info" title="Preview: nothing is saved yet">
              {summary(result)}
            </Alert>
          )}
          <p className="text-xs text-text-muted">
            Columns read: {result.columns.join(", ") || "none"}
            {result.ignored_columns.length > 0 && ` · Ignored: ${result.ignored_columns.join(", ")}`}
          </p>
          {result.rows.length > 0 && (
            <div
              role="region"
              aria-label="Rows to check"
              tabIndex={0}
              className="max-h-96 overflow-auto rounded-xl border border-border"
            >
              <table className="w-full min-w-[36rem] text-sm">
                <thead className="sticky top-0 bg-surface-sunken text-xs text-text-muted">
                  <tr>
                    <th scope="col" className="px-3 py-2 text-start font-medium">Row</th>
                    <th scope="col" className="px-3 py-2 text-start font-medium">Course</th>
                    <th scope="col" className="px-3 py-2 text-start font-medium">Result</th>
                    <th scope="col" className="px-3 py-2 text-start font-medium">Details</th>
                  </tr>
                </thead>
                <tbody>
                  {result.rows.map((row) => (
                    <tr key={row.line} className="border-t border-border align-top">
                      <td className="px-3 py-2 text-text-muted">{row.line}</td>
                      <td className="px-3 py-2 font-semibold">{row.code ?? "—"}</td>
                      <td className="px-3 py-2">
                        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${ACTION_STYLES[row.action] ?? "bg-surface-sunken"}`}>
                          {ACTION_LABELS[row.action] ?? row.action}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-xs text-text-muted">{row.messages.join(" · ")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
