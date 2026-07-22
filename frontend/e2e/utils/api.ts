import { type APIResponse, type Page } from "@playwright/test";

// Direct, real HTTP against the running API — the CI Docker stack exposes it on
// :8000 next to the :8080 web app (see e2e/README.md). Used to assert SERVER
// authentication truth (`/me`, protected reads) instead of trusting a static
// page heading, which can render while its protected query shows UNAUTHENTICATED
// (audit TEST-08).
export const API_BASE = process.env.E2E_API_BASE_URL ?? "http://localhost:8000/api/v1";

// The exact key the app persists the opaque Bearer session token under
// (frontend/src/lib/session.ts TOKEN_KEY) — the E2E reads it to prove the very
// token the browser holds is accepted (or, after logout, rejected) by the server.
const TOKEN_KEY = "entropia.sessionToken";

export function readSessionToken(page: Page): Promise<string | null> {
  return page.evaluate((key) => localStorage.getItem(key), TOKEN_KEY);
}

export interface Me {
  principal_id: string | null;
  principal_type: string;
  role: string | null;
  is_admin: boolean;
  is_authenticated: boolean;
}

// A GET against the API carrying the given Bearer token verbatim (or none). Never
// reads the token itself — the caller passes exactly what it wants the server to
// see, so a test can replay a now-revoked token and prove it is rejected.
export function apiGet(page: Page, path: string, token: string | null): Promise<APIResponse> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  return page.request.get(`${API_BASE}${path}`, { headers });
}

export async function getMe(page: Page, token: string | null): Promise<Me> {
  const res = await apiGet(page, "/me", token);
  return (await res.json()) as Me;
}

// Every backend plane the product needs must report ready — API + Postgres +
// Redis + MinIO + scheduler + coordinator + workers behind one readiness probe
// (audit §9.4 step 14). Returns the raw response so a test can assert 200.
export function apiReady(page: Page): Promise<APIResponse> {
  return page.request.get(`${API_BASE}/health/ready`);
}
