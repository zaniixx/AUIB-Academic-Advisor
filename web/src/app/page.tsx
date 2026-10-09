import type { CSSProperties, ReactNode } from "react";
import Link from "next/link";
import { ContinueLink } from "@/components/ContinueLink";
import {
  ArrowRightIcon,
  BookOpenIcon,
  CalendarCheckIcon,
  ClipboardIcon,
  ClockIcon,
  FlagIcon,
  LayersIcon,
  ListChecksIcon,
  RouteIcon,
  ShieldCheckIcon,
  SparklesIcon,
  SwapIcon,
  TargetIcon,
} from "@/components/icons";
import { ButtonLink, CheckIcon, IconBadge, Keycap, ProgressRing } from "@/components/ui";

const STEPS: { title: string; Icon: typeof RouteIcon; text: ReactNode }[] = [
  {
    title: "Pick your major",
    Icon: TargetIcon,
    text: "Computer Science is ready now, with minors in Psychology and Teaching and Learning Design.",
  },
  {
    title: "Paste your Course History",
    Icon: ClipboardIcon,
    text: (
      <>
        In SIS open Academic Record → Course History, press <Keycap>Ctrl</Keycap> + <Keycap>A</Keycap> then{" "}
        <Keycap>Ctrl</Keycap> + <Keycap>C</Keycap>, and paste. New students can skip this.
      </>
    ),
  },
  {
    title: "Get your plan",
    Icon: RouteIcon,
    text: "See what is left, what you can take next term, and a term-by-term route to graduation.",
  },
];

const FEATURES = [
  { title: "What's left", Icon: ListChecksIcon, text: "Every requirement with credits done, in progress and still needed." },
  { title: "Next term", Icon: CalendarCheckIcon, text: "Courses you can take now, with prerequisites already checked." },
  {
    title: "Route to graduation",
    Icon: FlagIcon,
    text: "A plan that respects prerequisites and your credit limit, with your expected graduation term.",
  },
  { title: "What if I drop this?", Icon: SwapIcon, text: "See which courses move, and whether graduation slips, before you decide." },
  {
    title: "Electives that fit you",
    Icon: SparklesIcon,
    text: "Suggestions ranked by your interests and goals, each with the reason it was suggested.",
  },
  {
    title: "Bottlenecks flagged",
    Icon: LayersIcon,
    text: "Gateway courses that many later courses depend on are flagged so they are not delayed.",
  },
];

// An illustration of the plan page with sample courses; it is decorative, so screen readers skip it.
const SAMPLE_TERM = [
  { code: "CSC 231", title: "Data Structure" },
  { code: "CSC 310", title: "Web Programming" },
  { code: "MAT 220", title: "Ordinary Differential Equations" },
  { code: "PSY 101", title: "Introduction to Psychology" },
];

