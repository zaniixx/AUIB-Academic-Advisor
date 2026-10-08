/**
 * Small shared UI pieces. Status is always shown with an icon and a word, never by
 * colour alone (accessibility requirement), and colours come only from the design tokens.
 */
"use client";

import Link from "next/link";
import { useEffect, useRef, type ComponentProps, type ReactNode } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";

// AUIB's buttons: filled maroon, or outlined in the text colour, with fully rounded ends.
const VARIANTS: Record<Variant, string> = {
  primary: "border border-primary bg-primary text-primary-contrast hover:opacity-90",
  secondary: "border border-text bg-surface text-text hover:border-primary hover:text-primary",
  ghost: "text-primary underline-offset-4 hover:underline",
  danger: "border border-status-blocked bg-surface text-status-blocked hover:bg-background",
};

const BUTTON_BASE =
  "inline-flex items-center justify-center gap-2 rounded-button px-5 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50";

export function Button({
  variant = "primary",
  className = "",
  type = "button",
  ...props
}: ComponentProps<"button"> & { variant?: Variant }) {
  return <button type={type} className={`${BUTTON_BASE} ${VARIANTS[variant]} ${className}`} {...props} />;
}

export function ButtonLink({
  variant = "primary",
  className = "",
  ...props
}: ComponentProps<typeof Link> & { variant?: Variant }) {
  return <Link className={`${BUTTON_BASE} ${VARIANTS[variant]} ${className}`} {...props} />;
}

export function Card({ className = "", ...props }: ComponentProps<"section">) {
  return <section className={`rounded-card border border-border bg-surface p-4 ${className}`} {...props} />;
}

export function Heading({ level = 2, children, className = "" }: { level?: 1 | 2 | 3; children: ReactNode; className?: string }) {
  const sizes = { 1: "text-2xl", 2: "text-lg", 3: "text-base" };
  const Tag = `h${level}` as const;
  return <Tag className={`font-heading font-semibold ${sizes[level]} ${className}`}>{children}</Tag>;
}

export type Status = "done" | "in-progress" | "planned" | "blocked" | "warning";

const STATUS_STYLE: Record<Status, { label: string; className: string; icon: ReactNode }> = {
  done: { label: "Done", className: "text-status-done border-status-done", icon: <CheckIcon /> },
  "in-progress": {
    label: "In progress",
    className: "text-status-in-progress border-status-in-progress",
    icon: <HalfIcon />,
  },
  planned: { label: "Planned", className: "text-status-planned border-status-planned", icon: <CircleIcon /> },
  blocked: { label: "Blocked", className: "text-status-blocked border-status-blocked", icon: <CrossIcon /> },
  warning: { label: "Check", className: "text-status-warning border-status-warning", icon: <AlertIcon /> },
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

export function Badge({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <span className={`inline-flex items-center rounded-full bg-background px-2 py-0.5 text-xs text-text-muted ${className}`}>
      {children}
    </span>
  );
}

/** Stacked bar: completed, in progress and planned parts of a total. */
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
  return (
    <div
      role="img"
      aria-label={label}
      className="flex h-2.5 w-full overflow-hidden rounded-full border border-border bg-background"
    >
      <div className="bg-status-done" style={{ width: `${part(done)}%` }} />
      <div className="bg-status-in-progress" style={{ width: `${part(inProgress)}%` }} />
      <div
        className="bg-status-planned opacity-50"
        style={{ width: `${part(planned)}%` }}
      />
    </div>
  );
}

export function Alert({
  tone = "info",
  title,
  children,
}: {
  tone?: "info" | "warning" | "error" | "success";
  title?: string;
  children?: ReactNode;
}) {
  const tones = {
    info: "border-status-in-progress",
    warning: "border-status-warning",
    error: "border-status-blocked",
    success: "border-status-done",
  };
  return (
    <div role={tone === "error" ? "alert" : "status"} className={`rounded-card border-s-4 bg-surface p-3 text-sm ${tones[tone]}`}>
      {title && <p className="font-semibold">{title}</p>}
      {children && <div className="text-text-muted">{children}</div>}
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

/** Native <dialog> as a modal: focus is trapped and Escape closes it. */
export function Dialog({
  open,
  title,
  onClose,
  children,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      aria-labelledby="dialog-title"
      className="m-auto w-[min(40rem,calc(100vw-2rem))] rounded-card border border-border bg-surface p-0 text-text backdrop:bg-black/50"
    >
      <div className="flex items-start justify-between gap-4 border-b border-border p-4">
        <h2 id="dialog-title" className="font-heading text-lg font-semibold">
          {title}
        </h2>
        <Button variant="ghost" onClick={onClose} aria-label="Close">
          ✕
        </Button>
      </div>
      <div className="max-h-[70vh] overflow-y-auto p-4">{children}</div>
    </dialog>
  );
}

export function CheckIcon() {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M3 8.5l3 3 7-7" />
    </svg>
  );
}

export function HalfIcon() {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className="h-3.5 w-3.5">
      <circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" strokeWidth="2" />
      <path d="M8 2a6 6 0 010 12z" fill="currentColor" />
    </svg>
  );
}

export function CircleIcon() {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2" strokeDasharray="3 2">
      <circle cx="8" cy="8" r="6" />
    </svg>
  );
}

export function CrossIcon() {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M4 4l8 8M12 4l-8 8" />
    </svg>
  );
}

export function AlertIcon() {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M8 2l6.5 11.5h-13z" />
      <path d="M8 6.5v3M8 11.5v.5" />
    </svg>
  );
}

export function LockIcon() {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="7" width="10" height="7" rx="1" />
      <path d="M5 7V5a3 3 0 016 0v2" />
    </svg>
  );
}
