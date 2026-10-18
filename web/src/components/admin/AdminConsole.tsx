"use client";

import { useState, useSyncExternalStore } from "react";
import { api } from "@/lib/api";
import { authSnapshot, recheckSession, serverAuthSnapshot, subscribeAuth } from "@/lib/auth";
import { useAsync } from "@/lib/hooks";
import {
  BookOpenIcon,
  CalendarIcon,
  ClockIcon,
  KeyIcon,
  LayersIcon,
  ListChecksIcon,
  ShieldCheckIcon,
  UsersIcon,
} from "@/components/icons";
import { Alert, Button, Card, FIELD, PageHeader, Skeleton, TabPanel, Tabs, type TabItem } from "@/components/ui";
import { BackupPanel } from "./BackupPanel";
import { CourseAdmin } from "./CourseAdmin";
import { ProgramAdmin } from "./ProgramAdmin";
import { RuleQueue } from "./RuleQueue";
import { ScheduleAdmin } from "./ScheduleAdmin";
import { StaffAdmin } from "./StaffAdmin";

// ADR 0009: admins sign in with their AUIB email (the session cookie does the work). The master token
// (ADVISOR_ADMIN_TOKEN) is entered here only to add or remove admins, or in an emergency.
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

const TABS: TabItem[] = [
  { id: "rules", label: "Rules to review", icon: <ListChecksIcon className="h-4 w-4" /> },
  { id: "courses", label: "Courses", icon: <BookOpenIcon className="h-4 w-4" /> },
  { id: "programs", label: "Majors and minors", icon: <LayersIcon className="h-4 w-4" /> },
  { id: "schedules", label: "Term schedules", icon: <CalendarIcon className="h-4 w-4" /> },
  { id: "backup", label: "Backup and restore", icon: <ShieldCheckIcon className="h-4 w-4" /> },
  { id: "people", label: "People", icon: <UsersIcon className="h-4 w-4" /> },
  { id: "history", label: "History", icon: <ClockIcon className="h-4 w-4" /> },
];

export function AdminConsole() {
  const auth = useSyncExternalStore(subscribeAuth, authSnapshot, serverAuthSnapshot);
  const token = useSyncExternalStore(subscribe, readToken, () => "");
  const [tab, setTab] = useState("rules");
  const forgetToken = () => writeToken("");
  const signedInAdmin = auth.status === "signed-in" && auth.role === "admin";
  // Without the master token, a refused request means the admin role was taken away: ask the server again.
  const signOut = token ? forgetToken : () => void recheckSession();

  if (!token && !signedInAdmin) {
    return <SignIn onToken={writeToken} email={auth.status === "signed-in" ? auth.email : null} />;
  }
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Admin"
        title="Course data"
        description={`Review rules, edit courses and programs, publish term schedules, and back up or restore the data. Every change is recorded in the audit log under ${
          token ? "the master token" : "your email address"
        }.`}
        actions={
          token ? (
            <Button variant="secondary" onClick={forgetToken}>
              Stop using the master token
            </Button>
          ) : undefined
        }
      />
      <Tabs items={TABS} active={tab} onChange={setTab} label="Admin sections" />
      <TabPanel id="rules" active={tab === "rules"}>
        <RuleQueue token={token} onUnauthorized={signOut} />
      </TabPanel>
      <TabPanel id="courses" active={tab === "courses"}>
        <CourseAdmin token={token} onUnauthorized={signOut} />
      </TabPanel>
      <TabPanel id="programs" active={tab === "programs"}>
        <ProgramAdmin token={token} onUnauthorized={signOut} />
      </TabPanel>
      <TabPanel id="schedules" active={tab === "schedules"}>
        <ScheduleAdmin token={token} onUnauthorized={signOut} />
      </TabPanel>
      <TabPanel id="backup" active={tab === "backup"}>
        <BackupPanel token={token} />
      </TabPanel>
      <TabPanel id="people" active={tab === "people"}>
        <StaffAdmin token={token} />
      </TabPanel>
      <TabPanel id="history" active={tab === "history"}>
        <div className="grid gap-6 xl:grid-cols-[1fr_1.4fr]">
          <section className="space-y-3">
            <h2 className="font-heading text-lg font-bold">Imports</h2>
            <Imports token={token} />
          </section>
          <section className="space-y-3">
            <h2 className="font-heading text-lg font-bold">Audit log</h2>
            <Audit token={token} />
          </section>
        </div>
      </TabPanel>
    </div>
  );
}

