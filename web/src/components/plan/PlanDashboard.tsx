"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api, type ChangeAction, type PreferencesIn, type Recommendations } from "@/lib/api";
import { useAsync, useProfile } from "@/lib/hooks";
import { clearProfile, toStudent, withPreferences, withRequirements, type Profile } from "@/lib/profile";
import {
  CompassIcon,
  FlagIcon,
  InfoIcon,
  LayersIcon,
  ListChecksIcon,
  MapIcon,
  PencilIcon,
  PrinterIcon,
  RouteIcon,
  ShieldCheckIcon,
  SlidersIcon,
  TrashIcon,
} from "@/components/icons";
import { Alert, Button, ButtonLink, EmptyState, Skeleton, TabPanel, Tabs, type TabItem } from "@/components/ui";
import { SummaryCards } from "./SummaryCards";
import { SettingsBar } from "./SettingsBar";
import { TermPlan, type PlanActions } from "./TermPlan";
import { ProgressPanel } from "./ProgressPanel";
import { EligibleList } from "./EligibleList";
import { RecommendationsPanel } from "./RecommendationsPanel";
import { NotesPanel } from "./NotesPanel";
import { WhatIfDialog, type WhatIfRequest } from "./WhatIfDialog";
import { DegreeMap } from "./DegreeMap";
import { MoveProvider } from "./MoveCourse";
import { ComparePanel } from "./ComparePanel";

const TABS = ["plan", "requirements", "map", "explore", "compare", "notes"] as const;
type Tab = (typeof TABS)[number];

// Links from before the tabs (#next-term, #electives) still land on the right tab.
const HASH_ALIASES: Record<string, Tab> = { "next-term": "explore", electives: "explore" };

function tabFromHash(): Tab {
  const hash = window.location.hash.slice(1);
  if ((TABS as readonly string[]).includes(hash)) return hash as Tab;
  return HASH_ALIASES[hash] ?? "plan";
}

export function PlanDashboard() {
  const profile = useProfile();
  if (profile === undefined) return <PlanSkeleton label="Loading your plan" />;
  if (profile === null) {
    return (
      <EmptyState
        icon={<RouteIcon className="h-8 w-8" />}
        title="No plan yet"
        action={<ButtonLink href="/start" size="lg">Start planning</ButtonLink>}
      >
        Set up your plan in about three minutes. No account needed.
      </EmptyState>
    );
  }
  return <Dashboard profile={profile} />;
}

/** The plan page's shape while it loads: summary, tabs and a few terms. */
function PlanSkeleton({ label }: { label: string }) {
  return (
    <div role="status" aria-label={label} className="space-y-6">
      <div className="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
        <Skeleton className="h-64 rounded-card" />
        <Skeleton className="h-64 rounded-card" />
      </div>
      <Skeleton className="h-12 rounded-full" />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <Skeleton className="h-72 rounded-card" />
        <Skeleton className="h-72 rounded-card" />
        <Skeleton className="h-72 rounded-card" />
      </div>
    </div>
  );
}

