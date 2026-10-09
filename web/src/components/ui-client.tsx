"use client";

/** The shared UI pieces that need state or effects; ui.tsx re-exports them. */
import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { CloseIcon } from "./icons";

/** A number that counts up to its value when it appears or changes (instantly with reduced motion). */
export function CountUp({ value, decimals = 0, duration = 900 }: { value: number; decimals?: number; duration?: number }) {
  const [shown, setShown] = useState(0);
  const from = useRef(0);
  useEffect(() => {
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    const start = performance.now();
    const origin = from.current;
    let frame = requestAnimationFrame(function tick(now) {
      const progress = reduce ? 1 : Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      setShown(origin + (value - origin) * eased);
      if (progress < 1) frame = requestAnimationFrame(tick);
      else from.current = value;
    });
    return () => cancelAnimationFrame(frame);
  }, [value, duration]);
  return <>{shown.toFixed(decimals)}</>;
}

/** Native <dialog> as a modal: focus is trapped, Escape closes it, and it scales in from the centre. */
export function Dialog({
  open,
  title,
  onClose,
  children,
  wide = false,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
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
      className={`m-auto ${wide ? "w-[min(60rem,calc(100vw-2rem))]" : "w-[min(40rem,calc(100vw-2rem))]"} rounded-card border border-border bg-surface p-0 text-text shadow-float backdrop:bg-ink-strong/55 backdrop:backdrop-blur-[2px] open:animate-scale-in`}
    >
      <div className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
        <h2 id="dialog-title" className="font-heading text-lg font-bold">
          {title}
        </h2>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="-me-2 inline-grid h-10 w-10 cursor-pointer place-items-center rounded-full text-text-muted transition hover:bg-surface-sunken hover:text-text"
        >
          <CloseIcon className="h-5 w-5" />
        </button>
      </div>
      <div className="max-h-[70vh] overflow-y-auto p-5">{children}</div>
    </dialog>
  );
}

export interface TabItem {
  id: string;
  label: string;
  icon?: ReactNode;
}

/** Accessible tabs: arrow keys move between tabs, Home and End jump to the ends. */
export function Tabs({
  items,
  active,
  onChange,
  label,
}: {
  items: TabItem[];
  active: string;
  onChange: (id: string) => void;
  label: string;
}) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  function move(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const last = items.length - 1;
    const next =
      event.key === "ArrowRight"
        ? (index + 1) % items.length
        : event.key === "ArrowLeft"
          ? (index - 1 + items.length) % items.length
          : event.key === "Home"
            ? 0
            : event.key === "End"
              ? last
              : null;
    if (next === null) return;
    event.preventDefault();
    refs.current[next]?.focus();
    onChange(items[next].id);
  }
  return (
    <div
      role="tablist"
      aria-label={label}
      className="flex w-full gap-1 overflow-x-auto rounded-full border border-border bg-surface p-1 shadow-soft [scrollbar-width:none] max-md:[mask-image:linear-gradient(to_right,black_82%,transparent)]"
    >
      {items.map((item, index) => {
        const selected = item.id === active;
        return (
          <button
            key={item.id}
            ref={(element) => {
              refs.current[index] = element;
            }}
            type="button"
            role="tab"
            id={`tab-${item.id}`}
            aria-selected={selected}
            aria-controls={`panel-${item.id}`}
            tabIndex={selected ? 0 : -1}
            onClick={(event) => {
              event.currentTarget.scrollIntoView({ block: "nearest", inline: "nearest" });
              onChange(item.id);
            }}
            onKeyDown={(event) => move(event, index)}
            className={`inline-flex min-h-10 flex-1 cursor-pointer items-center justify-center gap-2 whitespace-nowrap rounded-full px-4 text-sm font-medium transition duration-200 ${
              selected
                ? "bg-ink text-ink-contrast shadow-soft dark:bg-primary dark:text-primary-contrast"
                : "text-text-muted hover:bg-surface-sunken hover:text-text"
            }`}
          >
            {item.icon}
            {item.label}
          </button>
        );
      })}
    </div>
  );
}

export function TabPanel({ id, active, children }: { id: string; active: boolean; children: ReactNode }) {
  return (
    <div role="tabpanel" id={`panel-${id}`} aria-labelledby={`tab-${id}`} hidden={!active} className="animate-fade-up">
      {active && children}
    </div>
  );
}
