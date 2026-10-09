"use client";

import type { ProgramSummary } from "@/lib/api";
import { joinTermOptions } from "@/lib/format";
import { ArrowRightIcon, InfoIcon, TargetIcon } from "@/components/icons";
import { Alert, Button, Select } from "@/components/ui";
import { StepCard } from "./StepCard";

export function ProgramStep({
  majors,
  minors,
  programId,
  minorId,
  onChange,
  onMinorChange,
  entryTerm,
  onEntryTermChange,
  onNext,
}: {
  majors: ProgramSummary[];
  minors: ProgramSummary[];
  programId: string;
  minorId: string;
  onChange: (id: string) => void;
  onMinorChange: (id: string) => void;
  entryTerm: string;
  onEntryTermChange: (term: string) => void;
  onNext: () => void;
}) {
  const major = majors.find((program) => program.id === programId);
  const versioned = (major?.versions?.length ?? 0) > 1;
  return (
    <StepCard
      icon={<TargetIcon />}
      title="Choose your program"
      description="Your major sets the requirements. Add a minor if you have one or are thinking about one."
      footer={
        <>
          <span />
          <Button onClick={onNext} disabled={!programId}>
            Next
            <ArrowRightIcon className="h-4 w-4" />
          </Button>
        </>
      }
    >
      <div className="space-y-2">
        <label htmlFor="major" className="block font-semibold">
          Your major
        </label>
        <Select id="major" value={programId} onChange={(event) => onChange(event.target.value)} aria-describedby="major-help">
          <option value="" disabled>
            Choose a major
          </option>
          {majors.map((program) => (
            <option key={program.id} value={program.id}>
              {program.name}
            </option>
          ))}
        </Select>
        <p id="major-help" className="text-sm text-text-muted">
          Only programs whose requirements have been loaded are listed. Computer Science is first; more programs
          follow as their data is imported.
        </p>
      </div>

      {versioned && major && (
        <div className="space-y-2 animate-fade-in">
          <label htmlFor="entry-term" className="block font-semibold">
            When did you join AUIB?
          </label>
          <Select
            id="entry-term"
            value={entryTerm}
            onChange={(event) => onEntryTermChange(event.target.value)}
            aria-describedby="entry-term-help"
          >
            <option value="">Work it out from my Course History</option>
            {joinTermOptions().map((term) => (
              <option key={term} value={term}>
                {term}
              </option>
            ))}
          </Select>
          <p id="entry-term-help" className="text-sm text-text-muted">
            {major.name} has different requirements depending on when you joined:{" "}
            {major.versions!.map((version) => version.applies_to).join("; ")}. New students can leave this as it is.
          </p>
        </div>
      )}

      <div className="space-y-2">
        <label htmlFor="minor" className="block font-semibold">
          Minor <span className="font-normal text-text-muted">(optional)</span>
        </label>
        <Select
          id="minor"
          value={minors.some((minor) => minor.id === minorId) ? minorId : ""}
          onChange={(event) => onMinorChange(event.target.value)}
          disabled={minors.length === 0}
          aria-describedby="minor-help"
        >
          <option value="">{minors.length ? "No minor" : "No minors available yet"}</option>
          {minors.map((minor) => (
            <option key={minor.id} value={minor.id}>
              {minor.name}
            </option>
          ))}
        </Select>
        <p id="minor-help" className="flex gap-2 rounded-xl bg-surface-sunken p-3 text-sm text-text-muted">
          <InfoIcon className="mt-0.5 h-4 w-4 text-status-in-progress" />
          <span>
            A course can count toward your major and your minor at the same time, so a minor often adds few extra
            courses. Declaring a minor is done with your advisor and the Registrar.
          </span>
        </p>
      </div>

      {majors.length === 0 && (
        <Alert tone="warning" title="No programs available">
          The program data has not been imported on this server yet.
        </Alert>
      )}
    </StepCard>
  );
}
