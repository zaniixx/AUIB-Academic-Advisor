"use client";

import type { MetaOut, PreferencesIn } from "@/lib/api";
import { ArrowLeftIcon, ArrowRightIcon, SparklesIcon } from "@/components/icons";
import { Button, CheckIcon, Segmented, Select, Switch } from "@/components/ui";
import { StepCard } from "./StepCard";

const WORKLOADS = [
  { id: "light", label: "Lighter", hint: "About 12 credits a term", units: 12, bars: 1 },
  { id: "balanced", label: "Balanced", hint: "About 15 credits a term", units: 15, bars: 2 },
  { id: "challenging", label: "Challenging", hint: "Up to 18 credits a term", units: 18, bars: 3 },
] as const;

// Selectable cards: the real input is visually hidden, the card shows its state and its keyboard focus.
const CHOICE_CARD =
  "relative flex cursor-pointer gap-3 rounded-xl border border-border bg-surface p-3.5 text-sm transition duration-200 hover:border-border-strong hover:shadow-soft has-[:checked]:border-primary has-[:checked]:bg-tint has-[:focus-visible]:outline has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-primary";

function RadioDot({ checked }: { checked: boolean }) {
  return (
    <span
      aria-hidden
      className={`mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full border-2 transition ${
        checked ? "border-primary" : "border-border-strong"
      }`}
    >
      <span className={`h-2.5 w-2.5 rounded-full bg-primary transition-transform duration-200 ${checked ? "scale-100" : "scale-0"}`} />
    </span>
  );
}

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
    <StepCard
      icon={<SparklesIcon />}
      title="Interests and goals"
      description="These decide which electives are suggested first. You can change them any time from your plan."
      footer={
        <>
          <Button variant="secondary" onClick={onBack}>
            <ArrowLeftIcon className="h-4 w-4" />
            Back
          </Button>
          <Button size="lg" onClick={onFinish}>
            See my plan
            <ArrowRightIcon className="h-5 w-5" />
          </Button>
        </>
      }
    >
      <fieldset className="space-y-3">
        <legend className="font-semibold">What interests you?</legend>
        <p className="text-sm text-text-muted">Pick any. Electives that match are suggested first.</p>
        <div className="flex flex-wrap gap-2">
          {meta.interests.map((interest) => {
            const checked = interests.includes(interest.id);
            return (
              <label
                key={interest.id}
                className={`inline-flex min-h-10 cursor-pointer items-center gap-1.5 rounded-full border px-4 text-sm transition duration-200 has-[:focus-visible]:outline has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-primary ${
                  checked
                    ? "border-primary bg-primary text-primary-contrast shadow-soft"
                    : "border-border-strong bg-surface hover:border-primary hover:text-primary"
                }`}
              >
                <input type="checkbox" className="sr-only" checked={checked} onChange={() => toggleInterest(interest.id)} />
                {checked && <CheckIcon className="h-3.5 w-3.5 animate-pop" />}
                {interest.label}
              </label>
            );
          })}
        </div>
      </fieldset>

      <fieldset className="space-y-3">
        <legend className="font-semibold">After graduation I want to…</legend>
        <div className="grid gap-2 sm:grid-cols-2">
          {meta.goals.map((goal) => {
            const checked = preferences.goal === goal.id;
            return (
              <label key={goal.id} className={`${CHOICE_CARD} items-center`}>
                <input type="radio" name="goal" className="sr-only" checked={checked} onChange={() => set({ goal: goal.id })} />
                <RadioDot checked={checked} />
                <span className={checked ? "font-semibold" : ""}>{goal.label}</span>
              </label>
            );
          })}
        </div>
      </fieldset>

      <fieldset className="space-y-3">
        <legend className="font-semibold">Preferred workload</legend>
        <div className="grid gap-2 sm:grid-cols-3">
          {WORKLOADS.map((workload) => {
            const checked = preferences.workload === workload.id;
            return (
              <label key={workload.id} className={CHOICE_CARD}>
                <input
                  type="radio"
                  name="workload"
                  className="sr-only"
                  checked={checked}
                  onChange={() =>
                    set({
                      workload: workload.id,
                      preferred_units: workload.units,
                      max_units: Math.max(preferences.max_units ?? 18, workload.units),
                    })
                  }
                />
                <RadioDot checked={checked} />
                <span className="min-w-0 flex-1">
                  <span className="block font-semibold">{workload.label}</span>
                  <span className="text-text-muted">{workload.hint}</span>
                  <span aria-hidden className="mt-2 flex gap-1">
                    {[1, 2, 3].map((bar) => (
                      <span
                        key={bar}
                        className={`h-1.5 flex-1 rounded-full ${bar <= workload.bars ? "bg-primary" : "bg-border"}`}
                      />
                    ))}
                  </span>
                </span>
              </label>
            );
          })}
        </div>
      </fieldset>

      <fieldset className="space-y-4 rounded-xl bg-surface-sunken p-4">
        <legend className="sr-only">Plan settings</legend>
        <p aria-hidden className="font-semibold">
          Plan settings
        </p>
        <div className="flex flex-wrap items-end gap-x-6 gap-y-4">
          <Segmented
            legend="Pace"
            name="pace"
            value={preferences.pace ?? "on_time"}
            onChange={(pace) => set({ pace })}
            options={[
              { value: "on_time", label: "Graduate on time" },
              { value: "fastest", label: "As early as possible" },
            ]}
          />
          <label className="text-sm">
            <span className="mb-2 block font-medium">Most credits in a term</span>
            <Select
              value={preferences.max_units ?? 18}
              onChange={(event) => set({ max_units: Number(event.target.value) })}
              wrapperClassName="w-36"
            >
              {[12, 13, 14, 15, 16, 17, 18, 19, 20, 21].map((value) => (
                <option key={value} value={value}>
                  {value} credits
                </option>
              ))}
            </Select>
          </label>
        </div>
        <Switch
          id="include-summer"
          checked={preferences.include_summer ?? false}
          onChange={(include_summer) => set({ include_summer })}
          label="Also plan other courses in summer"
          description={`Up to ${preferences.summer_max_units ?? 6} credits. Some courses are always in summer.`}
        />
      </fieldset>
    </StepCard>
  );
}
