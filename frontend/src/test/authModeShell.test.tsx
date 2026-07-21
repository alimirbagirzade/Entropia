import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import { Layout } from "@/app/Layout";
import { resetAuthMode } from "@/lib/authMode";
import { setDevActorId } from "@/lib/devActor";
import { clearSession, setSession } from "@/lib/session";
import type { AuthUser, Meta } from "@/lib/types";
import { stubApi } from "./helpers/apiStub";

// The app shell must pick its auth UI from the SERVER's runtime auth mode
// (/meta.auth_mode), never from "a token exists in localStorage".
//
// The bug this pins: with AUTH_MODE=dev the backend ignores Bearer tokens and
// resolves identity only from X-Actor-Id. The old shell hid DevActorControl the
// moment a token was stored, so after a "successful" login the browser held a
// token the backend discarded AND the only control dev mode honours was gone —
// every protected request came back 401 while the UI claimed to be signed in.

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

function renderShell(auth_mode: Meta["auth_mode"]) {
  vi.stubGlobal("EventSource", FakeEventSource);
  stubApi({
    "GET /meta": meta(auth_mode),
    "GET /me": { principal_id: null, principal_type: "anonymous", role: null, is_admin: false, is_authenticated: false },
    "GET /health/live": { status: "ok" },
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/"]}>
        <Layout />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const devActorField = () => screen.queryByLabelText("act as");

beforeEach(() => {
  localStorage.clear();
  resetAuthMode();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  resetAuthMode();
});

describe("app shell auth mode", () => {
  it("dev mode shows the dev actor control and offers no Login / Sign Up", async () => {
    renderShell("dev");

    await waitFor(() => expect(devActorField()).toBeInTheDocument());
    expect(screen.queryByRole("link", { name: /Login \/ Sign Up/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Log out" })).not.toBeInTheDocument();
  });

  it("session mode shows Login / Sign Up and never the dev actor control", async () => {
    renderShell("session");

    await screen.findByRole("link", { name: /Login \/ Sign Up/i });
    expect(devActorField()).not.toBeInTheDocument();
  });

  // The regression itself: a token left behind by an earlier session-mode run
  // must not suppress the only identity control dev mode honours.
  it("a stored session token cannot hide the dev actor control in dev mode", async () => {
    setSession({ token: "tok_stale", user: USER, expiresAt: null });
    renderShell("dev");

    await waitFor(() => expect(devActorField()).toBeInTheDocument());
    // ...and the shell must not claim the user is signed in.
    expect(screen.queryByRole("button", { name: "Log out" })).not.toBeInTheDocument();
  });

  // A deliberate logout must leave the user on the app shell as an anonymous
  // visitor — NOT bounce them to /login. Both logout and an expired session
  // clear the token, so keying the redirect off "the token went away" would
  // conflate them and replace this state (it broke e2e 01-auth). Only an
  // involuntary loss redirects.
  it("logout leaves the shell on Login / Sign Up instead of redirecting", async () => {
    setSession({ token: "tok_live", user: USER, expiresAt: null });
    renderShell("session");
    await screen.findByRole("button", { name: "Log out" });

    clearSession(); // what useLogout does after revoking server-side

    await screen.findByRole("link", { name: /Login \/ Sign Up/i });
    expect(screen.queryByRole("button", { name: "Log out" })).not.toBeInTheDocument();
  });

  it("renders neither auth control while /meta is still in flight", () => {
    setDevActorId("user_admin");
    renderShell("session");

    // First paint: mode unknown. Committing to either control here is what makes
    // the wrong one flash on a dev-mode server.
    expect(devActorField()).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Login \/ Sign Up/i })).not.toBeInTheDocument();
  });
});
