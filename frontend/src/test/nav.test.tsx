import { describe, expect, it } from "vitest";
import { FUTURE_DEV_SUBPAGES, MENU_BAR, NAV, ALL_NAV_ITEMS, type MenuLink } from "@/app/nav";

describe("navigation skeleton", () => {
  it("exposes every Entropia V18 screen", () => {
    // 22 canonical V18 screens + 2 post-V1 surfaces (System Metrics /panel/metrics,
    // Admin Provisioning /panel/provisioning) + 1 post-V1 Instrument Registry
    // (/instruments, GAP-16) − 1 (UI-03: "Add Outsource Signal" dropped from the
    // primary-nav registry; it is now the Mainboard Add-menu nested submenu. Its
    // /outsource-signal route stays a deep-link in App.tsx, just not in NAV)
    // + 1 (UI-19: the combined Panel entry splits into distinct Management and
    // Logs nav destinations; bare /panel redirects and is not a registry item).
    expect(ALL_NAV_ITEMS.length).toBe(25);
  });

  it("has a Mainboard home route", () => {
    expect(ALL_NAV_ITEMS.some((i) => i.path === "/" && i.label === "Mainboard")).toBe(true);
  });

  it("groups items into sections", () => {
    expect(NAV.length).toBeGreaterThan(0);
    for (const section of NAV) expect(section.items.length).toBeGreaterThan(0);
  });

  it("routes Panel Logs and Management to distinct destinations (UI-19)", () => {
    // Acceptance: the two Panel work contexts must not resolve to the same page.
    // Both the flat registry and the mockup menu-bar leaves are checked.
    const registryLogs = ALL_NAV_ITEMS.find((i) => i.path === "/panel/logs");
    const registryManagement = ALL_NAV_ITEMS.find((i) => i.path === "/panel/management");
    expect(registryLogs).toBeDefined();
    expect(registryManagement).toBeDefined();
    expect(registryLogs?.path).not.toBe(registryManagement?.path);
    // The combined /panel entry is gone from the registry (it only redirects now).
    expect(ALL_NAV_ITEMS.some((i) => i.path === "/panel")).toBe(false);

    const panelGroup = MENU_BAR.find((group) => group.label === "Panel");
    const leaves: MenuLink[] = [];
    const walk = (items: MenuLink[] | undefined) => {
      for (const item of items ?? []) {
        if (item.items) walk(item.items);
        else leaves.push(item);
      }
    };
    walk(panelGroup?.items);
    const logs = leaves.find((leaf) => leaf.label === "Logs");
    const management = leaves.find((leaf) => leaf.label === "Management");
    expect(logs?.path).toBe("/panel/logs");
    expect(management?.path).toBe("/panel/management");
    expect(logs?.path).not.toBe(management?.path);
  });
});

describe("Future Dev submenu targets (UI-22)", () => {
  it("declares one dedicated, distinct route path per capability sub-page", () => {
    // App.tsx generates one real route per entry — a duplicate or off-prefix
    // path here would silently break the no-NotFound acceptance criterion.
    expect(FUTURE_DEV_SUBPAGES).toHaveLength(6);
    const paths = FUTURE_DEV_SUBPAGES.map((subpage) => subpage.path);
    expect(new Set(paths).size).toBe(6);
    for (const path of paths) expect(path.startsWith("/future-dev/")).toBe(true);
  });

  it("points every Future Dev menu leaf at its dedicated sub-page route", () => {
    const group = MENU_BAR.find((candidate) => candidate.label === "Future Dev");
    const leaves: MenuLink[] = [];
    const walk = (items: MenuLink[] | undefined) => {
      for (const item of items ?? []) {
        if (item.items) walk(item.items);
        else leaves.push(item);
      }
    };
    walk(group?.items);
    // Live Trade stays the passive mockup placeholder (no target).
    expect(leaves.find((leaf) => leaf.label === "Live Trade")?.path).toBeUndefined();
    const targeted = leaves.filter((leaf) => leaf.label !== "Live Trade");
    expect(targeted).toHaveLength(6);
    const pathByLabel = Object.fromEntries(
      FUTURE_DEV_SUBPAGES.map((subpage) => [subpage.label, subpage.path]),
    );
    for (const leaf of targeted) expect(leaf.path).toBe(pathByLabel[leaf.label]);
  });
});
