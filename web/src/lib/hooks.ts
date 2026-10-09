"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import { ApiError } from "./api";
import { profileSnapshot, subscribeProfile, type Profile } from "./profile";

/** The saved profile; undefined while rendering on the server (storage is browser-only). */
export function useProfile(): Profile | null | undefined {
  return useSyncExternalStore(subscribeProfile, profileSnapshot, () => undefined);
}

export function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : "Something went wrong. Please try again.";
}

/**
 * Runs ``load`` whenever ``key`` changes and keeps only the latest answer, so a slow
 * earlier request can never overwrite a newer one. A null key means "nothing to load".
 * With ``keepPrevious`` the last answer stays in ``data`` while a new one loads (``loading``
 * is true meanwhile), so a page can show "updating" instead of going blank.
 */
export function useAsync<T>(key: string | null, load: () => Promise<T>, { keepPrevious = false } = {}) {
  const [state, setState] = useState<{ key: string; data?: T; error?: string } | null>(null);
  useEffect(() => {
    if (key === null) return;
    let active = true;
    load().then(
      (data) => active && setState({ key, data }),
      (error: unknown) => active && setState({ key, error: errorMessage(error) }),
    );
    return () => {
      active = false;
    };
    // `key` identifies the request; `load` is recreated on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  const current = state?.key === key ? state : null;
  const data = current ? current.data : keepPrevious ? state?.data : undefined;
  return { data, error: current?.error, loading: key !== null && current === null };
}
