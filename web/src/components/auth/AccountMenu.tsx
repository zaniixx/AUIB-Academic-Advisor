"use client";

import { useEffect, useId, useState, useSyncExternalStore } from "react";
import { authSnapshot, checkSession, serverAuthSnapshot, signOut, subscribeAuth } from "@/lib/auth";
import { LogOutIcon, UserIcon } from "@/components/icons";
import { Button, Dialog } from "@/components/ui";

/** F9.1: who is signed in, and signing out (with the choice to delete this browser's data, F9.2: and the server's). */
export function AccountMenu() {
  const auth = useSyncExternalStore(subscribeAuth, authSnapshot, serverAuthSnapshot);
  const [open, setOpen] = useState(false);
  const [clearData, setClearData] = useState(true);
  const [everywhere, setEverywhere] = useState(false);
  const [busy, setBusy] = useState(false);
  const clearId = useId();
  const everywhereId = useId();

  useEffect(() => {
    if (auth.status === "checking") void checkSession();
  }, [auth.status]);

  if (auth.status !== "signed-in") return null;
  const expires = new Date(auth.expiresAt).toLocaleDateString("en-GB", { day: "numeric", month: "long" });

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label={`Account: ${auth.email}`}
        className="inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-full px-3 text-sm font-medium text-ink-contrast/75 transition duration-200 hover:bg-white/8 hover:text-white"
      >
        <UserIcon className="h-4 w-4" />
        <span className="hidden max-w-40 truncate lg:inline">{auth.email}</span>
      </button>
      {open && (
        <Dialog open title="Your account" onClose={() => setOpen(false)}>
          <div className="space-y-4">
            <p className="text-sm">
              Signed in as <strong className="break-all">{auth.email}</strong> until {expires}.
            </p>
            <label htmlFor={clearId} className="flex items-start gap-3 rounded-xl border border-border p-3 text-sm">
              <input
                id={clearId}
                type="checkbox"
                checked={clearData}
                onChange={(event) => setClearData(event.target.checked)}
                className="mt-0.5 h-4 w-4 accent-primary"
              />
              <span>
                <span className="block font-medium">Also delete my courses and plan from this browser</span>
                <span className="text-text-muted">Do this on a shared or lab computer.</span>
              </span>
            </label>
            <label htmlFor={everywhereId} className="flex items-start gap-3 rounded-xl border border-border p-3 text-sm">
              <input
                id={everywhereId}
                type="checkbox"
                checked={everywhere}
                onChange={(event) => setEverywhere(event.target.checked)}
                className="mt-0.5 h-4 w-4 accent-primary"
              />
              <span>
                <span className="block font-medium">Sign out on all my devices and forget my email address</span>
                <span className="text-text-muted">The app keeps your address only while you are signed in.</span>
              </span>
            </label>
            <div className="flex flex-wrap justify-end gap-2">
              <Button variant="secondary" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button
                variant="danger"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  await signOut(clearData, everywhere).catch(() => undefined);
                  setBusy(false);
                  setOpen(false);
                }}
              >
                <LogOutIcon className="h-4 w-4" />
                Sign out
              </Button>
            </div>
          </div>
        </Dialog>
      )}
    </>
  );
}
