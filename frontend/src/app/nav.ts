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
      // UI-03: "Add Outsource Signal" is no longer a standalone primary-workflow
      // destination. It lives as the two-option nested submenu in the Mainboard
      // Add menu (Trading Signal / Trade Log → inline draft rows). The
      // /outsource-signal route + page stay reachable as a deep-link (App.tsx),
      // so no route path is removed — only the primary-nav registry entry is.
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
      // UI-19: the combined Panel is two distinct work contexts, one nav entry
      // each. Bare /panel still resolves (App.tsx redirects it to Management).
      { path: "/panel/management", label: "Panel / Management", stage: 6, adminOnly: true },
      { path: "/panel/logs", label: "Panel / Logs", stage: 6, adminOnly: true },
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

// R2-02 (GAP madde 6): the top-menu Add actions and the Mainboard "+ Add" menu
// share ONE action model. A menu entry carrying addIntent does not route-link;
// it dispatches to the Mainboard, which runs the same handler its own "+ Add"
// menu uses. The old primary targets (/strategy, /trading-signal, /trade-log,
// /packages/create) stay alive as deep-links in App.tsx.
export type MainboardAddIntent = "strategy" | "trading_signal" | "trade_log" | "package";

export interface MenuLink {
  label: string;
  path?: string; // omitted → non-navigating action item (e.g. About modal)
  action?: "about";
  addIntent?: MainboardAddIntent; // dispatch to the Mainboard add flow instead of routing
  adminOnly?: boolean;
  items?: MenuLink[]; // second-level submenu (v18 nested tree); a leaf with no
  // path/action/items is a passive placeholder (mockup "Live Trade").
}

export interface MenuGroup {
  label: string;
  path?: string; // top-level direct link (e.g. Mainboard) — no dropdown
  items?: MenuLink[]; // dropdown entries
  accent?: "blue"; // v18 "Future Dev" blue menu
  adminOnly?: boolean;
}

// UI-22: every Future Dev submenu target is a real dedicated route (spec
// §UI-22 — no menu target may resolve to Page Not Found). One entry per
// baseline capability key (domain/capability/enums.py BASELINE_CAPABILITY_KEYS
// minus live_trade, which stays a passive mockup placeholder with no target).
// App.tsx declares one route per entry; MENU_BAR below links to these paths.
export interface FutureDevSubpage {
  capabilityKey: string;
  label: string;
  path: string;
  area: "Graphic View" | "AI Operations" | "Research";
}

export const FUTURE_DEV_SUBPAGES: FutureDevSubpage[] = [
  {
    capabilityKey: "graphic_view",
    label: "Graphic View",
    path: "/future-dev/graphic-view",
    area: "Graphic View",
  },
  {
    capabilityKey: "backtest_review",
    label: "Backtest Review",
    path: "/future-dev/backtest-review",
    area: "AI Operations",
  },
  {
    capabilityKey: "signal_intelligence",
    label: "Signal Intelligence",
    path: "/future-dev/signal-intelligence",
    area: "AI Operations",
  },
  {
    capabilityKey: "regime_research",
    label: "Regime Research",
    path: "/future-dev/regime-research",
    area: "Research",
  },
  {
    capabilityKey: "hypothesis_lab",
    label: "Hypothesis Lab",
    path: "/future-dev/hypothesis-lab",
    area: "Research",
  },
  {
    capabilityKey: "parameter_fields",
    label: "Parameter Fields",
    path: "/future-dev/parameter-fields",
    area: "Research",
  },
];

// Lookup used by the Future Dev menu below — single source of truth for the
// submenu targets (the same list App.tsx generates the routes from).
const FUTURE_DEV_PATH: Record<string, string> = Object.fromEntries(
  FUTURE_DEV_SUBPAGES.map((subpage) => [subpage.capabilityKey, subpage.path]),
);

export const MENU_BAR: MenuGroup[] = [
  {
    label: "Mainboard",
    path: "/", // clickable title (opens the index) AND a hover dropdown
    items: [
      { label: "Add Strategy", addIntent: "strategy" },
      {
        label: "Add Outsource Signal",
        items: [
          { label: "Trading Signal", addIntent: "trading_signal" },
          { label: "Trade Log", addIntent: "trade_log" },
        ],
      },
      { label: "Add Package", addIntent: "package" },
      { label: "Portfolio / Equity Allocation", path: "/portfolio" },
    ],
  },
  {
    label: "Edit",
    items: [
      {
        label: "Package Library",
        items: [
          // M-12 (audit 22-Jul): the Production V1 catalog has only these package
          // kinds. Trading Signal / Trade Log are NOT backend catalog kinds — their
          // former menu entries pointed at an unfiltered library and implied a
          // PackageKind that does not exist, so they were removed. Trading Signal
          // and Trade Log are reached through the Mainboard "Add Outsource Signal"
          // flow (external working objects), never Package Library.
          { label: "Strategy Packages", path: "/packages/library?type=strategy" },
          { label: "Indicator Packages", path: "/packages/library?type=indicator" },
          { label: "Condition Packages", path: "/packages/library?type=condition" },
          { label: "Embedded System Packages", path: "/packages/embedded" },
        ],
      },
      { label: "Rationale Families", path: "/rationale-families" },
      { label: "Create Package", path: "/packages/create" },
      { label: "Market Data", path: "/market-data" },
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
    items: [
      { label: "Live Trade" }, // passive placeholder (mockup: no target)
      // UI-22: each submenu target is its own dedicated valid route from
      // FUTURE_DEV_SUBPAGES (App.tsx declares the matching routes) — never a
      // path that resolves to NotFound, never a shared catch-all.
      { label: "Graphic View", path: FUTURE_DEV_PATH.graphic_view },
      {
        label: "AI Operations",
        items: [
          { label: "Backtest Review", path: FUTURE_DEV_PATH.backtest_review },
          { label: "Signal Intelligence", path: FUTURE_DEV_PATH.signal_intelligence },
        ],
      },
      {
        label: "Research",
        items: [
          { label: "Regime Research", path: FUTURE_DEV_PATH.regime_research },
          { label: "Hypothesis Lab", path: FUTURE_DEV_PATH.hypothesis_lab },
          { label: "Parameter Fields", path: FUTURE_DEV_PATH.parameter_fields },
        ],
      },
    ],
  },
  {
    label: "Panel",
    adminOnly: true,
    items: [
      { label: "Logs", path: "/panel/logs", adminOnly: true },
      { label: "Management", path: "/panel/management", adminOnly: true },
      { label: "Trash", path: "/trash", adminOnly: true },
    ],
  },
  {
    label: "Agent Workspace",
    adminOnly: true,
    items: [
      { label: "Analysis Lab", path: "/analysis-lab" },
      { label: "Research Data", path: "/research-data" },
    ],
  },
];
