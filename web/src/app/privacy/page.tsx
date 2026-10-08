import type { Metadata } from "next";
import { ClearDataButton } from "@/components/ClearDataButton";

export const metadata: Metadata = { title: "Privacy" };

export default function PrivacyPage() {
  return (
    <article className="mx-auto max-w-3xl space-y-6 text-sm leading-relaxed">
      <h1 className="font-heading text-2xl font-bold">Privacy and how this app works</h1>

      <section className="space-y-2">
        <h2 className="font-heading text-lg font-semibold">What happens to your courses</h2>
        <ul className="list-disc space-y-1 ps-5">
          <li>
            Your courses, grades and goals are saved <strong>only in this browser</strong>. There is no account and
            nothing is stored on the server.
          </li>
          <li>
            When you plan, your courses are sent to the server over an encrypted connection, used to work out the
            plan, and discarded when the answer is sent back. They are not logged.
          </li>
          <li>When you paste your Course History, the text is read the same way and not kept.</li>
          <li>The app never asks for your SIS password and never logs into SIS for you.</li>
          <li>On a shared or lab computer, clear your data when you are done.</li>
        </ul>
        <ClearDataButton />
      </section>

      <section className="space-y-2">
        <h2 className="font-heading text-lg font-semibold">Where the course data comes from</h2>
        <p>
          Programs and courses come from AUIB&apos;s student information system (SIS). Prerequisites are read
          automatically from course descriptions and then checked by an administrator. Each course page shows the
          original SIS sentence beside the rule the app uses.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="font-heading text-lg font-semibold">This is a planning aid</h2>
        <p>
          The registrar&apos;s degree audit in SIS is authoritative. Confirm important decisions with your academic
          advisor. This app does not register you for classes.
        </p>
      </section>
    </article>
  );
}
