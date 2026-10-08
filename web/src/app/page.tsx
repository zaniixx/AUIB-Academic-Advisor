import { ButtonLink, Card } from "@/components/ui";
import { ContinueLink } from "@/components/ContinueLink";

const STEPS = [
  {
    title: "Pick your major",
    text: "Computer Science is available now. More programs and minors are added as their data is imported.",
  },
  {
    title: "Paste your Course History",
    text: "In SIS open Academic Record → Course History, press Ctrl+A then Ctrl+C, and paste. New students can skip this.",
  },
  {
    title: "Get your plan",
    text: "See what is left, what you can take next term, and a term-by-term route to graduation.",
  },
];

const FEATURES = [
  ["What's left", "Every requirement group with units done, in progress and still needed."],
  ["Next term", "Courses you can take now, with prerequisites already checked."],
  ["Route to graduation", "A plan that respects prerequisites and your unit limit, with your expected graduation term."],
  ["What if I drop this?", "See which courses move and whether graduation slips before you decide."],
  ["Electives that fit you", "Suggestions ranked by your interests and goals, each with the reason it was suggested."],
  ["Bottlenecks", "Gateway courses that many later courses depend on are flagged so they are not delayed."],
];

export default function Home() {
  return (
    <div className="space-y-8">
      <section className="space-y-4 rounded-card bg-ink px-6 py-10 text-ink-contrast sm:px-10">
        <p className="text-sm font-medium uppercase tracking-widest text-ink-contrast/80">
          American University of Iraq, Baghdad
        </p>
        <h1 className="font-heading text-3xl font-bold tracking-tight sm:text-5xl">Plan your AUIB degree</h1>
        <p className="max-w-2xl text-lg text-ink-contrast/85">
          Know exactly what is left, what to take next, and what a change does to your graduation date.
        </p>
        <div className="flex flex-wrap gap-3">
          <ButtonLink href="/start">Start planning</ButtonLink>
          <ContinueLink />
        </div>
        <p className="text-sm text-ink-contrast/80">
          No account needed. Your courses stay in this browser and are never stored on our server.
        </p>
      </section>

      <section aria-labelledby="how" className="space-y-3">
        <h2 id="how" className="font-heading text-xl font-semibold">
          How it works
        </h2>
        <ol className="grid gap-3 sm:grid-cols-3">
          {STEPS.map((step, index) => (
            <li key={step.title}>
              <Card className="h-full">
                <p className="text-sm font-semibold text-accent">Step {index + 1}</p>
                <p className="mt-1 font-semibold">{step.title}</p>
                <p className="mt-1 text-sm text-text-muted">{step.text}</p>
              </Card>
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="features" className="space-y-3">
        <h2 id="features" className="font-heading text-xl font-semibold">
          What you get
        </h2>
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map(([title, text]) => (
            <li key={title} className="rounded-card border border-border bg-surface p-4">
              <p className="font-semibold">{title}</p>
              <p className="mt-1 text-sm text-text-muted">{text}</p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
