// R2-13 — shared page/state/width matrix definitions for the screenshot
// baseline capture (specs/10-screenshot-matrix.spec.ts) and the visual
// regression suite (specs/11-visual-regression.spec.ts).
//
// The 22 target pages are the numbered page-specification documents
// docs/spec/01_*.md … 22_*.md; each entry records the doc number so the
// output tree is traceable back to its spec.

import type { Page } from "@playwright/test";

export interface TargetPage {
  doc: number;
  slug: string;
  path: string;
  adminOnly?: boolean;
  // Pages whose spec requires the extra mobile/tablet widths (Mainboard +
  // the three inline-editor row types).
  mobile?: boolean;
}

export const TARGET_PAGES: TargetPage[] = [
  { doc: 1, slug: "mainboard", path: "/", mobile: true },
  { doc: 2, slug: "strategy-details", path: "/strategy", mobile: true },
  { doc: 3, slug: "outsource-signal", path: "/outsource-signal" },
  { doc: 4, slug: "trading-signal", path: "/trading-signal", mobile: true },
  { doc: 5, slug: "trade-log", path: "/trade-log", mobile: true },
  { doc: 6, slug: "create-package", path: "/packages/create" },
  { doc: 7, slug: "pre-check", path: "/packages/pre-check" },
  { doc: 8, slug: "package-library", path: "/packages/library" },
  { doc: 9, slug: "embedded-packages", path: "/packages/embedded" },
  { doc: 10, slug: "rationale-families", path: "/rationale-families" },
  { doc: 11, slug: "market-data", path: "/market-data" },
  { doc: 12, slug: "research-data", path: "/research-data" },
  { doc: 13, slug: "portfolio", path: "/portfolio" },
  { doc: 14, slug: "ready-check", path: "/backtest/ready-check" },
  { doc: 15, slug: "run-results", path: "/backtest/run" },
  { doc: 16, slug: "results-history", path: "/backtest/history" },
  { doc: 17, slug: "arrange-metrics", path: "/backtest/metrics" },
  { doc: 18, slug: "analysis-lab", path: "/analysis-lab" },
  { doc: 19, slug: "panel-management", path: "/panel/management", adminOnly: true },
  { doc: 19, slug: "panel-logs", path: "/panel/logs", adminOnly: true },
  { doc: 20, slug: "trash", path: "/trash", adminOnly: true },
  { doc: 21, slug: "user-manual", path: "/user-manual" },
  { doc: 22, slug: "future-dev", path: "/future-dev" },
];

export const DESKTOP_WIDTHS = [1280, 1440, 1920] as const;
export const MOBILE_WIDTHS = [375, 768] as const;

// Height is a capture-viewport constant; matrix shots are fullPage so the
// height only affects lazy/sticky behavior, not the captured extent.
export const VIEWPORT_HEIGHT = 900;

// Pages that render server data lists — the ones where empty / error /
// loading states are meaningful (static doc pages and pure forms excluded).
export const DATA_PAGE_SLUGS = [
  "mainboard",
  "strategy-details",
  "trading-signal",
  "trade-log",
  "package-library",
  "embedded-packages",
  "rationale-families",
  "market-data",
  "research-data",
  "portfolio",
  "ready-check",
  "run-results",
  "results-history",
  "analysis-lab",
] as const;

export const ADMIN_ONLY_SLUGS = TARGET_PAGES.filter((p) => p.adminOnly).map((p) => p.slug);

// Kill animations/transitions/carets so captures are deterministic.
const FREEZE_CSS = `
  *, *::before, *::after {
    animation-duration: 0s !important;
    animation-delay: 0s !important;
    transition-duration: 0s !important;
    transition-delay: 0s !important;
    caret-color: transparent !important;
  }
`;

export async function freezePage(page: Page): Promise<void> {
  await page.addStyleTag({ content: FREEZE_CSS }).catch(() => {
    // Ignore: navigation raced the style injection; the retry below re-adds it.
  });
}

// Settle: network quiet + a short paint budget. networkidle can hang forever
// on pages with polling (SSE/react-query refetch), so cap it and fall through.
export async function settle(page: Page): Promise<void> {
  await page.waitForLoadState("domcontentloaded");
  await page.waitForLoadState("networkidle", { timeout: 8_000 }).catch(() => undefined);
  await freezePage(page);
  await page.waitForTimeout(400);
}

export function shotPath(slug: string, state: string, width: number): string {
  return `screenshots/baseline/${slug}/${state}--${width}.png`;
}
