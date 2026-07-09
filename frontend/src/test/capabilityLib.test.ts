import { describe, expect, it } from "vitest";

import {
  ANALYSIS_ARTIFACT_CAPABILITY,
  ANALYSIS_ARTIFACT_TYPES,
  buildGatesSnapshot,
  gateComplete,
} from "@/lib/capability";

describe("capability gate snapshot helpers", () => {
  it("reads completeness exactly like the server (_gate_complete)", () => {
    expect(gateComplete(true)).toBe(true);
    expect(gateComplete({ complete: true, note: "n" })).toBe(true);
    expect(gateComplete({ complete: false })).toBe(false);
    expect(gateComplete(undefined)).toBe(false);
  });

  it("merges a draft without clobbering object entries and fills every gate key", () => {
    const original = {
      gates: { domain: true, data: { complete: false, note: "pending lineage" } },
      extra: "kept",
    };
    const merged = buildGatesSnapshot(original, { data: true, ui: true });
    expect(merged.extra).toBe("kept");
    expect(merged.gates?.domain).toBe(true);
    expect(merged.gates?.data).toEqual({ complete: true, note: "pending lineage" });
    expect(merged.gates?.ui).toBe(true);
    // Gates absent from both original and draft come out incomplete, present.
    expect(merged.gates?.rollback).toBe(false);
  });
});

describe("analysis artifact capability mirror", () => {
  it("maps every artifact type to its doc-22 gating capability", () => {
    expect(ANALYSIS_ARTIFACT_CAPABILITY.monte_carlo).toBe("backtest_review");
    expect(ANALYSIS_ARTIFACT_CAPABILITY.walk_forward).toBe("backtest_review");
    expect(ANALYSIS_ARTIFACT_CAPABILITY.sensitivity).toBe("parameter_fields");
    expect(ANALYSIS_ARTIFACT_CAPABILITY.signal_intelligence).toBe("signal_intelligence");
    expect(ANALYSIS_ARTIFACT_CAPABILITY.regime_research).toBe("regime_research");
  });

  it("offers the composer options in the server's sorted `allowed` order", () => {
    expect(ANALYSIS_ARTIFACT_TYPES).toEqual([...ANALYSIS_ARTIFACT_TYPES].sort());
    expect(ANALYSIS_ARTIFACT_TYPES).toHaveLength(7);
    expect(new Set(ANALYSIS_ARTIFACT_TYPES).size).toBe(7);
  });
});