function PlanPreview() {
  return (
    <div aria-hidden className="relative mx-auto w-full max-w-sm animate-fade-up [animation-delay:200ms] lg:mx-0">
      <div className="absolute -inset-6 -z-10 rounded-[2.5rem] bg-[radial-gradient(closest-side,var(--brand-tint-strong),transparent)] opacity-90" />
      <div className="animate-float rounded-card border border-border bg-surface p-5 shadow-float">
        <div className="flex items-center justify-between">
          <span className="rounded-full bg-tint px-2.5 py-0.5 text-xs font-semibold text-primary">Example plan</span>
          <span className="text-xs text-text-muted">Computer Science</span>
        </div>
        <div className="mt-4 flex items-center gap-4">
          <ProgressRing done={0.6} inProgress={0.12} size={104} stroke={10} label="Example: 60% done">
            <span className="font-heading text-2xl font-bold">60%</span>
          </ProgressRing>
          <div className="space-y-1">
            <p className="text-xs text-text-muted">Graduating in</p>
            <p className="font-heading text-xl font-bold">Spring 2029</p>
            <p className="inline-flex items-center gap-1 text-xs font-medium text-status-done">
              <CheckIcon /> On track
            </p>
          </div>
        </div>
        <div className="mt-5 rounded-xl bg-surface-sunken p-3">
          <p className="text-xs font-semibold uppercase tracking-wider text-text-muted">Next term · 12 credits</p>
          <ul className="mt-2 space-y-1.5">
            {SAMPLE_TERM.map((course) => (
              <li key={course.code} className="flex items-center gap-2 rounded-lg bg-surface px-2.5 py-1.5 text-sm shadow-soft">
                <span className="h-2 w-2 rounded-full bg-status-planned" />
                <span className="font-semibold">{course.code}</span>
                <span className="truncate text-text-muted">{course.title}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

export default function Home() {
  return (
    <div className="space-y-20">
      <section className="relative grid items-center gap-12 pt-2 lg:grid-cols-[1.15fr_1fr] lg:pt-6">
        <div className="stagger space-y-6">
          <p
            style={{ "--i": 0 } as CSSProperties}
            className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1 text-xs font-medium text-text-muted shadow-soft"
          >
            <span className="h-1.5 w-1.5 rounded-full bg-primary" />
            For American University of Iraq, Baghdad students
          </p>
          <h1
            style={{ "--i": 1 } as CSSProperties}
            className="font-heading text-4xl font-bold leading-[1.08] tracking-tight sm:text-6xl"
          >
            Plan your AUIB degree <span className="text-primary">term by term</span>
          </h1>
          <p style={{ "--i": 2 } as CSSProperties} className="max-w-xl text-lg text-text-muted">
            Know exactly what is left, what to take next, and what a change does to your graduation date.
          </p>
          <div style={{ "--i": 3 } as CSSProperties} className="flex flex-wrap gap-3">
            <ButtonLink href="/start" size="lg">
              Start planning
              <ArrowRightIcon className="h-5 w-5" />
            </ButtonLink>
            <ContinueLink />
          </div>
          <ul
            style={{ "--i": 4 } as CSSProperties}
            className="flex flex-wrap gap-x-5 gap-y-2 text-sm text-text-muted"
          >
            <li className="inline-flex items-center gap-1.5">
              <CheckIcon className="h-4 w-4 text-status-done" /> No account needed
            </li>
            <li className="inline-flex items-center gap-1.5">
              <ShieldCheckIcon className="h-4 w-4 text-status-done" /> Saved only in this browser
            </li>
            <li className="inline-flex items-center gap-1.5">
              <ClockIcon className="h-4 w-4 text-status-done" /> Takes a few minutes
            </li>
          </ul>
        </div>
        <PlanPreview />
      </section>

      <section aria-labelledby="how" className="space-y-8">
        <div className="space-y-2 text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-primary">How it works</p>
          <h2 id="how" className="font-heading text-3xl font-bold tracking-tight">
            Three steps to your plan
          </h2>
        </div>
        <ol className="grid gap-4 md:grid-cols-3">
          {STEPS.map(({ title, Icon, text }, index) => (
            <li
              key={title}
              className="relative rounded-card border border-border bg-surface p-6 text-center shadow-soft"
            >
              <span className="relative mx-auto grid h-11 w-11 place-items-center rounded-full bg-primary text-primary-contrast shadow-card">
                <Icon className="h-5 w-5" />
                <span className="absolute -end-1 -top-1 grid h-5 w-5 place-items-center rounded-full border-2 border-surface bg-ink text-[0.65rem] font-bold text-ink-contrast">
                  {index + 1}
                </span>
              </span>
              <h3 className="mt-4 font-heading text-lg font-bold">{title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-text-muted">{text}</p>
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="features" className="space-y-8">
        <div className="space-y-2 text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-primary">What you get</p>
          <h2 id="features" className="font-heading text-3xl font-bold tracking-tight">
            Everything an advising session needs
          </h2>
        </div>
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map(({ title, Icon, text }) => (
            <li
              key={title}
              className="group flex gap-4 rounded-card border border-border bg-surface p-5 shadow-soft transition duration-300 ease-out hover:-translate-y-1 hover:border-tint-strong hover:shadow-card"
            >
              <span className="transition duration-300 group-hover:scale-110">
                <IconBadge>
                  <Icon />
                </IconBadge>
              </span>
              <div>
                <h3 className="font-semibold">{title}</h3>
                <p className="mt-1 text-sm leading-relaxed text-text-muted">{text}</p>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section
        aria-labelledby="privacy-band"
        className="relative overflow-hidden rounded-[1.5rem] bg-ink px-6 py-10 text-ink-contrast sm:px-12"
      >
        <span
          aria-hidden
          className="absolute -end-16 -top-24 h-72 w-72 rounded-full bg-[radial-gradient(closest-side,rgb(156_33_63/0.55),transparent)]"
        />
        <div className="relative grid items-center gap-8 md:grid-cols-[1fr_auto]">
          <div className="space-y-3">
            <ShieldCheckIcon className="h-8 w-8 text-white" />
            <h2 id="privacy-band" className="font-heading text-2xl font-bold tracking-tight sm:text-3xl">
              Your courses are saved only in this browser
            </h2>
            <p className="max-w-2xl text-ink-contrast/80">
              There is no account and nothing to sign in to. When you plan, your courses are sent over an encrypted
              connection, used to work out the plan and discarded. Nothing is stored on the server, and the app never
              asks for your SIS password.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <ButtonLink href="/start" size="lg">
              Start planning
              <ArrowRightIcon className="h-5 w-5" />
            </ButtonLink>
            <Link
              href="/privacy"
              className="inline-flex min-h-12 items-center gap-2 rounded-button border border-white/30 px-6 font-medium text-white transition hover:bg-white/10"
            >
              <BookOpenIcon className="h-5 w-5" />
              How privacy works
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
