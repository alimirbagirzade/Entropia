import { expect, test } from "@playwright/test";

import { ensureAdmin } from "../fixtures/auth";
import { apiGet, readSessionToken } from "../utils/api";

// Doc 22 Future-Dev boundary, asserted as a POSITIVE contract.
//
// "Bu belge Live Trade, Graphic View renderer, Backtest Review, Signal
// Intelligence, Regime Research, Hypothesis Lab veya Parameter Fields'in aktif
// ürün modüllerini bugün implement etmez" — the placeholders must stay honest
// placeholders. A regression here is silent and expensive: a capability that
// flips to operational without its published feature definitions would let the
// product advertise analysis it cannot actually compute.
//
// This is also the E2E-level record of the I-02 REGIME_TABLE decision: Regime
// Research is a Future-Dev slot with no engine behind it, which is exactly why
// no REGIME_TABLE result artifact was added (spec 18 asserts the other half —
// asking for one is a hard rejection, not an empty page).
interface Capability {
  capability_key: string;
  lifecycle_state: string;
  is_operational: boolean;
  menu_path?: string;
}

const FUTURE_DEV_KEYS = [
  "regime_research",
  "hypothesis_lab",
  "parameter_fields",
  "backtest_review",
  "signal_intelligence",
];

test.describe("Future Dev boundary: placeholders stay honest (doc 22)", () => {
  test("every Future-Dev capability is registered but NOT operational", async ({ page }) => {
    test.setTimeout(120_000);
    await ensureAdmin(page);
    const token = await readSessionToken(page);
    expect(token).toBeTruthy();

    const response = await apiGet(page, "/capabilities", token);
    expect(response.status()).toBe(200);
    // lib/capability.ts::CapabilityListResponse — `capabilities`, not `data`.
    const body = (await response.json()) as { capabilities?: Capability[]; count?: number };
    const capabilities = body.capabilities ?? [];
    expect(capabilities.length, "capability registry is empty — seed missing?").toBeGreaterThan(0);

    const byKey = new Map(capabilities.map((c) => [c.capability_key, c]));
    for (const key of FUTURE_DEV_KEYS) {
      const capability = byKey.get(key);
      expect(capability, `${key} is not registered in the capability matrix`).toBeTruthy();
      // The whole point of the boundary: registered, discoverable, and inert.
      expect(
        capability?.is_operational,
        `${key} reports operational — doc 22 says V18 ships it as a placeholder only`,
      ).toBe(false);
    }
  });

  test("the Future Dev page renders the registry rather than an empty shell", async ({ page }) => {
    test.setTimeout(120_000);
    await ensureAdmin(page);

    await page.goto("/future-dev");
    await expect(page.getByRole("heading", { name: "Future Dev", exact: true })).toBeVisible({
      timeout: 30_000,
    });
    // Scope to the registry SECTION. An unscoped getByText("Regime Research")
    // resolves to the collapsed nav link (<a href="/future-dev/regime-research">),
    // which is hidden — the page-level match is the sidebar, not the projection.
    const registry = page.getByRole("region", { name: "Capabilities" });
    await expect(registry).toBeVisible({ timeout: 30_000 });
    // The seeded rows a user actually sees: title + the machine key beside it.
    await expect(registry.getByRole("cell", { name: /Regime Research/ })).toBeVisible({
      timeout: 30_000,
    });
    await expect(registry.getByRole("cell", { name: /Hypothesis Lab/ })).toBeVisible();
    // And the boundary is visible ON the page, not only in the API: the
    // "Operational" column reads "no" for the Regime Research row.
    const regimeRow = registry.getByRole("row", { name: /Regime Research/ });
    await expect(regimeRow.getByRole("cell", { name: "no", exact: true })).toBeVisible();
  });
});
