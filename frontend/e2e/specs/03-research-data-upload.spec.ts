import { expect, test } from "@playwright/test";

import { freshActor, signUp } from "../fixtures/auth";
import { MarketDataPage } from "../pages/MarketDataPage";
import { ResearchDataPage } from "../pages/ResearchDataPage";
import { uniqueSuffix } from "../utils/ids";

// R2-06 (GAP item 8): the DR3 Approved Market Data dependency is server-truth.
// A freshly created (not yet Admin-approved) Market Data dataset can no longer
// even be LINKED — its picker row is disabled ("not eligible — draft") and the
// Create button stays locked, so the old "type an unapproved id and get
// DEPENDENCY_BLOCKED back" flow is impossible by construction. This spec
// exercises the real, unmocked registry against that fail-closed contract.
test.describe("Research Data upload", () => {
  test("locks create behind a server-confirmed approved Market Data link", async ({ page }) => {
    await signUp(page, freshActor("researchdata"));

    const marketData = new MarketDataPage(page);
    await marketData.goto();
    const title = `E2E Linked Market Dataset ${uniqueSuffix()}`;
    await marketData.createDataset({ title });

    const researchData = new ResearchDataPage(page);
    await researchData.goto();

    // The free-text entity-id input is gone and the workflow is locked by
    // default — no text can unlock it.
    await expect(researchData.freeTextMarketInput()).toHaveCount(0);
    await expect(researchData.createButton()).toBeDisabled();

    // The fresh dataset is visible in the picker (registry is newest-first)
    // but NOT selectable: its head revision is draft, not approved.
    await researchData.openMarketPicker();
    await researchData.searchMarketDatasets(title);
    const row = researchData.pickerRow(title);
    await expect(row).toBeVisible();
    await expect(row).toBeDisabled();
    await expect(row).toContainText(/not eligible — /);

    // Nothing was selected, so the lock holds — the server-truth dependency
    // was never confirmed and Create never unlocks.
    await expect(researchData.createButton()).toBeDisabled();
  });
});
