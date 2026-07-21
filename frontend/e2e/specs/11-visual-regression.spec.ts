// R2-13 — Playwright screenshot REGRESSION for the critical pages
// (Mainboard, Strategy inline, Trading Signal / Trade Log inline, Market
// Data, Create Package, Ready Check, RUN/Result).
//
// Unlike specs/07 (a capture tool), this spec ASSERTS with toHaveScreenshot
// against committed baselines in 11-visual-regression.spec.ts-snapshots/.
//
// Flake controls (documented per slice acceptance):
//   • animations: "disabled" + font caret freeze via settle()/freezePage()
//   • maxDiffPixelRatio 0.02 — tolerates AA/rendering jitter, still fails on
//     layout shifts, clipped controls, missing regions
//   • volatile regions (timestamps, relative dates, live IDs) are masked via
//     the MASKS locator list rather than per-page pixel exclusions
//   • deterministic viewport 1440×900, fullPage
//
// Honest boundary: baselines are only meaningful against the SAME seeded
// dataset they were captured from (the R2-07/KALAN e2e stack DB). Fresh
// stacks must regenerate baselines once:
//   npm run screenshots:update
// Platform note: toHaveScreenshot snapshots are platform-suffixed
// (…-darwin.png / …-linux.png); the committed set is captured on the
// authoring platform, and a CI platform runs --update-snapshots on first use.

import { expect, test, type Page } from "@playwright/test";

import { ensureAdmin } from "../fixtures/auth";
import { VIEWPORT_HEIGHT, settle } from "../utils/screenshotMatrix";

const CRITICAL_PAGES: Array<{ name: string; path: string }> = [
  { name: "mainboard", path: "/" },
  { name: "strategy-inline", path: "/strategy" },
  { name: "trading-signal-inline", path: "/trading-signal" },
  { name: "trade-log-inline", path: "/trade-log" },
  { name: "market-data", path: "/market-data" },
  { name: "create-package", path: "/packages/create" },
  { name: "ready-check", path: "/backtest/ready-check" },
  { name: "run-result", path: "/backtest/run" },
];

// Volatile content masked out of the comparison. `time` elements plus
// anything the app marks with data-e2e-volatile (slice boundary allows
// test-id-style attribute additions only).
function masks(page: Page) {
  return [page.locator("time"), page.locator("[data-e2e-volatile]")];
}

test.describe("@visual R2-13 screenshot regression — critical pages", () => {
  test.describe.configure({ mode: "serial" });
  test.setTimeout(5 * 60_000);

  for (const target of CRITICAL_PAGES) {
    test(`visual: ${target.name}`, async ({ page }) => {
      await ensureAdmin(page);
      await page.setViewportSize({ width: 1440, height: VIEWPORT_HEIGHT });
      await page.goto(target.path);
      await settle(page);
      await expect(page).toHaveScreenshot(`${target.name}.png`, {
        fullPage: true,
        animations: "disabled",
        maxDiffPixelRatio: 0.02,
        mask: masks(page),
      });
    });
  }
});
