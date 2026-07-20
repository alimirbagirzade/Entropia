import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import {
  LogicBasedStopCard,
  PositionEntryCard,
  PositionExitCard,
  RestrictionsCard,
  ScalingCard,
} from "@/components/StrategyGraphForm";
import {
  extractGraphSections,
  firstInvalidFilterConfig,
  mergeGraphSections,
  type StrategyGraphForm as GraphState,
} from "@/lib/strategyGraph";
import { stubApi } from "./helpers/apiStub";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

// A representative StrategyConfig payload with advanced per-block fields that
// the structured form does NOT surface — they must survive a round-trip.
function fullPayload(): Record<string, unknown> {
  return {
    strategy_root_id: "strat_1",
    position_entry_logic: {
      direction_mode: "long",
      signal_block: { rule: "required_plus_min_supporting", min_supporting_count: 2 },
      indicator_blocks: [
        {
          block_id: "b1",
          display_order: 0,
          enabled: true,
          package_ref: {
            package_root_id: "pkg_ind",
            package_revision_id: "rev_ind",
            package_content_hash: "hash_ind",
          },
          trigger_source: "indicator_native_trigger_plus_condition",
          direction: "long",
          timeframe: "15m",
          validity: "3_candles",
          requirement: "required",
          condition_block_rule: "required_condition_blocks_only",
          parameter_overrides: { length: 14 },
          condition_blocks: [
            {
              condition_block_id: "c1",
              display_order: 0,
              enabled: true,
              package_ref: {
                package_root_id: "pkg_cond",
                package_revision_id: "rev_cond",
                package_content_hash: "hash_cond",
              },
              requirement: "required",
              validity: "2_candles",
              reference_package_ref: {
                package_root_id: "pkg_ref",
                package_revision_id: "rev_ref",
                package_content_hash: "hash_ref",
              },
              reference_timeframe: "1h",
            },
          ],
        },
      ],
    },
    position_exit_logic: {
      applies_to_direction: "long",
      close_percentage: "100",
      partial_aftermath: "move_stop_to_entry",
    },
    position_sizing: { method: "base_position_size", base_position_size: "10" },
    scaling_logic: {
      enabled: true,
      timeframe: "15m",
      method: "price_distance_scaling",
      price_scaling: { retracement_distance: "1.0", layers: 3 },
      add_size: "percent_of_initial",
      add_size_value: "50",
      scaling_limits: { max_scaling_layers: 4 },
    },
    restrictions_filters: {
      rule: "any",
      filters: [
        {
          filter_id: "f1",
          filter_type: "volatility_filter",
          enabled: true,
          config: { condition: "too_high" },
        },
      ],
    },
    untouched_future_key: "preserved",
  };
}

