import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { BacktestRun } from "@/pages/BacktestRun";
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

const QUEUED_RUN = {
  run_id: "btrun_7",
  composition_id: "ws_1",
  state: "queued",
  manifest_hash: "mh_1",
  composition_fingerprint: "fp_1",
  composition_snapshot_id: null,
  ready_report_id: "rr_1",
  retry_of_run_id: null,
  result_id: null,
  failure_code: null,
  failure_message: null,
  job_id: "job_1",
  created_at: "2026-07-06T05:30:00+00:00",
  started_at: null,
  finished_at: null,
};

const FAILED_RUN = {
  ...QUEUED_RUN,
  run_id: "btrun_8",
  state: "failed",
  failure_code: "ASSET_UNAVAILABLE",
  failure_message: "processed asset missing",
  finished_at: "2026-07-06T05:31:00+00:00",
};

const RESULT_DETAIL = {
  result_id: "res_1",
  run_id: "btrun_7",
  composition_id: "ws_1",
  composition_fingerprint: "fp_1",
  manifest_hash: "mh_1",
  engine_version: "backtest-engine-v2-position-size-limits",
  summary: {
    symbol: "BTCUSDT",
    timeframe: "1h",
    period_start: "2026-01-01",
    period_end: "2026-03-01",
    total_trades: 42,
    headline: "Net profit +12.50%",
  },
  metrics: [
    {
      key: "net_profit",
      label: "Net Profit",
      unit: "percent",
      value_format: "signed_percent",
      value: "12.5",
      availability: "computed",
      formula_version: "v1",
    },
    {
      key: "romad",
      label: "ROMAD",
      unit: "ratio",
      value_format: "decimal2",
      value: null,
      availability: "not_available",
      formula_version: "v1",
    },
  ],
  manifest: {
    manifest_hash: "mh_1",
    execution_key: "exec_1",
    engine_version: "backtest-engine-v2-position-size-limits",
    pinned_item_count: 2,
  },
  artifact_counts: { trades: 42, equity_points: 1000 },
};

// Profile-hydrated metrics view (doc 17 §9.1) the ResultDetail Metrics section
// binds to; mirrors the persisted rows so the L4 assertions below exercise the
// HYDRATED path, not the fallback.
const RESULT_METRICS_VIEW = {
  result_id: "res_1",
  profile: {
    profile_id: "system_default",
    scope: "system_default",
    is_personal: false,
    is_locked: false,
    registry_version: "v1",
  },
  metrics: RESULT_DETAIL.metrics,
};

function renderPage(initialEntry = "/backtest/run") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/backtest/run" element={<BacktestRun />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("RUN & Backtest Results page", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders the composition context and admits a run", async () => {
    const fetchMock = stubApi({
      "GET /mainboards/default": MAINBOARD,
      "POST /mainboard-compositions/ws_1/backtest-runs": {
        run_id: "btrun_7",
        state: "queued",
        manifest_hash: "mh_1",
        composition_fingerprint: "fp_1",
        ready_report_id: "rr_1",
        retry_of_run_id: null,
        warning_count: 2,
        job_id: "job_1",
      },
      "GET /backtest-runs/btrun_7": QUEUED_RUN,
    });
    renderPage();

    expect(await screen.findByText("ws_1")).toBeInTheDocument();
    expect(screen.getByText("2 (1 enabled)")).toBeInTheDocument();
    expect(screen.getByText("No active run")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Request Backtest Run" }));

    // The admitted run id lands in ?run= and the durable status row renders.
    expect(await screen.findByText("queued")).toBeInTheDocument();
    expect(screen.getByText("btrun_7")).toBeInTheDocument();
    expect(screen.getByText("2 readiness warning(s)")).toBeInTheDocument();
    // GAP-13: the 202 admission carries a fresh Idempotency-Key so the server
    // dedups a network retry to a single run instead of admitting a duplicate.
    const runCall = fetchMock.mock.calls.find(
      ([url, init]) =>
        String(url).includes("/backtest-runs") && (init as RequestInit)?.method === "POST",
    );
    const runHeaders = (runCall?.[1] as RequestInit).headers as Record<string, string>;
    expect(runHeaders["Idempotency-Key"]).toBeTruthy();
  });

  it("deep-links an immutable result via ?result=", async () => {
    stubApi({
      // Route-aware order: most-specific fragment first. The artifacts URL
      // contains the detail fragment, and the metrics URL contains the detail
      // fragment — so both must precede the bare detail entry.
      "GET /backtest-results/res_1/artifacts/trade_ledger": {
        result_id: "res_1",
        artifact_type: "trade_ledger",
        items: [],
        next_cursor: null,
      },
      "GET /backtest-results/res_1/artifacts/diagnostics": {
        result_id: "res_1",
        artifact_type: "diagnostics",
        items: [],
        next_cursor: null,
      },
      "GET /backtest-results/res_1/metrics": RESULT_METRICS_VIEW,
      "GET /backtest-results/res_1": RESULT_DETAIL,
    });
    renderPage("/backtest/run?result=res_1");

    expect(await screen.findByText("+12.50%")).toBeInTheDocument();
    // The Metrics section is the profile-hydrated view, not the raw rows.
    expect(await screen.findByText(/Profile view · system default/)).toBeInTheDocument();
    // A non-computed metric shows its availability, never a fabricated 0 (L4).
    expect(screen.getByText("Not available")).toBeInTheDocument();
    expect(screen.getByText("BTCUSDT")).toBeInTheDocument();
    expect(screen.getByText("res_1")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "← Results History" })).toBeInTheDocument();
  });

  it("shows failure details and retries into a fresh run", async () => {
    const fetchMock = stubApi({
      "GET /mainboards/default": MAINBOARD,
      "GET /backtest-runs/btrun_8": FAILED_RUN,
      "POST /backtest-runs/btrun_8/retries": {
        run_id: "btrun_9",
        state: "queued",
        manifest_hash: "mh_2",
        composition_fingerprint: "fp_1",
        ready_report_id: "rr_2",
        retry_of_run_id: "btrun_8",
        warning_count: 0,
        job_id: "job_2",
      },
      "GET /backtest-runs/btrun_9": {
        ...QUEUED_RUN,
        run_id: "btrun_9",
        retry_of_run_id: "btrun_8",
      },
    });
    renderPage("/backtest/run?run=btrun_8");

    expect(await screen.findByText("failed")).toBeInTheDocument();
    expect(screen.getByText(/ASSET_UNAVAILABLE/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Retry run" }));

    // The retry admission swaps tracking onto the NEW run id (immutable original).
    expect(await screen.findByText("btrun_9")).toBeInTheDocument();
    expect(screen.getByText("queued")).toBeInTheDocument();
    // GAP-13: the retry admission carries a fresh Idempotency-Key.
    const retryCall = fetchMock.mock.calls.find(([url]) => String(url).includes("/retries"));
    const retryHeaders = (retryCall?.[1] as RequestInit).headers as Record<string, string>;
    expect(retryHeaders["Idempotency-Key"]).toBeTruthy();
  });
});
