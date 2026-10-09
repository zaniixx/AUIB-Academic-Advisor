"use client";

import { useEffect, useState } from "react";
import {
  api,
  type AdminProgram,
  type AdminProgramSummary,
  type Finding,
  type GroupDraft,
  type GroupDraftOut,
  type ProgramDraft,
} from "@/lib/api";
import { joinTermOptions } from "@/lib/format";
import { useAsync } from "@/lib/hooks";
import { ArrowLeftIcon, EyeOffIcon, LayersIcon, PencilIcon, PlusIcon, TrashIcon } from "@/components/icons";
import { Alert, Badge, Button, FIELD, Select, Skeleton, StatusBadge, Switch } from "@/components/ui";
import { errorText } from "./TableUploader";

const ROLES = [
  ["core", "Required (core)"],
  ["general_education", "General education"],
  ["major_elective", "Major elective"],
  ["free_elective", "Free elective (any course counts)"],
  ["other", "Choose from the list"],
] as const;

// Each group gets a local id so React keeps the right inputs when groups are added or removed.
interface EditableGroup extends Omit<GroupDraft, "children" | "courses"> {
  uid: number;
  coursesText: string;
  children: EditableGroup[];
}

let nextUid = 1;

function editable(group: GroupDraftOut): EditableGroup {
  return {
    uid: nextUid++,
    label: group.label,
    title: group.title === group.label ? null : group.title,
    role: group.role,
    units_required: group.units_required,
    coursesText: group.courses.join(", "),
    children: group.children.map(editable),
  };
}

function blankGroup(label = "", units = 3): EditableGroup {
  return { uid: nextUid++, label, title: null, role: "other", units_required: units, coursesText: "", children: [] };
}

function toDraft(group: EditableGroup): GroupDraft {
  return {
    label: group.label.trim(),
    title: group.title?.trim() || null,
    role: group.role,
    units_required: group.units_required,
    courses: group.children.length
      ? []
      : group.coursesText
          .split(/[,;\n]+/)
          .map((code) => code.trim())
          .filter(Boolean),
    children: group.children.map(toDraft),
  };
}

function slug(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 50);
}

