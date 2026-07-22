// R2-13 — Playwright screenshot REGRESSION for the critical pages
// (Mainboard, the three standalone working-object workbenches, Market Data,
// Create Package, Ready Check, RUN/Result).
//
// A-01 (audit 22-Jul): these captures navigate DIRECTLY to the standalone
// routes (/strategy, /trading-signal, /trade-log) — they are the standalone
// workbench, NOT the Mainboard inline editor. They were previously named
// "*-inline", which falsely implied inline coverage. They are now named
// "*-standalone" to state exactly what they capture. The authoritative
// INLINE coverage (open "/", invoke Add, expand the Mainboard row, assert the
// URL stays "/", assert the inline editor is mounted) lives in
// specs/08-mainboard-inline-editors.spec.ts (behavioral) and
// specs/12-prototype-capture.spec.ts (prototype reference). This regression
// suite proves the standalone workbenches did not change unexpectedly; it does
// not — and must not be read as — proof of prototype/inline fidelity.
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
  // A-01: honest names — these ARE the standalone workbench routes, not inline.
  { name: "strategy-standalone", path: "/strategy" },
  { name: "trading-signal-standalone", path: "/trading-signal" },
  { name: "trade-log-standalone", path: "/trade-log" },
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