describe("strategyGraph extract/merge", () => {
  it("extracts entry blocks, signal block and direction mode", () => {
    const form = extractGraphSections(fullPayload());
    expect(form.entry.direction_mode).toBe("long");
    expect(form.entry.signal_rule).toBe("required_plus_min_supporting");
    expect(form.entry.signal_min_supporting_count).toBe("2");
    expect(form.entry.blocks).toHaveLength(1);
    expect(form.entry.blocks[0].package_ref?.package_root_id).toBe("pkg_ind");
    expect(form.entry.blocks[0].conditions).toHaveLength(1);
    expect(form.entry.blocks[0].conditions[0].validity).toBe("2_candles");
  });

  it("seeds one blank entry block when none exist", () => {
    const form = extractGraphSections({});
    expect(form.entry.blocks).toHaveLength(1);
    expect(form.entry.blocks[0].package_ref).toBeNull();
    expect(form.exit.active).toBe(false);
  });

  it("round-trips advanced per-block fields and uncovered keys untouched", () => {
    const payload = fullPayload();
    const merged = mergeGraphSections(payload, extractGraphSections(payload));

    // Uncovered top-level keys preserved verbatim (scaling_logic /
    // restrictions_filters are now COVERED — asserted in their own suite).
    expect(merged.untouched_future_key).toBe("preserved");
    expect(merged.position_sizing).toEqual(payload.position_sizing);

    const entry = merged.position_entry_logic as Record<string, unknown>;
    const blocks = entry.indicator_blocks as Record<string, unknown>[];
    // parameter_overrides is typed now (R2-05a): the canonical key survives a
    // round-trip normalized to its string form (the engine parses digit strings).
    expect(blocks[0].parameter_overrides).toEqual({ length: "14" });
    const conditions = blocks[0].condition_blocks as Record<string, unknown>[];
    // reference chain fields must survive.
    expect(conditions[0].reference_package_ref).toEqual({
      package_root_id: "pkg_ref",
      package_revision_id: "rev_ref",
      package_content_hash: "hash_ref",
    });
    expect(conditions[0].reference_timeframe).toBe("1h");
    // Signal block min count survives for the min-supporting rule.
    expect(entry.signal_block).toEqual({
      rule: "required_plus_min_supporting",
      min_supporting_count: 2,
    });
  });

  it("omits the signal min count when the rule is not min-supporting", () => {
    const form = extractGraphSections(fullPayload());
    const changed: GraphState = {
      ...form,
      entry: { ...form.entry, signal_rule: "required_indicator_blocks_only" },
    };
    const merged = mergeGraphSections(fullPayload(), changed);
    const entry = merged.position_entry_logic as Record<string, unknown>;
    expect(entry.signal_block).toEqual({ rule: "required_indicator_blocks_only" });
  });

  it("keeps the exit inactive placeholder out of the compiled node", () => {
    const merged = mergeGraphSections(fullPayload(), extractGraphSections(fullPayload()));
    const exit = merged.position_exit_logic as Record<string, unknown>;
    expect(exit).not.toHaveProperty("indicator_blocks");
    expect(exit).not.toHaveProperty("signal_block");
    expect(exit.applies_to_direction).toBe("long");
    expect(exit.close_percentage).toBe("100");
  });

  it("emits exit blocks + signal block once exit is activated", () => {
    const form = extractGraphSections(fullPayload());
    const activeExit: GraphState = {
      ...form,
      exit: {
        ...form.exit,
        active: true,
        signal_rule: "required_indicator_blocks_only",
        blocks: form.entry.blocks,
      },
    };
    const merged = mergeGraphSections(fullPayload(), activeExit);
    const exit = merged.position_exit_logic as Record<string, unknown>;
    expect(exit.indicator_blocks).toHaveLength(1);
    expect(exit.signal_block).toEqual({ rule: "required_indicator_blocks_only" });
  });
});

