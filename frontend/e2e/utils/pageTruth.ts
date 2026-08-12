import { expect, type Page } from "@playwright/test";

import { apiGet, readSessionToken } from "./api";

// A page is "covered" only when BOTH halves hold (audit TEST-08): the heading
// rendered AND the protected query behind it actually succeeded on the server.
// Asserting the heading alone is the vacuous-green failure mode this suite had
// on 12 pages — they were screenshotted and axe-scanned, never exercised, and
// a page whose data query returns 401/403/500 still renders its <h1>.
export interface PageContract {
  /** Route the browser navigates to. */
  route: string;
  /** Exact page-title text (the app renders one per page). */
  heading: string;
  /**
   * Heading level, defaulting to h1. **No route sets it today** — `/user-manual`
   * was the sole divergence (`<h2 class="page-title">`) and ADIM 48 promoted it
   * to `<h1>` (K-4). Kept as the declared escape hatch so a future divergence is
   * stated in the contract rather than assumed by the assertion.
   */
  level?: 1 | 2;
  /**
   * The protected read the page's own data actually comes from. Omitted only
   * where the page's endpoint answers to a DIFFERENT credential than the browser
   * session, so a session-token cross-check would assert the wrong contract
   * (`/metrics` is a credentialed scrape endpoint — finding O-22).
   */
  api?: string;
  /**
   * A structural anchor proving the page rendered its PROJECTION, not just its
   * chrome: a column header, a landmark region, a tab, an explicit empty state.
   * Given as a callback so each page picks the locator that fits its shape.
   */
  projection: (page: Page) => ReturnType<Page["locator"]>;
}

export async function assertPageIsRealAndServed(
  page: Page,
  contract: PageContract,
): Promise<void> {
  await page.goto(contract.route);

  const level = contract.level ?? 1;
  await expect(
    page.getByRole("heading", { name: contract.heading, exact: true, level }),
  ).toBeVisible({ timeout: 30_000 });

  // Server truth, carried by the very token the browser holds.
  const token = await readSessionToken(page);
  expect(token, `${contract.route}: browser holds no session token`).toBeTruthy();
  if (contract.api) {
    const response = await apiGet(page, contract.api, token);
    expect(
      response.status(),
      `${contract.route}: ${contract.api} did not serve the page's data`,
    ).toBe(200);
  }

  await expect(contract.projection(page).first()).toBeVisible({ timeout: 30_000 });
}
