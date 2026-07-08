import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useLogin, useSignup } from "@/lib/auth";
import { useBootstrapStatus } from "@/lib/provisioning";
import { clearSession, getSessionToken } from "@/lib/session";
import type { AuthUser } from "@/lib/types";
import { stubApi } from "./helpers/apiStub";

// Regression guard for the post-V1 first-Admin Provisioning page freshness.
//
// useSignup/useLogin already invalidate EVERY query on success (blanket
// `queryClient.invalidateQueries()`), which includes the ["auth","bootstrap-status"]
// key that pages/Provisioning.tsx reads. So the "invalidate ['auth'] after signup"
// behavior is ALREADY present — narrowing that invalidate to a subset that drops
// ["auth"] would silently strand the Provisioning window on a stale value. These
// tests pin the invariant: a successful signup/login refetches bootstrap-status.

const USER: AuthUser = { user_id: "u1", username: "root", display_name: "Root", role: "user" };
const LOGIN_RESPONSE = { token: "tok_boot", session_id: "s1", expires_at: null, user: USER };

// The bootstrap-status route flips OPEN -> CLOSED across reads: the first read
// reports no active Admin (window open); a later read reports one (window closed).
// The flip is observable ONLY if signup/login success refetches the query.
function makeRoutes() {
  let bootstrapReads = 0;
  const routes = {
    "POST /auth/signup": { user: USER },
    "POST /auth/login": LOGIN_RESPONSE,
    "GET /auth/bootstrap-status": () => {
      bootstrapReads += 1;
      return { bootstrap_configured: true, active_admin_exists: bootstrapReads > 1 };
    },
  };
  return routes;
}

function AuthProbe() {
  const status = useBootstrapStatus();
  const signup = useSignup();
  const login = useLogin();
  const windowLabel = status.isSuccess
    ? status.data.active_admin_exists
      ? "closed"
      : "open"
    : "loading";
  return (
    <div>
      <span>{windowLabel}</span>
      <button
        type="button"
        onClick={() => signup.mutate({ username: "root", password: "pw", email: "root@entropia.dev" })}
      >
        Sign up
      </button>
      <button type="button" onClick={() => login.mutate({ username: "root", password: "pw" })}>
        Log in
      </button>
    </div>
  );
}

function renderProbe() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/panel/provisioning"]}>
        <AuthProbe />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function bootstrapReadCount(fetchMock: ReturnType<typeof stubApi>): number {
  return fetchMock.mock.calls.filter(([url]) => String(url).includes("/auth/bootstrap-status")).length;
}

describe("signup/login refresh the first-Admin bootstrap-status", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    cleanup();
    clearSession();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("refetches ['auth'] bootstrap-status after a successful signup", async () => {
    const fetchMock = stubApi(makeRoutes());
    renderProbe();

    // Initial read: bootstrap window OPEN (no active Admin yet).
    expect(await screen.findByText("open")).toBeInTheDocument();
    const before = bootstrapReadCount(fetchMock);

    fireEvent.click(screen.getByRole("button", { name: "Sign up" }));

    // Signup auto-logs-in, then its onSuccess blanket-invalidates every query;
    // the active ["auth","bootstrap-status"] observer refetches and the window
    // flips CLOSED. A narrowed invalidate that dropped ["auth"] would fail here.
    await waitFor(() => expect(getSessionToken()).toBe("tok_boot"));
    expect(await screen.findByText("closed")).toBeInTheDocument();
    expect(bootstrapReadCount(fetchMock)).toBeGreaterThan(before);
  });

  it("refetches ['auth'] bootstrap-status after a successful login", async () => {
    const fetchMock = stubApi(makeRoutes());
    renderProbe();

    expect(await screen.findByText("open")).toBeInTheDocument();
    const before = bootstrapReadCount(fetchMock);

    fireEvent.click(screen.getByRole("button", { name: "Log in" }));

    await waitFor(() => expect(getSessionToken()).toBe("tok_boot"));
    expect(await screen.findByText("closed")).toBeInTheDocument();
    expect(bootstrapReadCount(fetchMock)).toBeGreaterThan(before);
  });
});
