import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import { Provisioning } from "@/pages/Provisioning";
import { stubApi } from "./helpers/apiStub";

const ME_ANON = {
  principal_id: null,
  principal_type: "anonymous",
  role: "user",
  is_admin: false,
  is_authenticated: false,
};

const ME_ADMIN = {
  principal_id: "usr_root",
  principal_type: "human",
  role: "admin",
  is_admin: true,
  is_authenticated: true,
};

function renderPage(routes: Record<string, unknown>) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  stubApi(routes);
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Provisioning />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Provisioning page", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("open window, not configured -> prompts to set the env var", async () => {
    renderPage({
      "GET /auth/bootstrap-status": {
        bootstrap_configured: false,
        active_admin_exists: false,
        login_capable_admin_exists: false,
      },
      "GET /me": ME_ANON,
    });
    expect(await screen.findByText("Open — bootstrap email not configured")).toBeInTheDocument();
    // Distinct to the guidance <p> (the env var token also appears in the explainer).
    expect(screen.getByText(/the mechanism is off/)).toBeInTheDocument();
    expect(screen.getByText("email not configured")).toBeInTheDocument();
  });

  it("open window, configured -> prompts to sign up with the bootstrap email", async () => {
    renderPage({
      "GET /auth/bootstrap-status": {
        bootstrap_configured: true,
        active_admin_exists: false,
        login_capable_admin_exists: false,
      },
      "GET /me": ME_ANON,
    });
    expect(
      await screen.findByText("Open — configured, awaiting first sign-up"),
    ).toBeInTheDocument();
    expect(screen.getByText(/Sign up with the configured bootstrap email/)).toBeInTheDocument();
    expect(screen.getByText("window open")).toBeInTheDocument();
  });

  it("closed window (a login-capable Admin exists) is terminal regardless of the flag", async () => {
    renderPage({
      "GET /auth/bootstrap-status": {
        bootstrap_configured: true,
        active_admin_exists: true,
        login_capable_admin_exists: true,
      },
      "GET /me": ME_ANON,
    });
    expect(
      await screen.findByText("Closed — a login-capable Admin already exists"),
    ).toBeInTheDocument();
    expect(screen.getByText(/Provisioning is complete/)).toBeInTheDocument();
    expect(screen.getByText("window closed")).toBeInTheDocument();
  });

  it("legacy credentialless Admin -> window stays OPEN (PROV-05)", async () => {
    // An Admin ROLE ROW exists but no login-capable Admin: the window must NOT
    // read closed, and the legacy state is surfaced distinctly.
    renderPage({
      "GET /auth/bootstrap-status": {
        bootstrap_configured: true,
        active_admin_exists: true,
        login_capable_admin_exists: false,
      },
      "GET /me": ME_ANON,
    });
    expect(
      await screen.findByText("Open — a legacy Admin exists but cannot log in"),
    ).toBeInTheDocument();
    expect(screen.getByText("window open")).toBeInTheDocument();
    expect(screen.getByText("legacy admin (no login)")).toBeInTheDocument();
  });

  it("shows the caller identity and, for an Admin, a Panel link", async () => {
    renderPage({
      "GET /auth/bootstrap-status": {
        bootstrap_configured: false,
        active_admin_exists: true,
        login_capable_admin_exists: true,
      },
      "GET /me": ME_ADMIN,
    });
    // Identity card resolves from /me.
    expect(await screen.findByText("usr_root")).toBeInTheDocument();
    const panelLink = screen.getByRole("link", { name: "Panel" });
    expect(panelLink).toHaveAttribute("href", "/panel");
  });

  it("hides the Panel link for a non-Admin caller", async () => {
    renderPage({
      "GET /auth/bootstrap-status": {
        bootstrap_configured: true,
        active_admin_exists: false,
        login_capable_admin_exists: false,
      },
      "GET /me": ME_ANON,
    });
    await screen.findByText("Open — configured, awaiting first sign-up");
    expect(screen.queryByRole("link", { name: "Panel" })).toBeNull();
  });

  it("surfaces a bootstrap-status failure through the error state", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/auth/bootstrap-status")) {
          return {
            ok: false,
            status: 503,
            statusText: "Service Unavailable",
            text: async () => JSON.stringify({ error: { code: "UNAVAILABLE", message: "down" } }),
          };
        }
        return { ok: true, status: 200, statusText: "OK", text: async () => JSON.stringify(ME_ANON) };
      }),
    );
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <Provisioning />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(await screen.findByText("Unable to load")).toBeInTheDocument();
    expect(screen.getByText("UNAVAILABLE: down")).toBeInTheDocument();
  });
});
