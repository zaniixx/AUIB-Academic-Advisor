import type { PlanOut } from "@/lib/api";
import { Alert, Card, Heading } from "@/components/ui";

/** Warnings, conditions to confirm with an advisor, assumptions and the data source (transparency NFR). */
export function NotesPanel({ id, plan }: { id: string; plan: PlanOut }) {
  const warnings = plan.issues.filter((issue) => issue.severity === "warning");
  const checks = plan.issues.filter((issue) => issue.severity === "info");
  const source = plan.catalog;
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="space-y-3">
      <Heading>
        <span id={`${id}-title`}>Things to check</span>
      </Heading>
      {warnings.map((issue) => (
        <Alert key={issue.message} tone="warning">
          {issue.message}
        </Alert>
      ))}
      <div className="grid items-start gap-3 lg:grid-cols-2">
        <Card>
          <Heading level={3}>Confirm with your advisor</Heading>
          {checks.length === 0 ? (
            <p className="mt-2 text-sm">Nothing to confirm.</p>
          ) : (
            <ul className="mt-2 list-disc space-y-1 ps-5 text-sm">
              {checks.map((issue) => (
                <li key={issue.message}>{issue.message}</li>
              ))}
            </ul>
          )}
        </Card>
        <Card>
          <Heading level={3}>How this plan was made</Heading>
          <ul className="mt-2 list-disc space-y-1 ps-5 text-sm text-text-muted">
            {plan.assumptions.map((assumption) => (
              <li key={assumption}>{assumption}</li>
            ))}
          </ul>
          <p className="mt-3 text-xs text-text-muted">
            Requirements for {source.program_name} as shown in SIS on {source.source_date ?? "an unknown date"}
            {source.catalog_year ? `, catalog year ${source.catalog_year}` : " (catalog year not yet confirmed)"}.
          </p>
        </Card>
      </div>
    </section>
  );
}
