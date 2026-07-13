import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { StrategyConfigForm } from "@/components/StrategyConfigForm";
import {
  STRATEGY_INFO_PANELS,
  extractFlatSections,
  mergeFlatSections,
} from "@/lib/strategyForm";

afterEach(() => cleanup());

describe("extractFlatSections", () => {
  it("falls back to config.py defaults for an empty payload", () => {
    const form = extractFlatSections({});
    expect(form.data.order_type).toBe("market_order");
    expect(form.data.slippage_mode).toBe("percentage_slippage");
    expect(form.data.tick_policy).toBe("inherit");
    expect(form.sizing.method).toBe("base_position_size");
    expect(form.sizing.leverage_mode).toBe("isolated");
    expect(form.conflict.overlapping_signal_policy).toBe("queue_sequential");
    expect(form.conflict.exit_on_opposite_signal).toBe(true);
    // Required-no-default enums stay blank — the server, not the form, decides.
    expect(form.data.entry_timing).toBe("");
    expect(form.data.exit_timing).toBe("");
    // Stops default OFF — the form never fabricates an invisible stop (§5.5).
    expect(form.protection.percentage_enabled).toBe(false);
  });

  it("reads present scalar values (numbers rendered as strings)", () => {
    const form = extractFlatSections({
      data: {
        instrument_id: "BTCUSDT",
        initial_capital: 10000,
        order_config: { type: "limit_order", limit: { price_rule: "best_bid_ask" } },
        costs: { slippage_mode: "historical_slippage_if_available" },
      },
      protection_stop_logic: { percentage_stop: { enabled: true, loss_percentage: "1.5" } },
      position_sizing: {
        method: "risk_based_sizing",
        risk_based: { risk_percentage_per_trade: "2", stop_loss_point: "5" },
      },
    });
    expect(form.data.instrument_id).toBe("BTCUSDT");
    expect(form.data.initial_capital).toBe("10000");
    expect(form.data.order_type).toBe("limit_order");
    expect(form.data.limit_price_rule).toBe("best_bid_ask");
    expect(form.data.slippage_mode).toBe("historical_slippage_if_available");
    expect(form.protection.percentage_enabled).toBe(true);
    expect(form.protection.percentage_loss).toBe("1.5");
    expect(form.sizing.method).toBe("risk_based_sizing");
    expect(form.sizing.risk_percentage_per_trade).toBe("2");
  });
});

describe("mergeFlatSections", () => {
  it("overlays the covered sections and preserves every uncovered key", () => {
    const payload = {
      strategy_root_id: "root_x",
      display_name: "Momentum A",
      rationale_family_id: "fam_1",
      position_entry_logic: { signal_block: { rule: "required_indicator_blocks_only" } },
      scaling_logic: { enabled: false },
    };
    const merged = mergeFlatSections(payload, extractFlatSections(payload));
    // Uncovered keys survive verbatim.
    expect(merged.strategy_root_id).toBe("root_x");
    expect(merged.display_name).toBe("Momentum A");
    expect(merged.position_entry_logic).toEqual(payload.position_entry_logic);
    expect(merged.scaling_logic).toEqual(payload.scaling_logic);
    // Covered sections are written.
    expect(merged.data).toBeDefined();
    expect(merged.protection_stop_logic).toBeDefined();
    expect(merged.position_sizing).toBeDefined();
    expect(merged.conflict_position_handling).toBeDefined();
  });

  it("emits the limit subtree only for limit / stop-limit order types", () => {
    const market = extractFlatSections({ data: { order_config: { type: "market_order" } } });
    const marketMerged = mergeFlatSections({}, market) as Record<string, Record<string, unknown>>;
    expect((marketMerged.data.order_config as Record<string, unknown>).limit).toBeUndefined();

    const limit = extractFlatSections({
      data: { order_config: { type: "limit_order", limit: { price_rule: "entry_signal_price" } } },
    });
    const limitMerged = mergeFlatSections({}, limit) as Record<string, Record<string, unknown>>;
    const order = limitMerged.data.order_config as Record<string, unknown>;
    expect((order.limit as Record<string, unknown>).price_rule).toBe("entry_signal_price");
  });

  it("sends decimals as strings and omits blank optionals", () => {
    const form = extractFlatSections({});
    form.data.initial_capital = "10000.50";
    form.data.commission = ""; // blank → omitted
    const merged = mergeFlatSections({}, form) as Record<string, Record<string, unknown>>;
    expect(merged.data.initial_capital).toBe("10000.50");
    expect("commission" in (merged.data.costs as Record<string, unknown>)).toBe(false);
  });

  it("serializes only the active sizing branch and keeps formula params", () => {
    const base = extractFlatSections({});
    base.sizing.method = "base_position_size";
    base.sizing.base_position_size = "1000";
    const baseMerged = mergeFlatSections({}, base) as Record<string, Record<string, unknown>>;
    expect(baseMerged.position_sizing.base_position_size).toBe("1000");
    expect(baseMerged.position_sizing.risk_based).toBeUndefined();

    const payload = {
      position_sizing: { formula_based: { formula_params: { W: 0.55, R: 2 } } },
    };
    const formula = extractFlatSections(payload);
    formula.sizing.method = "formula_based_sizing";
    formula.sizing.formula_type = "kelly_criterion";
    const merged = mergeFlatSections(payload, formula) as Record<string, Record<string, unknown>>;
    const fb = merged.position_sizing.formula_based as Record<string, unknown>;
    expect(fb.formula_type).toBe("kelly_criterion");
    expect(fb.formula_params).toEqual({ W: 0.55, R: 2 });
  });

  it("keeps only enabled stops semantically representable (server filters disabled)", () => {
    const form = extractFlatSections({});
    form.protection.percentage_enabled = true;
    form.protection.percentage_loss = "1.0";
    const merged = mergeFlatSections({}, form) as Record<string, Record<string, unknown>>;
    const stops = merged.protection_stop_logic as Record<string, Record<string, unknown>>;
    expect(stops.percentage_stop.enabled).toBe(true);
    expect(stops.trailing_stop.enabled).toBe(false);
  });
});

