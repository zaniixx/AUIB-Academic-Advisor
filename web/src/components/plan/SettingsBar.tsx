"use client";

import type { PreferencesIn, ProgramVersion } from "@/lib/api";
import { joinTermOptions, pluralize } from "@/lib/format";
import { CloseIcon, RotateIcon, SlidersIcon } from "@/components/icons";
import { Button, Segmented, Select, Switch } from "@/components/ui";

/** The "Adjust plan" panel: changes apply at once and the plan updates in place. */
export interface RequirementsSetting {
  versions: ProgramVersion[];
  entryTerm: string;
  programVersion: string;
  onChange: (changes: { entryTerm?: string | null; programVersion?: string | null }) => void;
}

export function SettingsBar({
  preferences,
  onChange,
  onClose,
  requirements = null,
}: {
  preferences: PreferencesIn;
  onChange: (changes: Partial<PreferencesIn>) => void;
  onClose: () => void;
  requirements?: RequirementsSetting | null;
}) {
  const hidden = (preferences.exclude ?? []).length;
  return (
    <form
      aria-label="Plan settings"
      className="space-y-5 rounded-card border border-border bg-surface p-5 shadow-card animate-fade-up print:hidden"
      onSubmit={(event) => event.preventDefault()}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <SlidersIcon className="h-5 w-5 text-primary" />
          <div>
            <p className="font-heading font-bold">Adjust plan</p>
            <p className="text-sm text-text-muted">Changes apply right away.</p>
          </div>
        </div>
        <Button variant="quiet" size="sm" className="h-10 w-10 px-0" onClick={onClose} aria-label="Close plan settings">
          <CloseIcon className="h-5 w-5" />
        </Button>
      </div>
      <div className="flex flex-wrap items-end gap-x-8 gap-y-5">
        <Segmented
          legend="Pace"
          name="settings-pace"
          value={preferences.pace ?? "on_time"}
          onChange={(pace) => onChange({ pace })}
          options={[
            { value: "on_time", label: "Graduate on time" },
            { value: "fastest", label: "As early as possible" },
          ]}
        />
        <Segmented
          legend="Usual credits a term"
          name="settings-preferred"
          value={preferences.preferred_units ?? 15}
          onChange={(preferred_units) => onChange({ preferred_units })}
          options={[9, 12, 15, 18].map((value) => ({ value, label: String(value) }))}
        />
        <label className="text-sm">
          <span className="mb-2 block font-medium">Most credits a term</span>
          <Select
            value={preferences.max_units ?? 18}
            onChange={(event) => onChange({ max_units: Number(event.target.value) })}
            wrapperClassName="w-32"
          >
            {[12, 15, 16, 17, 18, 19, 20, 21].map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </Select>
        </label>
      </div>
      {requirements && <RequirementsRow {...requirements} />}
      <div className="flex flex-wrap items-center justify-between gap-4 border-t border-border pt-4">
        <Switch
          id="settings-summer"
          checked={preferences.include_summer ?? false}
          onChange={(include_summer) => onChange({ include_summer })}
          label="Plan other courses in summer too"
          description={`Up to ${preferences.summer_max_units ?? 6} credits. Some courses are always in summer.`}
        />
        {hidden > 0 && (
          <Button variant="ghost" size="sm" onClick={() => onChange({ exclude: [] })}>
            <RotateIcon className="h-4 w-4" />
            Show {pluralize(hidden, "replaced or hidden course")} again
          </Button>
        )}
      </div>
    </form>
  );
}

/** F0.4: when the student joined, and (with the registrar's approval) another version of the major. */
function RequirementsRow({ versions, entryTerm, programVersion, onChange }: RequirementsSetting) {
  const sentence = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);
  return (
    <div className="grid gap-4 border-t border-border pt-4 sm:grid-cols-2">
      <label className="text-sm">
        <span className="mb-2 block font-medium">When you joined AUIB</span>
        <Select value={entryTerm} onChange={(event) => onChange({ entryTerm: event.target.value || null })}>
          <option value="">From my Course History</option>
          {joinTermOptions().map((term) => (
            <option key={term} value={term}>
              {term}
            </option>
          ))}
        </Select>
      </label>
      <div className="text-sm">
        <label htmlFor="settings-version" className="mb-2 block font-medium">
          Requirements
        </label>
        <Select
          id="settings-version"
          value={programVersion}
          onChange={(event) => onChange({ programVersion: event.target.value || null })}
          aria-describedby="settings-version-help"
        >
          <option value="">The ones for when I joined</option>
          {versions.map((version) => (
            <option key={version.id} value={version.id}>
              {sentence(version.applies_to)}
            </option>
          ))}
        </Select>
        <p id="settings-version-help" className="mt-1 text-xs text-text-muted">
          Choose other requirements only if the registrar approved your move to them.
        </p>
      </div>
    </div>
  );
}
