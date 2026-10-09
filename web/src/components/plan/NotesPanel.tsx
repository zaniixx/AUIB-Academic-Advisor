import type { PlanOut } from "@/lib/api";
import { BookOpenIcon, ClipboardIcon } from "@/components/icons";
import { Alert, Card, CheckIcon } from "@/components/ui";

/** Warnings, conditions to confirm with an advisor, assumptions and the data source (transparency NFR). */
export function NotesPanel({ id, plan }: { id: string; plan: PlanOut }) {
  const warnings = plan.issues.filter((issue) => issue.severity === "warning");
  const checks = plan.issues.filter((issue) => issue.severity === "info");
  const source = plan.catalog;
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="space-y-4">
      <div className="space-y-1">
        <h2 id={`${id}-title`} className="font-heading text-xl font-bold tracking-tight">
          Things to check
        </h2>
        <p className="text-sm text-text-muted">Bring these to your advisor; they are also on the printed plan.</p>
      </div>
      {warnings.length > 0 && (
        <div className="space-y-2">
          {warnings.map((issue) => (
            <Alert key={issue.message} tone="warning">
              {issue.message}
            </Alert>
          ))}
        </div>
      )}
      <div className="grid items-start gap-4 lg:grid-cols-2">
        <Card className="space-y-3">
          <h3 className="flex items-center gap-2 font-heading font-bold">
            <ClipboardIcon className="h-5 w-5 text-primary" />
            Confirm with your advisor
          </h3>
          {checks.length === 0 ? (
            <p className="flex items-center gap-2 text-sm text-status-done">
              <CheckIcon /> Nothing to confirm.
            </p>
          ) : (
            <ul className="space-y-2 text-sm">
              {checks.map((issue) => (
                <li key={issue.message} className="flex gap-2">
                  <span aria-hidden className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                  {issue.message}
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card className="space-y-3">
          <h3 className="flex items-center gap-2 font-heading font-bold">
            <BookOpenIcon className="h-5 w-5 text-primary" />
            How this plan was made
          </h3>
          <ul className="space-y-2 text-sm text-text-muted">
            {plan.assumptions.map((assumption) => (
              <li key={assumption} className="flex gap-2">
                <span aria-hidden className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-border-strong" />
                {assumption}
              </li>
            ))}
          </ul>
          <p className="rounded-xl bg-surface-sunken p-3 text-xs text-text-muted">
            Requirements for {source.program_name} as shown in SIS on {source.source_date ?? "an unknown date"}
            {source.catalog_year ? `, catalog year ${source.catalog_year}` : " (catalog year not yet confirmed)"}.
          </p>
        </Card>
      </div>
    </section>
  );
}
