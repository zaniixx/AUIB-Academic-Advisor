"use client";

import Link from "next/link";
import { useEffect, useId, useState, type FormEvent } from "react";
import { ApiError, api } from "@/lib/api";
import { verifyCode } from "@/lib/auth";
import { ArrowLeftIcon, ArrowRightIcon, MailIcon, ShieldCheckIcon } from "@/components/icons";
import { Button, FIELD, IconBadge } from "@/components/ui";

export const AUIB_DOMAIN = "auib.edu.iq";

function message(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong. Please try again.";
}

/**
 * F9.1: sign in with an AUIB email address. Step one emails a 6-digit code; step two checks it.
 * No password: whoever can read the university mailbox can sign in.
 */
export function SignInCard() {
  const [step, setStep] = useState<"email" | "code">("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [sentTo, setSentTo] = useState("");
  const [minutes, setMinutes] = useState(10);
  const [resendIn, setResendIn] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const emailId = useId();
  const codeId = useId();
  const errorId = useId();

  // Count down until another code may be sent.
  useEffect(() => {
    if (resendIn <= 0) return;
    const timer = window.setTimeout(() => setResendIn((seconds) => seconds - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [resendIn]);

  async function sendCode(address: string) {
    setBusy(true);
    setError(null);
    try {
      const sent = await api.auth.requestCode(address);
      setSentTo(sent.email);
      setMinutes(sent.expires_in_minutes);
      setResendIn(sent.resend_after_seconds);
      setCode("");
      setStep("code");
    } catch (failure) {
      setError(message(failure));
    } finally {
      setBusy(false);
    }
  }

  function submitEmail(event: FormEvent) {
    event.preventDefault();
    const address = email.trim().toLowerCase();
    if (!address.endsWith(`@${AUIB_DOMAIN}`)) {
      setError(`Use your AUIB email address (name@${AUIB_DOMAIN}).`);
      return;
    }
    void sendCode(address);
  }

  async function submitCode(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await verifyCode(sentTo, code.trim());
    } catch (failure) {
      setError(failure instanceof ApiError && failure.status === 422 ? "Enter the 6 digits from the email." : message(failure));
      setBusy(false);
    }
  }

  return (
    <section
      aria-labelledby="sign-in-title"
      className="mx-auto max-w-md overflow-hidden rounded-card border border-border bg-surface shadow-card animate-fade-up"
    >
      <header className="flex items-start gap-4 border-b border-border p-5 sm:p-6">
        <IconBadge>
          <MailIcon />
        </IconBadge>
        <div className="min-w-0 space-y-1">
          <h1 id="sign-in-title" className="font-heading text-xl font-bold tracking-tight">
            Sign in with your AUIB email
          </h1>
          <p className="text-sm text-text-muted">
            The course catalog and the planner are for AUIB students. We email you a code; there is no password.
          </p>
        </div>
      </header>

      <div className="space-y-4 p-5 sm:p-6">
        {step === "email" ? (
          <form onSubmit={submitEmail} noValidate className="space-y-4">
            <div className="space-y-1.5">
              <label htmlFor={emailId} className="block text-sm font-medium">
                AUIB email address
              </label>
              <input
                id={emailId}
                type="email"
                inputMode="email"
                autoComplete="email"
                autoFocus
                required
                placeholder={`name@${AUIB_DOMAIN}`}
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                aria-invalid={error ? true : undefined}
                aria-describedby={error ? errorId : undefined}
                className={FIELD}
              />
            </div>
            {error && (
              <p id={errorId} role="alert" className="text-sm font-medium text-status-blocked">
                {error}
              </p>
            )}
            <Button type="submit" size="lg" className="w-full" disabled={busy}>
              {busy ? "Sending…" : "Email me a code"}
              <ArrowRightIcon className="h-5 w-5" />
            </Button>
          </form>
        ) : (
          <form onSubmit={submitCode} noValidate className="space-y-4">
            <p className="text-sm" aria-live="polite">
              We sent a 6-digit code to <strong className="break-all">{sentTo}</strong>. It works once and expires in{" "}
              {minutes} minutes. Check your junk folder if it does not arrive.
            </p>
            <div className="space-y-1.5">
              <label htmlFor={codeId} className="block text-sm font-medium">
                Code from the email
              </label>
              <input
                id={codeId}
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                autoFocus
                required
                maxLength={6}
                pattern="[0-9]{6}"
                value={code}
                onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
                aria-invalid={error ? true : undefined}
                aria-describedby={error ? errorId : undefined}
                className={`${FIELD} text-center font-mono text-2xl tracking-[0.5em]`}
              />
            </div>
            {error && (
              <p id={errorId} role="alert" className="text-sm font-medium text-status-blocked">
                {error}
              </p>
            )}
            <Button type="submit" size="lg" className="w-full" disabled={busy || code.length !== 6}>
              {busy ? "Checking…" : "Sign in"}
              <ArrowRightIcon className="h-5 w-5" />
            </Button>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <Button
                variant="quiet"
                size="sm"
                onClick={() => {
                  setStep("email");
                  setError(null);
                }}
              >
                <ArrowLeftIcon className="h-4 w-4" />
                Use a different email
              </Button>
              <Button variant="ghost" size="sm" disabled={busy || resendIn > 0} onClick={() => void sendCode(sentTo)}>
                {resendIn > 0 ? `Send a new code in ${resendIn} s` : "Send a new code"}
              </Button>
            </div>
          </form>
        )}
      </div>

      <footer className="flex items-start gap-2 border-t border-border bg-surface-sunken/60 px-5 py-4 text-xs text-text-muted sm:px-6">
        <ShieldCheckIcon className="mt-0.5 h-4 w-4 shrink-0 text-status-done" />
        <p>
          Your courses and plan stay in this browser. The server keeps your email address only while you are signed in.{" "}
          <Link href="/privacy" className="font-medium text-primary underline">
            Privacy
          </Link>
        </p>
      </footer>
    </section>
  );
}
