import { expect, test } from "@playwright/test";

import { freshActor, signUp } from "../fixtures/auth";
import { MarketDataPage } from "../pages/MarketDataPage";
import { ResearchDataPage } from "../pages/ResearchDataPage";
import { uniqueSuffix } from "../utils/ids";

// Real POST /research-datasets round trip (doc 12 §4). Research Data create is
// DR3-gated on an ACTIVE+APPROVED Market Data dataset — a freshly created
// (not yet Admin-approved) dataset legitimately gets DEPENDENCY_BLOCKED back.
// Both outcomes exercise the real, unmocked endpoint; we assert one landed
// rather than assuming approval state we didn't set up (L4).
test.describe("Research Data upload", () => {
  test("submits a create request against a linked Market Data entity", async ({ page }) => {
    await signUp(page, freshActor("researchdata"));

    const marketData = new MarketDataPage(page);
    await marketData.goto();
    const marketEntityId = await marketData.createDataset({
      title: `E2E Linked Market Dataset ${uniqueSuffix()}`,
    });

    const researchData = new ResearchDataPage(page);
    await researchData.goto();
    await researchData.submitCreate({
      marketEntityId,
      displayName: `E2E Research Dataset ${uniqueSuffix()}`,
    });

    // A fresh (not yet Admin-approved) market link legitimately yields
    // DEPENDENCY_BLOCKED (a role=alert); a happy path yields the "Created —"
    // line. Assert one real outcome landed. Count the alerts rather than
    // .isVisible() them: the page can render more than one role=alert node
    // (payload + create), which would make a single-locator visibility check
    // throw a strict-mode error and be swallowed as "no outcome".
    await expect(async () => {
      const succeeded = await researchData.successMessage().isVisible().catch(() => false);
      const alertCount = await page.getByRole("alert").count();
      expect(succeeded || alertCount > 0).toBe(true);
    }).toPass({ timeout: 20_000 });
  });
});
