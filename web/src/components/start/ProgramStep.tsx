"use client";

import type { ProgramSummary } from "@/lib/api";
import { Alert, Button, Card } from "@/components/ui";

export function ProgramStep({
  majors,
  minors,
  programId,
  minorId,
  onChange,
  onMinorChange,
  onNext,
}: {
  majors: ProgramSummary[];
  minors: ProgramSummary[];
  programId: string;
  minorId: string;
  onChange: (id: string) => void;
  onMinorChange: (id: string) => void;
  onNext: () => void;
}) {
  return (
    <Card className="space-y-5">
      <div className="space-y-2">
        <label htmlFor="major" className="block font-semibold">
          Your major
        </label>
        <select
          id="major"
          value={programId}
          onChange={(event) => onChange(event.target.value)}
          className="w-full rounded-button border border-border bg-surface px-3 py-2"
        >
          <option value="" disabled>
            Choose a major
          </option>
          {majors.map((program) => (
            <option key={program.id} value={program.id}>
              {program.name}
            </option>
          ))}
        </select>
        <p className="text-sm text-text-muted">
          Only programs whose requirements have been loaded are listed. Computer Science is first; more
          programs follow as their data is imported.
        </p>
      </div>

      <div className="space-y-2">
        <label htmlFor="minor" className="block font-semibold">
          Minor <span className="font-normal text-text-muted">(optional)</span>
        </label>
        <select
          id="minor"
          value={minors.some((minor) => minor.id === minorId) ? minorId : ""}
          onChange={(event) => onMinorChange(event.target.value)}
          disabled={minors.length === 0}
          className="w-full rounded-button border border-border bg-surface px-3 py-2 disabled:bg-background disabled:text-text-muted"
          aria-describedby="minor-help"
        >
          <option value="">{minors.length ? "No minor" : "No minors available yet"}</option>
          {minors.map((minor) => (
            <option key={minor.id} value={minor.id}>
              {minor.name}
            </option>
          ))}
        </select>
        <p id="minor-help" className="text-sm text-text-muted">
          A course can count toward your major and your minor at the same time, so a minor often adds few
          extra courses. Declaring a minor is done with your advisor and the Registrar.
        </p>
      </div>

      {majors.length === 0 && (
        <Alert tone="warning" title="No programs available">
          The program data has not been imported on this server yet.
        </Alert>
      )}
      <div className="flex justify-end">
        <Button onClick={onNext} disabled={!programId}>
          Next
        </Button>
      </div>
    </Card>
  );
}
