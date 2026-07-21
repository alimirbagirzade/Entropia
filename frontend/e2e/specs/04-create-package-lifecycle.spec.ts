import { expect, test } from "@playwright/test";

import { ensureAdmin, freshActor, signUp } from "../fixtures/auth";
import { CreatePackagePage } from "../pages/CreatePackagePage";

// R2-12 (GAP item 11): the FULL create-package lifecycle in ONE real browser
// journey — request → Pre-Check PASSED → candidate → draft → typed-field
// baseline upload + parse PASSED → validation PASSED → Admin approve →
// published → Library can_use=yes. Every expected state is asserted
// individually; "blocked or error also accepted" is forbidden.
//
// Prerequisites (same stack the golden-path spec 05 uses — see README):
// the seeded canonical ESP resolvers (python `ta.sma`) + at least one ACTIVE
// Rationale Family (regular seed or SEED_E2E_GOLDEN=1), and
// ENTROPIA_BOOTSTRAP_ADMIN_EMAIL matching the ADMIN_ACTOR fixture.
const PINE_SOURCE = [
  "//@version=5",
  'indicator("E2E SMA translate", overlay=true)',
  "fast = ta.sma(close, 14)",
  "plot(fast)",
].join("\n");

const BASELINE_CSV = [
  "time,close,sma",
  "2024-01-01T00:00:00Z,100,99.5",
  "2024-01-01T01:00:00Z,101,100.1",
  "2024-01-01T02:00:00Z,102,100.8",
].join("\n");

test.describe("Create Package lifecycle", () => {
  test("drives a translate request from compose to published + usable in Library", async ({
    page,
    browser,
  }) => {
    // ------------------------------------------------------------------ user
    await signUp(page, freshActor("createpkg"));

    const workspace = new CreatePackagePage(page);
    await workspace.goto();

    // 1. Compose — typed identity fields, PineScript source, declared ta.sma.
    // Exact ordered param types + return are the resolver identity (doc 09
    // §4.2) — the declared line carries the seeded ta.sma contract signature.
    const requestId = await workspace.submitTranslateIndicatorRequest(
      PINE_SOURCE,
      "ta.sma(series,int)->series",
    );
    expect(requestId).toMatch(/^\S+$/);
    await expect(workspace.myRequestsHeading()).toBeVisible();
    await workspace.selectRequest(requestId);

    // 2. Pre-Check must PASS (seeded python ta.sma resolver) — exactly.
    await workspace.runPreCheckExpectPassed();

    // 3. C.D.P: candidate generated + draft package created.
    await workspace.createDraftPackage();
    const packageRootId = await workspace.packageRootId();
    expect(packageRootId.length).toBeGreaterThan(4);

    // 4. Baseline (translate claims equivalence → REQUIRED for approval):
    //    typed metadata fields only — the journey never types JSON.
    await workspace.fillBaselineMetadata({
      provider: "TradingView",
      symbol: "BTCUSDT",
      timeframe: "1h",
      rangeStart: "2024-01-01",
      rangeEnd: "2024-01-02",
      timezone: "UTC",
      settings: "length=14, source=close",
      sourceRevisionContext: "Pine v5 export r1",
    });
    await workspace.uploadBaselineCsv("e2e-baseline.csv", BASELINE_CSV);
    await workspace.runBaselineParseExpectPassed();

    // 5. Validation must PASS — the request becomes eligible for approval.
    await workspace.runValidationExpectPassed();

    // 6. The owner is NOT an Admin: the primary Approve control is replaced by
    //    the fail-closed AdminGate note (R2-09/R2-12) with the waiting reason.
    await expect(page.getByText(/Admin approval required/)).toBeVisible();
    await expect(page.getByText(/awaiting an Admin approval decision/)).toBeVisible();

    // ----------------------------------------------------------------- admin
    const adminContext = await browser.newContext();
    const adminPage = await adminContext.newPage();
    await ensureAdmin(adminPage);

    const adminWorkspace = new CreatePackagePage(adminPage);
    await adminWorkspace.goto();
    // An Admin's "My requests" strip lists every actor's requests (doc 06 §2).
    await adminWorkspace.selectRequest(requestId);
    // 7. Approve & publish — the exact confirmation, not "any response".
    await adminWorkspace.approveExpectPublished();
    await adminContext.close();

    // ------------------------------------------------------- library (owner)
    // 8. The published package is usable: its server-computed can_use flag is
    //    yes in the owner's Package Library detail.
    await page.goto("/packages/library");
    await expect(
      page.getByRole("heading", { name: "Package Library", exact: true }),
    ).toBeVisible();

    const indicatorRows = page.getByRole("list", { name: "Indicator Packages rows" });
    await expect(indicatorRows).toBeVisible({ timeout: 15_000 });

    // Open rows until the detail pins OUR package_root_id, then assert
    // can_use: yes on that exact package (server-computed permission cell).
    const rowCount = await indicatorRows.getByRole("listitem").count();
    let found = false;
    for (let i = 0; i < Math.min(rowCount, 8); i += 1) {
      const row = indicatorRows.getByRole("listitem").nth(i);
      await row.getByRole("button", { name: "Detail" }).click();
      const detail = row.locator(".package-details");
      // Wait for the detail PROJECTION (not just the container) — the "Package"
      // definition row carries the real entity id once loaded.
      await expect(detail.getByText(/\(pkg_/)).toBeVisible({ timeout: 15_000 });
      const detailText = await detail.innerText();
      if (detailText.includes(packageRootId)) {
        await expect(
          detail.locator(".package-meta-cell", { hasText: /^can_use: yes$/ }),
        ).toBeVisible();
        found = true;
        break;
      }
      await row.getByRole("button", { name: "Detail" }).click();
    }
    expect(found, `package ${packageRootId} must be listed with can_use=yes`).toBe(true);
  });
});
