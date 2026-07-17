import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import { PanelLogs } from "@/pages/PanelLogs";
import { stubApi } from "./helpers/apiStub";

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

// Server-hydrated distinct target_entity_type set (real emitters only) — the source
// of truth for the "Resource type" filter. Deliberately contains NONE of the six
// curated options the old hand-list carried (user / package_revision / dataset_revision
// / artifact / allocation_plan / system), which matched no emitter → silent empty page.
const RESOURCE_TYPES = {
  resource_types: [
    "backtest_run",
    "human_user",
    "market_dataset",
    "package",
    "portfolio_allocation_plan",
    "strategy",
  ],
};

// Order matters for the fragment-matching stub: the detail route must come
// before the list route ("/admin/logs/evt_1" contains "/admin/logs").
const BASE_ROUTES = {
  "GET /admin/log-resource-types": RESOURCE_TYPES,
  "GET /admin/logs/evt_1": LOG_DETAIL,
  "GET /admin/logs": LOGS_PAGE,
  "GET /audit-events": AUDIT_PAGE,
};

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/panel/logs"]}>
        <PanelLogs />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return client;
}

describe("Panel / Logs page", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders the filtered logs projection alongside the raw audit stream", async () => {
    stubApi(BASE_ROUTES);
    renderPage();

    expect((await screen.findAllByText("user.role_assigned")).length).toBeGreaterThan(0);
    // The raw audit stream renders alongside the filtered Logs projection.
    expect(screen.getByText("Audit stream (raw)")).toBeInTheDocument();
  });

  it("links to the separate Management work context", async () => {
    stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("role assigned");

    expect(screen.getByRole("link", { name: "Go to PANEL / MANAGEMENT" })).toHaveAttribute(
      "href",
      "/panel/management",
    );
  });

  it("hydrates the Resource type filter from the server distinct-set (no curated drift)", async () => {
    stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("role assigned");

    const select = (await screen.findByLabelText("Resource type")) as HTMLSelectElement;
    // "all" (empty value) plus exactly the server-hydrated real targets — no more, no less.
    const values = Array.from(select.options).map((o) => o.value);
    expect(values).toEqual(["", ...RESOURCE_TYPES.resource_types]);
    // Every non-"all" option is a real emitted target the server returned (the R4 invariant).
    expect(values.filter((v) => v !== "")).toEqual(RESOURCE_TYPES.resource_types);
    // The six previously-broken curated options can never render — they are not in the
    // server set, so hydrating from truth structurally cannot resurrect the silent drift.
    for (const broken of ["user", "package_revision", "dataset_revision", "artifact", "allocation_plan", "system"]) {
      expect(values).not.toContain(broken);
    }

    // Selecting a hydrated option drives the filter and refetches the logs page.
    fireEvent.change(select, { target: { value: "package" } });
    await waitFor(() => expect(select.value).toBe("package"));
  });

  it("applies a family filter as a server-side query parameter", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("role assigned");

    fireEvent.change(screen.getByLabelText(/Family/), { target: { value: "backtest" } });

    await waitFor(() => {
      const filtered = fetchMock.mock.calls.find(([url]) =>
        String(url).includes("/admin/logs?family=backtest"),
      );
      expect(filtered).toBeDefined();
    });
  });

  it("sends time, resource and actor identity filters while omitting empty values", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("role assigned");

    const initialLogCall = fetchMock.mock.calls.find(([url]) =>
      String(url).endsWith("/admin/logs"),
    );
    expect(initialLogCall).toBeDefined();

    fireEvent.change(screen.getByLabelText(/From/), {
      target: { value: "2026-07-06T09:00" },
    });
    fireEvent.change(screen.getByLabelText(/To/), {
      target: { value: "2026-07-06T11:00" },
    });
    fireEvent.change(screen.getByLabelText(/Actor ID/), { target: { value: "  u_9  " } });
    fireEvent.change(screen.getByLabelText(/Resource type/), {
      target: { value: "backtest_run" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => {
      const filtered = fetchMock.mock.calls
        .map(([url]) => new URL(String(url), "http://entropia.test"))
        .find((url) => url.searchParams.get("actor_id") === "u_9");
      expect(filtered?.searchParams.get("resource_type")).toBe("backtest_run");
      expect(filtered?.searchParams.get("from")).toMatch(/Z$/);
      expect(filtered?.searchParams.get("to")).toMatch(/Z$/);
      expect(filtered?.searchParams.has("q")).toBe(false);
      expect(filtered?.searchParams.has("correlation_id")).toBe(false);
    });
  });

  it("shows the retained-event Trash affordance for a deleted source", async () => {
    stubApi({
      ...BASE_ROUTES,
      "GET /admin/logs/evt_1": { ...LOG_DETAIL, subject_deleted: true },
    });
    renderPage();
    await screen.findByText("role assigned");

    fireEvent.click(screen.getByRole("button", { name: "Detail" }));

    const trashLink = await screen.findByRole("link", { name: "See Trash." });
    expect(trashLink).toHaveAttribute("href", "/trash");
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
      "GET /admin/logs": () => {
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
