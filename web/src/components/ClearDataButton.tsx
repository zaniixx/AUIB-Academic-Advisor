"use client";

import { useState } from "react";
import { clearProfile } from "@/lib/profile";
import { TrashIcon } from "./icons";
import { Button, CheckIcon } from "./ui";

/** F11.5: one click removes everything this app keeps in the browser. */
export function ClearDataButton() {
  const [cleared, setCleared] = useState(false);
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button
        variant="danger"
        onClick={() => {
          clearProfile();
          setCleared(true);
        }}
      >
        <TrashIcon className="h-4 w-4" />
        Clear my data from this browser
      </Button>
      {cleared && (
        <span role="status" className="inline-flex items-center gap-1.5 text-sm font-medium text-status-done animate-fade-in">
          <CheckIcon className="h-4 w-4" />
          Done. Nothing is saved any more.
        </span>
      )}
    </div>
  );
}
