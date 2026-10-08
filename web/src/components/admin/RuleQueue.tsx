"use client";

import { useEffect, useState } from "react";
import { api, ApiError, type AdminRule, type RuleCheck } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { Alert, Badge, Button, Card, Spinner, StatusBadge } from "@/components/ui";

const FILTERS = [
  ["needs_review", "Needs review"],
  ["partial", "Partly understood"],
  ["unparsed", "Not understood"],
  ["source_changed", "Source changed"],
  ["overridden", "Corrected"],
  ["reviewed", "Reviewed"],
  ["all", "All"],
] as const;

const KIND_LABELS: Record<string, string> = { pre: "Prerequisite", co: "Corequisite", pre_or_co: "Pre- or corequisite" };

/** F0.2 and F0.3: every parsed rule beside its source sentence, with approve and correct actions. */
export function RuleQueue({ token, onUnauthorized }: { token: string; onUnauthorized: () => void }) {
  const [filter, setFilter] = useState<string>("needs_review");
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [version, setVersion] = useState(0);
  const list = useAsync(`${filter}|${query}|${offset}|${version}`, () =>
    api.admin.rules(token, filter, query.trim(), offset),
  );
  const refresh = () => setVersion((v) => v + 1);

  const unauthorized = list.error?.includes("admin token") ?? false;
  useEffect(() => {
    if (unauthorized) onUnauthorized();
  }, [unauthorized, onUnauthorized]);

  return (
    <div className="space-y-4">
      <RuleLanguageHelp />
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-wrap gap-2" role="group" aria-label="Filter rules">
          {FILTERS.map(([id, label]) => (
            <button
              key={id}
              type="button"
              aria-pressed={filter === id}
              onClick={() => {
                setFilter(id);
                setOffset(0);
              }}
              className={`rounded-full border px-3 py-1 text-sm ${filter === id ? "border-primary bg-primary text-primary-contrast" : "border-border bg-surface"}`}
            >
              {label}
              {list.data && ` (${list.data.counts[id] ?? 0})`}
            </button>
          ))}
        </div>
        <label className="text-sm">
          <span className="sr-only">Search rules</span>
          <input
            type="search"
            placeholder="Course code or title"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setOffset(0);
            }}
            className="rounded-button border border-border bg-surface px-3 py-1"
          />
        </label>
      </div>
      {list.loading && <Spinner label="Loading rules" />}
      {list.error && <Alert tone="error">{list.error}</Alert>}
      {list.data && (
        <>
          <p className="text-sm text-text-muted">{list.data.total} rule(s)</p>
          <ul className="space-y-3">
            {list.data.rules.map((rule) => (
              <li key={rule.id}>
                <RuleCard rule={rule} token={token} onChanged={refresh} />
              </li>
            ))}
          </ul>
          <div className="flex justify-between">
            <Button variant="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 25))}>
              Previous
            </Button>
            <Button variant="secondary" disabled={offset + 25 >= list.data.total} onClick={() => setOffset(offset + 25)}>
              Next
            </Button>
          </div>
        </>
      )}
    </div>
  );
}

function RuleCard({ rule, token, onChanged }: { rule: AdminRule; token: string; onChanged: () => void }) {
  const [text, setText] = useState(rule.effective_rule);
  const [note, setNote] = useState(rule.override_note ?? "");
  const [check, setCheck] = useState<RuleCheck | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      onChanged();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "The change was not saved.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-semibold">
          {rule.course_code} {rule.course_title}{" "}
          <span className="font-normal text-text-muted">· {KIND_LABELS[rule.kind] ?? rule.kind}</span>
        </p>
        <div className="flex flex-wrap gap-1">
          <Badge>{rule.status}</Badge>
          {rule.reviewed ? <StatusBadge status="done" label="Reviewed" /> : <StatusBadge status="warning" label="Not reviewed" />}
          {rule.override_rule !== null && <Badge>Corrected</Badge>}
          {rule.source_changed && <StatusBadge status="blocked" label="SIS text changed" />}
        </div>
      </div>
      <div className="grid gap-3 text-sm md:grid-cols-2">
        <div>
          <p className="text-xs font-medium uppercase text-text-muted">SIS description says</p>
          <p className="mt-1">{rule.source_text}</p>
          {rule.unparsed_text && <p className="mt-1 text-xs text-status-warning">Not understood: {rule.unparsed_text}</p>}
        </div>
        <div>
          <p className="text-xs font-medium uppercase text-text-muted">The app reads it as</p>
          <p className="mt-1 font-mono text-xs">{rule.parsed_rule}</p>
          <p className="mt-1">{rule.parsed_english}</p>
          {rule.override_rule !== null && (
            <p className="mt-2 text-xs">
              Corrected to <span className="font-mono">{rule.override_rule}</span>
              {rule.reviewed_by && ` by ${rule.reviewed_by}`}
            </p>
          )}
        </div>
      </div>
      <details>
        <summary className="cursor-pointer text-sm font-medium">Correct this rule</summary>
        <div className="mt-2 space-y-2">
          <label className="block text-sm">
            <span className="block text-text-muted">Rule</span>
            <textarea
              value={text}
              onChange={(event) => {
                setText(event.target.value);
                setCheck(null);
              }}
              rows={2}
              className="mt-1 w-full rounded-button border border-border bg-surface p-2 font-mono text-xs"
            />
          </label>
          <label className="block text-sm">
            <span className="block text-text-muted">Note (why, and the source you checked)</span>
            <input
              value={note}
              onChange={(event) => setNote(event.target.value)}
              maxLength={1000}
              className="mt-1 w-full rounded-button border border-border bg-surface px-2 py-1"
            />
          </label>
          {check && (
            <Alert tone={check.valid ? "success" : "error"}>
              {check.valid
                ? `Reads as: ${check.english}${check.unknown_courses?.length ? ` (not in the catalog: ${check.unknown_courses.join(", ")})` : ""}`
                : check.error}
            </Alert>
          )}
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" disabled={busy} onClick={async () => setCheck(await api.admin.check(token, text))}>
              Check
            </Button>
            <Button disabled={busy} onClick={() => run(() => api.admin.correct(token, rule.id, text, note || null))}>
              Save correction
            </Button>
          </div>
        </div>
      </details>
      {error && <Alert tone="error">{error}</Alert>}
      <div className="flex flex-wrap gap-2">
        {!rule.reviewed || rule.source_changed ? (
          <Button variant="secondary" disabled={busy} onClick={() => run(() => api.admin.approve(token, rule.id))}>
            Approve as shown
          </Button>
        ) : null}
        {rule.override_rule !== null && (
          <Button variant="danger" disabled={busy} onClick={() => run(() => api.admin.revert(token, rule.id))}>
            Remove correction
          </Button>
        )}
      </div>
    </Card>
  );
}

function RuleLanguageHelp() {
  return (
    <details className="rounded-card border border-border bg-surface p-3 text-sm">
      <summary className="cursor-pointer font-medium">How to write a rule</summary>
      <ul className="mt-2 space-y-1 font-mono text-xs">
        <li>CSC 230 AND MAT 111</li>
        <li>CSC 345 OR MIS 201</li>
        <li>STANDING(junior) AND (MAT 101 OR MAT 102)</li>
        <li>CREDITS(90)</li>
        <li>LEVEL(300) means every 300-level course in the major core</li>
        <li>CONSENT(&quot;Instructor approval&quot;) and PLACEMENT(&quot;Math placement test&quot;) are shown but never block a plan</li>
        <li>NONE means no requirement</li>
      </ul>
    </details>
  );
}
