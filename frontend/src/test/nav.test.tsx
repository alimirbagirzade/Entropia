import { describe, expect, it } from "vitest";
import { NAV, ALL_NAV_ITEMS } from "@/app/nav";

describe("navigation skeleton", () => {
  it("exposes every Entropia V18 screen", () => {
    // 22 canonical V18 screens + 1 post-V1 ops surface (System Metrics, /panel/metrics).
    expect(ALL_NAV_ITEMS.length).toBe(23);
  });

  it("has a Mainboard home route", () => {
    expect(ALL_NAV_ITEMS.some((i) => i.path === "/" && i.label === "Mainboard")).toBe(true);
  });

  it("groups items into sections", () => {
    expect(NAV.length).toBeGreaterThan(0);
    for (const section of NAV) expect(section.items.length).toBeGreaterThan(0);
  });
});
