/**
 * Shared UI pieces (see design-system/auib-academic-advisor/MASTER.md). Status is always shown
 * with an icon and a word, never by colour alone, and colours come only from the design tokens.
 * Nothing here uses hooks, so server pages can render these directly; the pieces with state
 * live in ui-client.tsx.
 */
import Link from "next/link";
import type { ComponentProps, CSSProperties, ReactNode } from "react";
import {
  AlertIcon,
  CheckIcon,
  ChevronDownIcon,
  CircleIcon,
  CrossIcon,
  HalfIcon,
  InfoIcon,
} from "./icons";

export { AlertIcon, CheckIcon, CircleIcon, CrossIcon, HalfIcon, LockIcon } from "./icons";
export { CountUp, Dialog, TabPanel, Tabs, type TabItem } from "./ui-client";

type Variant = "primary" | "secondary" | "ghost" | "danger" | "quiet";
type Size = "sm" | "md" | "lg";

// AUIB's buttons: filled maroon, or outlined, with fully rounded ends. Presses scale down slightly.
const VARIANTS: Record<Variant, string> = {
  primary:
    "border border-primary bg-primary text-primary-contrast shadow-soft hover:border-primary-strong hover:bg-primary-strong hover:shadow-card",
  secondary: "border border-border-strong bg-surface text-text shadow-soft hover:border-primary hover:text-primary",
  ghost: "text-primary hover:bg-tint",
  danger: "border border-status-blocked/40 bg-surface text-status-blocked hover:border-status-blocked hover:bg-status-blocked/5",
  quiet: "text-text-muted hover:bg-surface-sunken hover:text-text",
};

const SIZES: Record<Size, string> = {
  sm: "min-h-9 px-3.5 text-sm",
  md: "min-h-11 px-5 text-sm",
  lg: "min-h-12 px-6 text-base",
};

const BUTTON_BASE =
  "inline-flex cursor-pointer items-center justify-center gap-2 rounded-button font-medium transition duration-200 ease-out active:scale-[0.97] disabled:pointer-events-none disabled:opacity-45";

export function buttonClass(variant: Variant = "primary", size: Size = "md", extra = ""): string {
  return `${BUTTON_BASE} ${VARIANTS[variant]} ${SIZES[size]} ${extra}`;
}

export function Button({
  variant = "primary",
  size = "md",
  className = "",
  type = "button",
  ...props
}: ComponentProps<"button"> & { variant?: Variant; size?: Size }) {
  return <button type={type} className={buttonClass(variant, size, className)} {...props} />;
}

export function ButtonLink({
  variant = "primary",
  size = "md",
  className = "",
  ...props
}: ComponentProps<typeof Link> & { variant?: Variant; size?: Size }) {
  return <Link className={buttonClass(variant, size, className)} {...props} />;
}

/** Text fields and selects share one look; the global focus ring stays for keyboard users. */
export const FIELD =
  "min-h-11 w-full rounded-field border border-border-strong bg-surface px-3.5 py-2 text-[0.95rem] text-text shadow-soft transition placeholder:text-text-muted/70 hover:border-text-muted";

/** A native select with the shared field look and a chevron; the label stays tied to the select. */
export function Select({ className = "", wrapperClassName = "", ...props }: ComponentProps<"select"> & { wrapperClassName?: string }) {
  return (
    <div className={`relative ${wrapperClassName}`}>
      <select className={`${FIELD} appearance-none pe-10 disabled:cursor-not-allowed disabled:bg-surface-sunken disabled:text-text-muted ${className}`} {...props} />
      <ChevronDownIcon className="pointer-events-none absolute end-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
    </div>
  );
}

export function Card({
  className = "",
  interactive = false,
  ...props
}: ComponentProps<"section"> & { interactive?: boolean }) {
  return (
    <section
      className={`rounded-card border border-border bg-surface p-5 shadow-soft ${
        interactive ? "transition duration-300 ease-out hover:-translate-y-0.5 hover:shadow-card" : ""
      } ${className}`}
      {...props}
    />
  );
}

export function Heading({
  level = 2,
  children,
  className = "",
}: {
  level?: 1 | 2 | 3;
  children: ReactNode;
  className?: string;
}) {
  const sizes = { 1: "text-3xl", 2: "text-xl", 3: "text-base" };
  const Tag = `h${level}` as const;
  return <Tag className={`font-heading font-bold tracking-tight ${sizes[level]} ${className}`}>{children}</Tag>;
}

