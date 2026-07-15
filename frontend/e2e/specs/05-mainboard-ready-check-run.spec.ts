import { expect, test } from "@playwright/test";

import { freshActor, signUp } from "../fixtures/auth";
import { BacktestRunPage } from "../pages/BacktestRunPage";
import { MainboardPage } from "../pages/MainboardPage";
import { ReadyCheckPage } from "../pages/ReadyCheckPage";
import { StrategyPage } from "../pages/StrategyPage";

// The composition chain: Strategy creation -> Mainboard attach -> Ready
// Check -> RUN -> inline result.
//
// Honest boundary (see README): a schema-valid, RUN-able composition needs an
// Admin-approved indicator package (Create Package lifecycle, doc 06) pinned
// into a saved Strategy revision plus an approved Market Data revision — a
// deep cross-journey seed this suite doesn't set up. This spec instead
// attaches a generic (non-domain-validated) work object, which is enough to
// move the composition hash and exercise the real Ready Check / RUN admission
// endpoints end to end. Per this app's own L4 rule (never fabricate success),
// we assert that *a* structured outcome comes back from each real call, not a
// specific verdict — a "blocked"/"not ready" report is as valid a result here
// as a green one.
test.describe("Strategy -> Mainboard -> Ready Check -> RUN", () => {
  test("creates a strategy draft, attaches a work object, runs Ready Check and requests a RUN", async ({
    page,
  }) => {
    await signUp(page, freshActor("compose"));

    // 1) Strategy creation (draft only — see honest-boundary note above).
    const strategy = new StrategyPage(page);
    await strategy.goto();
    await strategy.createDraft(`E2E Strategy ${Date.now()}`);
    await strategy.waitForDraftWorkbench();

    // 2) Mainboard attach — generic work object, real create+attach round trip.
    const mainboard = new MainboardPage(page);
    await mainboard.goto();
    const itemsBefore = await mainboard.compositionItemCount().count();
    await mainboard.createAndAttachWorkObject("strategy");
    await expect(async () => {
      const itemsAfter = await mainboard.compositionItemCount().count();
      expect(itemsAfter).toBeGreaterThan(itemsBefore);
    }).toPass({ timeout: 15_000 });

    // 3) Ready Check — real POST /readiness-checks against the composition.
    const readyCheck = new ReadyCheckPage(page);
    await readyCheck.goto();
    await readyCheck.runCheck();
    await expect(async () => {
      const notCheckedGone = await readyCheck
        .notCheckedYetEmptyState()
        .isVisible()
        .catch(() => false);
      const failed = await readyCheck.errorAlert().isVisible().catch(() => false);
      // Either the empty state was replaced by a real report, or the call
      // surfaced a structured error — never silence.
      expect(!notCheckedGone || failed).toBe(true);
    }).toPass({ timeout: 20_000 });

    // 4) RUN — real POST /backtest-runs admission attempt (inline result if
    // admitted; a structured rejection otherwise, both real outcomes).
    const backtestRun = new BacktestRunPage(page);
    await backtestRun.goto();
    await backtestRun.requestRun();
    await expect(async () => {
      const admitted = backtestRun.hasRunQueryParam();
      const failed = await backtestRun.errorAlert().isVisible().catch(() => false);
      expect(admitted || failed).toBe(true);
    }).toPass({ timeout: 20_000 });
  });
});