describe("STRATEGY_INFO_PANELS", () => {
  it("carries verbatim ⓘ panel text for the flat-section fields", () => {
    expect(STRATEGY_INFO_PANELS.orderType.title).toBe("Order Type");
    expect(STRATEGY_INFO_PANELS.orderType.body).toContain("Market Order");
    expect(STRATEGY_INFO_PANELS.percentageStop.title).toBe("Percentage Stop");
    expect(STRATEGY_INFO_PANELS.leverageMode.body).toContain("Isolated");
  });
});

describe("StrategyConfigForm", () => {
  it("renders the four flat sections", () => {
    render(<StrategyConfigForm payload={{}} pending={false} onApply={() => {}} />);
    expect(screen.getByText("Data & Execution")).toBeTruthy();
    expect(screen.getByText("Position Sizing")).toBeTruthy();
    expect(screen.getByLabelText(/Market \(instrument\)/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Apply structured changes" })).toBeTruthy();
  });

  it("reveals the Limit Order Details subtree only for a limit order type", () => {
    render(<StrategyConfigForm payload={{}} pending={false} onApply={() => {}} />);
    expect(screen.queryByLabelText(/Limit price rule/)).toBeNull();
    fireEvent.change(screen.getByLabelText(/Order type/), {
      target: { value: "limit_order" },
    });
    expect(screen.getByLabelText(/Limit price rule/)).toBeTruthy();
  });

  it("swaps sizing sub-fields when the method changes", () => {
    render(<StrategyConfigForm payload={{}} pending={false} onApply={() => {}} />);
    expect(screen.getByLabelText(/Base position size/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText(/Sizing method/), {
      target: { value: "risk_based_sizing" },
    });
    expect(screen.getByLabelText(/Risk % per trade/)).toBeTruthy();
    expect(screen.queryByLabelText(/Base position size/)).toBeNull();
  });

  it("Apply merges the edited sections while preserving the graph payload", () => {
    const onApply = vi.fn();
    const payload = { strategy_root_id: "root_9", position_entry_logic: { signal_block: {} } };
    render(<StrategyConfigForm payload={payload} pending={false} onApply={onApply} />);

    fireEvent.change(screen.getByLabelText(/Market \(instrument\)/), {
      target: { value: "ETHUSDT" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Apply structured changes" }));

    expect(onApply).toHaveBeenCalledTimes(1);
    const sent = onApply.mock.calls[0][0] as Record<string, Record<string, unknown>>;
    expect(sent.strategy_root_id).toBe("root_9");
    expect(sent.position_entry_logic).toEqual(payload.position_entry_logic);
    expect(sent.data.instrument_id).toBe("ETHUSDT");
    expect(sent.conflict_position_handling).toBeDefined();
  });
});
