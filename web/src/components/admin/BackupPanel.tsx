"use client";

import { useId, useState } from "react";
import { api, type BackupCheck } from "@/lib/api";
import { DownloadIcon, FileIcon, KeyIcon, RotateIcon, ShieldCheckIcon } from "@/components/icons";
import { Alert, Button, FIELD } from "@/components/ui";
import { errorText, fileToBase64 } from "./TableUploader";

const MIN_LENGTH = 12;
const CONFIRM_WORD = "RESTORE";

// Names an admin recognises, in the order the tables matter to them; the revision counter is left out.
const TABLE_LABELS: Record<string, string> = {
  courses: "Courses",
  requisite_rules: "Prerequisite and corequisite rules",
  programs: "Majors and minors",
  requirement_groups: "Requirement groups",
  group_courses: "Courses listed in requirements",
  term_schedules: "Term schedules",
  term_offerings: "Scheduled sections",
  import_runs: "Import history",
  audit_log: "Audit log (kept as it is now)",
};

/** 32 random bytes from the browser's cryptographic generator, as URL-safe base64 (43 characters). */
function randomKey(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  return btoa(String.fromCharCode(...bytes))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

function saveFile(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function base64ToBlob(data: string): Blob {
  const binary = atob(data);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index++) bytes[index] = binary.charCodeAt(index);
  return new Blob([bytes], { type: "application/octet-stream" });
}

export function BackupPanel({ token }: { token: string }) {
  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_20rem]">
      <div className="space-y-5">
        <BackupSection token={token} />
        <RestoreSection token={token} />
      </div>
      <aside className="h-fit space-y-2 rounded-card bg-surface-sunken p-5 text-sm text-text-muted">
        <h3 className="font-heading font-bold text-text">How backups are protected</h3>
        <p>
          AES-256-GCM encryption, with the key derived from the passphrase (scrypt). The passphrase is not stored
          anywhere. Any change to a backup file is detected and the file is refused.
        </p>
        <h3 className="pt-2 font-heading font-bold text-text">What a restore keeps</h3>
        <p>
          The audit log is never rolled back: it keeps every change, including the ones a restore undoes, and
          records the restore itself.
        </p>
        <h3 className="pt-2 font-heading font-bold text-text">Moving to a new server</h3>
        <p>IT can restore everything, the audit log too, with:</p>
        <code className="block break-all rounded-lg bg-surface p-2 text-xs text-text">
          python -m app.cli backup-restore FILE --yes
        </code>
      </aside>
    </div>
  );
}

