import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import { PanelManagement } from "@/pages/PanelManagement";
import { stubApi } from "./helpers/apiStub";

const USERS_PAGE = {
  data: [
    {
      user_id: "u_1",
      username: "alice",
      display_name: "Alice",
      role: "user",
      version: 3,
      status: "active",
      role_changed_at: null,
      role_changed_by: null,
      created_at: "2026-07-01T00:00:00+00:00",
    },
  ],
  meta: { cursor: null, has_more: false, limit: 20 },
};

const SYSTEM_ACTORS = {
  data: [
    {
      actor_type: "system_agent",
      actor_id: "alpha",
      display_name: "Alpha Agent",
      status: "enabled",
      assignable: false,
    },
  ],
};

const ROLE_MATRIX = {
  policy_revision: "2026-06-role-matrix-v1",
  columns: ["view_use", "edit", "delete", "trash", "role_assignment"],
  rows: [
    {
      role: "admin",
      is_system_actor: false,
      assignable: true,
      view_use: "all",
      edit: "all",
      delete: "all",
      trash: "manage",
      role_assignment: "manage",
    },
    {
      role: "supervisor",
      is_system_actor: false,
      assignable: true,
      view_use: "shared_and_published",
      edit: "own",
      delete: "own",
      trash: "none",
      role_assignment: "none",
    },
    {
      role: "user",
      is_system_actor: false,
      assignable: true,
      view_use: "own_and_published",
      edit: "own",
      delete: "own",
      trash: "none",
      role_assignment: "none",
    },
    {
      role: "agent",
      is_system_actor: true,
      assignable: false,
      view_use: "own_system_outputs",
      edit: "own_output",
      delete: "none",
      trash: "none",
      role_assignment: "none",
    },
  ],
};

const BASE_ROUTES = {
  "GET /admin/users": USERS_PAGE,
  "GET /admin/system-actors": SYSTEM_ACTORS,
  "GET /admin/role-matrix": ROLE_MATRIX,
};

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/panel/management"]}>
        <PanelManagement />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return client;
}

// Reveal the secondary operator-recovery flow (UI-19: kept behind a disclosure
// on the primary surface, never a one-click lever).
function openRecovery() {
  fireEvent.click(screen.getByRole("button", { name: "Open operator recovery" }));
}

