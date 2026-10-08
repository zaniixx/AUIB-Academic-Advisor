"use client";

import { useState } from "react";
import { api, ApiError, type HistoryParse } from "@/lib/api";
import { Alert, Button, Card } from "@/components/ui";

const MAX_CHARACTERS = 300_000;

export function HistoryStep({
  hasRows,
  onBack,
  onParsed,
  onKeep,
  onSkip,
}: {
  hasRows: boolean;
  onBack: () => void;
  onParsed: (result: HistoryParse) => void;
  onKeep: () => void;
  onSkip: () => void;
}) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function read() {
    setBusy(true);
    setError(null);
    try {
      const result = await api.parseHistory(text);
      if (result.rows.length === 0) {
        setError(
          "No courses were found in that text. Make sure you copied the Course History page itself, including the course table.",
        );
        return;
      }
      setText("");
      onParsed(result);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not read the text. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="space-y-4">
      <div>
        <h2 className="font-heading text-lg font-semibold">Add your Course History</h2>
        <p className="mt-1 text-sm text-text-muted">Copy it straight from SIS. No password or login is shared.</p>
      </div>
      <ol className="list-decimal space-y-1 ps-5 text-sm">
        <li>
          Open <strong>SIS</strong>, then <strong>Academic Record → Course History</strong>.
        </li>
        <li>
          Press <kbd className="rounded border border-border px-1">Ctrl</kbd> +{" "}
          <kbd className="rounded border border-border px-1">A</kbd> to select the whole page, then{" "}
          <kbd className="rounded border border-border px-1">Ctrl</kbd> +{" "}
          <kbd className="rounded border border-border px-1">C</kbd> to copy it (on a Mac use{" "}
          <kbd className="rounded border border-border px-1">⌘</kbd>).
        </li>
        <li>Paste it into the box below.</li>
      </ol>
      <div className="space-y-1">
        <label htmlFor="history" className="block text-sm font-semibold">
          Pasted Course History
        </label>
        <textarea
          id="history"
          value={text}
          onChange={(event) => setText(event.target.value.slice(0, MAX_CHARACTERS))}
          rows={10}
          placeholder="Paste the whole Course History page here"
          className="w-full rounded-button border border-border bg-surface p-3 font-mono text-xs"
          aria-describedby="history-privacy"
        />
        <p id="history-privacy" className="text-xs text-text-muted">
          The text is read on the server to find your courses and then discarded. Only the courses you confirm
          are kept, in this browser.
        </p>
      </div>
      {error && <Alert tone="error">{error}</Alert>}
      <div className="flex flex-wrap justify-between gap-2">
        <Button variant="secondary" onClick={onBack}>
          Back
        </Button>
        <div className="flex flex-wrap gap-2">
          <Button variant="ghost" onClick={onSkip}>
            I&apos;m a new student, skip
          </Button>
          {hasRows && (
            <Button variant="secondary" onClick={onKeep}>
              Keep my saved courses
            </Button>
          )}
          <Button onClick={read} disabled={busy || text.trim().length === 0}>
            {busy ? "Reading…" : "Read my courses"}
          </Button>
        </div>
      </div>
    </Card>
  );
}
