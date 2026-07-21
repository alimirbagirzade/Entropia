// Runtime auth-mode store, initialized from GET /meta (`auth_mode`).
//
// Why a store and not "read the token": the backend's AUTH_MODE decides which
// credential it trusts, and it ignores the other one outright. Under
// AUTH_MODE=dev a stored Bearer token is ignored by the server, so a UI that
// keys off "a token exists in localStorage" hides DevActorControl and claims the
// user is logged in while every protected request resolves as anonymous —
// the login 200 -> protected 401 mismatch. The shell must follow the SERVER's
// mode, so it lives here and both the app shell and the API client read it.
//
// `null` means "not known yet" (/meta still in flight). Callers must render a
// neutral state for null rather than guessing a mode, so the wrong auth control
// never flashes on first paint.
//
// A tiny external store (subscribe / getSnapshot) so `useSyncExternalStore` can
// drive the shell reactively without a React context — matching lib/session.ts.

import { useSyncExternalStore } from "react";

export type AuthMode = "dev" | "session";

let current: AuthMode | null = null;

const listeners = new Set<() => void>();

export function subscribeAuthMode(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function getAuthMode(): AuthMode | null {
  return current;
}

export function setAuthMode(mode: AuthMode): void {
  if (mode === current) return;
  current = mode;
  for (const listener of listeners) listener();
}

// Test-only reset back to "not yet known" so suites do not leak a mode
// between cases.
export function resetAuthMode(): void {
  if (current === null) return;
  current = null;
  for (const listener of listeners) listener();
}

export function useAuthMode(): AuthMode | null {
  return useSyncExternalStore(subscribeAuthMode, getAuthMode, getAuthMode);
}
