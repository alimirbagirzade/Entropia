import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Layout } from "@/app/Layout";
import { ApiError, api, SESSION_INVALID } from "@/lib/apiClient";
import { resetAuthMode, setAuthMode } from "@/lib/authMode";
import {
  clearSession,
  getSessionInvalidations,
  getSessionToken,
  getStoredUser,
  setSession,
  subscribe,
} from "@/lib/session";
import type { AuthUser, Meta } from "@/lib/types";
import { apiErrorRoute, stubApi } from "./helpers/apiStub";

// TEST-10 / audit §9.3 — the invalid-session lifecycle regression suite.
//
// A logout is a DELIBERATE clear the shell must NOT redirect on (covered in
// authModeShell.test.tsx). This suite pins the OPPOSITE: an INVOLUNTARY,
// server-driven session loss — an expired, revoked, or otherwise unknown Bearer
// token the browser is still holding — discovered by unrelated protected reads.
// The server collapses expired/revoked/unknown into ONE canonical
// SESSION_INVALID code; the client can only see the code, so its whole contract
// is: clear exactly once, drop identity-bound state once, return to /login once,
// never loop — and never do any of that for a 403 (a valid session, denied act).

const USER: AuthUser = { user_id: "u1", username: "alice", display_name: "Alice", role: "user" };

class FakeEventSource {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSED = 2;
  readyState = FakeEventSource.CONNECTING;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  addEventListener(): void {}
  removeEventListener(): void {}
  close(): void {}
}

function meta(auth_mode: Meta["auth_mode"]): Meta {
  return {
    name: "Entropia V18",
    version: "0.1.0",
    environment: "local",
    api_base_path: "/api/v1",
    auth_mode,
  };
}

beforeEach(() => {
  localStorage.clear();
  resetAuthMode();
});

afterEach(() => {
  cleanup();
  clearSession();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  resetAuthMode();
});

// ---- The client contract: what a SESSION_INVALID answer does to local state ----

