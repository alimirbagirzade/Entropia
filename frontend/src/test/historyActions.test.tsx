import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import { ResultsHistory } from "@/pages/ResultsHistory";
import { stubApi } from "./helpers/apiStub";

const EMPTY_METRICS = {
  net_profit: null,
  romad: null,
  max_drawdown: null,
  win_rate: null,
  total_trades: null,
};

function historyRow(id: string, allowed: Partial<Record<string, boolean>> = {}) {
  return {
    result_id: id,
    display_title: `Backtest Result ${id}`,
    composition_context: { composition_id: "ws_1", composition_fingerprint: "fp_1" },
    key_metrics: EMPTY_METRICS,
    market_data_revision_summary: null,
    timeframe: "1h",
    backtest_range: { start: "2026-01-01", end: "2026-03-01" },
    manifest_hash: `mh_${id}`,
    engine_version: "engine-a",
    completed_at_utc: "2026-07-05T19:06:00+00:00",
    materialization_status: "complete",
    allowed_actions: { view: true, compare: true, export: true, soft_delete: true, ...allowed },
  };
}

function page(items: unknown[]) {
  return { items, next_cursor: null, query_fingerprint: "newest_current", sort: "newest_current" };
}

const COMPARE_RESPONSE = {
  results: [
    {
      result_id: "res_1",
      engine_version: "engine-a",
      manifest_hash: "mh_res_1",
      summary: {
        symbol: "BTCUSDT",
        timeframe: "1h",
        period_start: "2026-01-01",
        period_end: "2026-03-01",
        total_trades: 42,
        headline: null,
      },
      key_metrics: {
        ...EMPTY_METRICS,
        net_profit: {
          key: "net_profit",
          label: "Net Profit",
          unit: "percent",
          value_format: "signed_percent",
          value: "12.5",
          availability: "computed",
        },
      },
    },
    {
      result_id: "res_2",
      engine_version: "engine-b",
      manifest_hash: "mh_res_2",
      summary: null,
      key_metrics: EMPTY_METRICS,
    },
  ],
  context: {
    fields: {
      market_data_revision: { a: "Not available", b: "Not available", differs: false },
      engine_version: { a: "engine-a", b: "engine-b", differs: true },
      allocation_context: { a: { mode: "spot" }, b: { mode: "spot" }, differs: false },
      execution_key: { a: "exec_1", b: "exec_2", differs: true },
      composition_fingerprint: { a: "fp_1", b: "fp_1", differs: false },
    },
    context_differs: true,
  },
  context_differs: true,
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

describe("Results History compare & soft-delete", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("compares two selected results and renders the server context diff verbatim", async () => {
    const fetchMock = stubApi({
      "POST /backtest-results/compare": COMPARE_RESPONSE,
      "GET /backtest-results?": page([historyRow("res_1"), historyRow("res_2")]),
    });
    renderPage();
    await screen.findByText("res_1");

    const compareButton = screen.getByRole("button", { name: /Compare selected/ });
    expect(compareButton).toBeDisabled();

    fireEvent.click(screen.getByRole("checkbox", { name: "Select res_1 for compare" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Select res_2 for compare" }));
    fireEvent.click(screen.getByRole("button", { name: "Compare selected (2/2)" }));

    // The id pair goes over the wire in pick order.
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/backtest-results/compare"),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ result_ids: ["res_1", "res_2"] }),
        }),
      ),
    );

    // The difference is made visible — never ranked (RH-09).
    expect(await screen.findByText(/informational only; neither result is ranked/)).toBeInTheDocument();
    expect(screen.getByText("engine-b")).toBeInTheDocument();
    expect(screen.getAllByText("differs")).toHaveLength(2);
    // An object-valued context field renders as verbatim JSON.
    expect(screen.getAllByText('{"mode":"spot"}')).toHaveLength(2);
    expect(screen.getByText("+12.50%")).toBeInTheDocument();
  });

  it("caps the compare selection at two rows", async () => {
    stubApi({
      "GET /backtest-results?": page([historyRow("res_1"), historyRow("res_2"), historyRow("res_3")]),
    });
    renderPage();
    await screen.findByText("res_3");

    fireEvent.click(screen.getByRole("checkbox", { name: "Select res_1 for compare" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Select res_2 for compare" }));

    expect(screen.getByRole("checkbox", { name: "Select res_3 for compare" })).toBeDisabled();
    // Deselecting frees a slot again.
    fireEvent.click(screen.getByRole("checkbox", { name: "Select res_1 for compare" }));
    expect(screen.getByRole("checkbox", { name: "Select res_3 for compare" })).toBeEnabled();
  });

  it("soft-deletes a result only after the explicit confirm step", async () => {
    let listCalls = 0;
    const fetchMock = stubApi({
      "POST /backtest-results/res_1/delete": { result_id: "res_1", deletion_state: "soft_deleted" },
      "GET /backtest-results?": () => (++listCalls === 1 ? page([historyRow("res_1")]) : page([])),
    });
    renderPage();
    await screen.findByText("res_1");

    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    // Arming is client-side only — no wire call yet.
    const deleteCalls = () =>
      fetchMock.mock.calls.filter(([url]) => String(url).includes("/delete"));
    expect(deleteCalls()).toHaveLength(0);

    fireEvent.click(screen.getByRole("button", { name: "Confirm delete" }));

    await waitFor(() => expect(deleteCalls()).toHaveLength(1));
    // GAP-13: the soft-delete carries a fresh Idempotency-Key so the server can
    // dedup a retry to a single delete (the route reads the header).
    const deleteHeaders = (deleteCalls()[0][1] as RequestInit).headers as Record<string, string>;
    expect(deleteHeaders["Idempotency-Key"]).toBeTruthy();
    // The ["backtests"] invalidation refetches the index; the deleted row is gone.
    await waitFor(() => expect(screen.queryByText("res_1")).not.toBeInTheDocument());
  });

  it("hides the compare and delete affordances the server did not grant", async () => {
    stubApi({
      "GET /backtest-results?": page([historyRow("res_1", { compare: false, soft_delete: false })]),
    });
    renderPage();
    await screen.findByText("res_1");

    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View" })).toBeInTheDocument();
  });
});
