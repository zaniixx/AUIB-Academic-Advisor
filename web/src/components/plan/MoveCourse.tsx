"use client";

import {
  createContext,
  useContext,
  useRef,
  useState,
  type DragEvent,
  type HTMLAttributes,
  type ReactNode,
} from "react";
import { api, type MoveOption, type MoveOptions, type StudentIn } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { graduationEffect, optionFor, otherShifts } from "@/lib/move";
import { Alert, Button, CheckIcon, CrossIcon, Dialog, Skeleton, StatusBadge } from "@/components/ui";

/**
 * F6.1: moving a planned course to another term, by dragging it onto a term or from the "Move to
 * another term" dialog (the way for keyboards and phones). When a drag starts, the API checks
 * every term the course could go to, so each term shows at once whether the course fits there and
 * what that does to graduation. A drop on a term where it cannot go explains why instead.
 */

interface Subject {
  code: string;
  from: string;
}

interface MoveState {
  /** The course being dragged now. */
  dragging: Subject | null;
  /** The API's check of every term for the course being moved; undefined while it loads. */
  checks: MoveOptions | undefined;
  start: (code: string, from: string) => void;
  end: () => void;
  drop: (term: string) => void;
  open: (code: string, from: string) => void;
}

const MoveContext = createContext<MoveState | null>(null);

export function MoveProvider({
  student,
  onMove,
  children,
}: {
  student: StudentIn;
  onMove: (code: string, from: string, to: string) => void;
  children: ReactNode;
}) {
  const [subject, setSubject] = useState<Subject | null>(null);
  const [dragging, setDragging] = useState(false);
  // The dialog, and the term a drop was refused on (null when opened from the button).
  const [dialog, setDialog] = useState<{ attempted: string | null } | null>(null);
  const dialogOpen = useRef(false);
  const [announcement, setAnnouncement] = useState("");
  const key = subject ? JSON.stringify({ student, code: subject.code }) : null;
  const checks = useAsync<MoveOptions>(key, () => api.moveOptions(student, subject?.code ?? ""));

  function showDialog(attempted: string | null) {
    dialogOpen.current = true;
    setDialog({ attempted });
  }

  function closeDialog() {
    dialogOpen.current = false;
    setDialog(null);
    setSubject(null);
  }

  function move(code: string, from: string, option: MoveOption) {
    onMove(code, from, option.term.label);
    setAnnouncement(`Moved ${code} to ${option.term.label}. ${graduationEffect(option)}.`);
  }

  const state: MoveState = {
    dragging: dragging ? subject : null,
    checks: checks.data,
    start(code, from) {
      setAnnouncement("");
      setSubject({ code, from });
      setDragging(true);
    },
    end() {
      setDragging(false);
      // Keep the checks while the dialog explains a refused drop; otherwise let them go, so a
      // later change to the plan does not check this course again for nothing.
      if (!dialogOpen.current) setSubject(null);
    },
    drop(term) {
      setDragging(false);
      if (!subject || term === subject.from) return;
      const option = optionFor(checks.data, term);
      if (option?.valid) {
        move(subject.code, subject.from, option);
        setSubject(null);
      } else {
        showDialog(term); // explains why, or shows the check when it arrives
      }
    },
    open(code, from) {
      setAnnouncement("");
      setSubject({ code, from });
      showDialog(null);
    },
  };

  return (
    <MoveContext.Provider value={state}>
      {children}
      <p role="status" className="sr-only">
        {announcement}
      </p>
      {dialog && subject && (
        <MoveDialog
          subject={subject}
          attempted={dialog.attempted}
          checks={checks.data}
          error={checks.error}
          onMove={(option) => {
            move(subject.code, subject.from, option);
            closeDialog();
          }}
          onClose={closeDialog}
        />
      )}
    </MoveContext.Provider>
  );
}

/** Props that let a course be dragged to another term; none outside a MoveProvider. */
export function useDraggable(code: string | null, term: string): HTMLAttributes<HTMLElement> {
  const move = useContext(MoveContext);
  if (!move || !code) return {};
  return {
    draggable: true,
    onDragStart: (event: DragEvent) => {
      event.dataTransfer.setData("text/plain", code);
      event.dataTransfer.effectAllowed = "move";
      move.start(code, term);
    },
    onDragEnd: () => move.end(),
  };
}

/** Opens the "Move to another term" dialog for a course; null outside a MoveProvider. */
export function useMoveDialog(): ((code: string, from: string) => void) | null {
  return useContext(MoveContext)?.open ?? null;
}

export type DropState = "idle" | "source" | "checking" | "valid" | "invalid";

/** A term a dragged course can be dropped on: its state while a course is dragged, and the props. */
export function useDropTarget(term: string): {
  state: DropState;
  option: MoveOption | undefined;
  over: boolean;
  props: HTMLAttributes<HTMLElement>;
} {
  const move = useContext(MoveContext);
  const [over, setOver] = useState(false);
  const depth = useRef(0); // dragenter/dragleave fire for every child, so count them
  const dragging = move?.dragging;
  if (!move || !dragging) return { state: "idle", option: undefined, over: false, props: {} };
  const option = optionFor(move.checks, term);
  const state: DropState =
    dragging.from === term ? "source" : !move.checks ? "checking" : option?.valid ? "valid" : "invalid";
  return {
    state,
    option,
    over,
    props: {
      onDragEnter: () => {
        depth.current += 1;
        setOver(true);
      },
      onDragLeave: () => {
        depth.current = Math.max(0, depth.current - 1);
        if (depth.current === 0) setOver(false);
      },
      onDragOver: (event: DragEvent) => {
        // Every term accepts the drop, so a term where the course cannot go can say why.
        event.preventDefault();
        event.dataTransfer.dropEffect = "move";
      },
      onDrop: (event: DragEvent) => {
        event.preventDefault();
        depth.current = 0;
        setOver(false);
        move.drop(term);
      },
    },
  };
}

