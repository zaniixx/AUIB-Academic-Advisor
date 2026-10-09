"use client";

import { useEffect, useState } from "react";
import { api, type AdminCourse, type AdminCourseSummary, type CourseFields, type RuleCheck } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { PencilIcon, PlusIcon, RotateIcon, SearchIcon, UploadIcon } from "@/components/icons";
import {
  Alert,
  Badge,
  Button,
  Dialog,
  FIELD,
  Select,
  Skeleton,
  StatusBadge,
  Switch,
} from "@/components/ui";
import { RuleCard, RuleLanguageHelp } from "./RuleQueue";
import { TableUploader, errorText, type UploadResult } from "./TableUploader";

const FILTERS = [
  ["all", "All"],
  ["admin", "Added here"],
  ["edited", "Edited here"],
  ["source_changed", "Files changed"],
  ["hidden", "Hidden"],
] as const;

const SEASONS = [
  ["fall", "Fall"],
  ["spring", "Spring"],
  ["summer", "Summer"],
] as const;

const RULE_KINDS = [
  ["pre", "Prerequisite"],
  ["co", "Corequisite"],
  ["pre_or_co", "Pre- or corequisite"],
] as const;

export function CourseAdmin({ token, onUnauthorized }: { token: string; onUnauthorized: () => void }) {
  const [filter, setFilter] = useState("all");
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [version, setVersion] = useState(0);
  const [editing, setEditing] = useState<string | null>(null); // a code, "" for a new course
  const [bulk, setBulk] = useState(false);
  const list = useAsync(
    `${filter}|${query}|${offset}|${version}`,
    () => api.admin.courses(token, filter, query.trim(), offset),
    { keepPrevious: true },
  );
  const refresh = () => setVersion((v) => v + 1);
  const unauthorized = list.error?.includes("admin token") ?? false;
  useEffect(() => {
    if (unauthorized) onUnauthorized();
  }, [unauthorized, onUnauthorized]);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <label className="relative block w-full max-w-sm">
          <span className="sr-only">Search courses</span>
          <SearchIcon className="pointer-events-none absolute start-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
          <input
            type="search"
            placeholder="Course code or title"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setOffset(0);
            }}
            className={`${FIELD} rounded-full ps-10`}
          />
        </label>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={() => setBulk(!bulk)} aria-expanded={bulk}>
            <UploadIcon className="h-4 w-4" />
            Upload many courses
          </Button>
          <Button onClick={() => setEditing("")}>
            <PlusIcon className="h-4 w-4" />
            Add a course
          </Button>
        </div>
      </div>

      {bulk && <BulkCourses token={token} onSaved={refresh} />}

      <div className="flex flex-wrap gap-2" role="group" aria-label="Show courses">
        {FILTERS.map(([id, label]) => (
          <button
            key={id}
            type="button"
            aria-pressed={filter === id}
            onClick={() => {
              setFilter(id);
              setOffset(0);
            }}
            className={`min-h-9 cursor-pointer rounded-full border px-3.5 text-sm transition ${
              filter === id ? "border-ink bg-ink text-ink-contrast" : "border-border bg-surface hover:border-border-strong"
            }`}
          >
            {label}
            {list.data && <span className="ms-1 opacity-70">{list.data.counts[id] ?? 0}</span>}
          </button>
        ))}
      </div>

      {list.error && !unauthorized && <Alert tone="error">{list.error}</Alert>}
      {!list.data && !list.error && <Skeleton className="h-96 rounded-card" />}
      {list.data && (
        <div className={`space-y-3 transition-opacity ${list.loading ? "opacity-60" : ""}`}>
          <p className="text-sm text-text-muted">{list.data.total} course(s)</p>
          <ul className="divide-y divide-border overflow-hidden rounded-card border border-border bg-surface">
            {list.data.courses.map((course) => (
              <CourseRow key={course.code} course={course} onEdit={() => setEditing(course.code)} />
            ))}
          </ul>
          <div className="flex justify-between">
            <Button variant="secondary" size="sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 50))}>
              Previous
            </Button>
            <Button
              variant="secondary"
              size="sm"
              disabled={offset + 50 >= list.data.total}
              onClick={() => setOffset(offset + 50)}
            >
              Next
            </Button>
          </div>
        </div>
      )}

      {editing !== null && (
        <CourseDialog
          token={token}
          code={editing || null}
          onClose={() => setEditing(null)}
          onChanged={(code) => {
            refresh();
            if (code) setEditing(code);
          }}
        />
      )}
    </div>
  );
}