describe("invalid-session client contract", () => {
  it("a revoked/expired token (SESSION_INVALID) clears the local session exactly once", async () => {
    setAuthMode("session");
    setSession({ token: "tok_stale", user: USER, expiresAt: null });
    stubApi({ "GET /mainboards/default": apiErrorRoute(401, SESSION_INVALID, "session is no longer valid") });
    const before = getSessionInvalidations();

    await expect(api.get("/mainboards/default")).rejects.toMatchObject({ code: SESSION_INVALID });

    // The token the browser was holding is gone, and the involuntary-loss counter
    // ticked exactly once — the signal the shell redirects on.
    expect(getSessionToken()).toBeNull();
    expect(getSessionInvalidations()).toBe(before + 1);
  });

  it("expired and revoked both surface as the same one-shot clear", async () => {
    setAuthMode("session");
    for (const message of ["token expired", "token revoked"]) {
      setSession({ token: "tok", user: USER, expiresAt: null });
      stubApi({ "GET /me": apiErrorRoute(401, SESSION_INVALID, message) });
      const before = getSessionInvalidations();
      await expect(api.get("/me")).rejects.toBeInstanceOf(ApiError);
      expect(getSessionToken()).toBeNull();
      expect(getSessionInvalidations()).toBe(before + 1);
      vi.unstubAllGlobals();
    }
  });

  it("N concurrent SESSION_INVALID failures clear once and count once (no storm)", async () => {
    setAuthMode("session");
    setSession({ token: "tok_stale", user: USER, expiresAt: null });
    stubApi({
      "GET /mainboards/default": apiErrorRoute(401, SESSION_INVALID),
      "GET /strategy-drafts": apiErrorRoute(401, SESSION_INVALID),
      "GET /me": apiErrorRoute(401, SESSION_INVALID),
    });
    const before = getSessionInvalidations();

    const results = await Promise.allSettled([
      api.get("/mainboards/default"),
      api.get("/strategy-drafts"),
      api.get("/me"),
    ]);

    expect(results.every((r) => r.status === "rejected")).toBe(true);
    // Ten parallel 401s must still clear once and increment once — the guard in
    // noteSessionInvalid() makes every call after the first a no-op.
    expect(getSessionInvalidations()).toBe(before + 1);
    expect(getSessionToken()).toBeNull();
  });

  it("a 403 ACCESS_DENIED preserves the session — a denied action is not a lost one", async () => {
    setAuthMode("session");
    setSession({ token: "tok_live", user: USER, expiresAt: null });
    stubApi({ "DELETE /trash/xyz": apiErrorRoute(403, "ACCESS_DENIED", "not your resource") });
    const before = getSessionInvalidations();

    await expect(api.del("/trash/xyz")).rejects.toMatchObject({ status: 403 });

    // The Bearer session is perfectly valid; a single forbidden read must never
    // log the user out.
    expect(getSessionToken()).toBe("tok_live");
    expect(getSessionInvalidations()).toBe(before);
  });

  it("a non-auth error (404) preserves the session", async () => {
    setAuthMode("session");
    setSession({ token: "tok_live", user: USER, expiresAt: null });
    stubApi({ "GET /strategy-drafts/nope": apiErrorRoute(404, "STRATEGY_REVISION_NOT_FOUND") });
    const before = getSessionInvalidations();

    await expect(api.get("/strategy-drafts/nope")).rejects.toMatchObject({ status: 404 });

    expect(getSessionToken()).toBe("tok_live");
    expect(getSessionInvalidations()).toBe(before);
  });

  it("the text transport honours SESSION_INVALID the same one-shot way", async () => {
    setAuthMode("session");
    setSession({ token: "tok_stale", user: USER, expiresAt: null });
    stubApi({ "GET /metrics": apiErrorRoute(401, SESSION_INVALID) });
    const before = getSessionInvalidations();

    await expect(api.getText("/metrics")).rejects.toMatchObject({ code: SESSION_INVALID });

    expect(getSessionToken()).toBeNull();
    expect(getSessionInvalidations()).toBe(before + 1);
  });
});

// ---- The shell landing: clear once, drop identity-bound reads once, redirect once ----

