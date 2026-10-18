import type { ReactNode } from "react";
import { SignInGate } from "@/components/auth/SignInGate";

/**
 * F9.1: every page in this group shows course or program data, which is only for AUIB students, so
 * each shows the sign-in screen until a student has signed in with their university email address.
 * The home and privacy pages stay open.
 */
export default function StudentsLayout({ children }: { children: ReactNode }) {
  return <SignInGate>{children}</SignInGate>;
}
