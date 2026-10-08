import { ButtonLink } from "@/components/ui";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-xl space-y-4 py-10 text-center">
      <h1 className="font-heading text-2xl font-bold">Page not found</h1>
      <p className="text-text-muted">That page does not exist.</p>
      <ButtonLink href="/">Go to the start page</ButtonLink>
    </div>
  );
}
