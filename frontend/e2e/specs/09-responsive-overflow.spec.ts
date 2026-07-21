import { expect, test, type Page } from "@playwright/test";

import { ensureAdmin } from "../fixtures/auth";

// R2-11 (GAP item 15): the shared app shell must not impose a minimum width —
// at every audited viewport the document never scrolls horizontally at the
// body level. Inner tables keep their own overflow-x:auto containers; those
// are allowed to scroll WITHIN themselves, never to widen the page. The five
// audit widths come straight from the GAP document (375 / 768 / 1280 / 1440 /
// 1920), and screenshots of the core screens are captured at each width as
// the remediation evidence set.

const WIDTHS = [375, 768, 1280, 1440, 1920] as const;

// Core screens (GAP item 15 evidence set). Panel renders the Admin work
// context for the bootstrap Admin actor ensureAdmin() signs in.
const SCREENS: ReadonlyArray<{ name: string; path: string }> = [
  { name: "mainboard", path: "/" },
  { name: "market-data", path: "/market-data" },
  { name: "panel-management", path: "/panel/management" },
];

async function assertNoBodyOverflow(page: Page, width: number, label: string): Promise<void> {
  const scrollWidth = await page.evaluate(
    () => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth),
  );
  expect(scrollWidth, `${label} @ ${width}px must not overflow horizontally`).toBeLessThanOrEqual(width);
}

test.describe("R2-11 responsive app shell — zero body-level horizontal overflow", () => {
  test.beforeEach(async ({ page }) => {
    await ensureAdmin(page);
  });

  for (const width of WIDTHS) {
    test(`no horizontal overflow at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });

      for (const screen of SCREENS) {
        await page.goto(screen.path);
        // networkidle never settles here (the shell keeps a persistent SSE
        // stream open) — wait for the workspace to mount and paint instead.
        await page.locator("main").waitFor();
        await page.waitForTimeout(600);
        await assertNoBodyOverflow(page, width, screen.name);
        await page.screenshot({
          path: `test-results/responsive/${screen.name}-${width}.png`,
          fullPage: true,
        });
      }

      // TS inline editor: mount an unsaved Trading Signal draft row through the
      // Mainboard "+ Add" menu (R2-01b inline panel) and re-audit the width.
      await page.goto("/");
      await page.locator("main").waitFor();
      await page.getByRole("button", { name: "+ Add" }).click();
      await page.getByRole("button", { name: "Add Outsource Signal" }).click();
      await page.getByRole("menuitem", { name: "Trading Signal" }).click();
      await expect(page.getByRole("group", { name: "Trading Signal draft" })).toBeVisible();
      await assertNoBodyOverflow(page, width, "ts-inline");
      await page.screenshot({
        path: `test-results/responsive/ts-inline-${width}.png`,
        fullPage: true,
      });
    });
  }

  test("mobile hamburger menu is usable at 375px", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/");
    // Desktop menu bar is replaced by the hamburger disclosure…
    const hamburger = page.getByRole("button", { name: /Menu/ });
    await expect(hamburger).toBeVisible();
    await expect(hamburger).toHaveAttribute("aria-expanded", "false");
    // …which opens an in-flow expanded tree of every menu group…
    await hamburger.click();
    await expect(hamburger).toHaveAttribute("aria-expanded", "true");
    const primaryNav = page.getByRole("navigation", { name: "Primary" });
    await expect(primaryNav.getByRole("link", { name: "Market Data" })).toBeVisible();
    await assertNoBodyOverflow(page, 375, "open-mobile-menu");
    // …and navigating from it closes the drawer.
    await primaryNav.getByRole("link", { name: "Market Data" }).click();
    await expect(page).toHaveURL(/\/market-data$/);
    await expect(hamburger).toHaveAttribute("aria-expanded", "false");
  });
});