/** A page's title block: optional eyebrow, the title, a short description and actions on the right. */
export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0 space-y-1.5">
        {eyebrow && <p className="text-xs font-semibold uppercase tracking-[0.14em] text-primary">{eyebrow}</p>}
        <h1 className="font-heading text-3xl font-bold tracking-tight sm:text-4xl">{title}</h1>
        {description && <div className="max-w-2xl text-text-muted">{description}</div>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

/** A tinted square with an icon, used to anchor cards and list items. */
export function IconBadge({ children, tone = "brand" }: { children: ReactNode; tone?: "brand" | "ink" | "done" }) {
  const tones = {
    brand: "bg-tint text-primary",
    ink: "bg-surface-sunken text-text",
    done: "bg-status-done/10 text-status-done",
  };
  return <span className={`grid h-11 w-11 shrink-0 place-items-center rounded-xl ${tones[tone]}`}>{children}</span>;
}

export type Status = "done" | "in-progress" | "planned" | "blocked" | "warning";

const STATUS_STYLE: Record<Status, { label: string; className: string; icon: ReactNode }> = {
  done: { label: "Done", className: "text-status-done border-status-done/40 bg-status-done/8", icon: <CheckIcon /> },
  "in-progress": {
    label: "In progress",
    className: "text-status-in-progress border-status-in-progress/40 bg-status-in-progress/8",
    icon: <HalfIcon />,
  },
  planned: {
    label: "Planned",
    className: "text-status-planned border-status-planned/40 bg-status-planned/8",
    icon: <CircleIcon />,
  },
  blocked: {
    label: "Blocked",
    className: "text-status-blocked border-status-blocked/40 bg-status-blocked/8",
    icon: <CrossIcon />,
  },
  warning: {
    label: "Check",
    className: "text-status-warning border-status-warning/40 bg-status-warning/8",
    icon: <AlertIcon />,
  },
};

export function StatusBadge({ status, label }: { status: Status; label?: string }) {
  const style = STATUS_STYLE[status];
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${style.className}`}
    >
      {style.icon}
      {label ?? style.label}
    </span>
  );
}

const BADGE_TONES = {
  neutral: "bg-surface-sunken text-text-muted",
  brand: "bg-tint text-primary",
};

export function Badge({
  children,
  tone = "neutral",
  className = "",
}: {
  children: ReactNode;
  tone?: keyof typeof BADGE_TONES;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${BADGE_TONES[tone]} ${className}`}
    >
      {children}
    </span>
  );
}

/** Stacked bar: completed, in progress and planned parts of a total; the parts grow in from the left. */
export function ProgressBar({
  total,
  done,
  inProgress = 0,
  planned = 0,
  label,
}: {
  total: number;
  done: number;
  inProgress?: number;
  planned?: number;
  label: string;
}) {
  const part = (value: number) => (total > 0 ? Math.min(100, (value / total) * 100) : 0);
  const grow: CSSProperties = { animation: "grow-x 900ms var(--ease-out) backwards", transformOrigin: "left" };
  return (
    <div role="img" aria-label={label} className="flex h-2.5 w-full overflow-hidden rounded-full bg-surface-sunken">
      <div className="bg-status-done" style={{ width: `${part(done)}%`, ...grow }} />
      <div className="bg-status-in-progress" style={{ width: `${part(inProgress)}%`, ...grow, animationDelay: "120ms" }} />
      <div
        className="bg-status-planned/45"
        style={{ width: `${part(planned)}%`, ...grow, animationDelay: "240ms" }}
      />
    </div>
  );
}

/**
 * A ring that draws itself from the top: the in-progress arc runs ahead and the completed arc
 * follows on top of it, so it ends green for done and blue for in progress.
 */
export function ProgressRing({
  done,
  inProgress = 0,
  size = 144,
  stroke = 13,
  label,
  children,
}: {
  done: number;
  inProgress?: number;
  size?: number;
  stroke?: number;
  label: string;
  children?: ReactNode;
}) {
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const clamp = (value: number) => Math.max(0, Math.min(1, value));
  const doneLength = circumference * clamp(done);
  const reachLength = circumference * clamp(done + inProgress);
  const circle = { cx: size / 2, cy: size / 2, r: radius, fill: "none", strokeWidth: stroke, strokeLinecap: "round" as const };
  const draw = (length: number, delay: number): CSSProperties =>
    ({
      "--ring-from": `${length}px`,
      animation: `ring-draw 1100ms var(--ease-out) ${delay}ms backwards`,
    }) as CSSProperties;
  return (
    <div className="relative inline-grid shrink-0 place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={label} className="-rotate-90">
        <circle {...circle} stroke="var(--surface-sunken)" />
        {reachLength > doneLength + 0.5 && (
          <circle
            {...circle}
            stroke="var(--status-in-progress)"
            strokeDasharray={`${reachLength} ${circumference}`}
            style={draw(reachLength, 0)}
          />
        )}
        {doneLength > 0.5 && (
          <circle
            {...circle}
            stroke="var(--status-done)"
            strokeDasharray={`${doneLength} ${circumference}`}
            style={draw(doneLength, 120)}
          />
        )}
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center">{children}</div>
    </div>
  );
}

const ALERT_TONES = {
  info: { box: "border-status-in-progress/30 bg-status-in-progress/6", icon: "text-status-in-progress" },
  warning: { box: "border-status-warning/35 bg-status-warning/8", icon: "text-status-warning" },
  error: { box: "border-status-blocked/35 bg-status-blocked/6", icon: "text-status-blocked" },
  success: { box: "border-status-done/30 bg-status-done/6", icon: "text-status-done" },
};

