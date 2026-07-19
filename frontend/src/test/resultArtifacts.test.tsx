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
  manifest_excerpt: {
    result_id: "res_x",
    composition_snapshot_id: null,
    strategy_revision_refs: [],
    external_work_refs: [],
    package_revision_refs: [],
    market_data_revision: null,
    research_data_revision_refs: [],
    portfolio_allocation_plan_revision_id: null,
    execution_context: {
      execution_key: null,
      composition_fingerprint: null,
      capital_execution: null,
    },
    engine_contract_version: null,
    artifact_context: null,
    completed_at_utc: null,
    artifact_availability: { counts: { trades: 2 }, any_available: true },
  },
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

// A run that fell back to the breakout proxy AND could not model the requested
// sizing method — the two honest L4 warnings the Diagnostics card must surface.
const DIAG_PAGE = {
  result_id: "res_x",
  artifact_type: "diagnostics",
  items: [
    {
      diagnostic_id: "btdiag_1",
      kind: "run_diagnostics",
      content: {
        engine_kind: "v1_bar_replay",
        entry_model: "deterministic_bar_breakout_proxy_v1",
        reproducibility_note:
          "Deterministic bar-replay over the pinned market revision; real bars and " +
          "protection stops, breakout entry proxy (indicator layer still stubbed).",
        bars_processed: 500,
        indicator_blocks: 0,
        condition_blocks: 0,
        decision_trace_count: 3,
        warnings: [
          "indicator_plan_empty_fallback_proxy",
          "position_sizing_method_unsupported:formula_based",
        ],
      },
      created_at: "2026-01-01T12:00:00+00:00",
    },
  ],
  next_cursor: null,
};

// A clean run: real indicator triggers, no honesty flags.
const DIAG_CLEAN = {
  result_id: "res_x",
  artifact_type: "diagnostics",
  items: [
    {
      diagnostic_id: "btdiag_2",
      kind: "run_diagnostics",
      content: {
        engine_kind: "v1_bar_replay",
        entry_model: "builtin_indicator_native_trigger_v1",
        reproducibility_note:
          "Deterministic bar-replay over the pinned market revision; real bars, " +
          "protection stops and built-in indicator native triggers.",
        bars_processed: 800,
        indicator_blocks: 2,
        warnings: [],
      },
      created_at: "2026-01-02T12:00:00+00:00",
    },
  ],
  next_cursor: null,
};

