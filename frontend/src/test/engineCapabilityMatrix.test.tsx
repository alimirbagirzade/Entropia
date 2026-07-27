import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import { DataExecutionCard, PositionSizingCard } from "@/components/StrategyConfigForm";
import {
  ENGINE_CAPABILITY_MATRIX,
  capabilityOption,
  isFutureDev,
} from "@/lib/engineCapabilityMatrix.generated";
import { LEVERAGE_MODE_OPTIONS, SLIPPAGE_MODE_OPTIONS } from "@/lib/strategyForm";

afterEach(() => cleanup());

/** The capability note a select points at via aria-describedby (asserts the wiring too). */
function capabilityNoteFor(select: HTMLSelectElement): HTMLElement {
  const noteId = select.getAttribute("aria-describedby");
  expect(noteId).toBeTruthy();
  const note = document.getElementById(noteId as string);
  expect(note).toBeTruthy();
  return note as HTMLElement;
}

// F-05 / M-05 — the UI half of the capability matrix.
//
// The matrix is generated from backend/src/entropia/domain/backtest/capabilities.py and
// pinned byte-for-byte by backend/tests/unit/test_capability_matrix.py, so these tests only
// need to prove the EDITOR consumes it: a `future_dev` option must be visibly disabled and
// explained BEFORE a user builds a strategy on it, never merely refused later at Ready Check.

describe("ENGINE_CAPABILITY_MATRIX", () => {
  it("is non-empty and classifies every row", () => {
    expect(ENGINE_CAPABILITY_MATRIX.length).toBeGreaterThan(0);
    for (const option of ENGINE_CAPABILITY_MATRIX) {
      expect(["active_v1", "future_dev"]).toContain(option.status);
      expect(option.fieldPath).not.toBe("");
      expect(option.value).not.toBe("");
    }
  });

  it("gives every future_dev row a dependency reason", () => {
    const gated = ENGINE_CAPABILITY_MATRIX.filter((o) => o.status === "future_dev");
    expect(gated.length).toBeGreaterThan(0);
    for (const option of gated) {
      expect(option.dependency.trim()).not.toBe("");
    }
  });

  it("looks options up by field path and value, and reports unknowns as undefined", () => {
    expect(capabilityOption("position_sizing.leverage_mode", "cross")?.status).toBe("future_dev");
    expect(capabilityOption("position_sizing.leverage_mode", "no_leverage")?.status).toBe(
      "active_v1",
    );
    // An unenumerated field or value is NOT a refusal — the matrix lists what is gated.
    expect(capabilityOption("data.costs.nope", "whatever")).toBeUndefined();
    expect(isFutureDev("data.costs.nope", "whatever")).toBe(false);
    expect(isFutureDev("", "cross")).toBe(false);
  });

  it("marks the historical-slippage mode as future_dev (the F-05 finding)", () => {
    // It used to be selectable AND saveable while the engine silently ran zero slippage.
    expect(isFutureDev("data.costs.slippage_mode", "historical_slippage_if_available")).toBe(true);
    expect(isFutureDev("data.costs.slippage_mode", "percentage_slippage")).toBe(false);
  });
});

describe("Strategy editor disables future_dev options", () => {
  it("disables 'Historical Slippage If Available' and explains why", () => {
    render(<DataExecutionCard payload={{}} pending={false} onApply={() => {}} />);

    const select = screen.getByLabelText(/Slippage model/) as HTMLSelectElement;
    const byValue = new Map(
      [...select.options].map((option) => [option.value, option] as const),
    );

    // The gated option is present (so a saved config still round-trips) but NOT selectable.
    expect(byValue.get("historical_slippage_if_available")?.disabled).toBe(true);
    expect(byValue.get("percentage_slippage")?.disabled).toBe(false);
    expect(byValue.get("historical_slippage_if_available")?.textContent).toMatch(
      /not available in this build/i,
    );

    // The dependency is spelled out, and the control points at it for screen readers.
    const note = capabilityNoteFor(select);
    expect(note.textContent).toMatch(/Not available in this build/i);
    expect(note.textContent).toMatch(/historical slippage series/i);
  });

  it("disables 'Cross' leverage and explains the missing portfolio margin model", () => {
    render(<PositionSizingCard payload={{}} pending={false} onApply={() => {}} />);

    const select = screen.getByLabelText(/Leverage mode/) as HTMLSelectElement;
    const cross = [...select.options].find((option) => option.value === "cross");
    expect(cross?.disabled).toBe(true);
    expect(capabilityNoteFor(select).textContent).toMatch(/portfolio-level margin\/risk model/i);
  });

  it("disables both unmodelled signal-strength modes but leaves the modelled ones", () => {
    render(<PositionSizingCard payload={{}} pending={false} onApply={() => {}} />);

    const select = screen.getByLabelText(/Signal strength/) as HTMLSelectElement;
    const disabledValues = [...select.options]
      .filter((option) => option.disabled)
      .map((option) => option.value);
    expect(disabledValues).toEqual(["trend_adjusted", "divergence_adjusted"]);
  });

  it("keeps an ALREADY-SAVED future_dev value selectable, flagged as blocked", () => {
    // Disabling the current value would make an existing strategy un-editable and let the
    // form silently rewrite saved config; Ready Check is what stops the run.
    render(
      <DataExecutionCard
        payload={{ data: { costs: { slippage_mode: "historical_slippage_if_available" } } }}
        pending={false}
        onApply={() => {}}
      />,
    );

    const select = screen.getByLabelText(/Slippage model/) as HTMLSelectElement;
    expect(select.value).toBe("historical_slippage_if_available");
    const current = [...select.options].find(
      (option) => option.value === "historical_slippage_if_available",
    );
    expect(current?.disabled).toBe(false);
    expect(capabilityNoteFor(select).textContent).toMatch(/saved but will not run/i);
  });

  it("leaves selects with no matrix-gated option free of a capability note", () => {
    render(<DataExecutionCard payload={{}} pending={false} onApply={() => {}} />);
    // Order type is not an enumerated capability field, so it must render no note at all.
    const select = screen.getByLabelText(/Order type/) as HTMLSelectElement;
    expect([...select.options].some((option) => option.disabled)).toBe(false);
    expect(select.getAttribute("aria-describedby")).toBeNull();
  });

  it("never disables an option the matrix marks active_v1", () => {
    const gatedValues = new Set(
      ENGINE_CAPABILITY_MATRIX.filter((o) => o.status === "future_dev").map((o) => o.value),
    );
    for (const option of [...SLIPPAGE_MODE_OPTIONS, ...LEVERAGE_MODE_OPTIONS]) {
      const row = ENGINE_CAPABILITY_MATRIX.find((entry) => entry.value === option.value);
      if (row?.status === "active_v1") {
        expect(gatedValues.has(option.value)).toBe(false);
      }
    }
  });
});