export function Alert({
  tone = "info",
  title,
  children,
}: {
  tone?: "info" | "warning" | "error" | "success";
  title?: string;
  children?: ReactNode;
}) {
  const style = ALERT_TONES[tone];
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={`flex gap-3 rounded-card border p-4 text-sm animate-fade-in ${style.box}`}
    >
      <span className={`mt-0.5 ${style.icon}`}>
        {tone === "success" ? <CheckIcon className="h-4 w-4" /> : tone === "info" ? <InfoIcon className="h-4 w-4" /> : <AlertIcon className="h-4 w-4" />}
      </span>
      <div className="min-w-0 space-y-0.5">
        {title && <p className="font-semibold text-text">{title}</p>}
        {children && <div className="text-text-muted">{children}</div>}
      </div>
    </div>
  );
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="flex items-center gap-2 text-sm text-text-muted">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-border border-t-primary" aria-hidden />
      {label}…
    </div>
  );
}

/** A placeholder in the shape of what is loading, so nothing jumps when it arrives. */
export function Skeleton({ className = "" }: { className?: string }) {
  return <div aria-hidden className={`skeleton ${className}`} />;
}

/** A labelled choice between a few options, drawn as a pill with a sliding highlight. */
export function Segmented<T extends string | number>({
  legend,
  name,
  value,
  options,
  onChange,
}: {
  legend: string;
  name: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
}) {
  return (
    <fieldset className="min-w-0">
      <legend className="text-sm font-medium">{legend}</legend>
      <div className="mt-2 inline-flex max-w-full flex-wrap gap-1 rounded-2xl border border-border bg-surface-sunken p-1">
        {options.map((option) => {
          const checked = option.value === value;
          return (
            <label
              key={String(option.value)}
              className={`cursor-pointer rounded-xl px-3.5 py-1.5 text-sm transition duration-200 has-[:focus-visible]:outline has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-primary ${
                checked ? "bg-surface font-medium text-text shadow-soft dark:bg-border-strong" : "text-text-muted hover:text-text"
              }`}
            >
              <input
                type="radio"
                name={name}
                className="sr-only"
                checked={checked}
                onChange={() => onChange(option.value)}
              />
              {option.label}
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}

/** An on/off setting with its label and an optional explanation. */
export function Switch({
  id,
  checked,
  onChange,
  label,
  description,
}: {
  id: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  description?: string;
}) {
  return (
    <label htmlFor={id} className="flex cursor-pointer items-start gap-3">
      <span className="relative mt-0.5 inline-flex h-6 w-11 shrink-0 items-center">
        <input
          id={id}
          type="checkbox"
          role="switch"
          checked={checked}
          onChange={(event) => onChange(event.target.checked)}
          className="peer sr-only"
        />
        <span className="absolute inset-0 rounded-full bg-border-strong transition duration-200 peer-checked:bg-primary peer-focus-visible:outline peer-focus-visible:outline-3 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-primary" />
        <span className="relative ms-0.5 h-5 w-5 rounded-full bg-white shadow-soft transition-transform duration-200 ease-out peer-checked:translate-x-5 rtl:peer-checked:-translate-x-5" />
      </span>
      <span className="min-w-0">
        <span className="block text-sm font-medium">{label}</span>
        {description && <span className="block text-xs text-text-muted">{description}</span>}
      </span>
    </label>
  );
}

/** A <details> disclosure with a chevron that turns; its content slides in when opened. */
export function Disclosure({
  summary,
  children,
  defaultOpen = false,
  className = "",
}: {
  summary: ReactNode;
  children: ReactNode;
  defaultOpen?: boolean;
  className?: string;
}) {
  return (
    <details open={defaultOpen} className={`group ${className}`}>
      <summary className="flex cursor-pointer items-center justify-between gap-3 rounded-xl py-2 font-medium">
        <span className="min-w-0">{summary}</span>
        <ChevronDownIcon className="h-5 w-5 text-text-muted transition-transform duration-200 group-open:rotate-180" />
      </summary>
      <div className="disclosure-body">{children}</div>
    </details>
  );
}

/** A friendly placeholder when there is nothing to show yet, with the next step to take. */
export function EmptyState({
  icon,
  title,
  children,
  action,
}: {
  icon: ReactNode;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-4 py-16 text-center animate-fade-up">
      <span className="grid h-16 w-16 place-items-center rounded-2xl bg-tint text-primary">{icon}</span>
      <h1 className="font-heading text-2xl font-bold tracking-tight">{title}</h1>
      {children && <div className="text-text-muted">{children}</div>}
      {action}
    </div>
  );
}

export function Keycap({ children }: { children: ReactNode }) {
  return (
    <kbd className="inline-flex min-w-7 items-center justify-center rounded-md border border-border-strong border-b-2 bg-surface px-1.5 py-0.5 font-sans text-xs font-semibold text-text shadow-soft">
      {children}
    </kbd>
  );
}
