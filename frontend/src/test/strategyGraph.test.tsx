import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { StrategyGraphForm } from "@/components/StrategyGraphForm";
import {
  extractGraphSections,
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
    scaling_logic: { enabled: false },
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

    // Uncovered top-level keys preserved verbatim.
    expect(merged.untouched_future_key).toBe("preserved");
    expect(merged.position_sizing).toEqual(payload.position_sizing);
    expect(merged.scaling_logic).toEqual(payload.scaling_logic);

    const entry = merged.position_entry_logic as Record<string, unknown>;
    const blocks = entry.indicator_blocks as Record<string, unknown>[];
    // parameter_overrides is not surfaced by the form but must survive.
    expect(blocks[0].parameter_overrides).toEqual({ length: 14 });
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

function renderForm(payload: Record<string, unknown>, onApply = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <StrategyGraphForm payload={payload} pending={false} onApply={onApply} />
    </QueryClientProvider>,
  );
  return onApply;
}

describe("StrategyGraphForm", () => {
  it("renders the Entry, Exit and Logic-Based Stop sections", () => {
    stubApi({ "GET /library": LIBRARY_PAGE });
    renderForm({});
    expect(screen.getByRole("heading", { name: /Position Entry Logic/ })).toBeTruthy();
    expect(screen.getByRole("heading", { name: /Position Exit Logic/ })).toBeTruthy();
    expect(screen.getByRole("heading", { name: /Logic-Based Stop Block/ })).toBeTruthy();
    // Honest boundary note about the unimplemented logic-based stop.
    expect(screen.getByText(/does not yet implement/i)).toBeTruthy();
  });

  it("pins a package via the picker browsing the Library catalog", async () => {
    stubApi({ "GET /library": LIBRARY_PAGE });
    renderForm({});
    fireEvent.click(screen.getByRole("button", { name: "Choose indicator" }));
    const row = await screen.findByRole("button", { name: /Reversal Sensor/ });
    fireEvent.click(row);
    // The pinned ref renders the chosen row's root id.
    await waitFor(() => expect(screen.getByText("pkg_lib")).toBeTruthy());
  });

  it("applies the merged payload preserving uncovered sections", () => {
    stubApi({ "GET /library": LIBRARY_PAGE });
    const onApply = renderForm(fullPayload());
    fireEvent.click(screen.getByRole("button", { name: "Apply graph changes" }));
    expect(onApply).toHaveBeenCalledTimes(1);
    const sent = onApply.mock.calls[0][0] as Record<string, unknown>;
    expect(sent.untouched_future_key).toBe("preserved");
    const entry = sent.position_entry_logic as Record<string, unknown>;
    const blocks = entry.indicator_blocks as Record<string, unknown>[];
    expect(blocks[0].parameter_overrides).toEqual({ length: 14 });
  });
});
