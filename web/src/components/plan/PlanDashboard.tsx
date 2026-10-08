"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, type ChangeAction, type PreferencesIn, type Recommendations } from "@/lib/api";
import { useAsync, useProfile } from "@/lib/hooks";
import { clearProfile, toStudent, withPreferences, type Profile } from "@/lib/profile";
import { Alert, Button, ButtonLink, Spinner } from "@/components/ui";
import { SummaryCards } from "./SummaryCards";
import { SettingsBar } from "./SettingsBar";
import { TermPlan } from "./TermPlan";
import { ProgressPanel } from "./ProgressPanel";
import { EligibleList } from "./EligibleList";
import { RecommendationsPanel } from "./RecommendationsPanel";
import { NotesPanel } from "./NotesPanel";
import { WhatIfDialog, type WhatIfRequest } from "./WhatIfDialog";
import { DegreeMap } from "./DegreeMap";

const SECTIONS = [
  ["map", "Degree map"],
  ["plan", "Term by term"],
  ["requirements", "Requirements"],
  ["next-term", "Next term"],
  ["electives", "Electives for you"],
  ["notes", "Things to check"],
] as const;

export function PlanDashboard() {
  const profile = useProfile();
  if (profile === undefined) return <Spinner label="Loading your plan" />;
  if (profile === null) {
    return (
      <div className="mx-auto max-w-xl space-y-4 py-10 text-center">
        <h1 className="font-heading text-2xl font-bold">No plan yet</h1>
        <p className="text-text-muted">Set up your plan in about three minutes. No account needed.</p>
        <ButtonLink href="/start">Start planning</ButtonLink>
      </div>
    );
  }
  return <Dashboard profile={profile} />;
}

function Dashboard({ profile }: { profile: Profile }) {
  const router = useRouter();
  const student = toStudent(profile);
  const key = JSON.stringify(student);
  const plan = useAsync(key, () => api.plan(student));
  const recommendations = useAsync<Recommendations>(key, () => api.recommendations(student));
  const [whatIf, setWhatIf] = useState<WhatIfRequest | null>(null);

  const updatePreferences = (changes: Partial<PreferencesIn>) => withPreferences(profile, changes);
  const preferences = profile.preferences;
  const inProgress = profile.attempts.filter((attempt) => attempt.status === "in_progress");

  const actions = {
    lock: (code: string, term: string) =>
      updatePreferences({
        locks: [...(preferences.locks ?? []).filter((lock) => lock.code !== code), { code, term }],
      }),
    unlock: (code: string) =>
      updatePreferences({ locks: (preferences.locks ?? []).filter((lock) => lock.code !== code) }),
    include: (code: string) =>
      updatePreferences({
        include: [...new Set([...(preferences.include ?? []), code])],
        exclude: (preferences.exclude ?? []).filter((c) => c !== code),
      }),
    exclude: (code: string) =>
      updatePreferences({
        exclude: [...new Set([...(preferences.exclude ?? []), code])],
        include: (preferences.include ?? []).filter((c) => c !== code),
      }),
    replace: (previous: string | null, next: string, term: string) =>
      updatePreferences({
        locks: [
          ...(preferences.locks ?? []).filter((lock) => lock.code !== previous && lock.code !== next),
          { code: next, term },
        ],
        include: (preferences.include ?? []).filter((c) => c !== previous && c !== next),
        exclude: [...new Set([...(preferences.exclude ?? []).filter((c) => c !== next), ...(previous ? [previous] : [])])],
      }),
    whatIf: (code: string, action: ChangeAction) => setWhatIf({ code, action }),
  };

  function clearData() {
    if (window.confirm("Delete your saved courses and plan from this browser?")) {
      clearProfile();
      router.push("/");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-heading text-2xl font-bold">Your plan</h1>
          {plan.data && (
            <p className="text-sm text-text-muted">
              {plan.data.catalog.program_name}
              {plan.data.minor && ` · Minor in ${plan.data.minor.name}`}
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-2 print:hidden">
          <ButtonLink href="/start" variant="secondary">
            Edit courses and goals
          </ButtonLink>
          <ButtonLink href="/plan/print" variant="secondary">
            Print for my advisor
          </ButtonLink>
          <Button variant="danger" onClick={clearData}>
            Clear my data
          </Button>
        </div>
      </div>

      <SettingsBar preferences={preferences} onChange={updatePreferences} />

      {plan.error && (
        <Alert tone="error" title="The plan could not be made">
          {plan.error}
        </Alert>
      )}
      {plan.loading && !plan.data && <Spinner label="Working out your plan" />}

      {plan.data && (
        <>
          <Alert tone="info">{plan.data.disclaimer}</Alert>
          <SummaryCards plan={plan.data} />
          <nav aria-label="Plan sections" className="print:hidden">
            <ul className="flex flex-wrap gap-2 text-sm">
              {SECTIONS.map(([id, label]) => (
                <li key={id}>
                  <a href={`#${id}`} className="rounded-full border border-border bg-surface px-3 py-1 hover:bg-background">
                    {label}
                  </a>
                </li>
              ))}
            </ul>
          </nav>
          {plan.loading && <Spinner label="Updating" />}
          <DegreeMap id="map" data={plan.data.degree_map} />
          <TermPlan
            id="plan"
            plan={plan.data}
            inProgress={inProgress}
            locks={preferences.locks ?? []}
            actions={actions}
          />
          <ProgressPanel id="requirements" plan={plan.data} />
          <EligibleList id="next-term" plan={plan.data} />
          <RecommendationsPanel
            id="electives"
            data={recommendations.data}
            error={recommendations.error}
            included={preferences.include ?? []}
            actions={actions}
          />
          <NotesPanel id="notes" plan={plan.data} />
        </>
      )}

      {whatIf && (
        <WhatIfDialog
          request={whatIf}
          student={student}
          onClose={() => setWhatIf(null)}
          onKeep={(code, term) => {
            actions.lock(code, term);
            setWhatIf(null);
          }}
        />
      )}
    </div>
  );
}
