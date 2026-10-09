"use client";

import { useSyncExternalStore } from "react";
import { PROFILE_KEY } from "@/lib/profile";
import { RouteIcon } from "./icons";
import { ButtonLink } from "./ui";

function subscribe(onChange: () => void) {
  window.addEventListener("storage", onChange);
  return () => window.removeEventListener("storage", onChange);
}

function hasSavedProfile(): boolean {
  try {
    return window.localStorage.getItem(PROFILE_KEY) !== null;
  } catch {
    return false;
  }
}

/** Shown only when this browser already holds a plan. */
export function ContinueLink() {
  const saved = useSyncExternalStore(subscribe, hasSavedProfile, () => false);
  if (!saved) return null;
  return (
    <ButtonLink href="/plan" variant="secondary" size="lg" className="animate-fade-in">
      <RouteIcon className="h-5 w-5" />
      Continue my plan
    </ButtonLink>
  );
}
