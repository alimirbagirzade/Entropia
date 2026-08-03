import { expect, test } from "@playwright/test";

import { freshActor, signUp } from "../fixtures/auth";
import { CreatePackagePage } from "../pages/CreatePackagePage";

// G-04: Request Validation driven from the PACKAGE LIBRARY, in one real browser
// journey — draft package → Library detail → Request Validation → durable worker →
// PASSED → Request Approval becomes available.
//
// Spec 04 already proves the Create Package plane can validate. The point of THIS
// journey is that the Library plane reaches the SAME pipeline: validation is never
// started from the request workspace here, yet the package ends up certified and
// approval-eligible. If the Library action were a second certification path (or a
// silent no-op), this journey would either fail or leave approval unavailable.
//
// Prerequisites are spec 04's: the seeded canonical ESP resolvers (python `ta.sma`)
// and at least one ACTIVE Rationale Family (regular seed or SEED_E2E_GOLDEN=1).
const PINE_SOURCE = [
  "//@version=5",
  'indicator("E2E library validation", overlay=true)',
  "fast = ta.sma(close, 14)",
  "plot(fast)",
].join("\n");

const BASELINE_CSV = [
  "time,close,sma",
  "2024-01-01T00:00:00Z,100,99.5",
  "2024-01-01T01:00:00Z,101,100.1",
  "2024-01-01T02:00:00Z,102,100.8",
].join("\n");

// Open Indicator rows until the detail panel pins OUR package root, and return that
// panel. Mirrors spec 04's walk — the catalog is server-ordered, so the row index is
// never assumed.
async function openOwnPackageDetail(page: import("@playwright/test").Page, rootId: string) {
  const rows = page.getByRole("list", { name: "Indicator Packages rows" });
  await expect(rows).toBeVisible({ timeout: 15_000 });
  const rowCount = await rows.getByRole("listitem").count();
  for (let i = 0; i < Math.min(rowCount, 8); i += 1) {
    const row = rows.getByRole("listitem").nth(i);
    await row.getByRole("button", { name: "Detail" }).click();
    const detail = row.locator(".package-details");
    await expect(detail.getByText(/\(pkg_/)).toBeVisible({ timeout: 15_000 });
    if ((await detail.innerText()).includes(rootId)) return detail;
    await row.getByRole("button", { name: "Detail" }).click();
  }
  throw new Error(`package ${rootId} was not listed in the Indicator catalog`);
}

test.describe("Package Library — Request Validation", () => {
  // Three durable jobs run before the Library action even starts (Pre-Check scan,
  // candidate generation, baseline parse), and the validation run is a fourth. The
  // shared 90s budget cannot hold four cold worker round-trips, so it is raised here
  // for the same reason spec 04 raises it.
  test.setTimeout(300_000);

  test("certifies a draft package from the Library and unlocks Request Approval", async ({
    page,
  }) => {
    await signUp(page, freshActor("libval"));

    // ------------------------------------------------- draft package (setup only)
    const workspace = new CreatePackagePage(page);
    await workspace.goto();
    const requestId = await workspace.submitTranslateIndicatorRequest(
      PINE_SOURCE,
      "ta.sma(series,int)->series",
    );
    await workspace.selectRequest(requestId);
    await workspace.runPreCheckExpectPassed();
    await workspace.createDraftPackage();
    const packageRootId = await workspace.packageRootId();
    expect(packageRootId.length).toBeGreaterThan(4);

    // A translate request claims equivalence, so the baseline is required evidence
    // before the seven mandatory checks can pass.
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
    await workspace.uploadBaselineCsv("e2e-libval-baseline.csv", BASELINE_CSV);
    await workspace.runBaselineParseExpectPassed();

    // Deliberately NOT validated here. The Library must be able to start it.

    // ------------------------------------------------------------- library plane
    await page.goto("/packages/library");
    await expect(
      page.getByRole("heading", { name: "Package Library", exact: true }),
    ).toBeVisible();
    const detail = await openOwnPackageDetail(page, packageRootId);

    // The server advertises the capability — and now something can actually use it.
    await expect(
      detail.locator(".package-meta-cell", { hasText: /^can_request_validation: yes$/ }),
    ).toBeVisible();

    // Idle → confirm → submit.
    await detail.getByRole("button", { name: "Request Validation" }).click();
    await detail.getByRole("button", { name: "Confirm request validation" }).click();

    // The admission is durable and names both planes' identifiers.
    const status = detail.getByRole("status", { name: "Validation run status" });
    await expect(status).toBeVisible({ timeout: 30_000 });
    await expect(status).toContainText(/attempt \d+/, { timeout: 30_000 });

    // The worker carries it to PASSED — asserted exactly, never "passed or failed".
    await expect(status).toContainText("this revision is certified", { timeout: 180_000 });
    // Passing is not approval: the panel says so in the same breath.
    await expect(status).toContainText("passing does not approve or publish anything");

    // --------------------------------------------- approval is now the next step
    // A reload proves the verdict is durable server state, not a live-region artifact
    // ("refresh does not stop it", doc 08 §7).
    await page.reload();
    const reopened = await openOwnPackageDetail(page, packageRootId);
    await expect(
      reopened.locator(".package-meta-cell", { hasText: /^can_request_approval: yes$/ }),
    ).toBeVisible({ timeout: 30_000 });
    await expect(reopened.getByRole("button", { name: "Request Approval" })).toBeVisible();
  });
});
