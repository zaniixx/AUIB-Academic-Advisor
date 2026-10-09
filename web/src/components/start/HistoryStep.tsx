"use client";

import { useState } from "react";
import { api, ApiError, type HistoryParse } from "@/lib/api";
import { ArrowLeftIcon, ClipboardIcon, ShieldCheckIcon } from "@/components/icons";
import { Alert, Button, FIELD, Keycap } from "@/components/ui";
import { StepCard } from "./StepCard";

const MAX_CHARACTERS = 300_000;

const HOW_TO = [
  {
    title: "Open your Course History",
    text: (
      <>
        In <strong>SIS</strong>, go to <strong>Academic Record → Course History</strong>.
      </>
    ),
  },
  {
    title: "Copy the whole page",
    text: (
      <>
        Press <Keycap>Ctrl</Keycap> + <Keycap>A</Keycap>, then <Keycap>Ctrl</Keycap> + <Keycap>C</Keycap> (on a Mac,{" "}
        <Keycap>⌘</Keycap> instead of Ctrl).
      </>
    ),
  },
  { title: "Paste it below", text: "Menus and headings are fine; only the course table is read." },
];

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
  const lines = text.trim() ? text.trim().split("\n").length : 0;

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
    <StepCard
      icon={<ClipboardIcon />}
      title="Add your Course History"
      description="Copy it straight from SIS. No password or login is shared."
      footer={
        <>
          <Button variant="secondary" onClick={onBack}>
            <ArrowLeftIcon className="h-4 w-4" />
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
              {busy && (
                <span aria-hidden className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
              )}
              {busy ? "Reading…" : "Read my courses"}
            </Button>
          </div>
        </>
      }
    >
      <ol className="grid gap-3 sm:grid-cols-3">
        {HOW_TO.map((item, index) => (
          <li key={item.title} className="flex gap-3 rounded-xl bg-surface-sunken p-3.5">
            <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-ink text-xs font-bold text-ink-contrast">
              {index + 1}
            </span>
            <div className="min-w-0 space-y-1 text-sm">
              <p className="font-semibold">{item.title}</p>
              <p className="leading-relaxed text-text-muted">{item.text}</p>
            </div>
          </li>
        ))}
      </ol>

      <div className="space-y-2">
        <div className="flex items-baseline justify-between gap-2">
          <label htmlFor="history" className="block font-semibold">
            Pasted Course History
          </label>
          {lines > 0 && (
            <span className="text-xs text-text-muted animate-fade-in" aria-live="polite">
              {lines.toLocaleString()} lines pasted
            </span>
          )}
        </div>
        <textarea
          id="history"
          value={text}
          onChange={(event) => setText(event.target.value.slice(0, MAX_CHARACTERS))}
          rows={9}
          placeholder="Paste the whole Course History page here"
          className={`${FIELD} min-h-48 resize-y font-mono text-xs leading-relaxed`}
          aria-describedby="history-privacy"
        />
        <p id="history-privacy" className="flex items-start gap-2 text-xs text-text-muted">
          <ShieldCheckIcon className="h-4 w-4 text-status-done" />
          The text is read on the server to find your courses and then discarded. Only the courses you confirm are
          kept, in this browser.
        </p>
      </div>
      {error && <Alert tone="error">{error}</Alert>}
    </StepCard>
  );
}
