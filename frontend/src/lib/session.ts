// Session token store for real auth (Master §20 / M1 §4). Humans present an
// opaque Bearer session token; the frontend persists it here and the API client
// attaches it as `Authorization: Bearer`. The server re-resolves the ROLE on
// every request — this store never asserts identity, it only carries the token.
//
// A tiny external store (subscribe / getSnapshot) so `useSyncExternalStore` can
// drive header UI reactively without a React context.

import type { AuthUser } from "./types";

const TOKEN_KEY = "entropia.sessionToken";
const SESSION_KEY = "entropia.session";

export interface StoredSession {
  token: string;
  user: AuthUser;
  expiresAt: string | null;
}

interface PersistedMeta {
  user: AuthUser;
  expiresAt: string | null;
}

const listeners = new Set<() => void>();

let invalidations = 0;

function emit(): void {
  for (const listener of listeners) listener();
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

// Fast path for the API client: a bare string read on every request.
export function getSessionToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function getStoredUser(): AuthUser | null {
  const raw = localStorage.getItem(SESSION_KEY);
  if (!raw) return null;
  try {
    return (JSON.parse(raw) as PersistedMeta).user;
  } catch {
    return null;
  }
}

export function setSession(session: StoredSession): void {
  const meta: PersistedMeta = { user: session.user, expiresAt: session.expiresAt };
  localStorage.setItem(TOKEN_KEY, session.token);
  localStorage.setItem(SESSION_KEY, JSON.stringify(meta));
  emit();
}

export function clearSession(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(SESSION_KEY);
  emit();
}

// The server rejected our Bearer token (missing / expired / revoked). Clearing is
// guarded on "a token is actually stored" so it happens EXACTLY ONCE even when a
// page fires ten parallel requests that all fail: the first call clears and emits,
// the rest are no-ops. Without the guard every failed request would emit another
// token transition and the shell's redirect-on-transition would fire repeatedly.
//
// This function deliberately knows nothing about routing or react-query — the
// shell observes the token transition and owns the invalidate + redirect, which
// keeps this module free of a cycle back into queryClient/apiClient.
export function noteSessionInvalid(): void {
  if (localStorage.getItem(TOKEN_KEY) === null) return;
  invalidations += 1;
  clearSession();
}

// Monotonic count of INVOLUNTARY session losses. A deliberate logout is not one:
// it clears the token too, so "the token went away" cannot tell the two apart —
// and conflating them would bounce the user to /login on every logout, replacing
// the shell's anonymous "Login / Sign Up" state. The shell watches this counter
// to redirect only when the server pulled the session out from under the user.
export function getSessionInvalidations(): number {
  return invalidations;
}

// AUTH-10 — cross-tab session synchronization.
//
// setSession/clearSession call emit() for listeners in THIS tab, but a login or
// logout in ANOTHER tab writes these same localStorage keys without touching this
// module's in-memory `listeners` set in the current tab. The browser `storage`
// event is the only cross-tab signal, and it fires exclusively in the OTHER tabs
// (never the writer), so relaying it into emit() propagates a sibling tab's
// login/logout/clear without any risk of a double-emit in the tab that made the
// change. This is UI reactivity only: a cross-tab logout is a DELIBERATE clear, so
// it must NOT increment the involuntary-loss counter — otherwise a logout in one
// tab would bounce every other tab to /login, contradicting the single-tab logout
// contract (the shell stays on anonymous "Login / Sign Up").
function isSessionKeyEvent(event: StorageEvent): boolean {
  // A different storage area (e.g. sessionStorage) is never our session.
  if (event.storageArea && event.storageArea !== localStorage) return false;
  // localStorage.clear() fires with key === null; a targeted set/remove of a
  // session key fires with that key. Any other key is unrelated to identity.
  return event.key === null || event.key === TOKEN_KEY || event.key === SESSION_KEY;
}

function handleStorage(event: StorageEvent): void {
  if (isSessionKeyEvent(event)) emit();
}

// Bound exactly once. The guard is a module-scoped flag rather than an effect, so
// React Strict Mode's double-invoked effects cannot register a duplicate listener,
// and a single module instance never binds twice. (HMR re-imports the module with
// a fresh flag; the previous instance's listener is orphaned with its old `emit`,
// the standard dev-only trade-off — one live listener per running module.)
let storageBound = false;

export function startSessionSync(): void {
  if (storageBound || typeof window === "undefined") return;
  storageBound = true;
  window.addEventListener("storage", handleStorage);
}

startSessionSync();
