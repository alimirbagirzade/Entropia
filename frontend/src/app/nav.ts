// Canonical navigation skeleton — every Entropia V18 screen, grouped by area,
// tagged with the build STAGE that delivers its behavior. Stage 0 renders each
// as a placeholder; later stages replace the element with the real page.

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
