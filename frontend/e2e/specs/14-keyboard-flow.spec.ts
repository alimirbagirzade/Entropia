// R2-14 — keyboard-only basic flow (GAP madde 16 / roadmap R2-14 görev 2).
//
// Tagged @a11y (runs with `npm run a11y`, excluded from plain `npm test`).
// Drives the REAL stack with the keyboard alone — no mouse clicks after the
// initial page load: login form is reached and submitted via Tab/Enter, the
// Mainboard "+ Add" flow opens via keyboard activation, and Escape dismisses
// the add menu. Every step asserts on real focus state (document.activeElement).

import { expect, test, type Page } from "@playwright/test";

import { ADMIN_ACTOR } from "../fixtures/auth";

async function activeElementInfo(page: Page): Promise<{ tag: string; text: string; label: string }> {
  return page.evaluate(() => {
    const el = document.activeElement as HTMLElement | null;
    return {
      tag: el?.tagName ?? "",
      text: (el?.textContent ?? "").trim().slice(0, 60),
      label: el?.getAttribute("aria-label") ?? "",
    };
  });
}

// Tabs until the predicate matches the focused element, bounded to avoid an
// infinite loop when the target is unreachable by keyboard (that IS the bug
// this spec exists to catch).
async function tabUntil(
  page: Page,
  predicate: (info: { tag: string; text: string; label: string }) => boolean,
  maxTabs = 40,
): Promise<boolean> {
  for (let i = 0; i < maxTabs; i += 1) {
    await page.keyboard.press("Tab");
    const info = await activeElementInfo(page);
    if (predicate(info)) return true;
  }
  return false;
}

test.describe("@a11y keyboard-only basic flow", () => {
  test("login → Mainboard → open + close Add menu with keyboard only", async ({ page }) => {
    test.setTimeout(120_000);
    await page.goto("/login");
    await expect(page.getByText("ENTROPIA")).toBeVisible();

    // Login.tsx autofocuses Username on mount, so a keyboard user lands in the
    // form without pressing anything — assert that instead of tabbing to it
    // (tabbing first would skip PAST the already-focused field).
    const initialFocus = await page.evaluate(
      () => (document.activeElement as HTMLElement | null)?.getAttribute("name") ?? "",
    );
    expect(initialFocus, "Username must be focused on load for keyboard users").toBe("username");
    await page.keyboard.type(ADMIN_ACTOR.username);

    // One Tab from Username must reach Password (no intervening trap).
    await page.keyboard.press("Tab");
    const pw = await page.evaluate(
      () => (document.activeElement as HTMLElement | null)?.getAttribute("name") ?? "",
    );
    expect(pw, "Password must be the next Tab stop after Username").toBe("password");
    await page.keyboard.type(ADMIN_ACTOR.password);
    // Enter inside the form submits it (native submit path, no mouse).
    await page.keyboard.press("Enter");
    await expect(page.getByRole("heading", { name: "Mainboard", exact: true })).toBeVisible({
      timeout: 45_000,
    });

    // "+ Add" must be reachable and operable by keyboard.
    const reachedAdd = await tabUntil(page, (i) => i.tag === "BUTTON" && i.text === "+ Add", 80);
    expect(reachedAdd, '"+ Add" button must be reachable via Tab').toBe(true);
    await page.keyboard.press("Enter");
    await expect(page.getByRole("button", { name: "Add Strategy", exact: true })).toBeVisible();

    // The menu entries themselves must be Tab-reachable.
    const reachedEntry = await tabUntil(
      page,
      (i) => i.tag === "BUTTON" && i.text.startsWith("Add "),
      10,
    );
    expect(reachedEntry, "Add-menu entries must be keyboard reachable").toBe(true);

    // Escape closes the menu without a mouse.
    await page.keyboard.press("Escape");
    await expect(
      page.getByRole("button", { name: "Add Strategy", exact: true }),
    ).toBeHidden({ timeout: 5_000 });
  });
});