// A multi-item composition run (v17): two executing strategies + one non-executing
// Trade Log, each carrying its OWN per-item metrics and equity curve.
const DIAG_COMPOSITION = {
  result_id: "res_x",
  artifact_type: "diagnostics",
  items: [
    {
      diagnostic_id: "btdiag_3",
      kind: "run_diagnostics",
      content: {
        engine_kind: "v1_bar_replay_composition",
        entry_model: "builtin_indicator_native_trigger_v1",
        reproducibility_note: "Deterministic per-strategy bar-replay composed in pin order.",
        warnings: ["portfolio_curve_sequential_not_unified_clock"],
        composition: {
          strategy_count: 2,
          participating_item_count: 3,
          capital_allocation: "independent",
          // v17 Contribution — server-computed at run time, rendered VERBATIM. The two
          // strategies close one trade each at different times → 2 aligned points,
          // perfectly anti-correlated zero-filled PnL series.
          contribution: {
            method: {
              correlation:
                "Pearson correlation of per-trade realized PnL aligned on the union of trade close times.",
              marginal:
                "The composition re-folded WITHOUT the item over the remaining items' reused outputs.",
            },
            correlation: {
              item_ids: ["item_a", "item_b"],
              aligned_point_count: 2,
              matrix: [
                ["1.0000", "-1.0000"],
                ["-1.0000", "1.0000"],
              ],
              average_pairwise: "-1.0000",
            },
            diversification: {
              sum_of_item_max_drawdowns: "81.60",
              portfolio_max_drawdown: "81.60",
              drawdown_reduction: "0.00",
              average_pairwise_correlation: "-1.0000",
            },
            marginal: [
              {
                item_id: "item_a",
                without_item: {
                  initial_capital: "10000.00",
                  final_equity: "9969.40",
                  net_profit: "-30.60",
                  net_profit_pct: "-0.3060",
                  max_drawdown: "30.60",
                  max_drawdown_pct: "0.3069",
                  romad: "-1.00",
                  win_rate: "0.0000",
                  profit_factor: null,
                  total_trades: 1,
                  total_stops: 1,
                  max_stop_streak: 1,
                  total_winning_trades: 0,
                },
                delta: {
                  net_profit: "-51.00",
                  net_profit_pct: "-0.1040",
                  max_drawdown: "51.00",
                  max_drawdown_pct: "0.1031",
                  romad: "-0.33",
                  win_rate: "0.0000",
                  profit_factor: null,
                  total_trades: 1,
                  total_stops: 1,
                  max_stop_streak: 1,
                  total_winning_trades: 0,
                },
              },
              {
                item_id: "item_b",
                without_item: {
                  initial_capital: "10000.00",
                  final_equity: "9949.00",
                  net_profit: "-51.00",
                  net_profit_pct: "-0.5100",
                  max_drawdown: "51.00",
                  max_drawdown_pct: "0.5126",
                  romad: "-0.99",
                  win_rate: "0.0000",
                  profit_factor: null,
                  total_trades: 1,
                  total_stops: 1,
                  max_stop_streak: 1,
                  total_winning_trades: 0,
                },
                delta: {
                  net_profit: "-30.60",
                  net_profit_pct: "0.1020",
                  max_drawdown: "30.60",
                  max_drawdown_pct: "-0.1026",
                  romad: "0.66",
                  win_rate: "0.0000",
                  profit_factor: null,
                  total_trades: 1,
                  total_stops: 1,
                  max_stop_streak: 1,
                  total_winning_trades: 0,
                },
              },
            ],
          },
          items: [
            {
              item_id: "item_a",
              item_kind: "strategy",
              root_id: "root_a",
              revision_id: "rev_a",
              executed: true,
              symbol: "BTCUSDT",
              timeframe: "1m",
              initial_capital: "10000.00",
              final_equity: "9949.00",
              net_profit: "-51.00",
              net_profit_pct: "-0.5100",
              max_drawdown: "51.00",
              max_drawdown_pct: "0.5100",
              total_trades: 1,
              winning_trades: 0,
              trade_seq_range: [1, 1],
              equity_curve: [
                { seq: 0, timestamp: "", equity: "10000.00", drawdown: "0.00" },
                { seq: 1, timestamp: "2024-01-21T00:00:00Z", equity: "9949.00", drawdown: "51.00" },
              ],
            },
            {
              item_id: "item_b",
              item_kind: "strategy",
              root_id: "root_b",
              revision_id: "rev_b",
              executed: true,
              symbol: "BTCUSDT",
              timeframe: "1m",
              initial_capital: "10000.00",
              final_equity: "9969.40",
              net_profit: "-30.60",
              net_profit_pct: "-0.3060",
              max_drawdown: "30.60",
              max_drawdown_pct: "0.3060",
              total_trades: 1,
              winning_trades: 0,
              trade_seq_range: [2, 2],
              equity_curve: [
                { seq: 0, timestamp: "", equity: "10000.00", drawdown: "0.00" },
                { seq: 1, timestamp: "2024-01-22T00:00:00Z", equity: "9969.40", drawdown: "30.60" },
              ],
            },
            {
              item_id: "item_tl",
              item_kind: "trade_log",
              root_id: "root_tl",
              revision_id: "rev_tl",
              executed: false,
              symbol: null,
              timeframe: null,
              initial_capital: null,
              final_equity: null,
              net_profit: null,
              net_profit_pct: null,
              max_drawdown: null,
              max_drawdown_pct: null,
              total_trades: 0,
              winning_trades: 0,
              trade_seq_range: null,
              equity_curve: [],
              note: "non_executing_participating_object",
            },
          ],
        },
      },
      created_at: "2026-01-03T12:00:00+00:00",
    },
  ],
  next_cursor: null,
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
      "GET /backtest-results/res_x/artifacts/diagnostics": DIAG_PAGE,
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
      "GET /backtest-results/res_x/artifacts/diagnostics": DIAG_PAGE,
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
      "GET /backtest-results/res_x/artifacts/diagnostics": DIAG_PAGE,
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
      "GET /backtest-results/res_x/artifacts/diagnostics": DIAG_PAGE,
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

  it("surfaces the honest L4 diagnostic warnings and reproducibility note", async () => {
    stubApi({
      "GET /backtest-results/res_x/artifacts/trade_ledger": EMPTY_PAGE,
      "GET /backtest-results/res_x/metrics": METRICS_VIEW,
      "GET /backtest-results/res_x/artifacts/diagnostics": DIAG_PAGE,
    });
    renderDetail();

    // The fallback-proxy warning is a human-readable line: the user is told the
    // numbers came from a proxy, not real indicator signals (L4 — never hidden).
    expect(
      await screen.findByText(/breakout entry proxy, not real indicator signals/),
    ).toBeInTheDocument();
    // The unsupported-sizing warning keeps the specific method name.
    expect(
      screen.getByText(/Position sizing method "formula_based" is not modelled/),
    ).toBeInTheDocument();
    expect(screen.getByText("2 diagnostic warnings")).toBeInTheDocument();
    // The reproducibility note states how the result was produced.
    expect(
      screen.getByText(/breakout entry proxy \(indicator layer still stubbed\)/),
    ).toBeInTheDocument();
  });

  it("shows the clean state when the run produced no diagnostic warnings", async () => {
    stubApi({
      "GET /backtest-results/res_x/artifacts/trade_ledger": EMPTY_PAGE,
      "GET /backtest-results/res_x/metrics": METRICS_VIEW,
      "GET /backtest-results/res_x/artifacts/diagnostics": DIAG_CLEAN,
    });
    renderDetail();

    expect(
      await screen.findByText("No diagnostic warnings — the run produced no honesty flags."),
    ).toBeInTheDocument();
    expect(screen.getByText(/built-in indicator native triggers/)).toBeInTheDocument();
  });

  it("renders the per-item breakdown with each strategy's isolated metrics + own equity curve", async () => {
    stubApi({
      "GET /backtest-results/res_x/artifacts/trade_ledger": EMPTY_PAGE,
      "GET /backtest-results/res_x/metrics": METRICS_VIEW,
      "GET /backtest-results/res_x/artifacts/diagnostics": DIAG_COMPOSITION,
    });
    renderDetail();

    expect(await screen.findByText("Per-item breakdown")).toBeInTheDocument();
    // The header states the executing/participating counts verbatim.
    expect(
      screen.getByText(/2 executing strategies · 3 participating items/),
    ).toBeInTheDocument();
    // Each executing strategy shows its OWN isolated figures (not the composite).
    // (item_a also appears in the Contribution correlation/marginal sections below.)
    expect(screen.getAllByText("item_a").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/-51\.00 \(-0\.5100%\)/)).toBeInTheDocument();
    expect(screen.getByText(/-30\.60 \(-0\.3060%\)/)).toBeInTheDocument();
    // The per-item equity curve is rendered — item_a's final equity appears in BOTH the
    // metrics block and the equity-curve table's last point.
    expect(screen.getAllByText("9949.00").length).toBeGreaterThanOrEqual(2);
    // The equity-curve seed point (own capital basis) is present.
    expect(screen.getAllByText("10000.00").length).toBeGreaterThanOrEqual(1);
    // The non-executing Trade Log is recorded but carries no curve.
    expect(screen.getByText("item_tl")).toBeInTheDocument();
    expect(
      screen.getByText(/Recorded for traceability but not simulated/),
    ).toBeInTheDocument();
  });

  it("omits the per-item breakdown for a lone-strategy result (no composition block)", async () => {
    stubApi({
      "GET /backtest-results/res_x/artifacts/trade_ledger": EMPTY_PAGE,
      "GET /backtest-results/res_x/metrics": METRICS_VIEW,
      "GET /backtest-results/res_x/artifacts/diagnostics": DIAG_CLEAN,
    });
    renderDetail();

    // The clean single-strategy diagnostics loaded, but no composition block → no section.
    expect(
      await screen.findByText("No diagnostic warnings — the run produced no honesty flags."),
    ).toBeInTheDocument();
    expect(screen.queryByText("Per-item breakdown")).not.toBeInTheDocument();
    // No composition → no Contribution section either.
    expect(screen.queryByText("Contribution")).not.toBeInTheDocument();
  });

  it("renders the Contribution section verbatim — correlation, diversification, marginal", async () => {
    stubApi({
      "GET /backtest-results/res_x/artifacts/trade_ledger": EMPTY_PAGE,
      "GET /backtest-results/res_x/metrics": METRICS_VIEW,
      "GET /backtest-results/res_x/artifacts/diagnostics": DIAG_COMPOSITION,
    });
    renderDetail();

    expect(await screen.findByText("Contribution")).toBeInTheDocument();
    // Correlation matrix cells are the SERVER strings verbatim: the diagonal "1.0000"
    // twice and the anti-correlated pair "-1.0000" twice — plus the two average rows.
    expect(screen.getAllByText("-1.0000").length).toBeGreaterThanOrEqual(4);
    expect(screen.getAllByText("1.0000").length).toBeGreaterThanOrEqual(2);
    // Diversification summary values verbatim (sum + portfolio + reduction).
    expect(screen.getAllByText("81.60").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("Drawdown reduction")).toBeInTheDocument();
    // Marginal: one card per executing strategy with the without/delta table; the
    // without-item ROMAD values render verbatim (a marginal-only field — the per-item
    // breakdown never shows ROMAD).
    expect(screen.getAllByText(/Delta \(this item's contribution\)/).length).toBe(2);
    expect(screen.getByText("-0.99")).toBeInTheDocument();
    expect(screen.getByText("-0.33")).toBeInTheDocument();
    // profit_factor is null on both sides → an em dash, never a fabricated number.
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(1);
    // Method notes render verbatim.
    expect(
      screen.getByText(/Pearson correlation of per-trade realized PnL aligned on the union/),
    ).toBeInTheDocument();
  });

  it("omits the Contribution section when the composition has no contribution block", async () => {
    // A 1-executing-strategy composition (e.g. one Strategy + one Trade Log) persists
    // the per-item breakdown but NO contribution — the server omits it; the UI must too.
    const diagNoContribution = JSON.parse(JSON.stringify(DIAG_COMPOSITION));
    delete diagNoContribution.items[0].content.composition.contribution;
    stubApi({
      "GET /backtest-results/res_x/artifacts/trade_ledger": EMPTY_PAGE,
      "GET /backtest-results/res_x/metrics": METRICS_VIEW,
      "GET /backtest-results/res_x/artifacts/diagnostics": diagNoContribution,
    });
    renderDetail();

    expect(await screen.findByText("Per-item breakdown")).toBeInTheDocument();
    expect(screen.queryByText("Contribution")).not.toBeInTheDocument();
  });
});
