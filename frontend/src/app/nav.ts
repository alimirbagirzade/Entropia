// Canonical navigation skeleton — every Entropia V18 screen, grouped by area,
// tagged with the build STAGE that delivers its behavior. Stage 0 renders each
// as a placeholder; later stages replace the element with the real page.
//
// Two views of the same routes:
//   • NAV / ALL_NAV_ITEMS — flat grouped list (kept for route generation + tests).
//   • MENU_BAR            — the v18 mockup top menu-bar tree (horizontal menus +
//                           hover dropdowns). Presentation only; every entry
//                           points at an existing route path — no backend change.

export interface NavItem {
  path: string;
  label: string;
  stage: number;
  adminOnly?: boolean;
}

export interface NavSection {
  title: string;
  items: NavItem[];
}

export const NAV: NavSection[] = [
  {
    title: "Workspace",
    items: [
      { path: "/", label: "Mainboard", stage: 3 },
      { path: "/strategy", label: "Strategy Details", stage: 3 },
      { path: "/outsource-signal", label: "Add Outsource Signal", stage: 3 },
      { path: "/trading-signal", label: "Trading Signal", stage: 3 },
      { path: "/trade-log", label: "Trade Log", stage: 3 },
    ],
  },
  {
    title: "Packages & Data",
    items: [
      { path: "/packages/create", label: "Create Package", stage: 2 },
      { path: "/packages/pre-check", label: "Pre-Check", stage: 2 },
      { path: "/packages/library", label: "Package Library", stage: 2 },
      { path: "/packages/embedded", label: "Embedded System Packages", stage: 2 },
      { path: "/rationale-families", label: "Rationale Families", stage: 2 },
      { path: "/market-data", label: "Market Data", stage: 2 },
      { path: "/research-data", label: "Research Data", stage: 2 },
      { path: "/instruments", label: "Instrument Registry", stage: 2 },
    ],
  },
  {
    title: "Backtest",
    items: [
      { path: "/portfolio", label: "Portfolio / Equity Allocation", stage: 4 },
      { path: "/backtest/ready-check", label: "Backtest Ready Check", stage: 4 },
      { path: "/backtest/run", label: "RUN & Backtest Results", stage: 5 },
      { path: "/backtest/history", label: "Results History", stage: 5 },
      { path: "/backtest/metrics", label: "Arrange Metrics", stage: 5 },
    ],
  },
  {
    title: "Agent & Admin",
    items: [
      { path: "/analysis-lab", label: "Analysis Lab", stage: 6 },
      { path: "/panel", label: "Panel / Management / Logs", stage: 6, adminOnly: true },
      // First-Admin provisioning onboarding (post-V1 TIER 2). NOT adminOnly: the
      // first Admin is not yet an Admin, so the page must be reachable pre-elevation.
      { path: "/panel/provisioning", label: "Admin Provisioning", stage: 8 },
      // Ops dashboard over the Stage 8b GET /v1/metrics exposition (post-V1 TIER 2).
      { path: "/panel/metrics", label: "System Metrics", stage: 8, adminOnly: true },
      { path: "/trash", label: "Trash", stage: 6, adminOnly: true },
    ],
  },
  {
    title: "Docs",
    items: [
      { path: "/user-manual", label: "User Manual", stage: 7 },
      { path: "/future-dev", label: "Future Dev", stage: 7 },
    ],
  },
];

export const ALL_NAV_ITEMS: NavItem[] = NAV.flatMap((s) => s.items);

// ---------------------------------------------------------------------------
// v18 mockup top menu-bar tree (presentation shell).
// Every entry points at an existing route above — no new routes, no backend change.
// ---------------------------------------------------------------------------

export interface MenuLink {
  label: string;
  path?: string; // omitted → non-navigating action item (e.g. About modal)
  action?: "about";
  adminOnly?: boolean;
}

export interface MenuGroup {
  label: string;
  path?: string; // top-level direct link (e.g. Mainboard) — no dropdown
  items?: MenuLink[]; // dropdown entries
  accent?: "blue"; // v18 "Future Dev" blue menu
  adminOnly?: boolean;
}

export const MENU_BAR: MenuGroup[] = [
  { label: "Mainboard", path: "/" },
  {
    label: "Edit",
    items: [
      { label: "Add Strategy", path: "/strategy" },
      { label: "Trading Signal", path: "/trading-signal" },
      { label: "Trade Log", path: "/trade-log" },
      { label: "Add Outsource Signal", path: "/outsource-signal" },
      { label: "Portfolio / Equity Allocation", path: "/portfolio" },
      { label: "Create Package", path: "/packages/create" },
      { label: "Pre-Check", path: "/packages/pre-check" },
      { label: "Package Library", path: "/packages/library" },
      { label: "Embedded System Packages", path: "/packages/embedded" },
      { label: "Rationale Families", path: "/rationale-families" },
      { label: "Market Data", path: "/market-data" },
      { label: "Research Data", path: "/research-data" },
      { label: "Instrument Registry", path: "/instruments" },
    ],
  },
  {
    label: "Performance Metrics",
    items: [
      { label: "Results History", path: "/backtest/history" },
      { label: "Arrange Metrics", path: "/backtest/metrics" },
    ],
  },
  {
    label: "Help",
    items: [
      { label: "User Manual", path: "/user-manual" },
      { label: "About", action: "about" },
    ],
  },
  {
    label: "Future Dev",
    accent: "blue",
    items: [{ label: "Future Dev", path: "/future-dev" }],
  },
  {
    label: "Panel",
    adminOnly: true,
    items: [
      { label: "Logs / Management", path: "/panel", adminOnly: true },
      { label: "Admin Provisioning", path: "/panel/provisioning" },
      { label: "System Metrics", path: "/panel/metrics", adminOnly: true },
      { label: "Trash", path: "/trash", adminOnly: true },
    ],
  },
  {
    label: "Agent Workspace",
    adminOnly: true,
    items: [{ label: "Analysis Lab", path: "/analysis-lab" }],
  },
];