describe("strategyGraph scaling + restrictions", () => {
  it("round-trips price-distance scaling", () => {
    const p = fullPayload();
    const form = extractGraphSections(p);
    expect(form.scaling.enabled).toBe(true);
    expect(form.scaling.method).toBe("price_distance_scaling");
    expect(form.scaling.price.retracement_distance).toBe("1.0");
    const scaling = mergeGraphSections(p, form).scaling_logic as Record<string, unknown>;
    expect(scaling.enabled).toBe(true);
    expect(scaling.price_scaling).toEqual({ retracement_distance: "1.0", layers: 3 });
    expect(scaling).not.toHaveProperty("logic_scaling");
    expect(scaling.scaling_limits).toEqual({ max_scaling_layers: 4 });
  });

  it("switches scaling to logic-based, emitting indicator blocks", () => {
    const p = fullPayload();
    const form = extractGraphSections(p);
    const changed: GraphState = {
      ...form,
      scaling: { ...form.scaling, method: "logic_based_scaling", logic_blocks: form.entry.blocks },
    };
    const scaling = mergeGraphSections(p, changed).scaling_logic as Record<string, unknown>;
    expect(scaling).not.toHaveProperty("price_scaling");
    expect((scaling.logic_scaling as Record<string, unknown>).indicator_blocks).toHaveLength(1);
  });

  it("extracts default stop-combination modes", () => {
    const form = extractGraphSections(fullPayload());
    expect(form.stop.trigger_requirement).toBe("any_active");
    expect(form.stop.conflict_resolution).toBe("most_conservative");
    expect(form.stop.logic_blocks).toHaveLength(0);
  });

  it("serializes logic-stop blocks + all_active mode, preserving price stops", () => {
    const p = { ...fullPayload(), protection_stop_logic: { percentage_stop: { enabled: true, loss_percentage: "1.0" } } };
    const form = extractGraphSections(p);
    const changed: GraphState = {
      ...form,
      stop: {
        ...form.stop,
        trigger_requirement: "all_active",
        conflict_resolution: "priority_order",
        logic_blocks: form.entry.blocks,
      },
    };
    const stop = mergeGraphSections(p, changed).protection_stop_logic as Record<string, unknown>;
    expect(stop.stop_trigger_requirement).toBe("all_active");
    expect(stop.stop_conflict_resolution).toBe("priority_order");
    expect(stop.logic_blocks as unknown[]).toHaveLength(1);
    // the percentage price stop edited elsewhere survives the graph-form overlay.
    expect(stop.percentage_stop).toEqual({ enabled: true, loss_percentage: "1.0" });
  });

  it("omits logic_blocks when the stop section has none", () => {
    const p = fullPayload();
    const merged = mergeGraphSections(p, extractGraphSections(p)).protection_stop_logic as Record<
      string,
      unknown
    >;
    expect(merged).not.toHaveProperty("logic_blocks");
  });

  it("round-trips restriction filters preserving config", () => {
    const p = fullPayload();
    const form = extractGraphSections(p);
    expect(form.restrictions.rule).toBe("any");
    expect(form.restrictions.filters[0].filter_type).toBe("volatility_filter");
    const restrictions = mergeGraphSections(p, form).restrictions_filters as Record<string, unknown>;
    const filters = restrictions.filters as Record<string, unknown>[];
    expect(filters[0].config).toEqual({ condition: "too_high" });
    expect(filters[0].enabled).toBe(true);
  });

  it("flags an out-of-order blackout range, passes a valid typed config", () => {
    const form = extractGraphSections(fullPayload());
    expect(firstInvalidFilterConfig(form)).toBeNull();
    const bad: GraphState = {
      ...form,
      restrictions: {
        ...form.restrictions,
        filters: [
          {
            ...form.restrictions.filters[0],
            filter_type: "date_blackout_filter",
            date_ranges: [{ key: "r1", start: "2024-02-01", end: "2024-01-01" }],
          },
        ],
      },
    };
    expect(firstInvalidFilterConfig(bad)).toMatch(/start ≤ end/);
  });

  it("serializes typed filter configs to the engine's canonical keys", () => {
    const p = fullPayload();
    const form = extractGraphSections(p);
    const changed: GraphState = {
      ...form,
      restrictions: {
        ...form.restrictions,
        filters: [
          {
            ...form.restrictions.filters[0],
            filter_type: "date_blackout_filter",
            date_ranges: [{ key: "r1", start: "2024-01-01", end: "2024-01-05" }],
          },
          {
            key: "f2",
            filter_id: "f2",
            filter_type: "max_daily_loss_filter",
            enabled: true,
            date_ranges: [],
            limit_percent: "3",
            max_losses: "",
            raw: {},
          },
          {
            key: "f3",
            filter_id: "f3",
            filter_type: "consecutive_loss_filter",
            enabled: true,
            date_ranges: [],
            limit_percent: "",
            max_losses: "5",
            raw: {},
          },
        ],
      },
    };
    const restrictions = mergeGraphSections(p, changed).restrictions_filters as Record<
      string,
      unknown
    >;
    const filters = restrictions.filters as Record<string, unknown>[];
    expect(filters[0].config).toEqual({
      condition: "too_high",
      date_ranges: [{ start: "2024-01-01", end: "2024-01-05" }],
    });
    expect(filters[1].config).toEqual({ limit_percent: "3" });
    expect(filters[2].config).toEqual({ max_losses: 5 });
  });

  it("round-trips typed block parameter overrides via canonical keys", () => {
    const p = fullPayload();
    const form = extractGraphSections(p);
    expect(form.entry.blocks[0].override_length).toBe("14");
    const changed: GraphState = {
      ...form,
      entry: {
        ...form.entry,
        blocks: [{ ...form.entry.blocks[0], override_length: "21", override_rsi_lower: "25" }],
      },
    };
    const entry = mergeGraphSections(p, changed).position_entry_logic as Record<string, unknown>;
    const blocks = entry.indicator_blocks as Record<string, unknown>[];
    expect(blocks[0].parameter_overrides).toEqual({ length: "21", rsi_lower: "25" });
  });

  it("extracts + re-emits the condition reference chain via typed fields", () => {
    const p = fullPayload();
    const form = extractGraphSections(p);
    const cond = form.entry.blocks[0].conditions[0];
    expect(cond.reference_package_ref?.package_root_id).toBe("pkg_ref");
    expect(cond.reference_timeframe).toBe("1h");
    const changed: GraphState = {
      ...form,
      entry: {
        ...form.entry,
        blocks: [
          {
            ...form.entry.blocks[0],
            conditions: [
              {
                ...cond,
                reference_length: "50",
                additional_references: [
                  {
                    key: "leg1",
                    package_ref: {
                      package_root_id: "pkg_leg",
                      package_revision_id: "rev_leg",
                      package_content_hash: "hash_leg",
                    },
                    timeframe: "4h",
                    reference_length: "200",
                    raw: {},
                  },
                ],
              },
            ],
          },
        ],
      },
    };
    const entry = mergeGraphSections(p, changed).position_entry_logic as Record<string, unknown>;
    const blocks = entry.indicator_blocks as Record<string, unknown>[];
    const conditions = blocks[0].condition_blocks as Record<string, unknown>[];
    expect(conditions[0].parameter_overrides).toEqual({ reference_length: "50" });
    expect(conditions[0].additional_reference_package_refs).toEqual([
      {
        package_ref: {
          package_root_id: "pkg_leg",
          package_revision_id: "rev_leg",
          package_content_hash: "hash_leg",
        },
        timeframe: "4h",
        parameter_overrides: { reference_length: "200" },
      },
    ]);
  });

  it("writes a constant-threshold condition and drops chain fields when unpinned", () => {
    const p = fullPayload();
    const form = extractGraphSections(p);
    const cond = form.entry.blocks[0].conditions[0];
    const changed: GraphState = {
      ...form,
      entry: {
        ...form.entry,
        blocks: [
          {
            ...form.entry.blocks[0],
            conditions: [
              {
                ...cond,
                reference_package_ref: null,
                source: "indicator_output",
                threshold: "30",
              },
            ],
          },
        ],
      },
    };
    const entry = mergeGraphSections(p, changed).position_entry_logic as Record<string, unknown>;
    const blocks = entry.indicator_blocks as Record<string, unknown>[];
    const conditions = blocks[0].condition_blocks as Record<string, unknown>[];
    expect(conditions[0]).not.toHaveProperty("reference_package_ref");
    expect(conditions[0]).not.toHaveProperty("reference_timeframe");
    expect(conditions[0].parameter_overrides).toEqual({
      source: "indicator_output",
      threshold: "30",
    });
  });

  it("emits stop_priority_order only for priority-based resolutions", () => {
    const p = fullPayload();
    const form = extractGraphSections(p);
    const withOrder: GraphState = {
      ...form,
      stop: {
        ...form.stop,
        conflict_resolution: "priority_order",
        priority_order: ["percentage", "trailing"],
      },
    };
    const stop = mergeGraphSections(p, withOrder).protection_stop_logic as Record<string, unknown>;
    expect(stop.stop_priority_order).toEqual(["percentage", "trailing"]);

    const conservative: GraphState = {
      ...form,
      stop: {
        ...form.stop,
        conflict_resolution: "most_conservative",
        priority_order: ["percentage"],
      },
    };
    const stop2 = mergeGraphSections(p, conservative).protection_stop_logic as Record<
      string,
      unknown
    >;
    expect(stop2).not.toHaveProperty("stop_priority_order");
  });
});

