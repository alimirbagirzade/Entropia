import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ReadyCheck } from "@/pages/ReadyCheck";
import { stubApi } from "./helpers/apiStub";

const MAINBOARD = {
  workspace_id: "ws_1",
  workspace_kind: "human_default",
  composition_hash: "hash_abc",
  row_version: 3,
  items: [
    {
      item_id: "item_1",
      item_kind: "strategy",
      work_object_root_id: "root_1",
      pinned_revision_id: "rev_1",
      position_index: 0,
      is_enabled: true,
      display_label_override: null,
      row_version: 1,
    },
    {
      item_id: "item_2",
      item_kind: "indicator",
      work_object_root_id: "root_2",
      pinned_revision_id: "rev_2",
      position_index: 1,
      is_enabled: false,
      display_label_override: null,
      row_version: 1,
    },
  ],
  ready_summary: { state: "not_ready", report_id: null },
  latest_result_summary: null,
};

const NOT_CHECKED = { composition_id: "ws_1", state: "not_checked", report_id: null };

const WARN_REPORT = {
  report_id: "rep_1",
  composition_id: "ws_1",
  snapshot_id: "snap_1",
  composition_fingerprint: "hash_abc",
  current_fingerprint: "hash_abc",
  stored_state: "ready_with_warnings",
  state: "ready_with_warnings",
  is_current: true,
  summary: { blocker_count: 0, warning_count: 1, pass_count: 2, allocation_enabled: false },
  issues: [
    {
      code: "EXECUTION_ASSUMPTIONS_DEFAULT",
      severity: "warning",
      scope: "strategy",
      message: "Execution assumptions use engine defaults.",
      remediation: "Review slippage and fees before relying on the result.",
      field_path: "execution",
      scope_id: "item_1",
    },
  ],
};

// POST .../readiness-checks return (omits the read-time currentness fields).
const RUN_RESULT = {
  report_id: "rep_1",
  composition_id: "ws_1",
  state: "ready_with_warnings",
  snapshot_id: "snap_1",
  composition_fingerprint: "hash_abc",
  summary: WARN_REPORT.summary,
  issues: WARN_REPORT.issues,
};

const BLOCKER_REPORT = {
  report_id: "rep_3",
  composition_id: "ws_1",
  snapshot_id: "snap_3",
  composition_fingerprint: "hash_x",
  current_fingerprint: "hash_x",
  stored_state: "not_ready",
  state: "not_ready",
  is_current: true,
  summary: { blocker_count: 1, warning_count: 0, pass_count: 1, allocation_enabled: true },
  issues: [
    {
      code: "COMPOSITION_EMPTY",
      severity: "blocker",
      scope: "composition",
      message: "The composition has no enabled items.",
      remediation: "Enable at least one item.",
      field_path: null,
      scope_id: null,
    },
  ],
};

const STALE_REPORT = {
  ...WARN_REPORT,
  report_id: "rep_2",
  current_fingerprint: "hash_changed",
  stored_state: "ready",
  state: "stale",
  is_current: false,
};

// Superseded: the composition is unchanged (fingerprint matches) but a newer
// report exists for it. The effective state is "superseded", not "stale" — a
// different hint than STALE_REPORT (regression guard for the state === "stale"
// branch, not stored_state !== state which is true for both).
const SUPERSEDED_REPORT = {
  ...WARN_REPORT,
  report_id: "rep_4",
  stored_state: "ready_with_warnings",
  state: "superseded",
  is_current: false,
};

function renderPage(initialEntry = "/backtest/ready-check") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/backtest/ready-check" element={<ReadyCheck />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function postCallBody(fetchMock: ReturnType<typeof stubApi>): unknown {
  const call = fetchMock.mock.calls.find(([url]) => String(url).includes("/readiness-checks"));
  expect(call).toBeTruthy();
  const init = call?.[1] as RequestInit;
  return JSON.parse(String(init.body));
}

