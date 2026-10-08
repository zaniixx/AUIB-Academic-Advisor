"use client";

import { useState, useSyncExternalStore } from "react";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { Alert, Button, Card, Spinner } from "@/components/ui";
import { RuleQueue } from "./RuleQueue";

const TOKEN_KEY = "auib-advisor:admin-token";
const tokenListeners = new Set<() => void>();

// The token lives in sessionStorage: it is forgotten when the tab closes.
function readToken(): string {
  try {
    return window.sessionStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
}

function writeToken(token: string) {
  try {
    if (token) window.sessionStorage.setItem(TOKEN_KEY, token);
    else window.sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    // storage blocked: the token simply is not remembered
  }
  tokenListeners.forEach((listener) => listener());
}

function subscribe(listener: () => void) {
  tokenListeners.add(listener);
  return () => tokenListeners.delete(listener);
}

const TABS = [
  ["rules", "Rules to review"],
  ["imports", "Imports"],
  ["audit", "Audit log"],
] as const;

export function AdminConsole() {
  const token = useSyncExternalStore(subscribe, readToken, () => "");
  const [tab, setTab] = useState<(typeof TABS)[number][0]>("rules");

  if (!token) return <SignIn onToken={writeToken} />;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="font-heading text-2xl font-bold">Admin</h1>
        <Button variant="secondary" onClick={() => writeToken("")}>
          Sign out
        </Button>
      </div>
      <div role="tablist" aria-label="Admin sections" className="flex flex-wrap gap-2">
        {TABS.map(([id, label]) => (
          <button
            key={id}
            role="tab"
            type="button"
            aria-selected={tab === id}
            onClick={() => setTab(id)}
            className={`rounded-full border px-3 py-1 text-sm ${tab === id ? "border-primary bg-primary text-primary-contrast" : "border-border bg-surface"}`}
          >
            {label}
          </button>
        ))}
      </div>
      {tab === "rules" && <RuleQueue token={token} onUnauthorized={() => writeToken("")} />}
      {tab === "imports" && <Imports token={token} />}
      {tab === "audit" && <Audit token={token} />}
    </div>
  );
}

function SignIn({ onToken }: { onToken: (token: string) => void }) {
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.admin.rules(value, "needs_review", "");
      onToken(value);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Sign-in failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="mx-auto max-w-md space-y-3">
      <h1 className="font-heading text-xl font-bold">Admin sign-in</h1>
      <p className="text-sm text-text-muted">
        For people who maintain the course data. Enter the admin token configured on the server.
      </p>
      <form onSubmit={submit} className="space-y-3">
        <label className="block text-sm">
          <span className="block font-medium">Admin token</span>
          <input
            type="password"
            autoComplete="off"
            value={value}
            onChange={(event) => setValue(event.target.value)}
            className="mt-1 w-full rounded-button border border-border bg-surface px-3 py-2"
          />
        </label>
        {error && <Alert tone="error">{error}</Alert>}
        <Button type="submit" disabled={!value || busy}>
          {busy ? "Checking…" : "Sign in"}
        </Button>
      </form>
    </Card>
  );
}

function Imports({ token }: { token: string }) {
  const runs = useAsync(`imports:${token}`, () => api.admin.imports(token));
  if (runs.loading) return <Spinner />;
  if (runs.error) return <Alert tone="error">{runs.error}</Alert>;
  return (
    <ul className="space-y-2">
      {runs.data?.map((run) => (
        <li key={run.id}>
          <Card>
            <p className="font-medium">
              {run.program_id}: {run.status}
              {run.published ? ", published" : ", not published"}
            </p>
            <p className="text-xs text-text-muted">
              {new Date(run.started_at).toLocaleString()} by {run.actor}
            </p>
            <details className="mt-2 text-xs">
              <summary className="cursor-pointer">Report</summary>
              <pre className="mt-2 max-h-80 overflow-auto rounded-button bg-background p-2">
                {JSON.stringify(run.report, null, 2)}
              </pre>
            </details>
          </Card>
        </li>
      ))}
    </ul>
  );
}

function Audit({ token }: { token: string }) {
  const entries = useAsync(`audit:${token}`, () => api.admin.audit(token));
  if (entries.loading) return <Spinner />;
  if (entries.error) return <Alert tone="error">{entries.error}</Alert>;
  return (
    <div className="relative overflow-x-auto">
      <table className="w-full min-w-[40rem] text-sm">
        <thead>
          <tr className="border-b border-border text-text-muted">
            <th scope="col" className="py-2 text-start font-medium">When</th>
            <th scope="col" className="py-2 text-start font-medium">Who</th>
            <th scope="col" className="py-2 text-start font-medium">Action</th>
            <th scope="col" className="py-2 text-start font-medium">Target</th>
            <th scope="col" className="py-2 text-start font-medium">Detail</th>
          </tr>
        </thead>
        <tbody>
          {entries.data?.map((entry) => (
            <tr key={entry.id} className="border-b border-border align-top">
              <td className="py-2 pe-2 whitespace-nowrap">{new Date(entry.at).toLocaleString()}</td>
              <td className="py-2 pe-2">{entry.actor}</td>
              <td className="py-2 pe-2">{entry.action}</td>
              <td className="py-2 pe-2">{entry.target}</td>
              <td className="py-2 font-mono text-xs">{JSON.stringify(entry.detail)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
