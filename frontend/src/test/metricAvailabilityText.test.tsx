import { describe, expect, it } from "vitest";

import {
  EM_DASH,
  formatMetricValue,
  METRIC_AVAILABILITY_NOTES,
  metricAvailabilityStatusLabel,
} from "@/lib/backtest";

// I-01 — a null metric must read as the doc 17 §6.1 "Nihai UI metni", and the
// STATUS must keep the reason the backend sent (no_drawdown / no_losing_trade).
// Presentation only: the browser never recomputes a metric (doc 15 §15).

function cell(availability: string) {
  return { value: null, value_format: "decimal2", availability };
}

describe("metric availability text (doc 17 §6.1)", () => {
  it("renders a zero-drawdown ROMAD as Not available, never infinity or 0", () => {
    // doc 17 §9.2: "Max drawdown=0 ise null + no_drawdown; infinity yasak."
    expect(formatMetricValue(cell("no_drawdown"))).toBe("Not available");
    expect(formatMetricValue(cell("no_drawdown"))).not.toBe("0.00");
    expect(formatMetricValue(cell("no_drawdown"))).not.toBe(EM_DASH);
    expect(metricAvailabilityStatusLabel("no_drawdown")).toBe("No drawdown");
  });

  it("renders a Profit Factor with no losing trade as Not available", () => {
    // doc 17 §9.2: "Gross loss=0 ise null + no_losing_trade; infinity yasak."
    expect(formatMetricValue(cell("no_losing_trade"))).toBe("Not available");
    expect(formatMetricValue(cell("no_losing_trade"))).not.toBe(EM_DASH);
    expect(metricAvailabilityStatusLabel("no_losing_trade")).toBe("No losing trade");
  });

  it("uses the doc 17 §6.1 verbatim value text for every null status", () => {
    expect(formatMetricValue(cell("not_available"))).toBe("Not available");
    expect(formatMetricValue(cell("no_qualifying_trades"))).toBe("No qualifying trades");
    expect(formatMetricValue(cell("not_computed"))).toBe("Not computed for this result");
  });

  it("keeps the doc 17 §6 reason sentence for the two divide-by-zero statuses", () => {
    expect(METRIC_AVAILABILITY_NOTES.no_drawdown).toContain(
      "it is reported as Not available with a no_drawdown status",
    );
    expect(METRIC_AVAILABILITY_NOTES.no_losing_trade).toContain(
      "with a no_losing_trade status rather than as infinity",
    );
    // A plain not_available carries no extra reason — nothing is invented.
    expect(METRIC_AVAILABILITY_NOTES.not_available).toBeUndefined();
  });

  it("still formats a computed value and falls back to an em dash for a missing cell", () => {
    expect(formatMetricValue({ value: "1.5", value_format: "decimal2", availability: "computed" }))
      .toBe("1.50");
    expect(formatMetricValue(null)).toBe(EM_DASH);
  });
});
