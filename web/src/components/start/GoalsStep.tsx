"use client";

import type { MetaOut, PreferencesIn } from "@/lib/api";
import { Button, Card } from "@/components/ui";

const WORKLOADS = [
  { id: "light", label: "Lighter", hint: "About 12 units a term", units: 12 },
  { id: "balanced", label: "Balanced", hint: "About 15 units a term", units: 15 },
  { id: "challenging", label: "Challenging", hint: "Up to 18 units a term", units: 18 },
] as const;

/** F2.1: the onboarding questionnaire. */
export function GoalsStep({
  meta,
  preferences,
  onChange,
  onBack,
  onFinish,
}: {
  meta: MetaOut;
  preferences: PreferencesIn;
  onChange: (preferences: PreferencesIn) => void;
  onBack: () => void;
  onFinish: () => void;
}) {
  const interests = preferences.interests ?? [];
  const set = (changes: Partial<PreferencesIn>) => onChange({ ...preferences, ...changes });
  const toggleInterest = (id: string) =>
    set({ interests: interests.includes(id) ? interests.filter((i) => i !== id) : [...interests, id] });

  return (
    <Card className="space-y-6">
      <fieldset className="space-y-2">
        <legend className="font-semibold">What interests you?</legend>
        <p className="text-sm text-text-muted">Pick any. Electives that match are suggested first.</p>
        <div className="flex flex-wrap gap-2">
          {meta.interests.map((interest) => {
            const checked = interests.includes(interest.id);
            return (
              <label
                key={interest.id}
                className={`cursor-pointer rounded-full border px-3 py-1 text-sm ${
                  checked ? "border-primary bg-primary text-primary-contrast" : "border-border"
                }`}
              >
                <input
                  type="checkbox"
                  className="sr-only"
                  checked={checked}
                  onChange={() => toggleInterest(interest.id)}
                />
                {interest.label}
              </label>
            );
          })}
        </div>
      </fieldset>

      <fieldset className="space-y-2">
        <legend className="font-semibold">After graduation I want to…</legend>
        <div className="grid gap-2 sm:grid-cols-2">
          {meta.goals.map((goal) => (
            <label key={goal.id} className="flex items-center gap-2 rounded-button border border-border px-3 py-2 text-sm">
              <input
                type="radio"
                name="goal"
                checked={preferences.goal === goal.id}
                onChange={() => set({ goal: goal.id })}
              />
              {goal.label}
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset className="space-y-2">
        <legend className="font-semibold">Preferred workload</legend>
        <div className="grid gap-2 sm:grid-cols-3">
          {WORKLOADS.map((workload) => (
            <label key={workload.id} className="flex items-start gap-2 rounded-button border border-border px-3 py-2 text-sm">
              <input
                type="radio"
                name="workload"
                className="mt-1"
                checked={preferences.workload === workload.id}
                onChange={() =>
                  set({
                    workload: workload.id,
                    preferred_units: workload.units,
                    max_units: Math.max(preferences.max_units ?? 18, workload.units),
                  })
                }
              />
              <span>
                <span className="block font-medium">{workload.label}</span>
                <span className="text-text-muted">{workload.hint}</span>
              </span>
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset className="grid gap-4 sm:grid-cols-3">
        <legend className="mb-2 font-semibold">Plan settings</legend>
        <label className="text-sm">
          <span className="block font-medium">Pace</span>
          <select
            value={preferences.pace ?? "on_time"}
            onChange={(event) => set({ pace: event.target.value as PreferencesIn["pace"] })}
            className="mt-1 w-full rounded-button border border-border bg-surface px-2 py-1"
          >
            <option value="on_time">Graduate on time</option>
            <option value="fastest">Graduate as early as possible</option>
          </select>
        </label>
        <label className="text-sm">
          <span className="block font-medium">Most units in a term</span>
          <select
            value={preferences.max_units ?? 18}
            onChange={(event) => set({ max_units: Number(event.target.value) })}
            className="mt-1 w-full rounded-button border border-border bg-surface px-2 py-1"
          >
            {[12, 13, 14, 15, 16, 17, 18, 19, 20, 21].map((value) => (
              <option key={value} value={value}>
                {value} units
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 self-end text-sm">
          <input
            type="checkbox"
            checked={preferences.include_summer ?? false}
            onChange={(event) => set({ include_summer: event.target.checked })}
          />
          Also plan other courses in summer (up to {preferences.summer_max_units ?? 6} units). Internships are always in summer.
        </label>
      </fieldset>

      <div className="flex justify-between gap-2">
        <Button variant="secondary" onClick={onBack}>
          Back
        </Button>
        <Button onClick={onFinish}>See my plan</Button>
      </div>
    </Card>
  );
}
