// R2-13 — V18 prototype (mockup) reference captures for the side-by-side
// review. The canonical mockup lives at docs/spec/
// index_guncellenmis_duzeltilmis_v18.html; per CLAUDE.md it is served as the
// gitignored dev copy frontend/public/mockup_v18.html (cp before running).
//
// The mockup is a single-page JS prototype: screens are rendered by calling
// its own show* functions directly (no auth, no backend). Output goes to
// screenshots/prototype/<slug>--1440.png and feeds the deviation review in
// docs/implementation/v18_visual_deviations.md.
//
// Run: npm run screenshots:prototype

import { test } from "@playwright/test";

import { VIEWPORT_HEIGHT, settle } from "../utils/screenshotMatrix";

// slug → JS invocation inside the mockup. Every mockup handler calls
// `event.stopPropagation()` unguarded, so a real Event instance is passed
// (`EV` below). Admin-gated screens flip the mockup's own role state first
// (top-level `let` bindings are reachable from evaluate's global scope).
const EV = `new Event("click")`;
const AS_ADMIN = `currentRole = "Admin"; adminAccess = true; try { updateAdminOnlyMenus(); } catch (e) {}`;
// Inline rows render collapsed; the ▼ arrow opens the inline editor — the
// screen the page docs 02/04/05 actually specify.
const EXPAND = `document.querySelector(".strategy-arrow").click()`;

const PROTOTYPE_SCREENS: Array<{ slug: string; js: string }> = [
  { slug: "mainboard", js: "showMainboard()" },
  { slug: "strategy-details", js: `showMainboard(); addStrategyBox(${EV}); ${EXPAND}` },
  { slug: "trading-signal", js: `showMainboard(); addSignalPackageBox(${EV}); ${EXPAND}` },
  { slug: "trade-log", js: `showMainboard(); addTradeLogBox(${EV}); ${EXPAND}` },
  { slug: "create-package", js: `showCreatePackagePage(${EV})` },
  { slug: "package-library", js: `showPackagePool(${EV}, 'all')` },
  { slug: "embedded-packages", js: `showPackagePool(${EV}, 'embedded')` },
  { slug: "rationale-families", js: `showRationaleFamilies(${EV})` },
  { slug: "market-data", js: `showMarketData(${EV})` },
  { slug: "research-data", js: `${AS_ADMIN}; showResearchData(${EV})` },
  { slug: "portfolio", js: `showPortfolioEquityPanel(${EV})` },
  { slug: "ready-check", js: `showMainboard(); addStrategyBox(${EV}); runBacktestReadyCheck()` },
  { slug: "run-results", js: `showMainboard(); addStrategyBox(${EV}); runBacktestReadyCheck(); addBacktestResult()` },
  { slug: "results-history", js: `showResultsHistory(${EV})` },
  { slug: "arrange-metrics", js: `showArrangeMetrics(${EV})` },
  { slug: "analysis-lab", js: `${AS_ADMIN}; showAnalysisLab(${EV})` },
  { slug: "panel-management", js: `${AS_ADMIN}; showPanelManagement(${EV})` },
  { slug: "panel-logs", js: `${AS_ADMIN}; showPanelLogs(${EV})` },
  { slug: "trash", js: `${AS_ADMIN}; showTrash(${EV})` },
  { slug: "user-manual", js: `showUserManual(${EV})` },
];

test.describe("@prototype R2-13 V18 mockup reference captures", () => {
  test.describe.configure({ mode: "serial" });
  test.setTimeout(10 * 60_000);

  test("capture prototype screens @1440", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: VIEWPORT_HEIGHT });
    for (const screen of PROTOTYPE_SCREENS) {
      await page.goto("/mockup_v18.html");
      await settle(page);
      // No try/catch swallow: a broken invocation must FAIL the capture run
      // (a silent failure produced blank reference shots in the first pass).
      await page.evaluate(`(() => { ${screen.js} })()`);
      await page.waitForTimeout(300);
      await page.screenshot({
        path: `screenshots/prototype/${screen.slug}--1440.png`,
        fullPage: true,
      });
    }
  });
});