function CourseRow({ course, onEdit }: { course: AdminCourseSummary; onEdit: () => void }) {
  return (
    <li className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
      <div className="min-w-0 flex-1">
        <p className="text-sm">
          <span className="font-semibold">{course.code}</span> <span>{course.title}</span>{" "}
          <span className="text-xs text-text-muted">{course.units ?? 3} cr</span>
        </p>
        <div className="mt-1 flex flex-wrap gap-1">
          {course.origin === "admin" && <Badge tone="brand">Added here</Badge>}
          {course.admin_edited && course.origin === "import" && <Badge tone="brand">Edited here</Badge>}
          {course.source_changed && <StatusBadge status="warning" label="Course files changed" />}
          {course.hidden && <StatusBadge status="blocked" label="Hidden" />}
        </div>
      </div>
      <Button variant="ghost" size="sm" onClick={onEdit} aria-label={`Edit ${course.code}`}>
        <PencilIcon className="h-4 w-4" />
        Edit
      </Button>
    </li>
  );
}

function fieldsOf(course: AdminCourse | null): CourseFields {
  return {
    title: course?.title ?? "",
    units: course?.units ?? 3,
    description: course?.description ?? "",
    component: course?.component ?? null,
    offered_terms: (course?.offered_terms ?? null) as CourseFields["offered_terms"],
    notices: course?.notices ?? [],
  };
}

function CourseDialog({
  token,
  code,
  onClose,
  onChanged,
}: {
  token: string;
  code: string | null;
  onClose: () => void;
  onChanged: (code: string | null) => void;
}) {
  const [version, setVersion] = useState(0);
  const [notice, setNotice] = useState<string | null>(null);
  const loaded = useAsync(code ? `${code}|${version}` : null, () => api.admin.course(token, code ?? ""));
  const course = code ? loaded.data ?? null : null;
  const title = code ? `Edit ${code}` : "Add a course";
  return (
    <Dialog open wide title={title} onClose={onClose}>
      {code && loaded.loading && !course && <Skeleton className="h-80 rounded-xl" />}
      {loaded.error && <Alert tone="error">{loaded.error}</Alert>}
      {notice && (
        <div className="mb-4">
          <Alert tone="success">{notice}</Alert>
        </div>
      )}
      {(!code || course) && (
        <CourseForm
          key={`${code}|${version}`}
          token={token}
          course={course}
          onSaved={(saved, text) => {
            setNotice(text);
            onChanged(saved);
            setVersion((v) => v + 1);
          }}
        />
      )}
    </Dialog>
  );
}

