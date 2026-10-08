"use client";

import { useState } from "react";
import { clearProfile } from "@/lib/profile";
import { Button } from "./ui";

/** F11.5: one click removes everything this app keeps in the browser. */
export function ClearDataButton() {
  const [cleared, setCleared] = useState(false);
  return (
    <div className="flex items-center gap-3">
      <Button
        variant="danger"
        onClick={() => {
          clearProfile();
          setCleared(true);
        }}
      >
        Clear my data from this browser
      </Button>
      {cleared && (
        <span role="status" className="text-status-done">
          Done. Nothing is saved any more.
        </span>
      )}
    </div>
  );
}