/** Outline classes for a term while a course is dragged; the term under the pointer gets a thicker one. */
export function dropClasses(state: DropState, over: boolean): string {
  const width = over ? "outline-4" : "outline-2";
  switch (state) {
    case "source":
      return "opacity-60";
    case "checking":
      return `${width} outline-dashed outline-border-strong`;
    case "valid":
      return `${width} outline-status-done`;
    case "invalid":
      return `${width} outline-dashed outline-status-blocked/60`;
    default:
      return "";
  }
}

/** One line at the top of a term while a course is dragged: whether it fits there, and the effect. */
export function DropHint({ state, option }: { state: DropState; option: MoveOption | undefined }) {
  if (state === "idle" || state === "source") return null;
  const tone =
    state === "valid"
      ? "bg-status-done/10 text-status-done"
      : state === "invalid"
        ? "bg-status-blocked/8 text-status-blocked"
        : "bg-surface-sunken text-text-muted";
  return (
    <p aria-hidden className={`flex items-start gap-1.5 px-4 py-2 text-xs font-medium ${tone}`}>
      {state === "checking" && "Checking this term…"}
      {state === "valid" && option && (
        <>
          <CheckIcon className="mt-px h-3.5 w-3.5 shrink-0" />
          Fits here. {graduationEffect(option)}
        </>
      )}
      {state === "invalid" && (
        <>
          <CrossIcon className="mt-px h-3.5 w-3.5 shrink-0" />
          {option?.problems[0] ?? "This term was not checked."}
        </>
      )}
    </p>
  );
}

function MoveDialog({
  subject,
  attempted,
  checks,
  error,
  onMove,
  onClose,
}: {
  subject: Subject;
  attempted: string | null;
  checks: MoveOptions | undefined;
  error: string | undefined;
  onMove: (option: MoveOption) => void;
  onClose: () => void;
}) {
  const tried = attempted ? optionFor(checks, attempted) : undefined;
  return (
    <Dialog open title={`Move ${subject.code}`} onClose={onClose}>
      {error && <Alert tone="error">{error}</Alert>}
      {!checks && !error && (
        <div role="status" aria-label="Checking every term" className="space-y-3">
          <Skeleton className="h-16 rounded-xl" />
          <Skeleton className="h-16 rounded-xl" />
          <Skeleton className="h-16 rounded-xl" />
        </div>
      )}
      {checks && (
        <div className="space-y-4 text-sm">
          {attempted && !tried && (
            <Alert tone="warning" title={`${attempted} was not checked`}>
              Pick one of the terms below.
            </Alert>
          )}
          {tried && !tried.valid && (
            <Alert tone="error" title={`${subject.code} can't go in ${attempted}`}>
              <ul className="list-disc space-y-0.5 ps-4">
                {tried.problems.map((problem) => (
                  <li key={problem}>{problem}</li>
                ))}
              </ul>
            </Alert>
          )}
          {tried?.valid && (
            // Dropped before the check arrived: it fits, so offer the move the student asked for.
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-card border border-status-done/30 bg-status-done/6 p-4">
              <p>
                <span className="font-semibold">
                  {subject.code} fits in {attempted}.
                </span>{" "}
                {graduationEffect(tried)}.
              </p>
              <Button size="sm" onClick={() => onMove(tried)}>
                Move it to {attempted}
              </Button>
            </div>
          )}
          <p className="text-text-muted">
            {subject.code} is in {checks.term.label} now, and you graduate in{" "}
            {checks.graduation_term?.label ?? "your last planned term"}. A course you move stays in its new term, as
            with &ldquo;Keep in term&rdquo;.
          </p>
          <ul aria-label="Terms" className="space-y-2">
            {checks.options.map((option) => (
              <MoveRow key={option.term.label} code={subject.code} option={option} onMove={() => onMove(option)} />
            ))}
          </ul>
        </div>
      )}
    </Dialog>
  );
}

function MoveRow({ code, option, onMove }: { code: string; option: MoveOption; onMove: () => void }) {
  const others = otherShifts(option, code);
  return (
    <li
      className={`flex flex-wrap items-start justify-between gap-3 rounded-xl border px-3 py-2.5 ${
        option.valid ? "border-border" : "border-dashed border-border-strong"
      }`}
    >
      <div className="min-w-0 flex-1 basis-56 space-y-1">
        <p className="flex flex-wrap items-center gap-2">
          <span className="font-semibold">{option.term.label}</span>
          {option.valid ? (
            <StatusBadge status={option.terms_later > 0 ? "warning" : "done"} label={graduationEffect(option)} />
          ) : (
            <StatusBadge status="blocked" label="Can't go here" />
          )}
        </p>
        {option.problems.map((problem) => (
          <p key={problem} className="text-xs text-status-blocked">
            {problem}
          </p>
        ))}
        {option.valid && others.length > 0 && (
          <p className="text-xs text-text-muted">
            Also moves: {others.slice(0, 4).join(", ")}
            {others.length > 4 ? ` and ${others.length - 4} more` : ""}
          </p>
        )}
      </div>
      {option.valid && (
        <Button size="sm" variant="secondary" onClick={onMove} aria-label={`Move ${code} to ${option.term.label}`}>
          Move here
        </Button>
      )}
    </li>
  );
}
