import { describe, expect, it } from "vitest";

import { buildGatesSnapshot, gateComplete } from "@/lib/capability";

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
