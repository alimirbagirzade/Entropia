import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { RuntimeAuthProvider } from "@/app/RuntimeAuthProvider";
import { api } from "@/lib/apiClient";
import { resetAuthMode } from "@/lib/authMode";
import type { Meta } from "@/lib/types";
import { apiErrorRoute, stubApi } from "./helpers/apiStub";

// AUTH-02: the boot gate must resolve GET /meta BEFORE any mode-dependent render
// or protected query. These tests pin the three states — loading (neutral, no
// controls, no protected fetch), error (fail-closed with a visible Retry) and
// ready (children mount) — and prove a protected query does not fire until ready.

function meta(auth_mode: Meta["auth_mode"]): Meta {
  return { name: "Entropia V18", version: "0.1.0", environment: "local", api_base_path: "/api/v1", auth_mode };
}

// A child whose ONLY job is to prove it mounted and to fire a protected query, so
// a test can assert the query never runs while the mode is unknown.
function ProtectedChild() {
  useQuery({ queryKey: ["me"], queryFn: () => api.get("/me"), retry: false });
  return <div>child-ready</div>;
}

function renderGate() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <RuntimeAuthProvider>
        <ProtectedChild />
      </RuntimeAuthProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  localStorage.clear();
  resetAuthMode();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  resetAuthMode();
});

describe("RuntimeAuthProvider boot gate", () => {
  it("shows a neutral loading state and mounts no child or protected query while /meta is in flight", () => {
    const calls: string[] = [];
    const mock = vi.fn((input: RequestInfo | URL) => {
      calls.push(String(input));
      return new Promise<Response>(() => {}); // /meta never resolves
    });
    vi.stubGlobal("fetch", mock);

    renderGate();

    expect(screen.getByText("Starting…")).toBeInTheDocument();
    // The child never mounted, so its protected /me query never fired — only the
    // anonymous bootstrap /meta went out.
    expect(screen.queryByText("child-ready")).not.toBeInTheDocument();
    expect(calls).toHaveLength(1);
    expect(calls[0]).toContain("/meta");
    // endsWith, not includes: "/api/v1/meta" contains the substring "/me".
    expect(calls.some((u) => u.endsWith("/me"))).toBe(false);
  });

  it("mounts children once /meta resolves the mode (ready)", async () => {
    stubApi({
      "GET /meta": meta("session"),
      "GET /me": { principal_id: null, principal_type: "anonymous", role: null, is_admin: false, is_authenticated: false },
    });

    renderGate();

    await screen.findByText("child-ready");
  });

  it("fails closed with a visible Retry on /meta error, then recovers on a successful retry", async () => {
    let metaReads = 0;
    stubApi({
      "GET /meta": () =>
        metaReads++ === 0 ? apiErrorRoute(503, "SERVICE_UNAVAILABLE", "backend down") : meta("session"),
      "GET /me": { principal_id: null, principal_type: "anonymous", role: null, is_admin: false, is_authenticated: false },
    });

    renderGate();

    // Fail-closed: the error surface names the failure and offers Retry — never a
    // guessed auth control, and the protected child stays unmounted.
    await screen.findByText(/Cannot reach the server/i);
    expect(screen.getByText(/SERVICE_UNAVAILABLE: backend down/)).toBeInTheDocument();
    expect(screen.queryByText("child-ready")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Retry/i }));

    // Second /meta read succeeds → mode resolves → children finally mount.
    await screen.findByText("child-ready");
    await waitFor(() => expect(screen.queryByText(/Cannot reach the server/i)).not.toBeInTheDocument());
  });
});
