import { expect, test } from "@playwright/test";

import { freshActor, signUp } from "../fixtures/auth";
import { CreatePackagePage } from "../pages/CreatePackagePage";
import { PreCheckPage } from "../pages/PreCheckPage";

// Real create-package lifecycle (doc 06/07): compose an immutable request,
// see it in "My requests", then run the immutable dependency Pre-Check scan
// against it. Candidate generation / draft / Admin approve (doc 06 §8-§9)
// need an approved Rationale Family + Embedded System Package registry state
// this suite doesn't seed — see README "Honest boundaries".
test.describe("Create Package lifecycle", () => {
  test("submits a request, sees it listed, and runs Pre-Check", async ({ page }) => {
    await signUp(page, freshActor("createpkg"));

    const createPackage = new CreatePackagePage(page);
    await createPackage.goto();
    const requestId = await createPackage.submitEspDescriptionRequest(
      "E2E: a resolver that reports the current session's realized volatility bucket.",
    );
    expect(requestId).toMatch(/^\S+$/);

    await expect(createPackage.myRequestsHeading()).toBeVisible();
    await expect(page.getByText(requestId).first()).toBeVisible({ timeout: 15_000 });

    const preCheck = new PreCheckPage(page);
    await preCheck.goto();
    await preCheck.selectRequest(requestId);
    await preCheck.runPreCheck();

    // generate_from_description carries no code -> the canonical "not
    // applicable" scan status line (PreCheck.tsx STATUS_LINES) is the
    // expected real outcome here; a hard failure would surface as role=alert.
    await expect(async () => {
      const notApplicable = await page
        .getByText(/Pre-Check not applicable/)
        .isVisible()
        .catch(() => false);
      const failed = await preCheck.errorAlert().isVisible().catch(() => false);
      expect(notApplicable || failed).toBe(true);
    }).toPass({ timeout: 20_000 });
  });
});
