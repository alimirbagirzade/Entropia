import { expect, test } from "@playwright/test";

import { ensureAdmin, freshActor, signUp } from "../fixtures/auth";
import { MarketDataPage } from "../pages/MarketDataPage";
import { uniqueSuffix } from "../utils/ids";

// KALAN-A (video 9:24–12:37): the raw source file selected in the browser is
// what STARTS the process. ONE submit chains create -> real multipart upload ->
// finalize -> durable analysis (202); the detail then polls until the REAL
// analysis job lands the revision on `verified`; an Admin approves it in a
// second browser context and the approved-bundle resolve pins the exact
// revision. Every expected state is asserted individually — no "blocked or
// error also accepted".
test.describe("Market Data upload", () => {
  test("Browse File starts the full ingest: upload → analysis → verified → Admin approve → bundle", async ({
    page,
    browser,
  }) => {
    await signUp(page, freshActor("marketdata"));

    const marketData = new MarketDataPage(page);
    await marketData.goto();

    const title = `E2E Market Dataset ${uniqueSuffix()}`;
    const entityId = await marketData.createDataset({ title, instrumentId: "BTCUSDT" });
    expect(entityId).toMatch(/^\S+$/);

    // The chained submit reached the durable analysis admission (202).
    await marketData.expectIngestStarted();
    await expect(marketData.registryRow(title)).toBeVisible({ timeout: 15_000 });

    // The auto-opened detail polls while ANALYZING; the real job parses the
    // transferred bytes and lands the revision on VERIFIED (validation pass).
    await marketData.waitForRevisionState("verified");

    // ----------------------------------------------------------------- admin
    const adminContext = await browser.newContext();
    const adminPage = await adminContext.newPage();
    await ensureAdmin(adminPage);

    const adminMarketData = new MarketDataPage(adminPage);
    await adminMarketData.goto();
    await adminMarketData.openFromRegistry(title);
    await adminMarketData.approveHeadRevision();
    await adminContext.close();

    // ------------------------------------------------------- owner resolve
    // The owner's detail reflects APPROVED and the resolve-probe pins the
    // exact approved revision (never "latest").
    await marketData.openFromRegistry(title);
    await marketData.waitForRevisionState("approved", 30_000);
    await marketData.resolveApprovedBundle();
  });
});
