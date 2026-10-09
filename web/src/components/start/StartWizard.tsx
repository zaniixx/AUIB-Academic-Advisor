"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api, type MetaOut, type PreferencesIn, type ProgramSummary } from "@/lib/api";
import { useAsync, useProfile } from "@/lib/hooks";
import { DEFAULT_PREFERENCES, saveProfile, type Profile } from "@/lib/profile";
import { Alert, CheckIcon, PageHeader, Skeleton } from "@/components/ui";
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
  if (saved === undefined || !data.data) return <WizardSkeleton />;
  const [majors, minors, meta] = data.data;
  return <Wizard majors={majors} minors={minors} meta={meta} saved={saved} />;
}

/** The wizard's shape while programs load, so nothing jumps when they arrive. */
function WizardSkeleton() {
  return (
    <div role="status" aria-label="Loading programs" className="mx-auto max-w-3xl space-y-8">
      <div className="space-y-3">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-10 w-72" />
        <Skeleton className="h-4 w-96 max-w-full" />
      </div>
      <Skeleton className="h-16 w-full" />
      <Skeleton className="h-80 w-full rounded-card" />
    </div>
  );
}

function Stepper({ current }: { current: number }) {
  return (
    <ol aria-label="Steps" className="grid grid-cols-4">
      {STEPS.map((label, index) => {
        const done = index < current;
        const active = index === current;
        return (
          <li
            key={label}
            aria-current={active ? "step" : undefined}
            className="relative flex flex-col items-center gap-2 px-1 text-center"
          >
            {index > 0 && (
              <span aria-hidden className="absolute -start-1/2 top-[1.0625rem] h-0.5 w-full bg-border">
                <span
                  className={`block h-full origin-left bg-primary transition-transform duration-500 ease-out ${
                    index <= current ? "scale-x-100" : "scale-x-0"
                  }`}
                />
              </span>
            )}
            <span
              className={`relative z-10 grid h-9 w-9 place-items-center rounded-full border-2 text-sm font-bold transition duration-300 ${
                done
                  ? "border-status-done bg-status-done text-surface"
                  : active
                    ? "border-primary bg-primary text-primary-contrast ring-4 ring-tint-strong"
                    : "border-border-strong bg-surface text-text-muted"
              }`}
            >
              {done ? <CheckIcon className="h-4 w-4 animate-pop" /> : index + 1}
            </span>
            <span className={`text-xs leading-snug sm:text-sm ${active ? "font-semibold text-text" : "text-text-muted"}`}>
              {label}
              {done && <span className="sr-only"> (done)</span>}
            </span>
          </li>
        );
      })}
    </ol>
  );
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
  const [entryTerm, setEntryTerm] = useState(saved?.entryTerm ?? "");
  const [rows, setRows] = useState<EditableRow[]>(() => (saved ? fromAttempts(saved.attempts) : []));
  const [unread, setUnread] = useState<{ line: number; text: string }[]>([]);
  const [ignored, setIgnored] = useState(0);
  const [preferences, setPreferences] = useState<PreferencesIn>(saved?.preferences ?? DEFAULT_PREFERENCES);

  // When the step changes, its title takes focus (and scrolls into view) so nobody is left mid-page.
  const shownStep = useRef(step);
  useEffect(() => {
    if (shownStep.current === step) return;
    shownStep.current = step;
    document.getElementById("step-title")?.focus();
  }, [step]);

  function finish() {
    saveProfile({
      programId,
      minorId: minorId || null,
      entryTerm: entryTerm || null,
      // A version chosen with the registrar's approval belongs to that major only.
      programVersion: saved && saved.programId === programId ? (saved.programVersion ?? null) : null,
      attempts: toAttempts(rows),
      preferences,
    });
    router.push("/plan");
  }

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <PageHeader
        eyebrow={`Step ${step + 1} of ${STEPS.length}`}
        title="Set up your plan"
        description="Takes about three minutes. Everything you enter stays in this browser."
      />
      <Stepper current={step} />

      <div key={step} className="animate-fade-up">
        {step === 0 && (
          <ProgramStep
            majors={majors}
            minors={minors}
            programId={programId}
            minorId={minorId}
            onChange={setProgramId}
            onMinorChange={setMinorId}
            entryTerm={entryTerm}
            onEntryTermChange={setEntryTerm}
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
    </div>
  );
}
