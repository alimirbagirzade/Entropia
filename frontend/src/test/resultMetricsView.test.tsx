import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { ResultDetail } from "@/components/ResultDetail";
import type { BacktestResultDetail } from "@/lib/backtest";
import { stubApi } from "./helpers/apiStub";

// Raw persisted rows — the pre-rebind projection the component falls back to.
const RESULT: BacktestResultDetail = {
  result_id: "res_9",
  run_id: "btrun_9",
  composition_id: "ws_1",
  composition_fingerprint: "fp_1",
  manifest_hash: "mh_9",
  engine_version: "engine-x",
  summary: null,
  metrics: [
    {
      key: "romad",
      label: "ROMAD",
      unit: "ratio",
      value_format: "decimal2",
      value: "1.5",
      availability: "computed",
    },
  ],
  manifest: null,
  artifact_counts: {},
};

// Profile-hydrated view (doc 17 §9.1): profile display order, including a
// selected-but-absent metric that arrives as not_computed (null value, L4).
const HYDRATED = {
  result_id: "res_9",
  profile: {
    profile_id: "mp_1",
    scope: "user",
    is_personal: true,
    is_locked: true,
    registry_version: "v1",
  },
  metrics: [
    {
      key: "sharpe_ratio",
      label: "Sharpe Ratio",
      unit: "ratio",
      value_format: "decimal2",
      value: "1.1",
      availability: "computed",
    },
    {
      key: "expectancy",
      label: "Expectancy",
      unit: "ratio",
      value_format: "decimal2",
      value: null,
      availability: "not_computed",
    },
  ],
};

// The Trade List section always drills the trade_ledger artifact; these tests
// exercise the Metrics section, so an empty page keeps that call satisfied.
const TRADE_LEDGER_EMPTY = {
  result_id: "res_9",
  artifact_type: "trade_ledger",
  items: [],
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

describe("ResultDetail profile-hydrated metrics", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("rebinds the Metrics section to the resolved-profile projection", async () => {
    stubApi({
      "GET /backtest-results/res_9/artifacts/trade_ledger": TRADE_LEDGER_EMPTY,
      "GET /backtest-results/res_9/metrics": HYDRATED,
    });
    renderDetail();

    expect(
      await screen.findByText(/Profile view · personal profile · locked · registry v1/),
    ).toBeInTheDocument();
    // Profile-ordered cards replace the raw persisted rows...
    expect(screen.getByText("Sharpe Ratio")).toBeInTheDocument();
    expect(screen.queryByText("ROMAD")).not.toBeInTheDocument();
    // ...and a selected-but-absent metric shows its availability, never 0 (L4).
    expect(screen.getByText("Not computed")).toBeInTheDocument();
    expect(screen.getByText("1.10")).toBeInTheDocument();
  });

  it("labels the System Default profile without a lock marker", async () => {
    stubApi({
      "GET /backtest-results/res_9/artifacts/trade_ledger": TRADE_LEDGER_EMPTY,
      "GET /backtest-results/res_9/metrics": {
        ...HYDRATED,
        profile: {
          profile_id: "system_default",
          scope: "system_default",
          is_personal: false,
          is_locked: false,
          registry_version: "v1",
        },
      },
    });
    renderDetail();

    const caption = await screen.findByText(/Profile view · system default · registry v1/);
    expect(caption.textContent).not.toContain("locked");
  });

  it("falls back to the persisted rows when the profile view is unavailable", async () => {
    stubApi({
      "GET /backtest-results/res_9/artifacts/trade_ledger": TRADE_LEDGER_EMPTY,
      "GET /backtest-results/res_9/metrics": () => {
        throw new Error("boom");
      },
    });
    renderDetail();

    expect(
      await screen.findByText(/Profile view unavailable — showing all persisted metrics/),
    ).toBeInTheDocument();
    expect(screen.getByText("ROMAD")).toBeInTheDocument();
    expect(screen.getByText("1.50")).toBeInTheDocument();
  });
});
