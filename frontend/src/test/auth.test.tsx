import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/apiClient";
import { resetAuthMode, setAuthMode } from "@/lib/authMode";
import { setDevActorId } from "@/lib/devActor";
import { clearSession, getSessionToken, getStoredUser, setSession, subscribe } from "@/lib/session";
import { Login } from "@/pages/Login";
import type { AuthUser, Meta } from "@/lib/types";
import { apiErrorRoute, stubApi } from "./helpers/apiStub";

const USER: AuthUser = { user_id: "u1", username: "alice", display_name: "Alice", role: "user" };

function meta(auth_mode: Meta["auth_mode"]): Meta {
  return {
    name: "Entropia V18",
    version: "0.1.0",
    environment: "local",
    api_base_path: "/api/v1",
    auth_mode,
  };
}

type FetchFn = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

function okFetch(body: unknown) {
  return vi.fn<FetchFn>(() =>
    Promise.resolve({
      ok: true,
      status: 200,
      statusText: "OK",
      text: () => Promise.resolve(JSON.stringify(body)),
    } as unknown as Response),
  );
}

beforeEach(() => {
  localStorage.clear();
  // The auth-mode store is module-level; without this a mode set by one case
  // would leak into the next and silently decide its auth UI.
  resetAuthMode();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  resetAuthMode();
});

describe("session store", () => {
  it("round-trips token and user, then clears", () => {
    expect(getSessionToken()).toBeNull();
    setSession({ token: "tok_abc", user: USER, expiresAt: null });
    expect(getSessionToken()).toBe("tok_abc");
    expect(getStoredUser()).toEqual(USER);
    clearSession();
    expect(getSessionToken()).toBeNull();
    expect(getStoredUser()).toBeNull();
  });

  it("notifies subscribers on set and clear", () => {
    const listener = vi.fn();
    const unsubscribe = subscribe(listener);
    setSession({ token: "t", user: USER, expiresAt: null });
    clearSession();
    expect(listener).toHaveBeenCalledTimes(2);
    unsubscribe();
    setSession({ token: "t2", user: USER, expiresAt: null });
    expect(listener).toHaveBeenCalledTimes(2);
  });
});

describe("apiClient auth header", () => {
  async function headersOf(fetchMock: ReturnType<typeof okFetch>): Promise<Record<string, string>> {
    return (fetchMock.mock.calls[0][1] as RequestInit).headers as Record<string, string>;
  }

  it("attaches Authorization: Bearer when a session token is present", async () => {
    setAuthMode("session");
    setSession({ token: "tok_xyz", user: USER, expiresAt: null });
    const fetchMock = okFetch({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    await api.get("/me");
    expect((await headersOf(fetchMock)).Authorization).toBe("Bearer tok_xyz");
  });

  it("omits Authorization when no session token is present", async () => {
    setAuthMode("session");
    const fetchMock = okFetch({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    await api.get("/me");
    expect((await headersOf(fetchMock)).Authorization).toBeUndefined();
  });

  // The mode mismatch that produced "login 200 -> protected 401": the client must
  // send the credential the SERVER trusts, not both.
  it("session mode never sends X-Actor-Id, even with a dev actor stored", async () => {
    setAuthMode("session");
    setSession({ token: "tok_xyz", user: USER, expiresAt: null });
    setDevActorId("user_admin");
    const fetchMock = okFetch({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    await api.get("/me");
    const headers = await headersOf(fetchMock);
    expect(headers.Authorization).toBe("Bearer tok_xyz");
    expect(headers["X-Actor-Id"]).toBeUndefined();
  });

  it("dev mode sends X-Actor-Id and never a stale Bearer token", async () => {
    setAuthMode("dev");
    setSession({ token: "tok_stale", user: USER, expiresAt: null });
    setDevActorId("user_admin");
    const fetchMock = okFetch({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    await api.get("/me");
    const headers = await headersOf(fetchMock);
    expect(headers["X-Actor-Id"]).toBe("user_admin");
    expect(headers.Authorization).toBeUndefined();
  });
});

describe("stale session handling", () => {
  it("clears the session exactly once on SESSION_INVALID", async () => {
    setAuthMode("session");
    setSession({ token: "tok_dead", user: USER, expiresAt: null });
    const listener = vi.fn();
    const unsubscribe = subscribe(listener);
    stubApi({
      "GET /mainboards/default": apiErrorRoute(401, "SESSION_INVALID", "Session is not valid."),
    });

    await expect(api.get("/mainboards/default")).rejects.toThrow();
    await expect(api.get("/mainboards/default")).rejects.toThrow();

    expect(getSessionToken()).toBeNull();
    // Two failing requests, ONE clear — the guard is what stops a redirect storm.
    expect(listener).toHaveBeenCalledTimes(1);
    unsubscribe();
  });

  it("keeps the session on an authorization failure (ACCESS_DENIED)", async () => {
    setAuthMode("session");
    setSession({ token: "tok_live", user: USER, expiresAt: null });
    stubApi({
      "GET /panel/logs": apiErrorRoute(403, "ACCESS_DENIED", "Admin only."),
    });

    await expect(api.get("/panel/logs")).rejects.toThrow();

    // A forbidden read says nothing about the session's validity — logging the
    // user out here would make one Admin-only page a logout button.
    expect(getSessionToken()).toBe("tok_live");
  });
});

describe("Login page", () => {
  function renderLogin() {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/login"]}>
          <Login />
        </MemoryRouter>
      </QueryClientProvider>,
    );
  }

  it("logs in and stores the returned session token", async () => {
    const fetchMock = stubApi({
      "GET /meta": meta("session"),
      "POST /auth/login": { token: "tok_login", session_id: "s1", expires_at: null, user: USER },
    });
    renderLogin();

    fireEvent.change(await screen.findByLabelText("Username"), { target: { value: "alice" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "pw" } });
    fireEvent.click(screen.getByRole("button", { name: "Log in" }));

    await waitFor(() => expect(getSessionToken()).toBe("tok_login"));
    expect(fetchMock.mock.calls.some((call) => String(call[0]).includes("/auth/login"))).toBe(true);
  });

  it("blocks submit and shows a hint when required fields are empty", async () => {
    const fetchMock = stubApi({ "GET /meta": meta("session") });
    renderLogin();

    fireEvent.click(await screen.findByRole("button", { name: "Log in" }));

    await waitFor(() => expect(screen.getByText("Username is required")).toBeInTheDocument());
    expect(fetchMock.mock.calls.some((call) => String(call[0]).includes("/auth/"))).toBe(false);
  });

  // Dev mode: the API resolves identity from X-Actor-Id and ignores session
  // tokens, so /login must not hand out a credential the backend will discard.
  it("dev mode replaces the form with a local-development message and a way back", async () => {
    stubApi({ "GET /meta": meta("dev") });
    renderLogin();

    await screen.findByText(/Local development mode/i);
    expect(screen.queryByRole("button", { name: "Log in" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Password")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Back to Entropia" })).toBeInTheDocument();
  });

  it("shows no auth form before /meta resolves the mode", () => {
    stubApi({ "GET /meta": meta("session") });
    renderLogin();

    // First paint, /meta still in flight: neither control may appear, or a
    // dev-mode server would flash a login form it does not honour.
    expect(screen.queryByRole("button", { name: "Log in" })).not.toBeInTheDocument();
    expect(screen.queryByText(/Local development mode/i)).not.toBeInTheDocument();
  });
});
