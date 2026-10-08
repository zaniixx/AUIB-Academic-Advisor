"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, type MetaOut, type PreferencesIn, type ProgramSummary } from "@/lib/api";
import { useAsync, useProfile } from "@/lib/hooks";
import { DEFAULT_PREFERENCES, saveProfile, type Profile } from "@/lib/profile";
import { Alert, Spinner } from "@/components/ui";
import { ProgramStep } from "./ProgramStep";
import { HistoryStep } from "./HistoryStep";
import { ReviewStep } from "./ReviewStep";
import { GoalsStep } from "./GoalsStep";
import { fromAttempts, fromHistory, toAttempts, type EditableRow } from "./rows";

const STEPS = ["Program", "Course history", "Check your courses", "Interests and goals"] as const;

export function StartWizard() {
  const saved = useProfile();
  const data = useAsync("start", () => Promise.all([api.programs("major"), api.programs("minor"), api.meta()]));
  if (data.error) return <Alert tone="error" title="Something went wrong">{data.error}</Alert>;
  if (saved === undefined || !data.data) return <Spinner label="Loading programs" />;
  const [majors, minors, meta] = data.data;
  return <Wizard majors={majors} minors={minors} meta={meta} saved={saved} />;
}

function Wizard({
  majors,
  minors,
  meta,
  saved,
}: {
  majors: ProgramSummary[];
  minors: ProgramSummary[];
  meta: MetaOut;
  saved: Profile | null;
}) {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [programId, setProgramId] = useState(saved?.programId ?? (majors.length === 1 ? majors[0].id : ""));
  const [minorId, setMinorId] = useState(saved?.minorId ?? "");
  const [rows, setRows] = useState<EditableRow[]>(() => (saved ? fromAttempts(saved.attempts) : []));
  const [unread, setUnread] = useState<{ line: number; text: string }[]>([]);
  const [ignored, setIgnored] = useState(0);
  const [preferences, setPreferences] = useState<PreferencesIn>(saved?.preferences ?? DEFAULT_PREFERENCES);

  function finish() {
    saveProfile({ programId, minorId: minorId || null, attempts: toAttempts(rows), preferences });
    router.push("/plan");
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="font-heading text-2xl font-bold">Set up your plan</h1>
        <p className="mt-1 text-sm text-text-muted">
          Takes about three minutes. Everything you enter stays in this browser.
        </p>
      </div>
      <ol className="flex flex-wrap gap-2 text-sm" aria-label="Steps">
        {STEPS.map((label, index) => (
          <li
            key={label}
            aria-current={index === step ? "step" : undefined}
            className={`rounded-full border px-3 py-1 ${
              index === step
                ? "border-primary bg-primary text-primary-contrast"
                : index < step
                  ? "border-status-done text-status-done"
                  : "border-border text-text-muted"
            }`}
          >
            {index + 1}. {label}
          </li>
        ))}
      </ol>

      {step === 0 && (
        <ProgramStep
          majors={majors}
          minors={minors}
          programId={programId}
          minorId={minorId}
          onChange={setProgramId}
          onMinorChange={setMinorId}
          onNext={() => setStep(1)}
        />
      )}
      {step === 1 && (
        <HistoryStep
          hasRows={rows.length > 0}
          onBack={() => setStep(0)}
          onParsed={(result) => {
            setRows(fromHistory(result.rows));
            setUnread(result.unread);
            setIgnored(result.ignored_line_count);
            setStep(2);
          }}
          onKeep={() => setStep(2)}
          onSkip={() => {
            setRows([]);
            setUnread([]);
            setIgnored(0);
            setStep(3);
          }}
        />
      )}
      {step === 2 && (
        <ReviewStep
          rows={rows}
          unread={unread}
          ignored={ignored}
          onChange={setRows}
          onBack={() => setStep(1)}
          onNext={() => setStep(3)}
        />
      )}
      {step === 3 && (
        <GoalsStep
          meta={meta}
          preferences={preferences}
          onChange={setPreferences}
          onBack={() => setStep(rows.length ? 2 : 1)}
          onFinish={finish}
        />
      )}
    </div>
  );
}
