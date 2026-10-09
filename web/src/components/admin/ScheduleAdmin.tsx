"use client";

import { useEffect, useState } from "react";
import { api, type ScheduleSummary } from "@/lib/api";
import { pluralize } from "@/lib/format";
import { useAsync } from "@/lib/hooks";
import { CalendarIcon, TrashIcon, UploadIcon } from "@/components/icons";
import { Alert, Button, Dialog, FIELD, Select, Skeleton } from "@/components/ui";
import { TableUploader, errorText, type UploadResult } from "./TableUploader";

const SEASONS = ["Spring", "Summer", "Fall"] as const;

function nextTerm(today = new Date()): { season: (typeof SEASONS)[number]; year: number } {
  const month = today.getMonth() + 1;
  if (month <= 5) return { season: "Fall", year: today.getFullYear() };
  return { season: "Spring", year: today.getFullYear() + 1 };
}

/** F0.5: the registrar's schedule for a term. A term with a schedule only plans courses on it. */
export function ScheduleAdmin({ token, onUnauthorized }: { token: string; onUnauthorized: () => void }) {
  const [version, setVersion] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [viewing, setViewing] = useState<ScheduleSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const list = useAsync(`schedules|${version}`, () => api.admin.schedules(token), { keepPrevious: true });
  const refresh = () => setVersion((v) => v + 1);
  const unauthorized = list.error?.includes("admin token") ?? false;
  useEffect(() => {
    if (unauthorized) onUnauthorized();
  }, [unauthorized, onUnauthorized]);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-2xl text-sm text-text-muted">
          When a term has a published schedule, only the courses on it are planned in that term. Terms without one
          assume each course runs in its usual season.
        </p>
        <Button onClick={() => setUploading(!uploading)} aria-expanded={uploading}>
          <UploadIcon className="h-4 w-4" />
          Upload a term&apos;s schedule
        </Button>
      </div>
      {uploading && <UploadSchedule token={token} onSaved={refresh} />}
      {error && <Alert tone="error">{error}</Alert>}
      {list.error && !unauthorized && <Alert tone="error">{list.error}</Alert>}
      {!list.data && !list.error && <Skeleton className="h-40 rounded-card" />}
      {list.data?.length === 0 && (
        <p className="rounded-card border border-dashed border-border-strong p-8 text-center text-sm text-text-muted">
          No schedules yet. Every term is planned by season.
        </p>
      )}
      {list.data && list.data.length > 0 && (
        <ul className="grid gap-3 md:grid-cols-2">
          {list.data.map((schedule) => (
            <li key={schedule.term.label} className="flex flex-wrap items-center gap-3 rounded-card border border-border bg-surface p-4 shadow-soft">
              <span className="grid h-10 w-10 place-items-center rounded-xl bg-tint text-primary">
                <CalendarIcon />
              </span>
              <div className="min-w-0 flex-1">
                <p className="font-semibold">{schedule.term.label}</p>
                <p className="text-xs text-text-muted">
                  {pluralize(schedule.courses, "course")}, {pluralize(schedule.sections, "section")} · {new Date(schedule.updated_at).toLocaleString()}{" "}
                  by {schedule.updated_by}
                </p>
              </div>
              <div className="flex gap-2">
                <Button variant="secondary" size="sm" onClick={() => setViewing(schedule)}>
                  View
                </Button>
                <Button
                  variant="quiet"
                  size="sm"
                  aria-label={`Remove the ${schedule.term.label} schedule`}
                  onClick={async () => {
                    if (!window.confirm(`Remove the ${schedule.term.label} schedule? That term is then planned by season.`)) return;
                    setError(null);
                    try {
                      await api.admin.deleteSchedule(token, schedule.term.year, schedule.term.season);
                      refresh();
                    } catch (caught) {
                      setError(errorText(caught));
                    }
                  }}
                >
                  <TrashIcon className="h-4 w-4" />
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}
      {viewing && <ScheduleDialog token={token} schedule={viewing} onClose={() => setViewing(null)} />}
    </div>
  );
}

function UploadSchedule({ token, onSaved }: { token: string; onSaved: () => void }) {
  const initial = nextTerm();
  const [season, setSeason] = useState<string>(initial.season);
  const [year, setYear] = useState(initial.year);
  const term = `${season} ${year}`;
  const describe = (result: UploadResult) =>
    `${term}: ${pluralize(result.counts.sections ?? 0, "section")} of ${pluralize(result.counts.courses ?? 0, "course")}` +
    (result.counts.skipped ? `; ${pluralize(result.counts.skipped, "row")} skipped (listed below).` : ".");
  return (
    <section className="space-y-4 rounded-card border border-border bg-surface p-5 shadow-card animate-fade-up">
      <div>
        <h3 className="font-heading text-lg font-bold">Upload a term&apos;s schedule</h3>
        <p className="text-sm text-text-muted">The upload replaces any schedule the term already has.</p>
      </div>
      <TableUploader
        extra={
          <div className="flex flex-wrap gap-3">
            <label className="text-sm">
              <span className="mb-1 block font-medium">Term</span>
              <Select value={season} onChange={(e) => setSeason(e.target.value)} wrapperClassName="w-36">
                {SEASONS.map((name) => (
                  <option key={name}>{name}</option>
                ))}
              </Select>
            </label>
            <label className="text-sm">
              <span className="mb-1 block font-medium">Year</span>
              <input
                type="number"
                min={2000}
                max={2100}
                value={year}
                onChange={(e) => setYear(Number(e.target.value))}
                className={`${FIELD} w-28`}
              />
            </label>
          </div>
        }
        columnsHelp={
          <>
            Columns: <strong>code</strong> (or <strong>subject</strong> and <strong>catalog number</strong>), and if
            you have them: section, days, time (or start and end), instructor, room. A SIS class-search export
            usually works as it is. Rows for courses that are not in the catalog are skipped and listed.
          </>
        }
        saveLabel={() => `Publish the ${term} schedule`}
        summary={describe}
        onSubmit={async (upload, dryRun) => {
          const result = await api.admin.uploadSchedule(token, { ...upload, term });
          if (!dryRun) onSaved();
          return result;
        }}
      />
    </section>
  );
}

function ScheduleDialog({
  token,
  schedule,
  onClose,
}: {
  token: string;
  schedule: ScheduleSummary;
  onClose: () => void;
}) {
  const detail = useAsync(`schedule|${schedule.term.label}`, () =>
    api.admin.schedule(token, schedule.term.year, schedule.term.season),
  );
  return (
    <Dialog open wide title={`${schedule.term.label} schedule`} onClose={onClose}>
      {detail.error && <Alert tone="error">{detail.error}</Alert>}
      {!detail.data && !detail.error && <Skeleton className="h-64 rounded-xl" />}
      {detail.data && (
        <div role="region" aria-label="Sections" tabIndex={0} className="overflow-x-auto">
          <table className="w-full min-w-[40rem] text-sm">
            <thead className="text-xs text-text-muted">
              <tr className="border-b border-border">
                {["Course", "Section", "Days", "Time", "Instructor", "Room"].map((heading) => (
                  <th key={heading} scope="col" className="py-2 pe-3 text-start font-medium">
                    {heading}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {detail.data.offerings.map((offering, index) => (
                <tr key={index} className="border-b border-border">
                  <td className="py-2 pe-3">
                    <span className="font-semibold">{offering.code}</span>{" "}
                    <span className="text-text-muted">{offering.title}</span>
                  </td>
                  <td className="py-2 pe-3">{offering.section}</td>
                  <td className="py-2 pe-3">{offering.days}</td>
                  <td className="py-2 pe-3 whitespace-nowrap">{offering.time}</td>
                  <td className="py-2 pe-3">{offering.instructor}</td>
                  <td className="py-2">{offering.room}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Dialog>
  );
}
