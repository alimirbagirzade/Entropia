// R2-13 — 22-page × state × width screenshot matrix (GAP madde 16,
// Implementation Spec PART IV "Visual regression and responsive coverage").
//
// This spec is a CAPTURE TOOL, not an assertion suite: it produces the
// versioned baseline tree under frontend/e2e/screenshots/baseline/
// (<page-slug>/<state>--<width>.png) against the live seeded stack.
// Run it explicitly:
//
//   npm run screenshots        # only this spec (grep @screenshots)
//
// States:
//   normal            admin actor + seeded DB, all 22 pages, 1280/1440/1920
//                     (+375/768 for Mainboard and the three inline-editor rows)
//   empty             brand-new plain user (no data), data pages @1440
//   loading           API responses stalled via route interception @1440
//   error             API responses forced to 500 envelope @1440
//   permission-denied plain user on adminOnly pages @1440
//
// Honest boundaries:
//   • "loading" is frozen deterministically by stalling the API route, not by
//     racing a real response — it shows the genuine loading UI the app renders
//     while a request is in flight.
//   • "empty" reflects a fresh user against the shared seeded DB: pages whose
//     queries are user-scoped render truly empty; globally-scoped registries
//     (e.g. Package Library) may legitimately still show seeded rows. The
//     capture records what the product actually does — it does not fake
//     emptiness.

import { test } from "@playwright/test";

import { ensureAdmin, freshActor, signUp } from "../fixtures/auth";
import {
  ADMIN_ONLY_SLUGS,
  DATA_PAGE_SLUGS,
  DESKTOP_WIDTHS,
  MOBILE_WIDTHS,
  TARGET_PAGES,
  VIEWPORT_HEIGHT,
  settle,
  shotPath,
} from "../utils/screenshotMatrix";

test.describe("@screenshots R2-13 screenshot matrix", () => {
  // Full matrix in one worker against one login session per state group.
  test.describe.configure({ mode: "serial" });
  test.setTimeout(20 * 60_000);

  test("normal state — all 22 pages at desktop (+mobile) widths", async ({ page }) => {
    await ensureAdmin(page);
    for (const target of TARGET_PAGES) {
      const widths: number[] = [...DESKTOP_WIDTHS, ...(target.mobile ? MOBILE_WIDTHS : [])];
      for (const width of widths) {
        await page.setViewportSize({ width, height: VIEWPORT_HEIGHT });
        await page.goto(target.path);
        await settle(page);
        await page.screenshot({ path: shotPath(target.slug, "normal", width), fullPage: true });
      }
    }
  });

  test("empty state — fresh user, data pages @1440", async ({ page }) => {
    await signUp(page, freshActor("shot_empty"));
    await page.setViewportSize({ width: 1440, height: VIEWPORT_HEIGHT });
    for (const slug of DATA_PAGE_SLUGS) {
      const target = TARGET_PAGES.find((p) => p.slug === slug)!;
      await page.goto(target.path);
      await settle(page);
      await page.screenshot({ path: shotPath(slug, "empty", 1440), fullPage: true });
    }
  });

  test("permission-denied state — plain user on adminOnly pages @1440", async ({ page }) => {
    await signUp(page, freshActor("shot_perm"));
    await page.setViewportSize({ width: 1440, height: VIEWPORT_HEIGHT });
    for (const slug of ADMIN_ONLY_SLUGS) {
      const target = TARGET_PAGES.find((p) => p.slug === slug)!;
      await page.goto(target.path);
      await settle(page);
      await page.screenshot({ path: shotPath(slug, "permission-denied", 1440), fullPage: true });
    }
  });

  test("loading state — stalled API, data pages @1440", async ({ page }) => {
    await ensureAdmin(page);
    await page.setViewportSize({ width: 1440, height: VIEWPORT_HEIGHT });
    for (const slug of DATA_PAGE_SLUGS) {
      const target = TARGET_PAGES.find((p) => p.slug === slug)!;
      // Stall every subsequent API call so the page freezes in its loading UI.
      // Auth/session must still resolve or the shell redirects to /login.
      await page.route("**/api/v1/**", async (route) => {
        const url = route.request().url();
        if (url.includes("/auth/")) return route.continue();
        await new Promise((r) => setTimeout(r, 120_000));
        return route.abort();
      });
      await page.goto(target.path, { waitUntil: "domcontentloaded" });
      await page.waitForTimeout(1_200);
      await page.screenshot({ path: shotPath(slug, "loading", 1440), fullPage: true });
      await page.unroute("**/api/v1/**");
    }
  });

  test("error state — forced 500 envelope, data pages @1440", async ({ page }) => {
    await ensureAdmin(page);
    await page.setViewportSize({ width: 1440, height: VIEWPORT_HEIGHT });
    for (const slug of DATA_PAGE_SLUGS) {
      const target = TARGET_PAGES.find((p) => p.slug === slug)!;
      await page.route("**/api/v1/**", (route) => {
        const url = route.request().url();
        if (url.includes("/auth/")) return route.continue();
        return route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({
            error: { code: "INTERNAL_ERROR", message: "Injected E2E failure (R2-13 error-state capture)" },
          }),
        });
      });
      await page.goto(target.path, { waitUntil: "domcontentloaded" });
      await settle(page);
      await page.screenshot({ path: shotPath(slug, "error", 1440), fullPage: true });
      await page.unroute("**/api/v1/**");
    }
  });
});
