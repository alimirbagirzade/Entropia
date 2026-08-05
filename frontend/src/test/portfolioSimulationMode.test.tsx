import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { MemoryRouter } from "react-router-dom";

import { ResultDetail } from "@/components/ResultDetail";
import { ResultsHistory } from "@/pages/ResultsHistory";
import type { BacktestResultDetail, PortfolioSimulationContext } from "@/lib/backtest";
import { stubApi } from "./helpers/apiStub";

const LEGACY_NOTE =
  "Produced by the pre-containment sequential approximation: each item was replayed " +
  "independently and the runs were folded in pin order, so this portfolio equity curve " +
  "is not a unified-clock valuation.";

function makeResult(
  portfolio_simulation: PortfolioSimulationContext | null,
): BacktestResultDetail {
  return {
    result_id: "res_mode",
    run_id: "btrun_mode",
    composition_id: "ws_1",
    composition_fingerprint: "fp_1",
    manifest_hash: "mh_mode",
    engine_version: "engine-x",
    summary: null,
    metrics: [],
    manifest: null,
    portfolio_simulation,
    manifest_excerpt: {
      result_id: "res_mode",
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
      artifact_availability: { counts: {}, any_available: false },
    },
    artifact_counts: {},
  };
}

function renderDetail(context: PortfolioSimulationContext | null) {
  stubApi({});
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <ResultDetail result={makeResult(context)} />
    </QueryClientProvider>,
  );
  return screen.getByLabelText("Portfolio simulation mode");
}

afterEach(cleanup);

describe("Result detail portfolio simulation mode", () => {
  it("names the legacy sequential era and says it is not comparable", () => {
    const badge = renderDetail({
      mode: "legacy_sequential",
      note: LEGACY_NOTE,
      comparable_with_unified_clock: false,
    });
    expect(badge).toHaveAttribute("data-portfolio-mode", "legacy_sequential");
    expect(badge.textContent).toContain("Legacy sequential");
    expect(badge.textContent).toContain("not comparable with a unified-clock result");
    expect(badge.textContent).toContain("folded in pin order");
  });

  it("names a unified-clock result and does not warn about comparability", () => {
    const badge = renderDetail({
      mode: "unified_clock",
      note: "Produced by the unified-clock co-simulation.",
      comparable_with_unified_clock: true,
    });
    expect(badge).toHaveAttribute("data-portfolio-mode", "unified_clock");
    expect(badge.textContent).toContain("Unified clock");
    expect(badge.textContent).not.toContain("not comparable");
  });

  it("says single item when there is no cross-item simulation to characterise", () => {
    const badge = renderDetail({
      mode: "single_item",
      note: "A single item was executed.",
      comparable_with_unified_clock: false,
    });
    expect(badge).toHaveAttribute("data-portfolio-mode", "single_item");
    expect(badge.textContent).toContain("Single item");
  });

  it("renders Unknown rather than guessing an era when the server states none", () => {
    // A Result read back through an older projection carries no block. The component
    // must NOT infer a mode — that would re-interpret an immutable Result client-side.
    const badge = renderDetail(null);
    expect(badge).toHaveAttribute("data-portfolio-mode", "unknown");
    expect(badge.textContent).toContain("Unknown");
    expect(badge.textContent).not.toContain("Legacy sequential");
    expect(badge.textContent).not.toContain("not comparable");
  });

  it("shows the server note verbatim and derives nothing from live state", () => {
    const badge = renderDetail({
      mode: "unknown",
      note: "This Result does not retain the diagnostics needed to say which co-simulation produced it.",
      comparable_with_unified_clock: false,
    });
    expect(badge.textContent).toContain("does not retain the diagnostics");
  });
});

// --------------------------------------------------------------------------- //
// Results History index
// --------------------------------------------------------------------------- //
function historyRow(result_id: string, portfolio_simulation: PortfolioSimulationContext | null) {
  return {
    result_id,
    display_title: `Backtest Result ${result_id}`,
    composition_context: { composition_id: "ws_1", composition_fingerprint: "fp_1" },
    key_metrics: { net_profit: null, romad: null, max_drawdown: null, win_rate: null },
    market_data_revision_summary: { symbol: "BTCUSDT" },
    timeframe: "1h",
    backtest_range: { start: "2026-01-01", end: "2026-03-01" },
    manifest_hash: `mh_${result_id}`,
    engine_version: "engine-x",
    completed_at_utc: "2026-03-01T00:00:00Z",
    materialization_status: "complete",
    portfolio_simulation,
    allowed_actions: { view: true, compare: false, export: true, soft_delete: false },
  };
}

describe("Results History portfolio simulation mode", () => {
  it("labels each row from its own server-derived mode", async () => {
    stubApi({
      "GET /backtest-results": {
        items: [
          historyRow("res_legacy", {
            mode: "legacy_sequential",
            note: LEGACY_NOTE,
            comparable_with_unified_clock: false,
          }),
          historyRow("res_unknown", null),
        ],
        next_cursor: null,
        query_fingerprint: "newest_current",
        sort: "newest_current",
      },
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <ResultsHistory />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    const badges = await screen.findAllByLabelText("Portfolio simulation mode");
    expect(badges).toHaveLength(2);
    // Two rows from different eras must not be presented as like-for-like.
    expect(badges[0]).toHaveAttribute("data-portfolio-mode", "legacy_sequential");
    expect(badges[0].textContent).toContain("Legacy sequential");
    // A row the server could not classify says Unknown — it is not assumed legacy.
    expect(badges[1]).toHaveAttribute("data-portfolio-mode", "unknown");
    expect(badges[1].textContent).toContain("Unknown");
  });
});
