// R2-13 — Playwright screenshot REGRESSION across EVERY audited route.
//
// Coverage (RC §6.7 / P11-2, 2026-08-11): this suite used to assert eight
// hand-listed pages while the a11y scan, the keyboard probes and the human
// review all walked twenty-three. The other fifteen had no pixel protection at
// all, and nothing in the file said so — a reader saw a green "visual gate" and
// reasonably assumed it covered the product. The page list is therefore no
// longer written here: it is derived from
// utils/screenshotMatrix.ts::TARGET_PAGES, the same single source the
// screenshot matrix (specs/10), the axe scan (specs/13) and the keyboard
// prechecks (specs/20) already read. A route added there is asserted here on
// the next run instead of being silently uncovered; a second hand-maintained
// list could only drift back apart.
//
// Snapshot names are the TARGET_PAGES slugs, so a baseline file, a matrix
// capture (screenshots/baseline/<slug>/) and a prototype reference
// (screenshots/prototype/<slug>--1440.png) all name the same page. Five of the
// original eight were renamed by that rule: strategy-standalone ->
// strategy-details, trading-signal-standalone -> trading-signal,
// trade-log-standalone -> trade-log, run-result -> run-results (mainboard,
// market-data, create-package and ready-check already matched).
//
// A-01 (audit 22-Jul) still holds, and the rename does not weaken it: the
// /strategy, /trading-signal and /trade-log captures navigate DIRECTLY to the
// standalone routes — they are the standalone workbench, NOT the Mainboard
// inline editor. (The names they carried before A-01 were "*-inline", which
// falsely implied inline coverage; a doc-numbered slug implies neither.) The
// authoritative INLINE coverage (open "/", invoke Add, expand the Mainboard
// row, assert the URL stays "/", assert the inline editor is mounted) lives in
// specs/08-mainboard-inline-editors.spec.ts (behavioral) and
// specs/12-prototype-capture.spec.ts (prototype reference). This regression
// suite proves the routes did not change unexpectedly; it does not — and must
// not be read as — proof of prototype/inline fidelity. What the pixels DO and
// do NOT mean is recorded in docs/implementation/v18_visual_deviations.md:
// several of these pages deviate from the v18 mockup by signed decision (D-1),
// and freezing them here freezes the deviation too, not an endorsement of it.
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
// Platform note (RC §6.7 / P11-3, revised 2026-08-11): toHaveScreenshot
// snapshots are platform-suffixed (…-chromium-linux.png / …-chromium-darwin.png)
// and Playwright only ever compares against the suffix of the RUNNING platform.
// Every runs-on: in .github/workflows is ubuntu-latest, so ONLY the -linux set
// is committed, and scripts/visual-baseline-platform-gate.sh keeps it that way.
// An eight-file -darwin set used to be committed beside it; no job asserted it,
// and when it was finally measured six of the eight no longer matched what the
// app renders on darwin (height deltas 44–539 px). They were deleted rather
// than refreshed: a baseline nothing asserts does not protect these pages, it
// only looks like it does. Running this suite on macOS therefore reports
// MISSING snapshots — the honest answer — and CI never runs
// --update-snapshots. Adding a platform means adding a job that runs it first.

import { expect, test, type Page } from "@playwright/test";

import { ensureAdmin } from "../fixtures/auth";
import { TARGET_PAGES, VIEWPORT_HEIGHT, settle } from "../utils/screenshotMatrix";

// Volatile content masked out of the comparison. `time` elements plus
// anything the app marks with data-e2e-volatile (slice boundary allows
// test-id-style attribute additions only).
function masks(page: Page) {
  return [page.locator("time"), page.locator("[data-e2e-volatile]")];
}

test.describe("@visual R2-13 screenshot regression — every audited route", () => {
  // NOT `mode: "serial"`. Execution is already sequential (playwright.config.ts
  // sets fullyParallel:false + workers:1) and the tests share nothing — each one
  // gets its own context and does its own ensureAdmin — so serial bought no
  // isolation. What it did buy was silence: on a failure it SKIPS the rest of
  // the group, so one regressed page reported the other twenty-two as "skipped"
  // and the gate could not say which pages were actually still good. At eight
  // pages that was a wart; at twenty-three it would defeat the point of widening
  // the coverage. Independent tests also retry only the page that failed rather
  // than replaying the whole group.
  test.setTimeout(5 * 60_000);

  for (const target of TARGET_PAGES) {
    test(`visual: ${target.slug}`, async ({ page }) => {
      // Admin for every route, not just the adminOnly ones: the three admin
      // pages need it, and using one actor everywhere keeps the captures
      // comparable (a plain user sees a different nav and different row
      // actions). This is the pattern the original eight already used.
      await ensureAdmin(page);
      await page.setViewportSize({ width: 1440, height: VIEWPORT_HEIGHT });
      await page.goto(target.path);
      await settle(page);
      await expect(page).toHaveScreenshot(`${target.slug}.png`, {
        fullPage: true,
        animations: "disabled",
        maxDiffPixelRatio: 0.02,
        mask: masks(page),
      });
    });
  }
});
