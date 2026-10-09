import type { ReactNode } from "react";
import { IconBadge } from "@/components/ui";

/**
 * One wizard step: a titled card with the step's buttons in its footer. The title takes focus when
 * the step opens (see StartWizard), so screen-reader users hear where they are.
 */
export function StepCard({
  icon,
  title,
  description,
  children,
  footer,
}: {
  icon: ReactNode;
  title: string;
  description?: ReactNode;
  children: ReactNode;
  footer: ReactNode;
}) {
  return (
    <section aria-labelledby="step-title" className="rounded-card border border-border bg-surface shadow-card">
      <header className="flex items-start gap-4 border-b border-border p-5 sm:p-6">
        <IconBadge>{icon}</IconBadge>
        <div className="min-w-0 space-y-1">
          <h2 id="step-title" tabIndex={-1} className="font-heading text-xl font-bold tracking-tight">
            {title}
          </h2>
          {description && <p className="text-sm text-text-muted">{description}</p>}
        </div>
      </header>
      <div className="space-y-6 p-5 sm:p-6">{children}</div>
      <footer className="flex flex-wrap items-center justify-between gap-3 rounded-b-card border-t border-border bg-surface-sunken/60 px-5 py-4 sm:px-6">
        {footer}
      </footer>
    </section>
  );
}
