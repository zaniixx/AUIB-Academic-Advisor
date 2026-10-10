import type { Metadata } from "next";
import type { ReactNode } from "react";
import { ClearDataButton } from "@/components/ClearDataButton";
import { BookOpenIcon, ClipboardIcon, InfoIcon, RotateIcon, ShieldCheckIcon, TrashIcon } from "@/components/icons";
import { IconBadge, LockIcon, PageHeader } from "@/components/ui";

export const metadata: Metadata = { title: "Privacy" };

const PROMISES: { icon: ReactNode; title: string; text: ReactNode }[] = [
  {
    icon: <ShieldCheckIcon />,
    title: "Saved only in this browser",
    text: (
      <>
        Your courses, grades, goals and the plans you save to compare are kept <strong>only in this browser</strong>. There is no account and
        nothing is stored on the server.
      </>
    ),
  },
  {
    icon: <RotateIcon />,
    title: "Used for your plan, then discarded",
    text: "When you plan, your courses are sent to the server over an encrypted connection, used to work out the plan, and discarded when the answer is sent back. They are not logged.",
  },
  {
    icon: <ClipboardIcon />,
    title: "Your pasted history is not kept",
    text: "When you paste your Course History, the text is read the same way and not kept.",
  },
  {
    icon: <LockIcon className="h-5 w-5" />,
    title: "No SIS password, ever",
    text: "The app never asks for your SIS password and never logs into SIS for you.",
  },
];

export default function PrivacyPage() {
  return (
    <article className="mx-auto max-w-4xl space-y-10">
      <PageHeader
        eyebrow="Privacy"
        title="Privacy and how this app works"
        description="A short, plain account of what happens to your information and where the course data comes from."
      />

      <section aria-labelledby="your-courses" className="space-y-4">
        <h2 id="your-courses" className="font-heading text-xl font-bold tracking-tight">
          What happens to your courses
        </h2>
        <ul className="grid gap-4 sm:grid-cols-2">
          {PROMISES.map((promise) => (
            <li key={promise.title} className="flex gap-4 rounded-card border border-border bg-surface p-5 shadow-soft">
              <IconBadge tone="done">{promise.icon}</IconBadge>
              <div className="space-y-1 text-sm leading-relaxed">
                <h3 className="font-semibold">{promise.title}</h3>
                <p className="text-text-muted">{promise.text}</p>
              </div>
            </li>
          ))}
        </ul>
        <div className="flex flex-wrap items-center justify-between gap-4 rounded-card border border-status-blocked/25 bg-status-blocked/5 p-5">
          <div className="flex gap-4">
            <IconBadge tone="ink">
              <TrashIcon />
            </IconBadge>
            <div className="space-y-1 text-sm">
              <h3 className="font-semibold">Using a shared or lab computer?</h3>
              <p className="text-text-muted">Clear your data when you are done.</p>
            </div>
          </div>
          <ClearDataButton />
        </div>
      </section>

      <div className="grid gap-4 md:grid-cols-2">
        <section aria-labelledby="data-source" className="space-y-2 rounded-card border border-border bg-surface p-5 shadow-soft">
          <h2 id="data-source" className="flex items-center gap-2 font-heading text-lg font-bold">
            <BookOpenIcon className="h-5 w-5 text-primary" />
            Where the course data comes from
          </h2>
          <p className="text-sm leading-relaxed text-text-muted">
            Programs and courses come from AUIB&apos;s student information system (SIS). Prerequisites are read
            automatically from course descriptions and then checked by an administrator. Each course page shows the
            original SIS sentence beside the rule the app uses.
          </p>
        </section>
        <section aria-labelledby="planning-aid" className="space-y-2 rounded-card border border-border bg-surface p-5 shadow-soft">
          <h2 id="planning-aid" className="flex items-center gap-2 font-heading text-lg font-bold">
            <InfoIcon className="h-5 w-5 text-primary" />
            This is a planning aid
          </h2>
          <p className="text-sm leading-relaxed text-text-muted">
            The registrar&apos;s degree audit in SIS is authoritative. Confirm important decisions with your academic
            advisor. This app does not register you for classes.
          </p>
        </section>
      </div>
    </article>
  );
}
