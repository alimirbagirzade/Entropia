import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { Mainboard } from "@/pages/Mainboard";
import { stubApi } from "./helpers/apiStub";

// UI-14 — the fixed lower-right Ready Check / RUN shell on Mainboard, and the
// in-context Ready Check modal it opens (Passed / Failed / Warnings, 3 columns).
// Readiness is server-authoritative: the modal renders the immutable report
// projection verbatim, and RUN stays locked from the real ready state (F-16).

const MAINBOARD = {
  workspace_id: "ws_1",
  workspace_kind: "human_default",
  composition_hash: "hash_abc",
  row_version: 7,
  items: [
    {
      item_id: "item_strat",
      item_kind: "strategy",
      work_object_root_id: "root_strat",
      pinned_revision_id: "wor_1",
      position_index: 0,
      is_enabled: true,
      display_label_override: "Momentum A",
      row_version: 5,
    },
  ],
  ready_summary: { state: "not_ready", report_id: "rr_1" },
  latest_result_summary: null,
};

// A readiness projection with one blocker + one warning + four passes.
const READINESS = {
  composition_id: "ws_1",
  state: "not_ready",
  report_id: "rr_1",
  snapshot_id: "snap_1",
  composition_fingerprint: "hash_abc",
  current_fingerprint: "hash_abc",
  stored_state: "not_ready",
  is_current: true,
  summary: { blocker_count: 1, warning_count: 1, pass_count: 4, allocation_enabled: false },
  issues: [
    {
      code: "STRATEGY_INCOMPLETE",
      severity: "blocker",
      scope: "strategy:root_strat",
      message: "Strategy entry logic is incomplete.",
      remediation: "Add at least one Indicator + Condition.",
      field_path: null,
      scope_id: "root_strat",
    },
    {
      code: "SHORT_HISTORY",
      severity: "warning",
      scope: "composition",
      message: "Backtest window is short.",
      remediation: null,
      field_path: null,
      scope_id: null,
    },
  ],
};

const RUN_CHECK_RESULT = {
  report_id: "rr_2",
  composition_id: "ws_1",
  state: "not_ready",
  snapshot_id: "snap_2",
  composition_fingerprint: "hash_abc",
  summary: { blocker_count: 1, warning_count: 1, pass_count: 4, allocation_enabled: false },
  issues: READINESS.issues,
};

function stubRoutes(overrides: Record<string, unknown> = {}) {
  return stubApi({
    "GET /mainboard-compositions/ws_1/readiness": READINESS,
    "POST /mainboard-compositions/ws_1/readiness-checks": RUN_CHECK_RESULT,
    "GET /mainboards/default": MAINBOARD,
    ...overrides,
  });
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="/" element={<Mainboard />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function headersOf(init: RequestInit | undefined): Record<string, string> {
  return (init?.headers ?? {}) as Record<string, string>;
}
function bodyOf(init: RequestInit | undefined): Record<string, unknown> {
  return JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("UI-14 Ready Check shell + modal", () => {
  it("renders the fixed Ready Check / RUN shell with a status strip bound to real readiness", async () => {
    stubRoutes();
    renderPage();
    await screen.findByText("Momentum A");
    // The strip reflects the REAL state from the default-Mainboard projection
    // (not_ready → the Not Ready line), not a static decoration.
    const strip = screen.getByRole("img", { name: "Backtest Ready: Not Ready" });
    // not_ready → the plain (red) strip: no "ready" (green) modifier class.
    expect(strip.classList.contains("ready")).toBe(false);
    // The Ready Check trigger is a real dialog-opening button (not a route link).
    expect(screen.getByRole("button", { name: /Backtest Ready Check/ })).toBeTruthy();
    // No readiness fetch happens until the modal opens.
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("colors the strip ready (green) when the composition is ready", async () => {
    stubRoutes({
      "GET /mainboards/default": {
        ...MAINBOARD,
        ready_summary: { state: "ready", report_id: "rr_9" },
      },
    });
    renderPage();
    await screen.findByText("Momentum A");
    const strip = screen.getByRole("img", { name: "Backtest Ready: Ready" });
    expect(strip.classList.contains("ready")).toBe(true);
  });

  it("opens the Ready Check modal and renders the 3-column server report", async () => {
    stubRoutes();
    renderPage();
    await screen.findByText("Momentum A");
    fireEvent.click(screen.getByRole("button", { name: /Backtest Ready Check/ }));

    const dialog = await screen.findByRole("dialog");
    // Passed column shows the server pass_count (no fabricated per-pass strings, L4).
    expect(await within(dialog).findByText("✓ 4 checks passed.")).toBeTruthy();
    // Failed column shows the blocker issue verbatim, with its code.
    const failed = within(dialog).getByLabelText("Failed");
    expect(within(failed).getByText(/Strategy entry logic is incomplete\./)).toBeTruthy();
    expect(within(failed).getByText("STRATEGY_INCOMPLETE")).toBeTruthy();
    // Warnings column shows the warning issue, not the blocker.
    const warnings = within(dialog).getByLabelText("Warnings");
    expect(within(warnings).getByText(/Backtest window is short\./)).toBeTruthy();
    expect(within(warnings).queryByText(/Strategy entry logic/)).toBeNull();
  });

  it("keeps RUN locked (disabled button, not a link) while the state is not ready", async () => {
    stubRoutes();
    renderPage();
    await screen.findByText("Momentum A");
    const run = screen.getByRole("button", { name: "RUN" });
    expect(run).toBeDisabled();
    expect(screen.queryByRole("link", { name: "RUN" })).toBeNull();
  });

  it("runs the Ready Check from the modal with a fresh Idempotency-Key and no OCC guard by default", async () => {
    const fetchMock = stubRoutes();
    renderPage();
    await screen.findByText("Momentum A");
    fireEvent.click(screen.getByRole("button", { name: /Backtest Ready Check/ }));
    await screen.findByRole("dialog");
    fireEvent.click(screen.getByRole("button", { name: "Run Ready Check" }));

    await vi.waitFor(() => {
      const call = fetchMock.mock.calls.find(
        (c) =>
          String(c[0]).includes("/mainboard-compositions/ws_1/readiness-checks") &&
          (c[1]?.method ?? "") === "POST",
      );
      expect(call).toBeTruthy();
      // Fresh Idempotency-Key per attempt; the guard is off, so no OCC token.
      expect(headersOf(call?.[1])["Idempotency-Key"]).toBeTruthy();
      expect(bodyOf(call?.[1]).expected_fingerprint).toBeUndefined();
    });
  });

  it("sends the composition fingerprint as the OCC guard when the guard is enabled", async () => {
    const fetchMock = stubRoutes();
    renderPage();
    await screen.findByText("Momentum A");
    fireEvent.click(screen.getByRole("button", { name: /Backtest Ready Check/ }));
    await screen.findByRole("dialog");
    fireEvent.click(screen.getByLabelText(/Guard: fail if the composition changed/));
    fireEvent.click(screen.getByRole("button", { name: "Run Ready Check" }));

    await vi.waitFor(() => {
      const call = fetchMock.mock.calls.find(
        (c) =>
          String(c[0]).includes("/readiness-checks") && (c[1]?.method ?? "") === "POST",
      );
      // The guard carries the loaded composition_hash as the fingerprint OCC token.
      expect(bodyOf(call?.[1]).expected_fingerprint).toBe("hash_abc");
    });
  });

  it("closes the modal on Close", async () => {
    stubRoutes();
    renderPage();
    await screen.findByText("Momentum A");
    fireEvent.click(screen.getByRole("button", { name: /Backtest Ready Check/ }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