// ---------------------------------------------------------------------------
// Component tests
// ---------------------------------------------------------------------------

const LIBRARY_PAGE = {
  data: [
    {
      entity_id: "pkg_lib",
      package_kind: "indicator",
      name: "Reversal Sensor",
      current_revision_id: "rev_lib",
      revision_no: 4,
      lifecycle_state: "active",
      validation_state: "passed",
      approval_state: "approved",
      visibility_scope: "published",
      content_hash: "hash_lib",
    },
  ],
  meta: { cursor: null, has_more: false },
};

function renderComponent(
  Component: (props: {
    payload: Record<string, unknown>;
    pending: boolean;
    onApply: (payload: Record<string, unknown>) => void;
  }) => JSX.Element,
  payload: Record<string, unknown>,
  onApply = vi.fn(),
) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <Component payload={payload} pending={false} onApply={onApply} />
    </QueryClientProvider>,
  );
  return onApply;
}

describe("PositionEntryCard / PositionExitCard / LogicBasedStopCard", () => {
  it("render as independently numbered sections", () => {
    stubApi({ "GET /library": LIBRARY_PAGE });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <PositionEntryCard payload={{}} pending={false} onApply={() => {}} />
        <PositionExitCard payload={{}} pending={false} onApply={() => {}} />
        <LogicBasedStopCard payload={{}} pending={false} onApply={() => {}} />
      </QueryClientProvider>,
    );
    // Anchor at the start of the accessible name — the Scaling Logic ⓘ body
    // references "Position Exit Logic", so an unanchored match is ambiguous.
    expect(screen.getByRole("heading", { name: /^3\. Position Entry Logic/ })).toBeTruthy();
    expect(screen.getByRole("heading", { name: /^4\. Position Exit Logic/ })).toBeTruthy();
    expect(screen.getByRole("heading", { name: /^Logic-Based Stop Block/ })).toBeTruthy();
    // F-08: the logic-based stop is now a real composer with a Stop mode selector.
    expect(screen.getByLabelText("Stop mode")).toBeTruthy();
    expect(screen.getByLabelText("Same-bar resolution")).toBeTruthy();
    expect(screen.queryByText(/does not yet implement/i)).toBeNull();
  });

  it("pins an entry indicator package via the picker browsing the Library catalog", async () => {
    stubApi({ "GET /library": LIBRARY_PAGE });
    renderComponent(PositionEntryCard, {});
    fireEvent.click(screen.getByRole("button", { name: "Choose indicator" }));
    const row = await screen.findByRole("button", { name: /Reversal Sensor/ });
    fireEvent.click(row);
    // The pinned ref renders the chosen row's root id.
    await waitFor(() => expect(screen.getByText("pkg_lib")).toBeTruthy());
  });

  it("Apply on the Entry card merges the payload preserving uncovered sections", () => {
    stubApi({ "GET /library": LIBRARY_PAGE });
    const onApply = renderComponent(PositionEntryCard, fullPayload());
    fireEvent.click(screen.getByRole("button", { name: "Apply Position Entry changes" }));
    expect(onApply).toHaveBeenCalledTimes(1);
    const sent = onApply.mock.calls[0][0] as Record<string, unknown>;
    expect(sent.untouched_future_key).toBe("preserved");
    const entry = sent.position_entry_logic as Record<string, unknown>;
    const blocks = entry.indicator_blocks as Record<string, unknown>[];
    expect(blocks[0].parameter_overrides).toEqual({ length: "14" });
  });
});

