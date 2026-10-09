"use client";

import { useEffect, useRef, useState, type MouseEvent } from "react";
import { api, type PreferencesIn, type Question } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { answer, selectedIn, visibleQuestions } from "@/lib/questions";
import { ArrowLeftIcon, ArrowRightIcon, SparklesIcon } from "@/components/icons";
import { Alert, Button, CheckIcon, Segmented, Select, Skeleton, Switch } from "@/components/ui";
import { StepCard } from "./StepCard";

const WORKLOADS = [
  { id: "light", label: "Lighter", hint: "About 12 credits a term", units: 12, bars: 1 },
  { id: "balanced", label: "Balanced", hint: "About 15 credits a term", units: 15, bars: 2 },
  { id: "challenging", label: "Challenging", hint: "Up to 18 credits a term", units: 18, bars: 3 },
] as const;

// A single-choice answer moves on by itself after this pause, so the choice is seen first.
const ADVANCE_MS = 220;

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

/**
 * F2.1: a few quick questions, one at a time. They come from the API for the student's major: which
 * parts of it they enjoy, what else interests them, what they would rather avoid in a course, and their
 * plans after graduating. The last screen sets the pace.
 */
export function GoalsStep({
  programId,
  preferences,
  onChange,
  onBack,
  onFinish,
}: {
  programId: string;
  preferences: PreferencesIn;
  onChange: (preferences: PreferencesIn) => void;
  onBack: () => void;
  onFinish: () => void;
}) {
  const loaded = useAsync(`questions|${programId}`, () => api.questions(programId));
  const questions = loaded.data?.questions ?? [];
  const asked = visibleQuestions(questions, preferences);
  const [index, setIndex] = useState(0);
  const atPace = !loaded.loading && index >= asked.length;
  const question = atPace ? null : (asked[index] ?? null);

  // Each new screen's heading takes focus, so screen-reader users hear the next question.
  const heading = useRef<HTMLHeadingElement>(null);
  const firstScreen = useRef(true);
  useEffect(() => {
    if (firstScreen.current) {
      firstScreen.current = false;
      return;
    }
    heading.current?.focus();
  }, [index]);

  const next = () => setIndex((current) => current + 1);
  const pick = (target: Question, optionId: string) => onChange(answer(questions, target, preferences, optionId));
  const chosen = question ? selectedIn(question, preferences) : [];

  return (
    <StepCard
      icon={<SparklesIcon />}
      title="A few quick questions"
      description="About a minute. Your answers decide which electives are suggested first, and you can change them any time."
      footer={
        <>
          <Button variant="secondary" onClick={() => (index === 0 ? onBack() : setIndex(Math.min(index, asked.length) - 1))}>
            <ArrowLeftIcon className="h-4 w-4" />
            Back
          </Button>
          {atPace ? (
            <Button size="lg" onClick={onFinish}>
              See my plan
              <ArrowRightIcon className="h-5 w-5" />
            </Button>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="quiet" size="sm" onClick={() => setIndex(asked.length)} disabled={loaded.loading}>
                Skip to the end
              </Button>
              <Button onClick={next} disabled={loaded.loading}>
                {chosen.length > 0 ? "Next" : "Skip"}
                <ArrowRightIcon className="h-4 w-4" />
              </Button>
            </div>
          )}
        </>
      }
    >
      <Progress current={Math.min(index, asked.length)} total={asked.length} loading={loaded.loading} />

      {loaded.loading && (
        <div role="status" aria-label="Loading the questions" className="space-y-3">
          <Skeleton className="h-6 w-72 max-w-full" />
          <div className="flex flex-wrap gap-2">
            {[1, 2, 3, 4, 5].map((n) => (
              <Skeleton key={n} className="h-10 w-36 rounded-full" />
            ))}
          </div>
        </div>
      )}
      {loaded.error && !question && index === 0 && (
        <Alert tone="info">The questions could not be loaded. You can still choose your pace and see your plan.</Alert>
      )}

      {question && (
        <fieldset key={question.id} className="animate-fade-up space-y-4">
          <legend>
            <h3 ref={heading} tabIndex={-1} className="font-heading text-xl font-bold tracking-tight focus:outline-none">
              {question.title}
            </h3>
          </legend>
          <p className="text-sm text-text-muted">{question.hint}</p>
          {question.kind === "multi" ? (
            <div className="flex flex-wrap gap-2">
              {question.options.map((option) => {
                const checked = chosen.includes(option.id);
                return (
                  <label
                    key={option.id}
                    className={`inline-flex min-h-11 cursor-pointer items-center gap-1.5 rounded-full border px-4 text-sm transition duration-200 has-[:focus-visible]:outline has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-primary ${
                      checked
                        ? "border-primary bg-primary text-primary-contrast shadow-soft"
                        : "border-border-strong bg-surface hover:border-primary hover:text-primary"
                    }`}
                  >
                    <input
                      type="checkbox"
                      className="sr-only"
                      checked={checked}
                      onChange={() => pick(question, option.id)}
                    />
                    {checked && <CheckIcon className="h-3.5 w-3.5 animate-pop" />}
                    {option.label}
                  </label>
                );
              })}
            </div>
          ) : (
            <div className="grid gap-2 sm:grid-cols-2">
              {question.options.map((option) => {
                const checked = chosen.includes(option.id);
                return (
                  <label
                    key={option.id}
                    className={`${CHOICE_CARD} items-center`}
                    // A tap or click moves on; choosing with the arrow keys does not (the click they
                    // cause has no pointer behind it, so its detail is 0). The click the label passes on
                    // to its radio button reaches here too, and is not counted twice.
                    onClick={(event: MouseEvent) => {
                      if (event.detail > 0 && !(event.target instanceof HTMLInputElement)) {
                        window.setTimeout(next, ADVANCE_MS);
                      }
                    }}
                  >
                    <input
                      type="radio"
                      name={question.id}
                      className="sr-only"
                      checked={checked}
                      onChange={() => pick(question, option.id)}
                    />
                    <RadioDot checked={checked} />
                    <span className={checked ? "font-semibold" : ""}>{option.label}</span>
                  </label>
                );
              })}
            </div>
          )}
        </fieldset>
      )}

      {atPace && (
        <div className="animate-fade-up space-y-6">
          <h3 ref={heading} tabIndex={-1} className="font-heading text-xl font-bold tracking-tight focus:outline-none">
            How busy do you want your terms?
          </h3>
          <Pace preferences={preferences} onChange={onChange} />
        </div>
      )}
    </StepCard>
  );
}

/** "Question 2 of 5" and a bar with one segment per question and one for the pace. */
function Progress({ current, total, loading }: { current: number; total: number; loading: boolean }) {
  if (loading) return <Skeleton className="h-2 w-full rounded-full" />;
  const done = current >= total;
  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-text-muted" aria-live="polite">
        {done ? "Last step" : `Question ${current + 1} of ${total}`}
      </p>
      <div aria-hidden className="flex gap-1.5">
        {Array.from({ length: total + 1 }, (_, segment) => (
          <span
            key={segment}
            className={`h-1.5 flex-1 rounded-full transition-colors duration-300 ${segment <= current ? "bg-primary" : "bg-border"}`}
          />
        ))}
      </div>
    </div>
  );
}

function Pace({ preferences, onChange }: { preferences: PreferencesIn; onChange: (preferences: PreferencesIn) => void }) {
  const set = (changes: Partial<PreferencesIn>) => onChange({ ...preferences, ...changes });
  return (
    <>
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
    </>
  );
}