describe("Panel / Management page", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders the registry, system actors and role matrix", async () => {
    stubApi(BASE_ROUTES);
    renderPage();

    expect(await screen.findByText("alice")).toBeInTheDocument();
    expect(screen.getByText("Alpha Agent")).toBeInTheDocument();
    expect(screen.getByText("2026-06-role-matrix-v1")).toBeInTheDocument();
  });

  it("links to the separate Logs work context", async () => {
    stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("alice");

    expect(screen.getByRole("link", { name: "Go to PANEL / LOGS" })).toHaveAttribute(
      "href",
      "/panel/logs",
    );
  });

  it("assigns a role with the row-version OCC guard and server-truth role options", async () => {
    const fetchMock = stubApi({
      ...BASE_ROUTES,
      "PATCH /admin/users/u_1/role": {
        user_id: "u_1",
        username: "alice",
        role: "supervisor",
        version: 4,
        role_changed_at: "2026-07-06T10:05:00+00:00",
        role_changed_by: "u_9",
        changed: true,
        audit_event_id: "evt_3",
        correlation_id: "corr-2",
      },
    });
    renderPage();
    await screen.findByText("alice");

    const roleSelect = await screen.findByLabelText("Role for alice");
    // Server truth: the Agent matrix row is not assignable → never an option.
    const options = Array.from((roleSelect as HTMLSelectElement).options).map((o) => o.value);
    expect(options).toEqual(["admin", "supervisor", "user"]);

    fireEvent.change(roleSelect, { target: { value: "supervisor" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));

    expect(
      await screen.findByText("Role assignment accepted — alice → supervisor (v4)."),
    ).toBeInTheDocument();
    const patchCall = fetchMock.mock.calls.find(
      ([url, init]) =>
        String(url).includes("/admin/users/u_1/role") && init?.method === "PATCH",
    );
    expect(patchCall).toBeDefined();
    // OCC: the body carries the registry row's version as the expected head.
    const body = JSON.parse(String((patchCall?.[1] as RequestInit).body));
    expect(body).toEqual({ target_role: "supervisor", expected_head_revision_id: 3 });
    // GAP-13: the PATCH also carries a fresh Idempotency-Key so a retry dedups to
    // a single role change (and one audit event) despite the OCC guard.
    const patchHeaders = (patchCall?.[1] as RequestInit).headers as Record<string, string>;
    expect(patchHeaders["Idempotency-Key"]).toBeTruthy();
  });

  it("surfaces the server denial verbatim (server policy, not a UI hint)", async () => {
    stubApi({
      ...BASE_ROUTES,
      "GET /admin/users": () => {
        throw new Error("FORBIDDEN: Admin Panel requires the Admin role.");
      },
    });
    renderPage();

    expect(await screen.findByText("Unable to load")).toBeInTheDocument();
    expect(
      screen.getByText("FORBIDDEN: Admin Panel requires the Admin role."),
    ).toBeInTheDocument();
  });

  it("keeps operator recovery behind a disclosure, not a one-click lever", async () => {
    stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("alice");

    // The dispatch control is not present until the operator opens the flow.
    expect(screen.queryByRole("button", { name: "Redeliver stuck jobs" })).toBeNull();
    openRecovery();
    expect(screen.getByRole("button", { name: "Redeliver stuck jobs" })).toBeInTheDocument();
  });

  it("redelivers stuck data-queue jobs after an explicit confirm and renders the routable result", async () => {
    const fetchMock = stubApi({
      ...BASE_ROUTES,
      "POST /admin/data-queue/redeliver": {
        scanned: 3,
        redeliverable: [
          { job_kind: "market_data_analysis", job_id: "job_1" },
          { job_kind: "trade_log_import", job_id: "job_2" },
        ],
        skipped_unknown_kind: 1,
      },
    });
    renderPage();
    await screen.findByText("alice");

    openRecovery();
    fireEvent.click(screen.getByRole("button", { name: "Redeliver stuck jobs" }));
    // Nothing is dispatched until the operator confirms the secondary step.
    expect(
      fetchMock.mock.calls.some(
        ([url, init]) =>
          String(url).includes("/admin/data-queue/redeliver") && init?.method === "POST",
      ),
    ).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Confirm redelivery" }));

    expect(
      await screen.findByText(
        /Scanned 3 stuck jobs · re-dispatched 2 · skipped 1 un-routable\./,
      ),
    ).toBeInTheDocument();
    // job_kind labels come from the server-mirrored taxonomy, not raw wire values.
    expect(screen.getByText("Market data analysis")).toBeInTheDocument();
    expect(screen.getByText("Trade Log import")).toBeInTheDocument();
    expect(screen.getByText("job_1")).toBeInTheDocument();
    // A blank grace input → the POST carries no query param (server default window).
    const postCall = fetchMock.mock.calls.find(
      ([url, init]) =>
        String(url).includes("/admin/data-queue/redeliver") && init?.method === "POST",
    );
    expect(postCall).toBeDefined();
    expect(String(postCall?.[0])).not.toContain("grace_seconds");
  });

  it("sweeps every queued data job with grace_seconds=0 and shows the empty result", async () => {
    const fetchMock = stubApi({
      ...BASE_ROUTES,
      "POST /admin/data-queue/redeliver": {
        scanned: 0,
        redeliverable: [],
        skipped_unknown_kind: 0,
      },
    });
    renderPage();
    await screen.findByText("alice");

    openRecovery();
    fireEvent.change(screen.getByLabelText(/Grace seconds/), { target: { value: "0" } });
    fireEvent.click(screen.getByRole("button", { name: "Redeliver stuck jobs" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm redelivery" }));

    await waitFor(() => {
      const swept = fetchMock.mock.calls.find(
        ([url, init]) =>
          String(url).includes("/admin/data-queue/redeliver?grace_seconds=0") &&
          init?.method === "POST",
      );
      expect(swept).toBeDefined();
    });
    // No routable rows → the empty state, never a fabricated row.
    expect(
      await screen.findByText("No routable data-queue jobs past the grace window"),
    ).toBeInTheDocument();
  });

  it("blocks redelivery for a negative or non-integer grace value", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("alice");

    openRecovery();
    fireEvent.change(screen.getByLabelText(/Grace seconds/), { target: { value: "-5" } });

    expect(screen.getByRole("button", { name: "Redeliver stuck jobs" })).toBeDisabled();
    expect(
      screen.getByText("Grace seconds must be a whole number of seconds (0 or greater)."),
    ).toBeInTheDocument();
    // The invalid value never reaches the server.
    const posted = fetchMock.mock.calls.some(([url, init]) =>
      String(url).includes("/admin/data-queue/redeliver") && init?.method === "POST",
    );
    expect(posted).toBe(false);
  });
});
