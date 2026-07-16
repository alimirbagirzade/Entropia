import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import { ResultsHistory } from "@/pages/ResultsHistory";
import { stubApi } from "./helpers/apiStub";

const ROW = {
  result_id: "res_1",
  display_title: "Backtest Result res_1",
  composition_context: { composition_id: "ws_1", composition_fingerprint: "fp_1" },
  key_metrics: {
    net_profit: {
      key: "net_profit",
      label: "Net Profit",
      unit: "percent",
      value_format: "signed_percent",
      value: "12.5",
      availability: "computed",
    },
    romad: null,
    max_drawdown: {
      key: "max_drawdown",
      label: "Max Drawdown",
      unit: "percent",
      value_format: "signed_percent",
      value: "-3.75",
      availability: "computed",
    },
    win_rate: {
      key: "win_rate",
      label: "Win Rate",
      unit: "percent",
      value_format: "percent",
      value: "55",
      availability: "computed",
    },
    total_trades: {
      key: "total_trades",
      label: "Total Trades",
      unit: "count",
      value_format: "integer",
      value: "42",
      availability: "computed",
    },
  },
  market_data_revision_summary: { symbol: "BTCUSDT" },
  timeframe: "1h",
  backtest_range: { start: "2026-01-01", end: "2026-03-01" },
  manifest_hash: "mh_1",
  engine_version: "backtest-engine-v2-position-size-limits",
  completed_at_utc: "2026-07-05T19:06:00+00:00",
  materialization_status: "complete",
  allowed_actions: { view: true, compare: true, export: true, soft_delete: true },
};

const PAGE_ONE = {
  items: [ROW],
  next_cursor: "cur_2",
  query_fingerprint: "newest_current",
  sort: "newest_current",
};

// Immutable Result detail lazily read when a row expands (UI-16 inline panel):
// its manifest excerpt carries the pinned Strategies/Parameters.
const RESULT_DETAIL = {
  result_id: "res_1",
  run_id: "run_1",
  composition_id: "ws_1",
  composition_fingerprint: "fp_1",
  manifest_hash: "mh_1",
  engine_version: "backtest-engine-v2-position-size-limits",
  summary: null,
  metrics: [],
  manifest: { manifest_hash: "mh_1", execution_key: "ek_1", engine_version: "e", pinned_item_count: 2 },
  manifest_excerpt: {
    result_id: "res_1",
    composition_snapshot_id: "cs_1",
    strategy_revision_refs: [
      {
        item_id: "it_1",
        item_kind: "strategy",
        root_id: "str_root",
        revision_id: "str_rev",
        position: 0,
        enabled: true,
      },
    ],
    external_work_refs: [],
    package_revision_refs: [
      {
        item_id: "it_2",
        item_kind: "package",
        root_id: "pkg_root",
        revision_id: "pkg_rev",
        position: 1,
        enabled: true,
      },
    ],
    market_data_revision: "md_rev_1",
    research_data_revision_refs: [],
    portfolio_allocation_plan_revision_id: "alloc_1",
    execution_context: { execution_key: "ek_1", composition_fingerprint: "fp_1", capital_execution: null },
    engine_contract_version: "contract-1",
    artifact_context: null,
    completed_at_utc: "2026-07-05T19:06:00+00:00",
    artifact_availability: { counts: {}, any_available: false },
  },
  artifact_counts: {},
};

const EMPTY_PAGE = {
  items: [],
  next_cursor: null,
  query_fingerprint: "newest_current",
  sort: "newest_current",
};

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/backtest/history"]}>
        <ResultsHistory />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Results History page", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders history rows with formatted key metrics and a view link", async () => {
    stubApi({ "GET /backtest-results?": PAGE_ONE });
    renderPage();

    expect(await screen.findByText("res_1")).toBeInTheDocument();
    expect(screen.getByText("+12.50%")).toBeInTheDocument(); // signed_percent
    expect(screen.getByText("-3.75%")).toBeInTheDocument(); // negative keeps its sign
    expect(screen.getByText("55.00%")).toBeInTheDocument(); // percent
    expect(screen.getByText("42")).toBeInTheDocument(); // integer
    expect(screen.getByText("—")).toBeInTheDocument(); // missing digest cell, never 0
    expect(screen.getByText("BTCUSDT")).toBeInTheDocument(); // S7: pinned instrument
    expect(screen.getByText("2026-07-05 19:06 UTC")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View" })).toHaveAttribute(
      "href",
      "/backtest/run?result=res_1",
    );
  });

  it("expands a row to reveal pinned strategies, parameters, data, date and the immutable manifest summary (UI-16)", async () => {
    stubApi({
      "GET /backtest-results/res_1": RESULT_DETAIL, // detail fragment precedes the list prefix
      "GET /backtest-results?": PAGE_ONE,
    });
    renderPage();
    await screen.findByText("res_1");

    // Manifest identity is in the inline panel from the immutable row — no
    // detail fetch, no separate View page required (UI-16 acceptance).
    expect(screen.getByText("Immutable manifest summary")).toBeInTheDocument();
    expect(screen.getByText("mh_1")).toBeInTheDocument(); // manifest hash
    expect(screen.getByText("fp_1")).toBeInTheDocument(); // composition fingerprint

    // Pinned Strategies + Parameters lazily load from the manifest excerpt once
    // the row is expanded.
    fireEvent.click(screen.getByRole("button", { name: "Details for res_1" }));

    expect(await screen.findByText("str_root @ str_rev")).toBeInTheDocument(); // Strategies
    expect(screen.getByText("pkg_root @ pkg_rev")).toBeInTheDocument(); // Parameters: packages
    expect(screen.getByText("ek_1")).toBeInTheDocument(); // Parameters: execution key
    expect(screen.getByText("alloc_1")).toBeInTheDocument(); // Parameters: allocation plan
  });

  it("switches to the selected server sort", async () => {
    const fetchMock = stubApi({ "GET /backtest-results?": PAGE_ONE });
    renderPage();
    await screen.findByText("res_1");

    fireEvent.change(screen.getByLabelText("Sort"), { target: { value: "romad_desc" } });

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("sort=romad_desc"),
        expect.anything(),
      ),
    );
  });

  it("pages forward with the server cursor and back to the first page", async () => {
    const fetchMock = stubApi({ "GET /backtest-results?": PAGE_ONE });
    renderPage();
    await screen.findByText("res_1");
    expect(screen.getByRole("button", { name: "← Previous" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Next →" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("cursor=cur_2"),
        expect.anything(),
      ),
    );
  });

  it("shows the empty state when no results exist", async () => {
    stubApi({ "GET /backtest-results?": EMPTY_PAGE });
    renderPage();

    expect(await screen.findByText("No backtest results yet")).toBeInTheDocument();
  });
});