function Dashboard({ profile }: { profile: Profile }) {
  const router = useRouter();
  const student = toStudent(profile);
  const key = JSON.stringify(student);
  const plan = useAsync(key, () => api.plan(student), { keepPrevious: true });
  const recommendations = useAsync<Recommendations>(key, () => api.recommendations(student), { keepPrevious: true });
  const [whatIf, setWhatIf] = useState<WhatIfRequest | null>(null);
  const [tab, setTab] = useState<Tab>(tabFromHash);
  const [adjusting, setAdjusting] = useState(false);
  const tabsTop = useRef<HTMLDivElement>(null);

  // A link to #notes (or the browser's back button) switches tabs too.
  useEffect(() => {
    const onHash = () => setTab(tabFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  function openTab(next: string) {
    setTab(next as Tab);
    window.history.replaceState(null, "", `#${next}`);
    // When the tab bar is stuck under the header, bring the new panel's start into view.
    const marker = tabsTop.current;
    if (marker && marker.getBoundingClientRect().top < 0) {
      marker.scrollIntoView({ block: "start", behavior: "smooth" });
    }
  }

  const updatePreferences = (changes: Partial<PreferencesIn>) => withPreferences(profile, changes);
  const preferences = profile.preferences;
  const inProgress = profile.attempts.filter((attempt) => attempt.status === "in_progress");
  const built = preferences.built_terms ?? [];

  const actions: PlanActions = {
    lock: (code: string, term: string) =>
      updatePreferences({
        locks: [...(preferences.locks ?? []).filter((lock) => lock.code !== code), { code, term }],
      }),
    unlock: (code: string) => {
      const lock = (preferences.locks ?? []).find((each) => each.code === code);
      const locks = (preferences.locks ?? []).filter((each) => each.code !== code);
      // Taking the last course out of a built term opens it again rather than leaving it empty.
      const emptied = lock !== undefined && built.includes(lock.term) && !locks.some((each) => each.term === lock.term);
      updatePreferences({ locks, ...(emptied ? { built_terms: built.filter((term) => term !== lock.term) } : {}) });
    },
    addAll: (codes: string[], term: string) =>
      updatePreferences({
        locks: [
          ...(preferences.locks ?? []).filter((lock) => !codes.includes(lock.code)),
          ...codes.map((code) => ({ code, term })),
        ],
        exclude: (preferences.exclude ?? []).filter((code) => !codes.includes(code)),
      }),
    finish: (term: string, empty = false) =>
      updatePreferences({
        built_terms: [...new Set([...built, term])],
        ...(empty ? { locks: (preferences.locks ?? []).filter((lock) => lock.term !== term) } : {}),
      }),
    reopen: (term: string) => updatePreferences({ built_terms: built.filter((each) => each !== term) }),
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
    move: (code: string, from: string, to: string) => {
      const locks = [...(preferences.locks ?? []).filter((lock) => lock.code !== code), { code, term: to }];
      // As with removing a course: a term the student built that loses its last course opens again.
      const emptied = built.includes(from) && !locks.some((lock) => lock.term === from);
      updatePreferences({
        locks,
        exclude: (preferences.exclude ?? []).filter((c) => c !== code),
        ...(emptied ? { built_terms: built.filter((term) => term !== from) } : {}),
      });
    },
  };

  function clearData() {
    if (window.confirm("Delete your saved courses and plan from this browser?")) {
      clearProfile();
      router.push("/");
    }
  }

  const data = plan.data;
  const toCheck = data ? data.issues.length + data.unscheduled.length : 0;
  const tabs: TabItem[] = [
    { id: "plan", label: "Plan", icon: <RouteIcon className="h-4 w-4" /> },
    { id: "requirements", label: "Requirements", icon: <ListChecksIcon className="h-4 w-4" /> },
    { id: "map", label: "Degree map", icon: <MapIcon className="h-4 w-4" /> },
    { id: "explore", label: "Explore courses", icon: <CompassIcon className="h-4 w-4" /> },
    { id: "compare", label: "Compare", icon: <LayersIcon className="h-4 w-4" /> },
    { id: "notes", label: toCheck ? `Notes (${toCheck})` : "Notes", icon: <FlagIcon className="h-4 w-4" /> },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0 space-y-1">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-primary">My plan</p>
          <h1 className="font-heading text-3xl font-bold tracking-tight sm:text-4xl">Your plan</h1>
          {data && (
            <p className="text-text-muted">
              {data.catalog.program_name}
              {data.minor && ` · Minor in ${data.minor.name}`}
            </p>
          )}
          {data && data.catalog.versions.length > 1 && (
            <p className="flex max-w-2xl items-start gap-1.5 text-sm text-text-muted">
              <InfoIcon className="mt-0.5 h-4 w-4 shrink-0 text-status-in-progress" />
              {data.catalog.version_note}
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-2 print:hidden">
          <Button
            variant="secondary"
            onClick={() => setAdjusting((open) => !open)}
            aria-expanded={adjusting}
            aria-controls="adjust-plan"
          >
            <SlidersIcon className="h-4 w-4" />
            Adjust plan
          </Button>
          <ButtonLink href="/start" variant="secondary">
            <PencilIcon className="h-4 w-4" />
            Edit courses and goals
          </ButtonLink>
          <ButtonLink href="/plan/print">
            <PrinterIcon className="h-4 w-4" />
            Print for my advisor
          </ButtonLink>
        </div>
      </div>

      <div id="adjust-plan" hidden={!adjusting}>
        {adjusting && (
          <SettingsBar
            preferences={preferences}
            onChange={updatePreferences}
            onClose={() => setAdjusting(false)}
            requirements={
              data && data.catalog.versions.length > 1
                ? {
                    versions: data.catalog.versions,
                    entryTerm: profile.entryTerm ?? "",
                    programVersion: profile.programVersion ?? "",
                    onChange: (changes) => withRequirements(profile, changes),
                  }
                : null
            }
          />
        )}
      </div>

      {plan.error && (
        <Alert tone="error" title="The plan could not be made">
          {plan.error}
        </Alert>
      )}
      {!data && !plan.error && <PlanSkeleton label="Working out your plan" />}

      {data && (
        <div aria-busy={plan.loading} className={`space-y-6 transition-opacity duration-300 ${plan.loading ? "opacity-60" : ""}`}>
          <SummaryCards plan={data} student={student} />
          <p className="flex items-start gap-2 text-sm text-text-muted">
            <InfoIcon className="mt-0.5 h-4 w-4 text-status-in-progress" />
            {data.disclaimer}
          </p>

          <div ref={tabsTop} className="scroll-mt-20" />
          <div className="sticky top-[4.25rem] z-30 -mx-4 bg-background/90 px-4 py-2 backdrop-blur-md print:hidden">
            <Tabs items={tabs} active={tab} onChange={openTab} label="Plan sections" />
          </div>

          <TabPanel id="plan" active={tab === "plan"}>
            <MoveProvider student={student} onMove={actions.move}>
              <TermPlan
                id="plan"
                plan={data}
                inProgress={inProgress}
                locks={preferences.locks ?? []}
                preferences={preferences}
                actions={actions}
              />
            </MoveProvider>
          </TabPanel>
          <TabPanel id="requirements" active={tab === "requirements"}>
            <ProgressPanel id="requirements" plan={data} />
          </TabPanel>
          <TabPanel id="map" active={tab === "map"}>
            <DegreeMap id="map" data={data.degree_map} />
          </TabPanel>
          <TabPanel id="explore" active={tab === "explore"}>
            <div className="space-y-10">
              <EligibleList id="next-term" plan={data} />
              <RecommendationsPanel
                id="electives"
                data={recommendations.data}
                error={recommendations.error}
                included={preferences.include ?? []}
                actions={actions}
              />
            </div>
          </TabPanel>
          <TabPanel id="compare" active={tab === "compare"}>
            <ComparePanel id="compare" profile={profile} plan={data} />
          </TabPanel>
          <TabPanel id="notes" active={tab === "notes"}>
            <NotesPanel id="notes" plan={data} />
          </TabPanel>
        </div>
      )}

      {plan.loading && data && (
        <div
          role="status"
          className="fixed inset-x-0 bottom-5 z-40 mx-auto flex w-fit items-center gap-2 rounded-full bg-ink px-4 py-2.5 text-sm font-medium text-ink-contrast shadow-float animate-fade-up print:hidden"
        >
          <span aria-hidden className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
          Updating your plan…
        </div>
      )}

      <section
        aria-label="Your data"
        className="flex flex-wrap items-center justify-between gap-3 rounded-card border border-dashed border-border-strong p-4 text-sm print:hidden"
      >
        <p className="flex items-start gap-2 text-text-muted">
          <ShieldCheckIcon className="mt-0.5 h-4 w-4 text-status-done" />
          Your plan is saved only in this browser. On a shared or lab computer, clear it when you are done.
        </p>
        <Button variant="danger" size="sm" onClick={clearData}>
          <TrashIcon className="h-4 w-4" />
          Clear my data
        </Button>
      </section>

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
