import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import { ConflictCard } from "@/components/StrategyConfigForm";
import { RestrictionsCard, ScalingCard } from "@/components/StrategyGraphForm";
import { ENGINE_CAPABILITY_MATRIX } from "@/lib/engineCapabilityMatrix.generated";
import { MODELLED_FILTER_TYPES } from "@/lib/strategyGraph";

afterEach(() => cleanup());

const noop = () => {};

function select(label: RegExp): HTMLSelectElement {
  return screen.getByLabelText(label) as HTMLSelectElement;
}

function disabledValues(label: RegExp): string[] {
  return [...select(label).options].filter((option) => option.disabled).map((o) => o.value);
}

/** The note a select points at via aria-describedby — null when it advertises none. */
function noteFor(label: RegExp): HTMLElement | null {
  const id = select(label).getAttribute("aria-describedby");
  return id === null ? null : document.getElementById(id);
}

// #539 / #533 — the capability mirror exists so a `future_dev` option is refused BEFORE a
// user builds a strategy on it. Two opposite failures are covered here:
//
//   #539 false-NEGATIVE — StrategyGraphForm never consumed the mirror, so 15 of the matrix's
//                         22 future_dev rows rendered as ordinary, selectable options.
//   #533 false-POSITIVE — the note decided from the VALUE alone and so claimed Ready Check
//                         blocks the shipped default of every new strategy, which it does not.
//
// Both are fixed by the same rule: gate on REACHABILITY, the way the backend readers do.

describe("#533 — ConflictCard states inertness, not a false blocker", () => {
  it("does not claim Ready Check blocks allow_hedge while exit-on-opposite is ON", () => {
    // The shipped default of every new strategy. `_read_opposite_hedge` reports no selection
    // here and `conflict_handling_is_modelled` is True, so the run trades.
    render(<ConflictCard payload={{}} pending={false} onApply={noop} />);

    expect(select(/Opposite-direction hedge/).value).toBe("allow_hedge");
    expect(document.body.textContent).not.toContain("Ready Check blocks it");
    const note = noteFor(/Opposite-direction hedge/);
    expect(note?.textContent).toMatch(/executes nothing in this configuration/i);
    expect(note?.textContent).toMatch(/does not block the run/i);
  });

  it("disables nothing while the field is inert — selecting the value would not block either", () => {
    render(<ConflictCard payload={{}} pending={false} onApply={noop} />);
    expect(disabledValues(/Opposite-direction hedge/)).toEqual([]);
  });

  it("keeps the genuine blocker wording when exit-on-opposite is OFF", () => {
    render(
      <ConflictCard
        payload={{
          conflict_position_handling: {
            opposite_direction_hedge: "allow_hedge",
            exit_on_opposite_signal: false,
          },
        }}
        pending={false}
        onApply={noop}
      />,
    );

    const note = noteFor(/Opposite-direction hedge/);
    expect(note?.textContent).toMatch(/is saved but will not run — Ready Check blocks it/);
    // The saved value still stays selectable — disabling it would break an existing strategy.
    expect(select(/Opposite-direction hedge/).value).toBe("allow_hedge");
    expect(disabledValues(/Opposite-direction hedge/)).not.toContain("allow_hedge");
  });
});

describe("#539 — StrategyGraphForm scaling fields disclose future_dev", () => {
  const enabledScaling = {
    scaling_logic: { enabled: true, timeframe: "1h", timeframe_mode: "increasing_by_layer" },
  };

  it("disables every future_dev timeframe except the saved one, and explains it", () => {
    render(<ScalingCard payload={enabledScaling} pending={false} onApply={noop} />);

    const disabled = disabledValues(/Scaling timeframe/);
    expect(disabled).not.toContain("1h"); // saved value stays selectable
    expect(disabled).not.toContain("same_as_base_tf"); // the only active_v1 row
    expect(disabled).toContain("use_package_default_tf");
    expect(disabled).toContain("1D");
    expect(noteFor(/Scaling timeframe/)?.textContent).toMatch(/is saved but will not run/);
  });

  it("labels a blocked option so the select itself carries the refusal", () => {
    render(<ScalingCard payload={enabledScaling} pending={false} onApply={noop} />);
    const blocked = [...select(/Scaling timeframe/).options].find((o) => o.value === "1D");
    expect(blocked?.textContent).toContain("not available in this build");
  });

  it("discloses increasing_by_layer on the timeframe mode field", () => {
    render(<ScalingCard payload={enabledScaling} pending={false} onApply={noop} />);
    expect(select(/Timeframe mode/).value).toBe("increasing_by_layer");
    expect(noteFor(/Timeframe mode/)?.textContent).toMatch(/is saved but will not run/);
  });

  it("says NOTHING while scaling is disabled — the engine never reads these fields", () => {
    render(
      <ScalingCard
        payload={{
          scaling_logic: { enabled: false, timeframe: "1h", timeframe_mode: "increasing_by_layer" },
        }}
        pending={false}
        onApply={noop}
      />,
    );

    expect(disabledValues(/Scaling timeframe/)).toEqual([]);
    expect(disabledValues(/Timeframe mode/)).toEqual([]);
    expect(noteFor(/Scaling timeframe/)).toBeNull();
    expect(noteFor(/Timeframe mode/)).toBeNull();
  });
});

