"use client";

import { useId, useState, type ReactNode } from "react";
import { api, type AttemptIn, type PlanOut } from "@/lib/api";
import {
  DEFAULT_PAPER,
  NOTICE_TEXT,
  NOTICE_TITLE,
  PAPER_SIZES,
  SIGN_OFF_NOTE,
  currentTermLabel,
  defaultTerm,
  formatDate,
  formatIsoDate,
  isLate,
  loadSummary,
  overviewRows,
  pageStyle,
  planNotes,
  requirementRows,
  termDetail,
  type PaperSize,
  type RequirementRow,
  type TermDetail,
} from "@/lib/advisor";
import { pluralize, units } from "@/lib/format";
import { useAsync, useProfile } from "@/lib/hooks";
import { toStudent, type Profile } from "@/lib/profile";
import { Alert, Button, ButtonLink, CheckIcon, Spinner } from "@/components/ui";

// Table cells: roomy on screen, tighter on paper.
const CELL = "py-2 pe-3 print:py-1";

/**
 * F5.4: the plan as a document for an advisor, to print or save as a PDF. The chosen term
 * comes first in detail, every term at a glance can be added, and a notice says approval is
 * not a promise of courses. It looks like paper in both themes and prints without the site chrome.
 */
export function AdvisorDocument() {
  const profile = useProfile();
  if (profile === undefined) return <Spinner label="Loading your plan" />;
  if (profile === null) {
    return (
      <div className="mx-auto max-w-xl space-y-4 py-10 text-center">
        <h1 className="font-heading text-2xl font-bold">No plan yet</h1>
        <p className="text-text-muted">Set up your plan first; then you can print it for your advisor.</p>
        <ButtonLink href="/start">Start planning</ButtonLink>
      </div>
    );
  }
  return <Document profile={profile} />;
}

function Document({ profile }: { profile: Profile }) {
  const student = toStudent(profile);
  const plan = useAsync(JSON.stringify(student), () => api.plan(student));
  const [chosen, setChosen] = useState<string | null>(null);
  const [paperId, setPaperId] = useState(DEFAULT_PAPER.id);
  const [withOverview, setWithOverview] = useState(false);
  const selectId = useId();
  const paperSelectId = useId();
  const paper = PAPER_SIZES.find((size) => size.id === paperId) ?? DEFAULT_PAPER;
  const terms = plan.data?.terms.map((term) => term.term.label) ?? [];
  const label = chosen && terms.includes(chosen) ? chosen : plan.data ? defaultTerm(plan.data) : null;
  const inProgress = profile.attempts.filter((attempt) => attempt.status === "in_progress");

  return (
    <div data-print-document className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4 print:hidden">
        <div className="max-w-xl space-y-1">
          <p className="font-heading text-lg font-semibold">Plan for my advisor</p>
          <p className="text-sm text-text-muted">
            Check the document below, then print it or save it as a PDF from the print window.
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          {terms.length > 1 && (
            <div className="flex flex-col gap-1 text-sm">
              <label htmlFor={selectId} className="font-medium">
                Semester to discuss
              </label>
              <select
                id={selectId}
                value={label ?? ""}
                onChange={(event) => setChosen(event.target.value)}
                className="rounded-button border border-border bg-surface px-4 py-2"
              >
                {terms.map((term) => (
                  <option key={term}>{term}</option>
                ))}
              </select>
            </div>
          )}
          <div className="flex flex-col gap-1 text-sm">
            <label htmlFor={paperSelectId} className="font-medium">
              Paper size
            </label>
            <select
              id={paperSelectId}
              value={paper.id}
              onChange={(event) => setPaperId(event.target.value)}
              className="rounded-button border border-border bg-surface px-4 py-2"
            >
              {PAPER_SIZES.map((size) => (
                <option key={size.id} value={size.id}>
                  {size.label}
                </option>
              ))}
            </select>
          </div>
          <Button
            variant="secondary"
            aria-pressed={withOverview}
            onClick={() => setWithOverview((included) => !included)}
            className={withOverview ? "border-primary text-primary" : ""}
          >
            {withOverview && <CheckIcon />}
            Include every term at a glance
          </Button>
          <ButtonLink href="/plan" variant="secondary">
            Back to my plan
          </ButtonLink>
          <Button onClick={() => window.print()} disabled={!plan.data}>
            Print or save as PDF
          </Button>
        </div>
      </div>

      {plan.error && (
        <Alert tone="error" title="The plan could not be made">
          {plan.error}
        </Alert>
      )}
      {plan.loading && !plan.data && <Spinner label="Preparing the document" />}
      {/* The paper size for printing; the browser's print window follows it. */}
      <style>{pageStyle(paper)}</style>
      {plan.data && (
        <Sheet
          plan={plan.data}
          profile={profile}
          inProgress={inProgress}
          label={label}
          paper={paper}
          withOverview={withOverview}
        />
      )}
    </div>
  );
}

