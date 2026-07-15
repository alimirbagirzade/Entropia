import { expect, test } from "@playwright/test";

import { ensureAdmin } from "../fixtures/auth";
import { MainboardPage } from "../pages/MainboardPage";
import { TrashPage } from "../pages/TrashPage";

// Real Admin-only Trash flow (doc 20): soft-delete a work object from the
// Mainboard (produces a real Trash entry), find it, then run the two-step,
// re-auth-gated Permanent Delete (purge) composer. Purge is itself only a
// 202 admission — the actual purge runs asynchronously on a worker — so we
// assert the "accepted" toast (doc 20 §9 copy, verbatim) rather than a
// terminal purged state.
test.describe("Trash — soft-delete then re-auth purge", () => {
  test("moves a work object to Trash and requests its permanent deletion", async ({ page }) => {
    await ensureAdmin(page);

    const mainboard = new MainboardPage(page);
    await mainboard.goto();
    const rootId = await mainboard.createAndAttachWorkObject("strategy");
    await mainboard.deleteLastItem();

    const trash = new TrashPage(page);
    await trash.goto();
    await trash.search(rootId);

    const row = trash.rowByName(rootId);
    await expect(row).toBeVisible({ timeout: 20_000 });

    await trash.openPurgeComposer(row);
    await trash.confirmPurge(rootId, "e2e-admin-reauth-proof");

    await expect(trash.purgeAcceptedToast()).toBeVisible({ timeout: 20_000 });
  });
});
