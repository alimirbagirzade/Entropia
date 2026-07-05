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