function Sheet({
  plan,
  profile,
  inProgress,
  label,
  paper,
  withOverview,
}: {
  plan: PlanOut;
  profile: Profile;
  inProgress: AttemptIn[];
  label: string | null;
  paper: PaperSize;
  withOverview: boolean;
}) {
  const detail = label ? termDetail(plan, label) : null;
  const source = plan.catalog;
  const graduation = plan.graduation_term
    ? `${plan.graduation_term.label}${
        plan.on_time_term ? (isLate(plan) ? ` (standard finish: ${plan.on_time_term.label})` : " (on time)") : ""
      }`
    : "Every requirement is covered";
  const today = formatDate(new Date());

  return (
    <article
      aria-labelledby="advisor-title"
      style={{ maxWidth: paper.width }}
      className="mx-auto bg-paper px-5 py-6 text-sm leading-relaxed text-paper-ink shadow-[0_2px_12px_rgba(0,0,0,0.18)] sm:px-12 sm:py-10 print:max-w-none print:p-0 print:text-[9.5pt] print:leading-snug print:shadow-none"
    >
      <header className="space-y-4 border-b-2 border-paper-accent pb-5 print:space-y-3 print:pb-3">
        <div className="space-y-1">
          <p className="text-xs font-medium tracking-wider text-paper-accent uppercase">
            AUIB Academic Advisor · planning document
          </p>
          <h1 id="advisor-title" className="font-heading text-2xl font-bold print:text-[17pt]">
            Course plan for advising
          </h1>
        </div>
        <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-3 lg:grid-cols-4 print:grid-cols-4 print:gap-y-2">
          <Fact term="Program">{source.program_name}</Fact>
          {plan.minor && <Fact term="Minor">{plan.minor.name}</Fact>}
          <Fact term="Catalog year">{source.catalog_year ?? "Not confirmed yet"}</Fact>
          <Fact term="Requirements as of">
            {source.source_date ? `${formatIsoDate(source.source_date)} (SIS)` : "Unknown date"}
          </Fact>
          <Fact term="Semester discussed">{label ?? "None left to plan"}</Fact>
          <Fact term="Expected graduation">{graduation}</Fact>
          <Fact term="Prepared">{today}</Fact>
          {plan.gpa && <Fact term="CGPA (estimate)">{plan.gpa.cumulative.toFixed(2)}</Fact>}
        </dl>
        <div className="grid gap-x-8 gap-y-4 pt-1 sm:grid-cols-2 print:grid-cols-2">
          <FillIn label="Student name" />
          <FillIn label="Student ID" />
        </div>
      </header>

      <div
        role="note"
        aria-labelledby="notice-title"
        className="my-6 border-2 border-paper-ink p-4 break-inside-avoid print:my-4 print:p-3"
      >
        <p id="notice-title" className="font-bold">
          Important: {NOTICE_TITLE}
        </p>
        <p className="mt-1">{NOTICE_TEXT}</p>
      </div>

      <section aria-labelledby="term-title" className="space-y-4 print:space-y-3">
        <SheetHeading id="term-title">1. {label ? `${label}: planned courses` : "Next semester"}</SheetHeading>
        {detail ? (
          <TermSection detail={detail} profile={profile} inProgress={inProgress} />
        ) : (
          <p>No courses are left to plan.</p>
        )}
      </section>

      {withOverview && <Overview plan={plan} profile={profile} inProgress={inProgress} label={label} />}

      <section aria-labelledby="review-title" className="mt-10 space-y-4 break-inside-avoid print:mt-8">
        <SheetHeading id="review-title">{withOverview ? 3 : 2}. Advisor review</SheetHeading>
        <p>{SIGN_OFF_NOTE}</p>
        <div className="space-y-1">
          <p className="font-semibold">Advisor notes</p>
          {[0, 1, 2, 3].map((line) => (
            <div key={line} aria-hidden className="h-8 border-b border-paper-rule" />
          ))}
        </div>
        <div className="grid gap-x-8 gap-y-5 pt-2 sm:grid-cols-3 print:grid-cols-3">
          <FillIn label="Advisor name" />
          <FillIn label="Signature" />
          <FillIn label="Date" />
        </div>
      </section>

      <footer className="mt-10 space-y-2 border-t border-paper-rule pt-3 text-xs text-paper-muted print:mt-8 print:text-[7.5pt]">
        <p>
          <span className="font-semibold">How this plan was made.</span> {plan.assumptions.join(" ")}
        </p>
        <p>
          Prepared on {today} with the AUIB Academic Advisor, a student-built planning aid that is not an official
          AUIB service, from the courses the student entered. Units are as counted by the app; the degree audit in SIS
          is authoritative.
        </p>
      </footer>
    </article>
  );
}

