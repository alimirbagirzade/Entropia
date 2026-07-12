import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { ResultDetail } from "@/components/ResultDetail";
import type { BacktestResultDetail } from "@/lib/backtest";
import { stubApi } from "./helpers/apiStub";

const RESULT: BacktestResultDetail = {
  result_id: "res_x",
  run_id: "btrun_x",
  composition_id: "ws_1",
  composition_fingerprint: "fp_1",
  manifest_hash: "mh_x",
  engine_version: "engine-x",
  summary: null,
  metrics: [],
  manifest: null,
  artifact_counts: { trades: 2 },
};

// The Metrics section is out of scope here; an empty profile view keeps its call
// satisfied without competing with the Trade List / export assertions.
const METRICS_VIEW = {
  result_id: "res_x",
  profile: {
    profile_id: "system_default",
    scope: "system_default",
    is_personal: false,
    is_locked: false,
    registry_version: "v1",
  },
  metrics: [],
};

const TRADE_PAGE = {
  result_id: "res_x",
  artifact_type: "trade_ledger",
  items: [
    {
      seq: 1,
      entry_time: "2026-01-01T10:00:00+00:00",
      exit_time: "2026-01-01T12:30:00+00:00",
      direction: "long",
      entry_price: "42000.50",
      exit_price: "42500.00",
      pnl: "499.50",
      exit_reason: "take_profit",
    },
    {
      seq: 2,
      entry_time: "2026-01-02T09:00:00+00:00",
      exit_time: null,
      direction: "short",
      entry_price: "41000.00",
      exit_price: null,
      pnl: null,
      exit_reason: null,
    },
  ],
  next_cursor: "cur_2",
};

const EMPTY_PAGE = {
  result_id: "res_x",
  artifact_type: "trade_ledger",
  items: [],
  next_cursor: null,
};

const EXPORT_RECEIPT = {
  export_id: "btexp_1",
  result_id: "res_x",
  export_type: "trade_ledger",
  export_format: "csv",
  source_manifest_hash: "mh_x",
  object_key: "exports/res_x/trade_ledger/btexp_1.csv",
  checksum: "abc123def456",
  schema_version: "v1",
  row_count: 2,
  status: "completed",
};

function renderDetail() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <ResultDetail result={RESULT} />
    </QueryClientProvider>,
  );
}

describe("ResultDetail trade list + export", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders the trade ledger columns from the cursor page", async () => {
    stubApi({
      "GET /backtest-results/res_x/artifacts/trade_ledger": TRADE_PAGE,
      "GET /backtest-results/res_x/metrics": METRICS_VIEW,
    });
    renderDetail();

    // Timestamps render as formatted UTC; prices/pnl render verbatim.
    expect(await screen.findByText("2026-01-01 10:00 UTC")).toBeInTheDocument();
    expect(screen.getByText("2026-01-01 12:30 UTC")).toBeInTheDocument();
    expect(screen.getByText("long")).toBeInTheDocument();
    expect(screen.getByText("42000.50")).toBeInTheDocument();
    expect(screen.getByText("499.50")).toBeInTheDocument();
    expect(screen.getByText("take_profit")).toBeInTheDocument();
    // An open trade's null cells are em dashes, never a fabricated 0 (L4).
    expect(screen.getByText("short")).toBeInTheDocument();
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("pages forward with the server cursor", async () => {
    const fetchMock = stubApi({
      "GET /backtest-results/res_x/artifacts/trade_ledger": TRADE_PAGE,
      "GET /backtest-results/res_x/metrics": METRICS_VIEW,
    });
    renderDetail();
    await screen.findByText("long");

    fireEvent.click(screen.getByRole("button", { name: "Next →" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("cursor=cur_2"),
        expect.anything(),
      ),
    );
  });

  it("shows the empty state when the result has no trades", async () => {
    stubApi({
      "GET /backtest-results/res_x/artifacts/trade_ledger": EMPTY_PAGE,
      "GET /backtest-results/res_x/metrics": METRICS_VIEW,
    });
    renderDetail();

    expect(
      await screen.findByText("No trades were recorded for this result."),
    ).toBeInTheDocument();
  });

  it("requests an export with a fresh Idempotency-Key and shows the receipt", async () => {
    const fetchMock = stubApi({
      "GET /backtest-results/res_x/artifacts/trade_ledger": EMPTY_PAGE,
      "GET /backtest-results/res_x/metrics": METRICS_VIEW,
      "POST /backtest-results/res_x/exports": EXPORT_RECEIPT,
    });
    renderDetail();
    await screen.findByText("No trades were recorded for this result.");

    fireEvent.click(screen.getByRole("button", { name: "Trade Ledger" }));

    expect(
      await screen.findByText(/Export requested\. The file will be available/),
    ).toBeInTheDocument();
    expect(screen.getByText("trade_ledger · csv · 2 rows · completed")).toBeInTheDocument();
    expect(screen.getByText("abc123def456")).toBeInTheDocument();

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/backtest-results/res_x/exports"),
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ "Idempotency-Key": expect.any(String) }),
      }),
    );
  });
});