describe("#539 — RestrictionsCard filter_type discloses future_dev", () => {
  const filterPayload = (enabled: boolean) => ({
    restrictions_filters: { filters: [{ filter_type: "volatility_filter", enabled }] },
  });

  it("disables the unmodelled categories except the saved one", () => {
    render(<RestrictionsCard payload={filterPayload(true)} pending={false} onApply={noop} />);

    const disabled = disabledValues(/Filter type/);
    expect(disabled).not.toContain("volatility_filter"); // saved value stays selectable
    expect(disabled).toEqual(
      expect.arrayContaining(["spread_filter", "volume_filter", "correlation_filter"]),
    );
    expect(disabled).not.toContain("date_blackout_filter"); // active_v1
    expect(noteFor(/Filter type/)?.textContent).toMatch(/is saved but will not run/);
  });

  it("says NOTHING on a disabled filter row — it is dropped from the saved revision", () => {
    render(<RestrictionsCard payload={filterPayload(false)} pending={false} onApply={noop} />);

    expect(disabledValues(/Filter type/)).toEqual([]);
    expect(noteFor(/Filter type/)).toBeNull();
    // The old hand-rolled warning fired on the value alone and claimed a blocker here.
    expect(document.body.textContent).not.toContain("Ready Check blocks a run");
  });
});

describe("MODELLED_FILTER_TYPES is derived, not hand-maintained (D-6)", () => {
  it("equals exactly the active_v1 filter_type rows of the matrix", () => {
    const expected = ENGINE_CAPABILITY_MATRIX.filter(
      (o) => o.fieldPath === "restrictions_filters.filters.filter_type" && o.status === "active_v1",
    ).map((o) => o.value);

    expect([...MODELLED_FILTER_TYPES].sort()).toEqual([...expected].sort());
    expect(MODELLED_FILTER_TYPES.size).toBeGreaterThan(0);
  });
});

// The exhaustiveness guard. Registering a field here is a claim that some form renders it
// through the capability mechanism. Any OTHER field is allowed to stay unregistered only
// while it has no future_dev row at all — the moment the matrix gains one, this fails and
// the field must be wired. That is what keeps `scaling_logic.method` and
// `position_exit_logic.partial_aftermath` (0 future_dev rows today) from silently becoming
// the next #539.
const CAPABILITY_WIRED_FIELDS: readonly string[] = [
  "conflict_position_handling.opposite_direction_hedge",
  "data.costs.slippage_mode",
  "data.execution.entry_timing",
  "data.execution.exit_timing",
  "data.order_config.limit.partial_fill_policy",
  "data.order_config.limit.price_rule",
  "position_sizing.formula_based.formula_type",
  "position_sizing.leverage_mode",
  "position_sizing.signal_strength_adjustment",
  "restrictions_filters.filters.filter_type",
  "scaling_logic.timeframe",
  "scaling_logic.timeframe_mode",
];

describe("every future_dev row is claimed by a form", () => {
  const fieldPaths = [...new Set(ENGINE_CAPABILITY_MATRIX.map((o) => o.fieldPath))];

  it("registers no field the matrix does not have", () => {
    expect(fieldPaths).toEqual(expect.arrayContaining([...CAPABILITY_WIRED_FIELDS]));
  });

  it("leaves no future_dev row on an unwired field", () => {
    const orphaned = ENGINE_CAPABILITY_MATRIX.filter(
      (o) => o.status === "future_dev" && !CAPABILITY_WIRED_FIELDS.includes(o.fieldPath),
    ).map((o) => `${o.fieldPath}=${o.value}`);

    expect(orphaned).toEqual([]);
  });
});
