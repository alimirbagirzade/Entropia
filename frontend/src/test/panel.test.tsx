import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import { Panel } from "@/pages/Panel";
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

const LOG_ROW = {
  event_id: "evt_1",
  occurred_at: "2026-07-06T10:00:00+00:00",
  event_kind: "user.role_assigned",
  family: "role_access",
  severity: "info",
  actor_type: "human",
  actor_id: "u_9",
  subject_type: "human_user",
  subject_id: "u_1",
  correlation_id: "corr-1",
  causation_event_id: null,
  message: "role assigned",
};

const LOGS_PAGE = {
  data: [LOG_ROW],
  meta: { cursor: null, has_more: false, limit: 50 },
};

const LOG_DETAIL = {
  ...LOG_ROW,
  previous_state: "user",
  new_state: "supervisor",
  reason: "promotion",
  subject_status: "active",
  subject_deleted: false,
  technical: { trace_id: null, job_id: null, target_revision_id: null },
  correlation_chain: [
    LOG_ROW,
    { ...LOG_ROW, event_id: "evt_2", event_kind: "auth.session_opened" },
  ],
  causation_event: null,
};

const AUDIT_PAGE = {
  data: [
    {
      event_id: "evt_1",
      occurred_at: "2026-07-06T10:00:00+00:00",
      event_kind: "user.role_assigned",
      severity: "info",
      actor_principal_id: "u_9",
      actor_kind: "human",
      target_entity_id: "u_1",
      target_entity_type: "human_user",
      previous_state: "user",
      new_state: "supervisor",
      correlation_id: "corr-1",
    },
  ],
  meta: { cursor: null, has_more: false },
};

// Order matters for the fragment-matching stub: the detail route must come
// before the list route ("/admin/logs/evt_1" contains "/admin/logs").
const BASE_ROUTES = {
  "GET /admin/users": USERS_PAGE,
  "GET /admin/system-actors": SYSTEM_ACTORS,
  "GET /admin/role-matrix": ROLE_MATRIX,
  "GET /admin/logs/evt_1": LOG_DETAIL,
  "GET /admin/logs": LOGS_PAGE,
  "GET /audit-events": AUDIT_PAGE,
};

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/panel"]}>
        <Panel />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return client;
}

describe("Panel / Management / Logs page", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders the registry, system actors, role matrix and logs projections", async () => {
    stubApi(BASE_ROUTES);
    renderPage();

    expect(await screen.findByText("alice")).toBeInTheDocument();
    expect(screen.getByText("Alpha Agent")).toBeInTheDocument();
    expect(screen.getByText("2026-06-role-matrix-v1")).toBeInTheDocument();
    expect((await screen.findAllByText("user.role_assigned")).length).toBeGreaterThan(0);
    // The raw audit stream renders alongside the filtered Logs projection.
    expect(screen.getByText("Audit stream (raw)")).toBeInTheDocument();
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
  });

  it("applies a family filter as a server-side query parameter", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("alice");

    fireEvent.change(screen.getByLabelText(/Family/), { target: { value: "backtest" } });

    await waitFor(() => {
      const filtered = fetchMock.mock.calls.find(([url]) =>
        String(url).includes("/admin/logs?family=backtest"),
      );
      expect(filtered).toBeDefined();
    });
  });

  it("opens the event detail with state transition and correlation chain", async () => {
    stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("role assigned");

    fireEvent.click(screen.getByRole("button", { name: "Detail" }));

    // "user → supervisor" also renders in the raw audit stream — wait on a
    // detail-only field, then assert the transition appears twice.
    expect(await screen.findByText("promotion")).toBeInTheDocument();
    expect(screen.getAllByText("user → supervisor").length).toBe(2);
    expect(screen.getByText("Correlation chain (2)")).toBeInTheDocument();
    expect(screen.getByText("auth.session_opened")).toBeInTheDocument();
  });

  it("refetches the logs when the SSE audit prefix is invalidated", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    const client = renderPage();
    await screen.findByText("role assigned");
    const callsBefore = fetchMock.mock.calls.filter(([url]) =>
      String(url).includes("/admin/logs"),
    ).length;

    // What lib/sse.ts does on `audit.event.created` — every log key is swept.
    await client.invalidateQueries({ queryKey: ["audit"] });

    await waitFor(() => {
      const callsAfter = fetchMock.mock.calls.filter(([url]) =>
        String(url).includes("/admin/logs"),
      ).length;
      expect(callsAfter).toBeGreaterThan(callsBefore);
    });
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
});