function renderShellWithProtectedFailure(routes: Record<string, unknown>) {
  vi.stubGlobal("EventSource", FakeEventSource);
  const fetchMock = stubApi({
    "GET /meta": meta("session"),
    "GET /health/live": { status: "ok" },
    ...routes,
  });
  // Match production ordering: protected queries only fire once the runtime mode
  // is known, so the redirect effect's `authMode === "session"` guard is already
  // satisfied when the first 401 lands (RuntimeAuthProvider gates this in prod).
  setAuthMode("session");
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/panel"]}>
        <Routes>
          <Route path="/login" element={<div>LOGIN SCREEN</div>} />
          <Route path="*" element={<Layout />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return fetchMock;
}

describe("session-mode shell landing on an involuntary session loss", () => {
  it("a server-revoked token drives exactly one clean redirect to /login", async () => {
    const before = getSessionInvalidations();
    setSession({ token: "tok_stale", user: USER, expiresAt: null });
    renderShellWithProtectedFailure({
      "GET /me": apiErrorRoute(401, SESSION_INVALID, "session revoked"),
    });

    // One clean return to the login screen...
    await screen.findByText("LOGIN SCREEN");
    // ...with the stale token cleared...
    expect(getSessionToken()).toBeNull();

    // ...and NO storm. The involuntary-loss counter is the true anti-loop signal:
    // it ticks exactly once. removeQueries may re-init the shell's still-mounted
    // reads, but each re-fires against a now-cleared token and hits the guarded
    // no-op in noteSessionInvalid, so the counter never climbs again and the
    // redirect cannot loop. Give any stray refetch a beat to prove it stays put.
    await new Promise((r) => setTimeout(r, 30));
    expect(getSessionInvalidations()).toBe(before + 1);
    expect(screen.getByText("LOGIN SCREEN")).toBeInTheDocument();
  });

  it("a 403 on a protected read keeps the user in the shell (no redirect)", async () => {
    setSession({ token: "tok_live", user: USER, expiresAt: null });
    renderShellWithProtectedFailure({
      "GET /me": { principal_id: "u1", principal_type: "human", role: "user", is_admin: false, is_authenticated: true },
      "GET /mainboards/default": apiErrorRoute(403, "ACCESS_DENIED"),
    });

    // The authenticated shell stays put; the session survives the forbidden read.
    await screen.findByRole("button", { name: "Log out" });
    expect(screen.queryByText("LOGIN SCREEN")).not.toBeInTheDocument();
    expect(getSessionToken()).toBe("tok_live");
  });
});

// ---- AUTH-08: the redirect preserves a safe return path and drops identity state ----

// A stand-in login screen that echoes the return path the shell handed it via
// router state, so a test can prove the originating page was preserved.
function LoginReturnProbe() {
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? "(none)";
  return <div>{`LOGIN return=${from}`}</div>;
}

describe("session-mode redirect return path and identity cleanup (AUTH-08)", () => {
  function renderShell(loginElement: ReactNode, routes: Record<string, unknown>) {
    vi.stubGlobal("EventSource", FakeEventSource);
    stubApi({ "GET /meta": meta("session"), "GET /health/live": { status: "ok" }, ...routes });
    setAuthMode("session");
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={["/panel"]}>
          <Routes>
            <Route path="/login" element={loginElement} />
            <Route path="*" element={<Layout />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    return client;
  }

  it("carries the originating path to /login as a safe internal return path", async () => {
    setSession({ token: "tok_stale", user: USER, expiresAt: null });
    renderShell(<LoginReturnProbe />, { "GET /me": apiErrorRoute(401, SESSION_INVALID) });

    // The user was on /panel when the session was revoked; a later re-login must be
    // able to land them back there (Login.tsx reads location.state.from).
    expect(await screen.findByText("LOGIN return=/panel")).toBeInTheDocument();
  });

  it("cancels and REMOVES identity-bound queries, not merely invalidates them", async () => {
    setSession({ token: "tok_stale", user: USER, expiresAt: null });
    const client = renderShell(<div>LOGIN SCREEN</div>, {
      "GET /me": apiErrorRoute(401, SESSION_INVALID),
    });
    // Spy after render so construction traffic is not counted.
    const cancelSpy = vi.spyOn(client, "cancelQueries");
    const removeSpy = vi.spyOn(client, "removeQueries");

    await screen.findByText("LOGIN SCREEN");

    // invalidate would refetch the active protected reads (re-failing with the now
    // cleared token) and leave the old principal's rows painted until each settled.
    // The loss path instead aborts in-flight reads and drops the cache outright —
    // the removal is deferred past the redirect (see Layout), so waitFor lets it run.
    expect(cancelSpy).toHaveBeenCalled();
    await waitFor(() => expect(removeSpy).toHaveBeenCalled());
  });
});

// ---- AUTH-10: cross-tab session sync via the browser `storage` event ----
//
// setSession/clearSession notify only THIS tab's in-memory listeners; a
// login/logout in ANOTHER tab writes the same localStorage keys and the browser
// delivers the change to the OTHER tabs as a `storage` event. session.ts relays
// that event into the same emit() (startSessionSync, bound once at import) so
// useSyncExternalStore re-reads the token/user and re-renders every tab. jsdom
// never fires `storage` for a same-document write, so each case constructs the
// event the sibling tab would deliver. These pin the four cross-tab outcomes plus
// the two the relay must IGNORE (a foreign key, a foreign storage area), and prove
// the single-binding and no-involuntary-counter-tick contracts.

const TOKEN_KEY = "entropia.sessionToken";
const SESSION_KEY = "entropia.session";

function siblingTabEvent(init: StorageEventInit): StorageEvent {
  return new StorageEvent("storage", { storageArea: localStorage, ...init });
}

describe("cross-tab session sync (AUTH-10)", () => {
  it("a logout in another tab notifies this tab's subscribers exactly once", () => {
    setSession({ token: "tok", user: USER, expiresAt: null });
    let notified = 0;
    const unsubscribe = subscribe(() => {
      notified += 1;
    });

    // The sibling tab removed the token; this tab receives the storage event.
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(SESSION_KEY);
    window.dispatchEvent(siblingTabEvent({ key: TOKEN_KEY, oldValue: "tok", newValue: null }));

    // Fired once — one bound listener, not a StrictMode/HMR double.
    expect(notified).toBe(1);
    expect(getSessionToken()).toBeNull();
    unsubscribe();
  });

  it("a cross-tab logout must NOT tick the involuntary-loss counter", () => {
    setSession({ token: "tok", user: USER, expiresAt: null });
    const before = getSessionInvalidations();
    const unsubscribe = subscribe(() => {});

    localStorage.removeItem(TOKEN_KEY);
    window.dispatchEvent(siblingTabEvent({ key: TOKEN_KEY, newValue: null }));

    // A deliberate logout elsewhere is not a server-driven loss; ticking the
    // counter would bounce every other tab to /login, breaking the logout contract.
    expect(getSessionInvalidations()).toBe(before);
    unsubscribe();
  });

  it("a login in another tab notifies subscribers and exposes the new user", () => {
    let notified = 0;
    const unsubscribe = subscribe(() => {
      notified += 1;
    });

    // The sibling tab logged in: it wrote both keys; this tab is told the session
    // key changed and re-reads the freshly persisted identity.
    const persisted = JSON.stringify({ user: USER, expiresAt: null });
    localStorage.setItem(TOKEN_KEY, "tok_new");
    localStorage.setItem(SESSION_KEY, persisted);
    window.dispatchEvent(siblingTabEvent({ key: SESSION_KEY, newValue: persisted }));

    expect(notified).toBe(1);
    expect(getSessionToken()).toBe("tok_new");
    expect(getStoredUser()).toMatchObject({ user_id: "u1" });
    unsubscribe();
  });

  it("a localStorage.clear() in another tab (key === null) still notifies", () => {
    setSession({ token: "tok", user: USER, expiresAt: null });
    let notified = 0;
    const unsubscribe = subscribe(() => {
      notified += 1;
    });

    localStorage.clear();
    window.dispatchEvent(siblingTabEvent({ key: null, newValue: null }));

    expect(notified).toBe(1);
    unsubscribe();
  });

  it("an unrelated key changed in another tab does NOT notify", () => {
    let notified = 0;
    const unsubscribe = subscribe(() => {
      notified += 1;
    });

    window.dispatchEvent(siblingTabEvent({ key: "theme.preference", newValue: "dark" }));

    expect(notified).toBe(0);
    unsubscribe();
  });

  it("a change in a DIFFERENT storage area (sessionStorage) is ignored", () => {
    let notified = 0;
    const unsubscribe = subscribe(() => {
      notified += 1;
    });

    // Same key name, foreign storageArea — never our identity store.
    window.dispatchEvent(
      new StorageEvent("storage", { key: TOKEN_KEY, newValue: "x", storageArea: sessionStorage }),
    );

    expect(notified).toBe(0);
    unsubscribe();
  });

  it("two sibling-tab events fire subscribers once each — the listener is bound once", () => {
    let notified = 0;
    const unsubscribe = subscribe(() => {
      notified += 1;
    });

    // A duplicate (StrictMode/HMR) binding would double every emit; one-per-event
    // proves exactly one `storage` listener is registered.
    window.dispatchEvent(siblingTabEvent({ key: SESSION_KEY, newValue: null }));
    window.dispatchEvent(siblingTabEvent({ key: TOKEN_KEY, newValue: null }));

    expect(notified).toBe(2);
    unsubscribe();
  });
});