export function ProgramAdmin({ token, onUnauthorized }: { token: string; onUnauthorized: () => void }) {
  const [version, setVersion] = useState(0);
  const [editing, setEditing] = useState<{
    id: string | null;
    kind: "major" | "minor";
    versionOf?: string; // copy this program's requirements into a new version of it (F0.4)
  } | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const list = useAsync(`programs|${version}`, () => api.admin.programs(token), { keepPrevious: true });
  const unauthorized = list.error?.includes("admin token") ?? false;
  useEffect(() => {
    if (unauthorized) onUnauthorized();
  }, [unauthorized, onUnauthorized]);

  if (editing) {
    return (
      <ProgramEditor
        token={token}
        id={editing.id}
        kind={editing.kind}
        versionOf={editing.versionOf ?? null}
        onDone={(saved) => {
          setEditing(null);
          setVersion((v) => v + 1);
          if (saved) setNotice(saved);
        }}
      />
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-2xl text-sm text-text-muted">
          Programs imported from the course files and programs added here. A program edited here is not replaced by
          a later import unless the import is run with <code>--replace-admin-edits</code>.
        </p>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={() => setEditing({ id: null, kind: "minor" })}>
            <PlusIcon className="h-4 w-4" />
            New minor
          </Button>
          <Button onClick={() => setEditing({ id: null, kind: "major" })}>
            <PlusIcon className="h-4 w-4" />
            New major
          </Button>
        </div>
      </div>
      {notice && <Alert tone="success">{notice}</Alert>}
      {list.error && !unauthorized && <Alert tone="error">{list.error}</Alert>}
      {!list.data && !list.error && <Skeleton className="h-64 rounded-card" />}
      {list.data && (
        <ul className="grid gap-3 md:grid-cols-2">
          {list.data.map((program) => (
            <ProgramCard
              key={program.id}
              program={program}
              token={token}
              onEdit={() => setEditing({ id: program.id, kind: program.kind as "major" | "minor" })}
              onNewVersion={() =>
                setEditing({ id: null, kind: program.kind as "major" | "minor", versionOf: program.id })
              }
              onChanged={() => setVersion((v) => v + 1)}
            />
          ))}
        </ul>
      )}
    </div>
  );
}

function ProgramCard({
  program,
  token,
  onEdit,
  onNewVersion,
  onChanged,
}: {
  program: AdminProgramSummary;
  token: string;
  onEdit: () => void;
  onNewVersion: () => void;
  onChanged: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const offered = program.published && !program.hidden;
  return (
    <li className="flex flex-col gap-3 rounded-card border border-border bg-surface p-4 shadow-soft">
      <div className="flex items-start gap-3">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-tint text-primary">
          <LayersIcon />
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-semibold">
            {program.kind === "minor" ? `Minor in ${program.name}` : program.name}
          </p>
          <p className="text-xs text-text-muted">
            {program.id} · {program.total_units} credits · {program.groups} requirement groups
            {program.catalog_year ? ` · catalog ${program.catalog_year}` : ""}
          </p>
          <div className="mt-2 flex flex-wrap gap-1">
            <Badge>{program.kind === "minor" ? "Minor" : "Major"}</Badge>
            {program.family !== program.id && <Badge tone="brand">Version of {program.family}</Badge>}
            {program.valid_from && <Badge>For students who joined from {program.valid_from}</Badge>}
            {offered ? <StatusBadge status="done" label="Offered to students" /> : null}
            {!program.published && <StatusBadge status="warning" label="Not published" />}
            {program.hidden && <StatusBadge status="blocked" label="Hidden" />}
            {program.origin === "admin" && <Badge tone="brand">Added here</Badge>}
            {program.admin_edited && program.origin === "import" && <Badge tone="brand">Edited here</Badge>}
          </div>
        </div>
      </div>
      {error && <Alert tone="error">{error}</Alert>}
      <div className="mt-auto flex flex-wrap gap-2">
        <Button variant="secondary" size="sm" onClick={onEdit}>
          <PencilIcon className="h-4 w-4" />
          Edit
        </Button>
        <Button variant="quiet" size="sm" onClick={onNewVersion}>
          <PlusIcon className="h-4 w-4" />
          New version
        </Button>
        <Button
          variant="quiet"
          size="sm"
          onClick={async () => {
            setError(null);
            try {
              await api.admin.hideProgram(token, program.id, !program.hidden);
              onChanged();
            } catch (caught) {
              setError(errorText(caught));
            }
          }}
        >
          <EyeOffIcon className="h-4 w-4" />
          {program.hidden ? "Show to students" : "Hide from students"}
        </Button>
      </div>
    </li>
  );
}

function ProgramEditor({
  token,
  id,
  kind,
  versionOf,
  onDone,
}: {
  token: string;
  id: string | null;
  kind: "major" | "minor";
  versionOf: string | null;
  onDone: (saved: string | null) => void;
}) {
  const source = id ?? versionOf;
  const loaded = useAsync(source ? `program|${source}` : null, () => api.admin.program(token, source ?? ""));
  if (source && !loaded.data) {
    return loaded.error ? <Alert tone="error">{loaded.error}</Alert> : <Skeleton className="h-96 rounded-card" />;
  }
  return (
    <ProgramForm
      token={token}
      existing={id ? (loaded.data ?? null) : null}
      template={versionOf ? (loaded.data ?? null) : null}
      kind={kind}
      onDone={onDone}
    />
  );
}

function ProgramForm({
  token,
  existing,
  template = null,
  kind,
  onDone,
}: {
  token: string;
  existing: AdminProgram | null;
  /** A program whose requirements a new version starts from (F0.4). */
  template?: AdminProgram | null;
  kind: "major" | "minor";
  onDone: (saved: string | null) => void;
}) {
  const base = existing ?? template;
  const family = existing ? existing.family : template ? template.family : null;
  const [name, setName] = useState(base?.name ?? "");
  const [programId, setProgramId] = useState(
    existing?.id ?? (template ? `${template.family}-${new Date().getFullYear() + 1}` : ""),
  );
  const [catalogYear, setCatalogYear] = useState(existing?.catalog_year ?? "");
  const [validFrom, setValidFrom] = useState(existing?.valid_from ?? "");
  const [totalUnits, setTotalUnits] = useState(base?.total_units ?? (kind === "minor" ? 18 : 120));
  const [source, setSource] = useState(base?.source ?? "");
  const [published, setPublished] = useState(existing?.published ?? false);
  const [acceptWarnings, setAcceptWarnings] = useState(false);
  const [root, setRoot] = useState<EditableGroup>(() =>
    base
      ? editable(base.root)
      : {
          ...blankGroup(kind === "minor" ? "Minor requirements" : "Degree requirements", kind === "minor" ? 18 : 120),
          children: [blankGroup(kind === "minor" ? "Required course" : "Major core courses")],
        },
  );
  const [findings, setFindings] = useState<Finding[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const autoId = (kind === "minor" ? "minor-" : "") + slug(name);
  const id = existing ? existing.id : programId || autoId;

  const draft = (): ProgramDraft => ({
    id,
    name: name.trim(),
    kind,
    catalog_year: catalogYear.trim() || null,
    total_units: totalUnits,
    source: source.trim() || null,
    source_date: existing?.source_date ?? null,
    published,
    accept_warnings: acceptWarnings,
    family: family && family !== id ? family : null,
    valid_from: validFrom || null,
    root: toDraft(root),
  });

  async function run(action: () => Promise<void>) {
    const problem = formProblem(root);
    if (problem) {
      setError(problem);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (caught) {
      setError(errorText(caught));
    } finally {
      setBusy(false);
    }
  }

  const errors = findings?.filter((f) => f.severity === "error") ?? [];
  const warnings = findings?.filter((f) => f.severity === "warning") ?? [];

  return (
    <div className="space-y-6">
      <Button variant="ghost" size="sm" onClick={() => onDone(null)}>
        <ArrowLeftIcon className="h-4 w-4" />
        Back to the list
      </Button>
      <div>
        <h2 className="font-heading text-2xl font-bold tracking-tight">
          {existing
            ? `Edit ${existing.name}`
            : template
              ? `New version of ${template.name}`
              : kind === "minor"
                ? "New minor"
                : "New major"}
        </h2>
        <p className="text-sm text-text-muted">
          Build the requirements as a tree: the top group holds the total, and each sub-category lists its courses
          (or has sub-categories of its own).
        </p>
      </div>

      <section className="grid gap-4 rounded-card border border-border bg-surface p-5 shadow-soft sm:grid-cols-2">
        <div className="text-sm">
          <label htmlFor="program-name" className="mb-1 block font-medium">
            Name
          </label>
          <input
            id="program-name"
            value={name}
            maxLength={200}
            onChange={(e) => setName(e.target.value)}
            placeholder={kind === "minor" ? "Data Science" : "Software Engineering"}
            aria-describedby={kind === "minor" ? "program-name-help" : undefined}
            className={FIELD}
          />
          {kind === "minor" && (
            <p id="program-name-help" className="mt-1 text-xs text-text-muted">
              Shown as &ldquo;Minor in {name || "…"}&rdquo;.
            </p>
          )}
        </div>
        <div className="text-sm">
          <label htmlFor="program-id" className="mb-1 block font-medium">
            Id
          </label>
          {existing ? (
            <span id="program-id" className={`${FIELD} flex items-center bg-surface-sunken`}>
              {existing.id}
            </span>
          ) : (
            <input
              id="program-id"
              value={programId}
              placeholder={autoId || "lowercase-with-dashes"}
              onChange={(e) => setProgramId(e.target.value)}
              aria-describedby="program-id-help"
              className={FIELD}
            />
          )}
          <p id="program-id-help" className="mt-1 text-xs text-text-muted">
            Used in links and imports; it cannot change later.
          </p>
        </div>
        <label className="block text-sm">
          <span className="mb-1 block font-medium">Total credits</span>
          <input type="number" min={1} max={400} value={totalUnits} onChange={(e) => setTotalUnits(Number(e.target.value))} className={FIELD} />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block font-medium">Catalog year</span>
          <input value={catalogYear} maxLength={20} placeholder="2026-2027" onChange={(e) => setCatalogYear(e.target.value)} className={FIELD} />
        </label>
        <div className="text-sm">
          <label htmlFor="program-valid-from" className="mb-1 block font-medium">
            Applies to students who joined from
          </label>
          <Select
            id="program-valid-from"
            value={validFrom}
            onChange={(e) => setValidFrom(e.target.value)}
            aria-describedby="program-valid-from-help"
          >
            <option value="">The start (no earlier version)</option>
            {joinTermOptions().map((term) => (
              <option key={term} value={term}>
                {term}
              </option>
            ))}
          </Select>
          <p id="program-valid-from-help" className="mt-1 text-xs text-text-muted">
            {family && family !== id
              ? `A version of ${family}. Students who joined before this term keep the earlier version.`
              : "Students follow the version that applied when they joined. Add later versions with \u201cNew version\u201d."}
          </p>
        </div>
        <label className="block text-sm sm:col-span-2">
          <span className="mb-1 block font-medium">Source (where these requirements come from)</span>
          <input value={source} maxLength={300} placeholder="Registrar's program sheet, 2026" onChange={(e) => setSource(e.target.value)} className={FIELD} />
        </label>
      </section>

      <section className="space-y-3">
        <h3 className="font-heading text-lg font-bold">Requirements</h3>
        <GroupEditor group={root} depth={0} onChange={setRoot} onRemove={null} />
      </section>

      <section className="space-y-4 rounded-card border border-border bg-surface p-5 shadow-soft">
        <Switch
          id="program-published"
          checked={published}
          onChange={setPublished}
          label="Published: offered to students"
          description="Leave this off while the program is being prepared."
        />
        {findings && (
          <div className="space-y-2">
            {findings.length === 0 && <Alert tone="success">No problems found.</Alert>}
            {errors.length > 0 && (
              <Alert tone="error" title={`${errors.length} problem(s) to fix before saving`}>
                <FindingList findings={errors} />
              </Alert>
            )}
            {warnings.length > 0 && (
              <Alert tone="warning" title={`${warnings.length} warning(s) to check`}>
                <FindingList findings={warnings} />
              </Alert>
            )}
          </div>
        )}
        {published && warnings.length > 0 && (
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={acceptWarnings} onChange={(e) => setAcceptWarnings(e.target.checked)} />
            I have checked the warnings; publish anyway
          </label>
        )}
        {error && <Alert tone="error">{error}</Alert>}
        <div className="flex flex-wrap gap-2">
          <Button
            variant="secondary"
            disabled={busy || !name.trim()}
            onClick={() =>
              run(async () => {
                setFindings((await api.admin.checkProgram(token, draft())).findings);
              })
            }
          >
            Check
          </Button>
          <Button
            disabled={busy || !name.trim()}
            onClick={() =>
              run(async () => {
                const body = draft();
                const result = existing
                  ? await api.admin.updateProgram(token, body)
                  : await api.admin.createProgram(token, body);
                setFindings(result.findings);
                if (result.saved) onDone(`${body.name} saved${body.published ? " and offered to students" : ""}.`);
              })
            }
          >
            {existing ? "Save changes" : kind === "minor" ? "Add minor" : "Add major"}
          </Button>
        </div>
      </section>
    </div>
  );
}

/** Mistakes the form can spot before asking the server, said in plain words. */
function formProblem(root: EditableGroup): string | null {
  const groups: EditableGroup[] = [];
  const walk = (group: EditableGroup) => {
    groups.push(group);
    group.children.forEach(walk);
  };
  walk(root);
  if (groups.some((group) => !group.label.trim())) return "Give every group a name: one of them is empty.";
  if (groups.some((group) => !(group.units_required > 0))) return "Every group needs more than 0 credits.";
  return null;
}

function FindingList({ findings }: { findings: Finding[] }) {
  return (
    <ul className="mt-1 list-disc space-y-0.5 ps-5">
      {findings.map((finding, index) => (
        <li key={index}>
          <span className="font-medium">{finding.where}:</span> {finding.message}
        </li>
      ))}
    </ul>
  );
}

function GroupEditor({
  group,
  depth,
  onChange,
  onRemove,
}: {
  group: EditableGroup;
  depth: number;
  onChange: (group: EditableGroup) => void;
  onRemove: (() => void) | null;
}) {
  const set = (changes: Partial<EditableGroup>) => onChange({ ...group, ...changes });
  const leaf = group.children.length === 0;
  const childUnits = group.children.reduce((sum, child) => sum + child.units_required, 0);
  return (
    <div className={`space-y-3 rounded-xl border p-4 ${depth === 0 ? "border-border-strong bg-surface shadow-soft" : "border-border bg-surface-sunken/50"}`}>
      <div className="grid gap-3 sm:grid-cols-[1fr_7rem]">
        <label className="block text-sm">
          <span className="mb-1 block font-medium">{depth === 0 ? "Top group" : "Sub-category"} name</span>
          <input value={group.label} maxLength={200} onChange={(e) => set({ label: e.target.value })} className={FIELD} />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block font-medium">Credits</span>
          <input
            type="number"
            min={0.5}
            max={400}
            step={0.5}
            value={group.units_required}
            onChange={(e) => set({ units_required: Number(e.target.value) })}
            className={FIELD}
          />
        </label>
      </div>
      {leaf ? (
        <div className="grid gap-3 sm:grid-cols-[14rem_1fr]">
          <label className="block text-sm">
            <span className="mb-1 block font-medium">Kind</span>
            <Select value={group.role ?? "other"} onChange={(e) => set({ role: e.target.value as EditableGroup["role"] })}>
              {ROLES.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          </label>
          <label className="block text-sm">
            <span className="mb-1 block font-medium">Courses (separate with commas)</span>
            <textarea
              rows={2}
              value={group.coursesText}
              onChange={(e) => set({ coursesText: e.target.value })}
              placeholder={group.role === "free_elective" ? "Leave empty: any course counts" : "CSC 231, CSC 313, CSC 333"}
              className={`${FIELD} resize-y font-mono text-xs`}
            />
          </label>
        </div>
      ) : (
        <p className={`text-xs ${Math.abs(childUnits - group.units_required) > 1e-6 ? "text-status-warning" : "text-text-muted"}`}>
          Sub-categories add up to {childUnits} of {group.units_required} credits.
        </p>
      )}
      {group.children.length > 0 && (
        <div className="space-y-3 border-s-2 border-tint-strong ps-4">
          {group.children.map((child, index) => (
            <GroupEditor
              key={child.uid}
              group={child}
              depth={depth + 1}
              onChange={(next) => set({ children: group.children.map((c, i) => (i === index ? next : c)) })}
              onRemove={() => set({ children: group.children.filter((_, i) => i !== index) })}
            />
          ))}
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        {depth < 5 && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() =>
              // A group's own courses move into its first sub-category, so nothing typed is lost.
              set({
                children: [...group.children, { ...blankGroup(), coursesText: leaf ? group.coursesText : "" }],
                coursesText: "",
              })
            }
          >
            <PlusIcon className="h-4 w-4" />
            Add a sub-category
          </Button>
        )}
        {onRemove && (
          <Button variant="quiet" size="sm" onClick={onRemove}>
            <TrashIcon className="h-4 w-4" />
            Remove
          </Button>
        )}
      </div>
    </div>
  );
}