function TermSection({ detail, profile, inProgress }: { detail: TermDetail; profile: Profile; inProgress: AttemptIn[] }) {
  const usual = profile.preferences.preferred_units ?? 15;
  const most = profile.preferences.max_units ?? 18;
  const current = currentTermLabel(inProgress);
  return (
    <>
      <ScrollTable label={`Courses planned for ${detail.term.term.label}`}>
        <thead>
          <tr className="border-b-2 border-paper-ink text-left">
            <Th className="w-[30%]">Course</Th>
            <Th className="text-right">Units</Th>
            <Th className="w-[22%]">Counts toward</Th>
            <Th>Notes for the advisor</Th>
          </tr>
        </thead>
        <tbody>
          {detail.rows.map((row) => (
            <tr key={row.key} className="border-b border-paper-rule align-top break-inside-avoid">
              <td className={CELL}>
                {row.choice ? (
                  <WriteIn label={`Open choice for ${row.countsToward ?? "this requirement"}: write in the course`} />
                ) : (
                  <>
                    <span className="font-semibold">{row.code}</span>
                    <br />
                    {row.title}
                  </>
                )}
              </td>
              <td className={`${CELL} text-right tabular-nums`}>{units(row.units)}</td>
              <td className={CELL}>
                {row.countsToward.length > 0
                  ? row.countsToward.map((label) => (
                      <span key={label} className="block">
                        {label}
                      </span>
                    ))
                  : "Not counted toward a requirement"}
              </td>
              <td className={`${CELL} pe-0`}>
                {row.notes.length > 0 ? (
                  <ul className="space-y-0.5">
                    {row.notes.map((note) => (
                      <li key={note}>{note}</li>
                    ))}
                  </ul>
                ) : (
                  "None"
                )}
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="border-t-2 border-paper-ink align-top">
            <th scope="row" className={`${CELL} text-left font-semibold`}>
              Total
            </th>
            <td className={`${CELL} text-right font-semibold tabular-nums`}>{units(detail.term.units)}</td>
            <td colSpan={2} className={`${CELL} pe-0`}>
              The student&apos;s usual load is {units(usual)} units, at most {units(most)}.
              {detail.term.units > usual && " This term is above the usual load."}
            </td>
          </tr>
        </tfoot>
      </ScrollTable>

      {inProgress.length > 0 && (
        <p>
          <span className="font-semibold">Assumes these courses in progress{current ? ` (${current})` : ""} are passed:</span>{" "}
          {inProgress.map((attempt) => attempt.code).join(", ")}.
        </p>
      )}
      {detail.warnings.length > 0 && (
        <div className="break-inside-avoid">
          <p className="font-semibold">Warnings</p>
          <ul className="list-disc ps-5">
            {detail.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      )}
      {detail.otherOptions.length > 0 && (
        <div className="break-inside-avoid">
          <p className="font-semibold">
            Other courses the student can take in {detail.term.term.label} (prerequisites met):
          </p>
          <ul className="mt-1 space-y-0.5">
            {detail.otherOptions.map((group) => (
              <li key={group.requirement}>
                <span className="font-medium">{group.requirement}:</span>{" "}
                {group.courses.map((course) => course.code).join(", ")}
                {group.more > 0 && ` and ${group.more} more`}
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  );
}

function Overview({
  plan,
  profile,
  inProgress,
  label,
}: {
  plan: PlanOut;
  profile: Profile;
  inProgress: AttemptIn[];
  label: string | null;
}) {
  const rows = overviewRows(plan, inProgress);
  const requirements = requirementRows(plan.progress_with_plan);
  const notes = planNotes(plan, label);
  const first = plan.terms[0]?.term.label;
  const last = plan.terms.at(-1)?.term.label;
  return (
    <section aria-labelledby="overview-title" className="mt-10 space-y-4 print:mt-0 print:space-y-3 print:break-before-page">
      <SheetHeading id="overview-title">2. Every term at a glance</SheetHeading>
      <p>
        {first && last
          ? `${pluralize(plan.terms.length, "term")} planned, from ${first} to ${last}. `
          : "No terms left to plan. "}
        {loadSummary(profile.preferences)}
      </p>
      <ScrollTable label="Courses by term">
        <thead>
          <tr className="border-b-2 border-paper-ink text-left">
            <Th className="w-[20%]">Term</Th>
            <Th>Courses</Th>
            <Th className="text-right">Units</Th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label} className="border-b border-paper-rule align-top break-inside-avoid">
              <th scope="row" className={`${CELL} text-left font-semibold`}>
                {row.label}
                {row.current && <span className="block text-xs font-normal text-paper-muted">In progress now</span>}
                {row.label === label && (
                  <span className="block text-xs font-normal text-paper-muted">Detailed in section 1</span>
                )}
              </th>
              <td className={CELL}>
                <ul className="gap-x-6 sm:columns-2 print:columns-2">
                  {row.courses.map((course) => (
                    <li key={course.key} className="break-inside-avoid">
                      {course.code ? (
                        <>
                          <span className="font-semibold">{course.code}</span> {course.title}
                        </>
                      ) : (
                        <span className="italic">{course.title}</span>
                      )}
                    </li>
                  ))}
                </ul>
              </td>
              <td className={`${CELL} pe-0 text-right tabular-nums`}>{units(row.units)}</td>
            </tr>
          ))}
        </tbody>
      </ScrollTable>

      <RequirementTable title="Requirements once this plan is complete" label="Units by requirement" rows={requirements} />
      {plan.minor && (
        <RequirementTable
          title={`Minor in ${plan.minor.name} once this plan is complete`}
          label="Units by minor requirement"
          rows={requirementRows(plan.minor.progress_with_plan, "Minor total")}
        />
      )}
      <p className="text-xs text-paper-muted">
        Units, as counted by this app; a course can count toward the major and the minor. Compare them with the
        degree audit in SIS.
      </p>

      {(notes.warnings.length > 0 || notes.checks.length > 0) && (
        <div className="break-inside-avoid">
          <p className="font-semibold">Notes on the whole plan</p>
          <ul className="list-disc ps-5">
            {notes.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
            {notes.checks.map((check) => (
              <li key={check}>To confirm before that term: {check}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

function RequirementTable({ title, label, rows }: { title: string; label: string; rows: RequirementRow[] }) {
  return (
    <div className="space-y-2 pt-2 break-inside-avoid">
      <h3 className="font-heading font-bold">{title}</h3>
      <ScrollTable label={label}>
        <thead>
          <tr className="border-b-2 border-paper-ink text-left">
            <Th>Requirement</Th>
            <Th className="text-right">Needed</Th>
            <Th className="text-right">Done</Th>
            <Th className="text-right">In progress</Th>
            <Th className="text-right">Planned</Th>
            <Th className="text-right">Left</Th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => {
            const total = index === rows.length - 1;
            return (
              <tr
                key={row.label}
                className={`align-top ${total ? "border-t-2 border-paper-ink font-semibold" : "border-b border-paper-rule"}`}
              >
                <th scope="row" className={`${CELL} text-left ${total ? "font-semibold" : "font-normal"}`}>
                  {row.label}
                </th>
                {[row.required, row.completed, row.inProgress, row.planned, row.left].map((value, column) => (
                  <td key={column} className={`${CELL} text-right tabular-nums last:pe-0`}>
                    {units(value)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </ScrollTable>
    </div>
  );
}

function SheetHeading({ id, children }: { id: string; children: ReactNode }) {
  return (
    <h2 id={id} className="font-heading text-lg font-bold text-paper-accent print:text-[13pt]">
      {children}
    </h2>
  );
}

/** A label above its value, like a form; the label is small so the values stand out. */
function Fact({ term, children }: { term: string; children: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs font-medium tracking-wide text-paper-muted uppercase print:text-[7.5pt]">{term}</dt>
      <dd className="font-medium">{children}</dd>
    </div>
  );
}

/** A blank line in the course column, for the course chosen in the advising session. */
function WriteIn({ label }: { label: string }) {
  return (
    <span className="block">
      <span className="sr-only">{label}</span>
      <span aria-hidden className="block h-7 border-b border-paper-ink print:h-6" />
    </span>
  );
}

/** A label and a line to write on by hand: the app never asks for names or IDs. */
function FillIn({ label }: { label: string }) {
  return (
    <div className="flex items-end gap-2">
      <span className="shrink-0 font-semibold">{label}:</span>
      <span aria-hidden className="h-6 min-w-0 flex-1 border-b border-paper-ink" />
    </div>
  );
}

function Th({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <th scope="col" className={`py-2 pe-3 font-semibold last:pe-0 print:py-1 ${className}`}>
      {children}
    </th>
  );
}

/** Tables keep their columns on a phone and scroll sideways inside their own box; print shows them whole. */
function ScrollTable({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div role="region" aria-label={label} tabIndex={0} className="relative overflow-x-auto print:overflow-visible">
      <table aria-label={label} className="w-full min-w-[34rem] border-collapse print:min-w-0">
        {children}
      </table>
    </div>
  );
}
