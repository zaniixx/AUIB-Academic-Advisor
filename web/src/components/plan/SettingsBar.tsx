"use client";

import type { PreferencesIn } from "@/lib/api";

export function SettingsBar({
  preferences,
  onChange,
}: {
  preferences: PreferencesIn;
  onChange: (changes: Partial<PreferencesIn>) => void;
}) {
  return (
    <form
      aria-label="Plan settings"
      className="flex flex-wrap items-end gap-4 rounded-card border border-border bg-surface p-3 text-sm print:hidden"
      onSubmit={(event) => event.preventDefault()}
    >
      <label>
        <span className="block font-medium">Pace</span>
        <select
          value={preferences.pace ?? "on_time"}
          onChange={(event) => onChange({ pace: event.target.value as PreferencesIn["pace"] })}
          className="mt-1 rounded-button border border-border bg-surface px-2 py-1"
        >
          <option value="on_time">Graduate on time</option>
          <option value="fastest">As early as possible</option>
        </select>
      </label>
      <label>
        <span className="block font-medium">Usual units a term</span>
        <select
          value={preferences.preferred_units ?? 15}
          onChange={(event) => onChange({ preferred_units: Number(event.target.value) })}
          className="mt-1 rounded-button border border-border bg-surface px-2 py-1"
        >
          {[9, 12, 15, 18].map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
      </label>
      <label>
        <span className="block font-medium">Most units a term</span>
        <select
          value={preferences.max_units ?? 18}
          onChange={(event) => onChange({ max_units: Number(event.target.value) })}
          className="mt-1 rounded-button border border-border bg-surface px-2 py-1"
        >
          {[12, 15, 16, 17, 18, 19, 20, 21].map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
      </label>
      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={preferences.include_summer ?? false}
          onChange={(event) => onChange({ include_summer: event.target.checked })}
        />
        Plan other courses in summer too
      </label>
      {(preferences.exclude ?? []).length > 0 && (
        <button
          type="button"
          onClick={() => onChange({ exclude: [] })}
          className="text-primary underline-offset-4 hover:underline"
        >
          Show {(preferences.exclude ?? []).length} replaced or hidden course(s) again
        </button>
      )}
    </form>
  );
}