function BackupSection({ token }: { token: string }) {
  const [passphrase, setPassphrase] = useState("");
  const [again, setAgain] = useState("");
  const [generated, setGenerated] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const tooShort = passphrase.length > 0 && passphrase.length < MIN_LENGTH;
  const mismatch = again.length > 0 && again !== passphrase;
  const ready = passphrase.length >= MIN_LENGTH && again === passphrase;

  async function download() {
    setBusy(true);
    setError(null);
    setDone(null);
    try {
      const { blob, filename } = await api.admin.backup(token, passphrase);
      saveFile(blob, filename);
      setDone(`${filename} (${(blob.size / 1024).toFixed(0)} KB) downloaded.`);
    } catch (caught) {
      setError(errorText(caught, "The backup could not be made."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="space-y-4 rounded-card border border-border bg-surface p-5 shadow-soft">
      <div className="flex items-start gap-3">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-tint text-primary">
          <ShieldCheckIcon />
        </span>
        <div>
          <h3 className="font-heading text-lg font-bold">Download an encrypted backup</h3>
          <p className="text-sm text-text-muted">
            Everything the database holds: courses, rules and corrections, majors and minors, term schedules, the
            import history and the audit log. There is no student data to include.
          </p>
        </div>
      </div>
      <form
        className="space-y-3"
        onSubmit={(event) => {
          event.preventDefault();
          if (ready) void download();
        }}
      >
        <div className="text-sm">
          <label htmlFor="backup-passphrase" className="mb-1 block font-medium">
            Passphrase or key
          </label>
          <input
            id="backup-passphrase"
            type="password"
            autoComplete="new-password"
            value={passphrase}
            onChange={(e) => {
              setPassphrase(e.target.value);
              setGenerated(null);
            }}
            aria-describedby="backup-passphrase-help"
            className={FIELD}
          />
          <p id="backup-passphrase-help" className={`mt-1 text-xs ${tooShort ? "text-status-blocked" : "text-text-muted"}`}>
            At least {MIN_LENGTH} characters. A few unrelated words make a strong passphrase.
          </p>
        </div>
        <div className="text-sm">
          <label htmlFor="backup-passphrase-again" className="mb-1 block font-medium">
            The same again
          </label>
          <input
            id="backup-passphrase-again"
            type="password"
            autoComplete="new-password"
            value={again}
            onChange={(e) => setAgain(e.target.value)}
            className={FIELD}
          />
          {mismatch && <p className="mt-1 text-xs text-status-blocked">The two do not match.</p>}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="secondary"
            onClick={() => {
              const key = randomKey();
              setPassphrase(key);
              setAgain(key);
              setGenerated(key);
              setCopied(false);
            }}
          >
            <KeyIcon className="h-4 w-4" />
            Create a random key
          </Button>
          <Button type="submit" disabled={!ready || busy}>
            <DownloadIcon className="h-4 w-4" />
            {busy ? "Encrypting…" : "Download backup"}
          </Button>
        </div>
      </form>
      {generated && (
        <Alert tone="warning" title="Save this key now">
          <span className="mt-1 block break-all rounded-lg bg-surface px-2 py-1 font-mono text-xs text-text">{generated}</span>
          <span className="mt-2 block">
            Keep it in a password manager, apart from the backup file. It is not stored anywhere: without it the
            backup cannot be opened or restored.
          </span>
          <Button
            variant="ghost"
            size="sm"
            className="mt-2 -ms-3"
            onClick={async () => {
              await navigator.clipboard.writeText(generated);
              setCopied(true);
            }}
          >
            {copied ? "Copied" : "Copy the key"}
          </Button>
        </Alert>
      )}
      {error && <Alert tone="error">{error}</Alert>}
      {done && <Alert tone="success">{done}</Alert>}
    </section>
  );
}

function RestoreSection({ token }: { token: string }) {
  const fileId = useId();
  const [file, setFile] = useState<File | null>(null);
  const [passphrase, setPassphrase] = useState("");
  const [check, setCheck] = useState<BackupCheck | null>(null);
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  function reset() {
    setCheck(null);
    setConfirm("");
    setError(null);
    setDone(null);
  }

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (caught) {
      setError(errorText(caught, "The backup could not be read."));
    } finally {
      setBusy(false);
    }
  }

  const checkFile = () =>
    run(async () => {
      if (!file) return;
      setCheck(await api.admin.checkRestore(token, await fileToBase64(file), passphrase));
    });

  const restore = () =>
    run(async () => {
      if (!file || !check) return;
      const result = await api.admin.restore(token, await fileToBase64(file), passphrase);
      saveFile(base64ToBlob(result.previous.data_base64), result.previous.filename);
      setDone(
        `Restored the backup made on ${new Date(check.created_at).toLocaleString()}: ` +
          `${result.restored.courses ?? 0} courses and ${result.restored.programs ?? 0} majors and minors. ` +
          `The data from just before the restore was downloaded as ${result.previous.filename}; it opens with the ` +
          "same passphrase, so keep it in case you want to undo this.",
      );
      setCheck(null);
      setConfirm("");
    });

  return (
    <section className="space-y-4 rounded-card border border-border bg-surface p-5 shadow-soft">
      <div className="flex items-start gap-3">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-status-blocked/8 text-status-blocked">
          <RotateIcon />
        </span>
        <div>
          <h3 className="font-heading text-lg font-bold">Restore from a backup</h3>
          <p className="text-sm text-text-muted">
            Puts the system back to the data in a backup file. First check the file; nothing changes until you
            confirm.
          </p>
        </div>
      </div>

      <form
        className="space-y-3"
        onSubmit={(event) => {
          event.preventDefault();
          if (file && passphrase) void checkFile();
        }}
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="text-sm">
            <label htmlFor={fileId} className="mb-1 flex items-center gap-2 font-medium">
              <FileIcon className="h-4 w-4 text-primary" />
              Backup file (.aab)
            </label>
            <input
              id={fileId}
              type="file"
              accept=".aab,application/octet-stream"
              onChange={(event) => {
                setFile(event.target.files?.[0] ?? null);
                reset();
              }}
              className="block w-full cursor-pointer rounded-field border border-dashed border-border-strong bg-surface-sunken p-2.5 text-sm file:me-3 file:cursor-pointer file:rounded-button file:border-0 file:bg-ink file:px-3 file:py-1.5 file:text-ink-contrast"
            />
          </div>
          <div className="text-sm">
            <label htmlFor="restore-passphrase" className="mb-1 block font-medium">
              Its passphrase or key
            </label>
            <input
              id="restore-passphrase"
              type="password"
              autoComplete="off"
              value={passphrase}
              onChange={(e) => {
                setPassphrase(e.target.value);
                reset();
              }}
              className={FIELD}
            />
          </div>
        </div>
        <Button type="submit" variant="secondary" disabled={!file || !passphrase || busy}>
          {busy && !check ? "Opening…" : "Check the file"}
        </Button>
      </form>

      {error && <Alert tone="error">{error}</Alert>}
      {done && (
        <Alert tone="success" title="Restored">
          {done}
        </Alert>
      )}

      {check && (
        <div className="space-y-4 animate-fade-in">
          <p className="text-sm">
            Backup made on <strong>{new Date(check.created_at).toLocaleString()}</strong> by version {check.app_version}.
          </p>
          {!check.restorable ? (
            <Alert tone="error" title="This backup cannot be restored here">
              {check.problem}
            </Alert>
          ) : (
            <>
              <div role="region" aria-label="What the restore changes" tabIndex={0} className="overflow-x-auto rounded-xl border border-border">
                <table className="w-full min-w-[26rem] text-sm">
                  <thead className="bg-surface-sunken text-xs text-text-muted">
                    <tr>
                      <th scope="col" className="px-3 py-2 text-start font-medium">Data</th>
                      <th scope="col" className="px-3 py-2 text-end font-medium">Now</th>
                      <th scope="col" className="px-3 py-2 text-end font-medium">After the restore</th>
                    </tr>
                  </thead>
                  <tbody>
                    {check.tables
                      .filter((table) => TABLE_LABELS[table.name])
                      .map((table) => {
                        const kept = table.name === "audit_log";
                        const after = kept ? table.now : table.in_backup;
                        return (
                          <tr key={table.name} className="border-t border-border">
                            <td className="px-3 py-2">{TABLE_LABELS[table.name]}</td>
                            <td className="px-3 py-2 text-end tabular-nums">{table.now}</td>
                            <td
                              className={`px-3 py-2 text-end font-medium tabular-nums ${after !== table.now ? "text-status-warning" : ""}`}
                            >
                              {after}
                            </td>
                          </tr>
                        );
                      })}
                  </tbody>
                </table>
              </div>
              <Alert tone="warning" title="Restoring replaces the current data">
                Courses, rules, majors and minors, term schedules and the import history become the backup&apos;s.
                Just before, the current data downloads as an encrypted backup with the same passphrase, so you can
                undo this by restoring that file.
              </Alert>
              <form
                className="flex flex-wrap items-end gap-3"
                onSubmit={(event) => {
                  event.preventDefault();
                  if (confirm === CONFIRM_WORD) void restore();
                }}
              >
                <div className="text-sm">
                  <label htmlFor="restore-confirm" className="mb-1 block font-medium">
                    Type {CONFIRM_WORD} to confirm
                  </label>
                  <input
                    id="restore-confirm"
                    value={confirm}
                    autoComplete="off"
                    onChange={(e) => setConfirm(e.target.value.toUpperCase())}
                    className={`${FIELD} w-48 font-mono tracking-widest`}
                  />
                </div>
                <Button type="submit" variant="danger" disabled={confirm !== CONFIRM_WORD || busy}>
                  <RotateIcon className="h-4 w-4" />
                  {busy ? "Restoring…" : "Restore this backup"}
                </Button>
              </form>
            </>
          )}
        </div>
      )}
    </section>
  );
}
