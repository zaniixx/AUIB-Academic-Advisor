"use client";

import { useState } from "react";
import { api, type StaffRole } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { TrashIcon, UserIcon } from "@/components/icons";
import { Alert, Button, Card, FIELD, Select, Skeleton } from "@/components/ui";

const ROLE_LABEL: Record<StaffRole, string> = { admin: "Admin", advisor: "Advisor" };

/**
 * ADR 0009: admins and advisors are AUIB addresses with a role. They sign in like students, so the
 * emailed code proves the address is theirs. Only the master token adds or removes admins.
 */
export function StaffAdmin({ token }: { token: string }) {
  const [version, setVersion] = useState(0);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<StaffRole>("advisor");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const me = useAsync(`admin-me|${token}`, () => api.admin.me(token));
  const people = useAsync(`staff|${token}|${version}`, () => api.admin.staff(token), { keepPrevious: true });
  const canManageAdmins = me.data?.can_manage_admins ?? false;
  const refresh = () => setVersion((v) => v + 1);

  async function act(run: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await run();
      refresh();
      return true;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "That did not work. Try again.");
      return false;
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <p className="max-w-3xl text-sm text-text-muted">
        Admins and advisors sign in with their AUIB email, like students: the code sent to that address proves it is
        theirs. Admins can use this page; advisors get their own view when it is built, and until then use the app
        like students. {canManageAdmins
          ? "You are using the master token, so you can add and remove admins."
          : "Only the holder of the master token can add or remove admins; admins add and remove advisors."}
      </p>

      <Card className="space-y-3">
        <h2 className="font-heading text-lg font-bold">Add someone</h2>
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={async (event) => {
            event.preventDefault();
            if (await act(() => api.admin.grant(token, email, role))) setEmail("");
          }}
        >
          <label className="min-w-64 flex-1 text-sm">
            <span className="mb-1 block font-medium">AUIB email address</span>
            <input
              type="email"
              inputMode="email"
              autoComplete="off"
              placeholder="name@auib.edu.iq"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className={FIELD}
              required
            />
          </label>
          <label className="text-sm">
            <span className="mb-1 block font-medium">Role</span>
            <Select value={role} onChange={(event) => setRole(event.target.value as StaffRole)} wrapperClassName="w-40">
              <option value="advisor">Advisor</option>
              <option value="admin" disabled={!canManageAdmins}>
                Admin{canManageAdmins ? "" : " (master token)"}
              </option>
            </Select>
          </label>
          <Button type="submit" disabled={busy || !email.trim()}>
            {busy ? "Saving…" : "Add"}
          </Button>
        </form>
      </Card>

      {error && <Alert tone="error">{error}</Alert>}
      {people.error && <Alert tone="error">{people.error}</Alert>}
      {!people.data && !people.error && <Skeleton className="h-32 rounded-card" />}
      {people.data?.length === 0 && (
        <p className="rounded-card border border-dashed border-border-strong p-8 text-center text-sm text-text-muted">
          No admins or advisors yet.
        </p>
      )}
      {people.data && people.data.length > 0 && (
        <ul className="grid gap-3 md:grid-cols-2" aria-label="Admins and advisors">
          {people.data.map((person) => {
            const locked = person.role === "admin" && !canManageAdmins;
            return (
              <li
                key={person.email}
                className="flex flex-wrap items-center gap-3 rounded-card border border-border bg-surface p-4 shadow-soft"
              >
                <span className="grid h-10 w-10 place-items-center rounded-xl bg-tint text-primary">
                  <UserIcon />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="break-all font-semibold">{person.email}</p>
                  <p className="text-xs text-text-muted">
                    {ROLE_LABEL[person.role]} · added {new Date(person.added_at).toLocaleDateString()} by {person.added_by}
                  </p>
                </div>
                <Button
                  variant="quiet"
                  size="sm"
                  disabled={busy || locked}
                  title={locked ? "Only the master token can remove an admin" : undefined}
                  aria-label={`Remove ${person.email} (${ROLE_LABEL[person.role]})`}
                  onClick={() => {
                    if (window.confirm(`Remove ${person.email} as ${ROLE_LABEL[person.role].toLowerCase()}?`)) {
                      void act(() => api.admin.revoke(token, person.email));
                    }
                  }}
                >
                  <TrashIcon className="h-4 w-4" />
                  Remove
                </Button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
