import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import { Layout } from "@/app/Layout";
import { ErrorState } from "@/components/ErrorState";
import { ApiError, BASE_URL } from "@/lib/apiClient";
import { stubApi } from "./helpers/apiStub";

// R2-10 (GAP madde 14): the app shell must surface backend reachability as a
// real state — "Backend unavailable" + the API address in use + a Retry action —
// instead of leaving pages on an endless spinner, and a 401 must land on a real
// UNAUTHENTICATED state with a Login action.

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

function renderLayout() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/"]}>
        <Layout />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const networkDown = () => {
  throw new TypeError("Failed to fetch");
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("app shell backend availability (R2-10)", () => {
  it("shows Backend unavailable + API address + Retry when /health/live fails", async () => {
    vi.stubGlobal("EventSource", FakeEventSource);
    stubApi({
      "GET /me": { is_authenticated: false, is_admin: false, role: null },
      "GET /meta": { name: "Entropia V18", version: "0", environment: "local", api_base_path: "/v1" },
      "GET /health/live": networkDown,
    });
    renderLayout();

    const banner = await screen.findByRole("alert");
    expect(banner).toHaveTextContent("Backend unavailable");
    expect(banner).toHaveTextContent(`API: ${BASE_URL}`);
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("recovers via the user Retry action once the backend answers again", async () => {
    vi.stubGlobal("EventSource", FakeEventSource);
    let backendUp = false;
    stubApi({
      "GET /me": { is_authenticated: false, is_admin: false, role: null },
      "GET /meta": { name: "Entropia V18", version: "0", environment: "local", api_base_path: "/v1" },
      "GET /health/live": () => {
        if (!backendUp) networkDown();
        return { status: "ok" };
      },
    });
    renderLayout();

    const retry = await screen.findByRole("button", { name: "Retry" });
    backendUp = true;
    fireEvent.click(retry);

    await waitFor(() => {
      expect(screen.queryByText("Backend unavailable")).not.toBeInTheDocument();
    });
  });

  it("presents API readiness, SSE and authentication as three separate indicators", async () => {
    vi.stubGlobal("EventSource", FakeEventSource);
    stubApi({
      "GET /me": { is_authenticated: false, is_admin: false, role: null },
      "GET /meta": { name: "Entropia V18", version: "0", environment: "local", api_base_path: "/v1" },
      "GET /health/live": { status: "ok" },
    });
    renderLayout();

    await screen.findByText("● api");
    expect(screen.getByTitle(/API readiness/)).toBeInTheDocument();
    expect(screen.getByTitle(/live events/)).toBeInTheDocument();
    expect(screen.getByText("anonymous")).toBeInTheDocument();
  });
});

describe("UNAUTHENTICATED state (R2-10)", () => {
  it("renders a real UNAUTHENTICATED state with a Login action on a 401", () => {
    render(
      <MemoryRouter>
        <ErrorState error={new ApiError(401, "UNAUTHENTICATED", "Authentication is required.")} />
      </MemoryRouter>,
    );
    expect(screen.getByText("UNAUTHENTICATED")).toBeInTheDocument();
    const login = screen.getByRole("link", { name: "Login" });
    expect(login).toHaveAttribute("href", "/login");
  });

  it("keeps the verbatim code:message render for non-401 errors", () => {
    render(
      <MemoryRouter>
        <ErrorState error={new ApiError(409, "STRATEGY_DRAFT_CONFLICT", "conflict")} />
      </MemoryRouter>,
    );
    expect(screen.getByText("STRATEGY_DRAFT_CONFLICT: conflict")).toBeInTheDocument();
  });
});
