import { CompassIcon } from "@/components/icons";
import { ButtonLink, EmptyState } from "@/components/ui";

export default function NotFound() {
  return (
    <EmptyState
      icon={<CompassIcon className="h-8 w-8" />}
      title="Page not found"
      action={<ButtonLink href="/">Go to the start page</ButtonLink>}
    >
      That page does not exist. It may have moved, or the link may be mistyped.
    </EmptyState>
  );
}
