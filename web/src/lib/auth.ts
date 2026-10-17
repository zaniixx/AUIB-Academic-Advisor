/**
 * F9.1: sign-in with an AUIB email address. The API emails a one-time code; entering it starts a
 * session kept in an HttpOnly cookie, so this code never sees the session itself. Course and program
 * data need a session: any 401 from the API (an expired session, say) shows the sign-in screen again.
 *
 * The student's courses and plan stay in this browser's storage, as before. On a shared computer the
 * next student must not see them, so signing in as someone else first clears the previous student's
 * data, and signing out offers to clear it too.
 */
import { ApiError, api, onSignedOut } from "./api";
import { clearProfile } from "./profile";

export const OWNER_KEY = "auib-advisor:owner";

export type AuthState =
  | { status: "checking" }
  | { status: "unreachable"; message: string }
  | { status: "signed-out" }
  | { status: "signed-in"; email: string; expiresAt: string };

const CHECKING: AuthState = { status: "checking" };
let state: AuthState = CHECKING;
let checking: Promise<void> | null = null;
const listeners = new Set<() => void>();

function set(next: AuthState) {
  state = next;
  listeners.forEach((listener) => listener());
}

export function subscribeAuth(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export const authSnapshot = (): AuthState => state;
export const serverAuthSnapshot = (): AuthState => CHECKING;

// The API answered 401: the session ended. Show the sign-in screen.
onSignedOut(() => {
  if (state.status === "signed-in") set({ status: "signed-out" });
});

function storage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

/** This browser's saved courses and plan belong to `email` from now on; another student's go first. */
export function claimBrowserData(email: string): void {
  const store = storage();
  const owner = store?.getItem(OWNER_KEY);
  if (owner && owner !== email) clearProfile();
  store?.setItem(OWNER_KEY, email);
}

/** Ask the API who is signed in, once at a time. */
export function checkSession(): Promise<void> {
  checking ??= api.auth
    .me()
    .then(
      (me) => {
        claimBrowserData(me.email);
        set({ status: "signed-in", email: me.email, expiresAt: me.expires_at });
      },
      (error: unknown) => {
        if (error instanceof ApiError && error.status === 401) set({ status: "signed-out" });
        else set({ status: "unreachable", message: error instanceof Error ? error.message : "Try again." });
      },
    )
    .finally(() => {
      checking = null;
    });
  return checking;
}

/** Check again after the server could not be reached. */
export function recheckSession(): Promise<void> {
  set(CHECKING);
  return checkSession();
}

/** Enter the emailed code. Throws an ApiError with a message to show when the code is not accepted. */
export async function verifyCode(email: string, code: string): Promise<void> {
  const me = await api.auth.verify(email, code);
  claimBrowserData(me.email);
  set({ status: "signed-in", email: me.email, expiresAt: me.expires_at });
}

/**
 * End the session; with `clearData`, also delete this browser's courses and plan. With `everywhere`, the
 * server ends every session of this student and forgets their address (F9.2).
 */
export async function signOut(clearData: boolean, everywhere = false): Promise<void> {
  try {
    await api.auth.signOut(everywhere);
  } finally {
    if (clearData) {
      clearProfile();
      storage()?.removeItem(OWNER_KEY);
    }
    set({ status: "signed-out" });
  }
}
