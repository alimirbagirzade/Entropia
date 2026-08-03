// ADIM 3 — a pre-containment shared-capital Result must READ honestly.
//
// Those results are immutable and are kept exactly as written; what changes is
// that their diagnostics tokens are no longer shown to the user as raw machine
// strings. The engine still emits the tokens (backend
// domain/backtest/execution/portfolio.py + execution/output.py), so the mapping
// here is the reader-facing half of the same honest boundary.
import { describe, expect, it } from "vitest";

import { diagnosticWarningLabel } from "../lib/backtest";

describe("legacy sequential portfolio diagnostics", () => {
  it("names the sequential composite curve instead of printing the raw token", () => {
    const label = diagnosticWarningLabel("portfolio_curve_sequential_not_unified_clock");

    expect(label).not.toBe("portfolio_curve_sequential_not_unified_clock");
    expect(label).toMatch(/legacy sequential/i);
    expect(label).toMatch(/not a unified-clock/i);
    // The reader is told the stored drawdown is not a portfolio drawdown, which is
    // the actual defect — not merely that "the curve is sequential".
    expect(label).toMatch(/not a portfolio drawdown/i);
  });

  it("names the forward-only cross-item rule enforcement", () => {
    const label = diagnosticWarningLabel("portfolio_rules_sequential_pin_order_precedence");

    expect(label).toMatch(/legacy sequential/i);
    expect(label).toMatch(/forward-only/i);
  });

  it("still surfaces an unknown code verbatim rather than dropping it (L4)", () => {
    expect(diagnosticWarningLabel("some_future_engine_warning")).toBe("some_future_engine_warning");
  });
});