function CourseForm({
  token,
  course,
  onSaved,
}: {
  token: string;
  course: AdminCourse | null;
  onSaved: (code: string, notice: string) => void;
}) {
  const [code, setCode] = useState("");
  const [fields, setFields] = useState<CourseFields>(() => fieldsOf(course));
  const [hidden, setHidden] = useState(course?.hidden ?? false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (changes: Partial<CourseFields>) => setFields({ ...fields, ...changes });
  const seasons = fields.offered_terms ?? [];

  async function act(action: () => Promise<{ code: string }>, done: string) {
    setBusy(true);
    setError(null);
    try {
      const saved = await action();
      onSaved(saved.code, done);
    } catch (caught) {
      setError(errorText(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      {course?.source_changed && course.imported_values && (
        <Alert tone="warning" title="The course files now say something different">
          Your edit is still in force. The files say: {String(course.imported_values.title)},{" "}
          {String(course.imported_values.units ?? 3)} credits. Use &ldquo;Go back to the course files&rdquo; to take
          their values instead.
        </Alert>
      )}
      <form
        className="space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          if (course) void act(() => api.admin.updateCourse(token, course.code, fields), "Saved. Plans use it now.");
          else void act(() => api.admin.createCourse(token, { ...fields, code, hidden }), "Added to the catalog.");
        }}
      >
        <div className="grid gap-4 sm:grid-cols-[10rem_1fr_7rem]">
          <label className="block text-sm">
            <span className="mb-1 block font-medium">Code</span>
            {course ? (
              <span className={`${FIELD} flex items-center bg-surface-sunken font-semibold`}>{course.code}</span>
            ) : (
              <input required value={code} onChange={(e) => setCode(e.target.value)} placeholder="CSC 395" className={FIELD} />
            )}
          </label>
          <label className="block text-sm">
            <span className="mb-1 block font-medium">Title</span>
            <input required maxLength={300} value={fields.title} onChange={(e) => set({ title: e.target.value })} className={FIELD} />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block font-medium">Credits</span>
            <input
              type="number"
              min={0}
              max={30}
              step={0.5}
              value={fields.units ?? ""}
              onChange={(e) => set({ units: e.target.value === "" ? null : Number(e.target.value) })}
              className={FIELD}
            />
          </label>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <fieldset className="text-sm">
            <legend className="mb-1 font-medium">Runs in</legend>
            <div className="flex flex-wrap gap-2">
              {SEASONS.map(([id, label]) => {
                const checked = seasons.includes(id);
                return (
                  <label
                    key={id}
                    className={`inline-flex min-h-10 cursor-pointer items-center gap-2 rounded-full border px-3.5 has-[:focus-visible]:outline has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-primary ${
                      checked ? "border-primary bg-tint text-primary" : "border-border-strong"
                    }`}
                  >
                    <input
                      type="checkbox"
                      className="sr-only"
                      checked={checked}
                      onChange={() => {
                        const next = checked ? seasons.filter((s) => s !== id) : [...seasons, id];
                        set({ offered_terms: next.length ? next : null });
                      }}
                    />
                    {label}
                  </label>
                );
              })}
            </div>
            <p className="mt-1 text-xs text-text-muted">None ticked: every Fall and Spring.</p>
          </fieldset>
          <label className="block text-sm">
            <span className="mb-1 block font-medium">Component</span>
            <Select value={fields.component ?? ""} onChange={(e) => set({ component: e.target.value || null })}>
              <option value="">Not stated</option>
              {["Lecture", "Laboratory", "Seminar", "Studio", "Internship", "Independent Study"].map((name) => (
                <option key={name}>{name}</option>
              ))}
            </Select>
          </label>
        </div>
        <div className="text-sm">
          <label htmlFor="course-description" className="mb-1 block font-medium">
            Description
          </label>
          <textarea
            id="course-description"
            rows={5}
            maxLength={20000}
            value={fields.description}
            onChange={(e) => set({ description: e.target.value })}
            aria-describedby="course-description-help"
            className={`${FIELD} resize-y`}
          />
          <p id="course-description-help" className="mt-1 text-xs text-text-muted">
            A &ldquo;Prerequisite: …&rdquo; sentence here is read into a rule for review. Corrections you made to a
            rule are kept.
          </p>
        </div>
        <label className="block text-sm">
          <span className="mb-1 block font-medium">Notices (one per line)</span>
          <textarea
            rows={2}
            value={(fields.notices ?? []).join("\n")}
            onChange={(e) => set({ notices: e.target.value.split("\n").filter((line) => line.trim()).slice(0, 20) })}
            className={`${FIELD} resize-y`}
          />
        </label>
        {!course && (
          <Switch
            id="new-course-hidden"
            checked={hidden}
            onChange={setHidden}
            label="Hidden from students"
            description="It stays in the catalog but is not shown or planned."
          />
        )}
        {error && <Alert tone="error">{error}</Alert>}
        <div className="flex flex-wrap gap-2">
          <Button type="submit" disabled={busy}>
            {course ? "Save changes" : "Add course"}
          </Button>
          {course?.imported_values && (
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() => act(() => api.admin.revertCourse(token, course.code), "Back to the course files' values.")}
            >
              <RotateIcon className="h-4 w-4" />
              Go back to the course files
            </Button>
          )}
        </div>
      </form>

      {course && (
        <>
          <section className="space-y-2 border-t border-border pt-5">
            <Switch
              id={`hide-${course.code}`}
              checked={course.hidden}
              onChange={(next) =>
                act(() => api.admin.hideCourse(token, course.code, next), next ? "Hidden from students." : "Shown again.")
              }
              label="Hidden from students"
              description="Not shown in search or plans. Students who passed it keep the credit."
            />
          </section>
          <section className="space-y-3 border-t border-border pt-5">
            <h3 className="font-heading font-bold">Prerequisites and corequisites</h3>
            {course.rules.length === 0 && <p className="text-sm text-text-muted">No rules.</p>}
            <ul className="space-y-3">
              {course.rules.map((rule) => (
                <li key={rule.id}>
                  <RuleCard rule={rule} token={token} onChanged={() => onSaved(course.code, "Rule updated.")} />
                </li>
              ))}
            </ul>
            <AddRule token={token} course={course} onAdded={() => onSaved(course.code, "Rule added.")} />
          </section>
          <section className="grid gap-4 border-t border-border pt-5 text-sm sm:grid-cols-2">
            <div>
              <h3 className="font-heading font-bold">Counts toward</h3>
              {course.counts_toward.length ? (
                <ul className="mt-2 space-y-1 text-text-muted">
                  {course.counts_toward.map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ul>
              ) : (
                <p className="mt-2 text-text-muted">No requirement lists it (free elective only).</p>
              )}
            </div>
            <div>
              <h3 className="font-heading font-bold">On published schedules</h3>
              {course.offerings.length ? (
                <ul className="mt-2 space-y-1 text-text-muted">
                  {course.offerings.map((term) => (
                    <li key={term.term.label}>
                      {term.term.label}: {term.sections.length} section(s)
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-2 text-text-muted">Not on any upcoming schedule.</p>
              )}
            </div>
          </section>
        </>
      )}
    </div>
  );
}

function AddRule({ token, course, onAdded }: { token: string; course: AdminCourse; onAdded: () => void }) {
  const free = RULE_KINDS.filter(([kind]) => !course.rules.some((rule) => rule.kind === kind));
  const [kind, setKind] = useState<string>(free[0]?.[0] ?? "pre");
  const [rule, setRule] = useState("");
  const [note, setNote] = useState("");
  const [check, setCheck] = useState<RuleCheck | null>(null);
  const [error, setError] = useState<string | null>(null);
  if (free.length === 0) return null;
  return (
    <details className="group rounded-xl border border-dashed border-border-strong p-4">
      <summary className="flex cursor-pointer items-center gap-2 text-sm font-medium">
        <PlusIcon className="h-4 w-4 text-primary" />
        Add a rule the description does not state
      </summary>
      <div className="disclosure-body mt-3 space-y-3">
        <RuleLanguageHelp />
        <div className="grid gap-3 sm:grid-cols-[12rem_1fr]">
          <label className="block text-sm">
            <span className="mb-1 block text-text-muted">Kind</span>
            <Select value={kind} onChange={(e) => setKind(e.target.value)}>
              {free.map(([id, label]) => (
                <option key={id} value={id}>
                  {label}
                </option>
              ))}
            </Select>
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-text-muted">Rule</span>
            <input
              value={rule}
              onChange={(e) => {
                setRule(e.target.value);
                setCheck(null);
              }}
              placeholder="CSC 230 AND MAT 111"
              className={`${FIELD} font-mono text-sm`}
            />
          </label>
        </div>
        <label className="block text-sm">
          <span className="mb-1 block text-text-muted">Note (why, and the source you checked)</span>
          <input value={note} maxLength={1000} onChange={(e) => setNote(e.target.value)} className={FIELD} />
        </label>
        {check && (
          <Alert tone={check.valid ? "success" : "error"}>
            {check.valid ? `Reads as: ${check.english}` : check.error}
          </Alert>
        )}
        {error && <Alert tone="error">{error}</Alert>}
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" disabled={!rule.trim()} onClick={async () => setCheck(await api.admin.check(token, rule))}>
            Check
          </Button>
          <Button
            disabled={!rule.trim()}
            onClick={async () => {
              setError(null);
              try {
                await api.admin.addRule(token, course.code, kind, rule, note || null);
                setRule("");
                setNote("");
                onAdded();
              } catch (caught) {
                setError(errorText(caught));
              }
            }}
          >
            Add rule
          </Button>
        </div>
      </div>
    </details>
  );
}

function BulkCourses({ token, onSaved }: { token: string; onSaved: () => void }) {
  const describe = (result: UploadResult) => {
    const c = result.counts;
    const parts = [
      c.create && `${c.create} new`,
      c.update && `${c.update} changed`,
      c.unchanged && `${c.unchanged} unchanged`,
      c.error && `${c.error} with problems`,
    ].filter(Boolean);
    return `${parts.join(", ") || "No rows"}.`;
  };
  return (
    <section className="space-y-4 rounded-card border border-border bg-surface p-5 shadow-card animate-fade-up">
      <div>
        <h3 className="font-heading text-lg font-bold">Upload many courses</h3>
        <p className="text-sm text-text-muted">
          New codes are added; existing ones are updated. Blank cells keep a course&apos;s current value.
        </p>
      </div>
      <TableUploader
        columnsHelp={
          <>
            Columns (the header names are matched loosely): <strong>code</strong> (required), <strong>title</strong>{" "}
            (required for new courses), credits (or units), description, component, offered (fall, spring, summer, or
            &ldquo;any&rdquo;), notices (separate several with |), hidden (yes or no). Other columns are ignored.
          </>
        }
        saveLabel={(result) => `Save ${(result.counts.create ?? 0) + (result.counts.update ?? 0)} change(s)`}
        summary={describe}
        onSubmit={async (upload, dryRun) => {
          const result = await api.admin.bulkCourses(token, upload);
          if (!dryRun) onSaved();
          return result;
        }}
      />
    </section>
  );
}
