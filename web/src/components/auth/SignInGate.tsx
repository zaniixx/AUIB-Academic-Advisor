"use client";

import { useEffect, useSyncExternalStore, type ReactNode } from "react";
import { authSnapshot, checkSession, recheckSession, serverAuthSnapshot, subscribeAuth } from "@/lib/auth";
import { Alert, Button, Skeleton } from "@/components/ui";
import { SignInCard } from "./SignInCard";

/** F9.1: the pages with course and program data show the sign-in screen until a student signs in. */
export function SignInGate({ children }: { children: ReactNode }) {
  const auth = useSyncExternalStore(subscribeAuth, authSnapshot, serverAuthSnapshot);

  useEffect(() => {
    if (auth.status === "checking") void checkSession();
  }, [auth.status]);

  if (auth.status === "signed-in") return <>{children}</>;
  if (auth.status === "signed-out") return <SignInCard />;
  if (auth.status === "unreachable") {
    return (
      <div className="mx-auto max-w-md space-y-3">
        <Alert tone="error" title="The server could not be reached">
          {auth.message}
        </Alert>
        <Button variant="secondary" onClick={() => void recheckSession()}>
          Try again
        </Button>
      </div>
    );
  }
  return (
    <div role="status" aria-label="Checking your sign-in" className="mx-auto max-w-md space-y-3">
      <Skeleton className="h-24 w-full rounded-card" />
      <Skeleton className="h-48 w-full rounded-card" />
    </div>
  );
}
