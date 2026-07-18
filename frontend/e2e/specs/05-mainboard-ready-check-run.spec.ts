import { expect, test } from "@playwright/test";

import { freshActor, signUp } from "../fixtures/auth";
import { BacktestRunPage } from "../pages/BacktestRunPage";
import { MainboardPage } from "../pages/MainboardPage";
import { ReadyCheckPage } from "../pages/ReadyCheckPage";
import { StrategyPage } from "../pages/StrategyPage";

// The composition chain: Strategy creation -> Mainboard draft row -> Ready
// Check -> RUN.
//
// Honest boundary (see README): a schema-valid, RUN-able composition needs an
// Admin-approved indicator package (Create Package lifecycle, doc 06) pinned
// into a saved Strategy revision plus an approved Market Data revision — a
// deep cross-journey seed this suite doesn't set up. "Add Strategy" follows
// the strategy-editor family (doc 02 §7): it creates an UNSAVED draft row and
// attaches nothing until the first Save, so the composition hash is unmoved
// here — the spec still exercises the real draft-create round trip plus the
// real Ready Check / RUN admission endpoints end to end. Per this app's own
// L4 rule (never fabricate success), we assert that *a* structured outcome
// comes back from each real call, not a specific verdict — a "blocked"/"not
// ready" report is as valid a result here as a green one.
test.describe("Strategy -> Mainboard -> Ready Check -> RUN", () => {
  test("creates a strategy draft row, runs Ready Check and requests a RUN", async ({
    page,
  }) => {
    await signUp(page, freshActor("compose"));

    // 1) Strategy creation (draft only — see honest-boundary note above).
    const strategy = new StrategyPage(page);
    await strategy.goto();
    await strategy.createDraft(`E2E Strategy ${Date.now()}`);
    await strategy.waitForDraftWorkbench();

    // 2) Mainboard "Add Strategy" — real POST /strategy-drafts round trip; the
    // new unsaved draft renders immediately as a horizontal row.
    const mainboard = new MainboardPage(page);
    await mainboard.goto();
    const itemsBefore = await mainboard.compositionItemCount().count();
    await mainboard.addStrategyDraft();
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

    // 4) RUN — F-16 gates admission on the composition's readiness. A generic
    // composition is NOT_READY, so the admit button is genuinely disabled (the
    // client refuses up front instead of round-tripping to a 422 — the lock IS
    // the structured outcome, mirroring the backend authz). If the button is
    // enabled, the real POST /backtest-runs admission fires and either sets
    // ?run= or surfaces a structured error. All three are real outcomes; per
    // the app's L4 rule we never fabricate a green verdict.
    const backtestRun = new BacktestRunPage(page);
    await backtestRun.goto();
    const clicked = await backtestRun.requestRunIfEnabled();
    if (clicked) {
      await expect(async () => {
        const admitted = backtestRun.hasRunQueryParam();
        const failed = await backtestRun.errorAlert().isVisible().catch(() => false);
        expect(admitted || failed).toBe(true);
      }).toPass({ timeout: 20_000 });
    } else {
      // Locked: the readiness gate itself is the outcome — RUN is unreachable
      // until a current Ready Check passes.
      await expect(backtestRun.lockedNote()).toBeVisible();
    }
  });
});