describe("Backtest Ready Check page", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders the composition context and the not-checked empty state", async () => {
    stubApi({
      "GET /mainboards/default": MAINBOARD,
      "GET /mainboard-compositions/ws_1/readiness": NOT_CHECKED,
    });
    renderPage();

    expect(await screen.findByText("ws_1")).toBeInTheDocument();
    expect(screen.getByText("2 (1 enabled)")).toBeInTheDocument();
    // Readiness is a second wave (enabled only once the composition id resolves).
    expect(await screen.findByText("Not checked yet")).toBeInTheDocument();
  });

  it("runs a ready check and renders the resulting report", async () => {
    // NOT_CHECKED until the run-check POST lands; the invalidation refetch then
    // returns the freshly produced report projection (robust to mount refetches).
    let ran = false;
    const fetchMock = stubApi({
      "GET /mainboards/default": MAINBOARD,
      "GET /mainboard-compositions/ws_1/readiness": () => (ran ? WARN_REPORT : NOT_CHECKED),
      "POST /mainboard-compositions/ws_1/readiness-checks": () => {
        ran = true;
        return RUN_RESULT;
      },
    });
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Run Ready Check" }));

    expect(await screen.findByText("Ready with warnings")).toBeInTheDocument();
    expect(screen.getByText("EXECUTION_ASSUMPTIONS_DEFAULT")).toBeInTheDocument();
    expect(screen.getByText("Execution assumptions use engine defaults.")).toBeInTheDocument();

    // Guard toggle is off → an empty body; a fresh Idempotency-Key is attached.
    expect(postCallBody(fetchMock)).toEqual({});
    const call = fetchMock.mock.calls.find(([url]) => String(url).includes("/readiness-checks"));
    const headers = (call?.[1] as RequestInit).headers as Record<string, string>;
    expect(headers["Idempotency-Key"]).toBeTruthy();
  });

  it("guards the run with the composition fingerprint when the toggle is on", async () => {
    const fetchMock = stubApi({
      "GET /mainboards/default": MAINBOARD,
      "GET /mainboard-compositions/ws_1/readiness": NOT_CHECKED,
      "POST /mainboard-compositions/ws_1/readiness-checks": RUN_RESULT,
    });
    renderPage();

    fireEvent.click(await screen.findByRole("checkbox"));
    fireEvent.click(await screen.findByRole("button", { name: "Run Ready Check" }));

    // The composition_hash travels as the OCC guard in the body (not If-Match).
    await vi.waitFor(() =>
      expect(postCallBody(fetchMock)).toEqual({ expected_fingerprint: "hash_abc" }),
    );
  });

  it("deep-links an immutable report with a blocker issue via ?report=", async () => {
    stubApi({ "GET /readiness-reports/rep_3": BLOCKER_REPORT });
    renderPage("/backtest/ready-check?report=rep_3");

    expect(await screen.findByText("Not ready")).toBeInTheDocument();
    expect(screen.getByText("COMPOSITION_EMPTY")).toBeInTheDocument();
    expect(screen.getByText("The composition has no enabled items.")).toBeInTheDocument();
    expect(screen.getByText("blocker")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "← Ready Check" })).toBeInTheDocument();
  });

  it("flags a stale report with a re-run hint", async () => {
    stubApi({ "GET /readiness-reports/rep_2": STALE_REPORT });
    renderPage("/backtest/ready-check?report=rep_2");

    expect(await screen.findByText("Stale")).toBeInTheDocument();
    expect(screen.getByText("stale · re-run to refresh")).toBeInTheDocument();
  });

  it("flags a superseded report distinctly from a stale one", async () => {
    stubApi({ "GET /readiness-reports/rep_4": SUPERSEDED_REPORT });
    renderPage("/backtest/ready-check?report=rep_4");

    expect(await screen.findByText("Superseded")).toBeInTheDocument();
    expect(screen.getByText("superseded · a newer report exists")).toBeInTheDocument();
    // Not the stale hint — the fix keys off state, not stored_state !== state.
    expect(screen.queryByText("stale · re-run to refresh")).not.toBeInTheDocument();
  });
});