describe("ScalingCard / RestrictionsCard", () => {
  it("render as independently numbered sections", () => {
    stubApi({ "GET /library": LIBRARY_PAGE });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <ScalingCard payload={fullPayload()} pending={false} onApply={() => {}} />
        <RestrictionsCard payload={fullPayload()} pending={false} onApply={() => {}} />
      </QueryClientProvider>,
    );
    expect(screen.getByRole("heading", { name: /^7\. Scaling Logic/ })).toBeTruthy();
    expect(screen.getByRole("heading", { name: /^8\. Restrictions \/ Filters/ })).toBeTruthy();
  });

  it("blocks apply when a typed blackout range is out of order", () => {
    stubApi({ "GET /library": LIBRARY_PAGE });
    const payload = {
      ...fullPayload(),
      restrictions_filters: {
        rule: "any",
        filters: [
          {
            filter_id: "f1",
            filter_type: "date_blackout_filter",
            enabled: true,
            config: { date_ranges: [{ start: "2024-02-01", end: "2024-01-01" }] },
          },
        ],
      },
    };
    const onApply = renderComponent(RestrictionsCard, payload);
    fireEvent.click(screen.getByRole("button", { name: "Apply Restrictions changes" }));
    expect(onApply).not.toHaveBeenCalled();
    expect(screen.getByRole("alert").textContent).toMatch(/start ≤ end/);
  });

  it("renders typed config controls per modelled filter type", () => {
    stubApi({ "GET /library": LIBRARY_PAGE });
    const payload = {
      restrictions_filters: {
        rule: "any",
        filters: [
          {
            filter_id: "f1",
            filter_type: "max_daily_loss_filter",
            enabled: true,
            config: { limit_percent: "3" },
          },
        ],
      },
    };
    renderComponent(RestrictionsCard, payload);
    const limit = screen.getByLabelText(/Daily loss limit/) as HTMLInputElement;
    expect(limit.value).toBe("3");
    expect(screen.queryByLabelText(/Config \(JSON/)).toBeNull();
  });
});