function SignIn({ onToken, email }: { onToken: (token: string) => void; email: string | null }) {
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.admin.me(value);
      onToken(value);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Sign-in failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="mx-auto max-w-md space-y-4 p-6 animate-fade-up">
      <span className="grid h-12 w-12 place-items-center rounded-xl bg-tint text-primary">
        <KeyIcon />
      </span>
      <h1 className="font-heading text-2xl font-bold">Admins only</h1>
      <p className="text-sm text-text-muted">
        Admins sign in with their AUIB email, as you did{email ? <> ({<strong className="break-all">{email}</strong>})</> : null}, but
        this account is not an admin. The person who holds the master token can add it.
      </p>
      <p className="text-sm text-text-muted">
        Holders of the master token can enter it here to add or remove admins, or to work in an emergency.
      </p>
      <form onSubmit={submit} className="space-y-3">
        <label className="block text-sm">
          <span className="mb-1 block font-medium">Master token</span>
          <input
            type="password"
            autoComplete="off"
            value={value}
            onChange={(event) => setValue(event.target.value)}
            className={FIELD}
          />
        </label>
        {error && <Alert tone="error">{error}</Alert>}
        <Button type="submit" disabled={!value || busy}>
          {busy ? "Checking…" : "Use the master token"}
        </Button>
      </form>
    </Card>
  );
}

function Imports({ token }: { token: string }) {
  const runs = useAsync(`imports:${token}`, () => api.admin.imports(token));
  if (runs.error) return <Alert tone="error">{runs.error}</Alert>;
  if (!runs.data) return <Skeleton className="h-64 rounded-card" />;
  return (
    <ul className="space-y-2">
      {runs.data.map((run) => (
        <li key={run.id} className="rounded-card border border-border bg-surface p-4 text-sm shadow-soft">
          <p className="font-medium">
            {run.program_id}: {run.status}
            {run.published ? ", published" : ", not published"}
          </p>
          <p className="text-xs text-text-muted">
            {new Date(run.started_at).toLocaleString()} by {run.actor}
          </p>
          <details className="mt-2 text-xs">
            <summary className="cursor-pointer text-primary">Report</summary>
            <pre tabIndex={0} className="mt-2 max-h-80 overflow-auto rounded-lg bg-surface-sunken p-2">
              {JSON.stringify(run.report, null, 2)}
            </pre>
          </details>
        </li>
      ))}
    </ul>
  );
}

function Audit({ token }: { token: string }) {
  const entries = useAsync(`audit:${token}`, () => api.admin.audit(token));
  if (entries.error) return <Alert tone="error">{entries.error}</Alert>;
  if (!entries.data) return <Skeleton className="h-64 rounded-card" />;
  return (
    <div
      role="region"
      aria-label="Audit log entries"
      tabIndex={0}
      className="relative overflow-x-auto rounded-card border border-border bg-surface shadow-soft"
    >
      <table className="w-full min-w-[40rem] text-sm">
        <thead className="bg-surface-sunken text-xs text-text-muted">
          <tr>
            <th scope="col" className="px-3 py-2 text-start font-medium">When</th>
            <th scope="col" className="px-3 py-2 text-start font-medium">Who</th>
            <th scope="col" className="px-3 py-2 text-start font-medium">Action</th>
            <th scope="col" className="px-3 py-2 text-start font-medium">Target</th>
            <th scope="col" className="px-3 py-2 text-start font-medium">Detail</th>
          </tr>
        </thead>
        <tbody>
          {entries.data.map((entry) => (
            <tr key={entry.id} className="border-t border-border align-top">
              <td className="px-3 py-2 whitespace-nowrap">{new Date(entry.at).toLocaleString()}</td>
              <td className="px-3 py-2">{entry.actor}</td>
              <td className="px-3 py-2 font-medium">{entry.action}</td>
              <td className="px-3 py-2">{entry.target}</td>
              <td className="max-w-md truncate px-3 py-2 font-mono text-xs" title={JSON.stringify(entry.detail)}>
                {JSON.stringify(entry.detail)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
