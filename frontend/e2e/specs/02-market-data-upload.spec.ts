import { expect, test } from "@playwright/test";

import { freshActor, signUp } from "../fixtures/auth";
import { MarketDataPage } from "../pages/MarketDataPage";
import { uniqueSuffix } from "../utils/ids";

// Real POST /market-datasets round trip (doc 11 §4) — any authenticated actor
// may propose a dataset. Approval/finalize is a separate Admin-gated chain
// (see README "Honest boundaries") and is out of scope for this journey.
test.describe("Market Data upload", () => {
  test("creates a dataset and it appears in the registry", async ({ page }) => {
    await signUp(page, freshActor("marketdata"));

    const marketData = new MarketDataPage(page);
    await marketData.goto();

    const title = `E2E Market Dataset ${uniqueSuffix()}`;
    const entityId = await marketData.createDataset({ title, instrumentId: "BTCUSDT" });
    expect(entityId).toMatch(/^\S+$/);

    await expect(marketData.registryRow(title)).toBeVisible({ timeout: 15_000 });
  });
});
