import { expect, test } from "@playwright/test";

import { ensureAdmin } from "../fixtures/auth";
import { InlineStrategyEditor } from "../pages/InlineStrategyEditor";
import { MainboardPage } from "../pages/MainboardPage";

// R2-07 — the REAL golden path (GAP madde 12): Strategy created INLINE on the
// Mainboard through the typed forms, the APPROVED indicator package pinned from
// the Library picker, the APPROVED market dataset pinned from the dataset
// picker, Validate -> Save -> auto-attach, Ready Check comes back an EXPLICIT
// "Ready", RUN flips disabled -> enabled, the admitted run reaches the real
// terminal SUCCEEDED state, and the immutable Result opens INLINE under the
// Mainboard with headline metrics + provenance. The URL stays "/" the whole
// time (GAP madde 1 acceptance folded in).
//
// Blocked / NOT_READY / error is a FAILURE of this spec. The former
// "a structured outcome is enough" reading of L4 is gone — L4 forbids
// FABRICATING success; it never excuses accepting a blocked report on a path
// that must genuinely succeed.
//
// Prerequisite: the E2E golden fixture must be seeded once per stack
// (SEED_E2E_GOLDEN=1 python -m entropia.apps.seed) — it provides the approved
// market dataset (with a processed Parquet bar asset), the approved+published
// ta.sma indicator package and the canonical rationale families as REAL records.
//
// Honest boundary (reported as a separate finding): the Mainboard inline flow
// has no control for the REQUIRED StrategyConfig.rationale_family_id, so this
// spec runs as the bootstrap Admin and sets the family through the admin-gated
// Advanced (raw payload) editor — a real product surface, no mocking. Once the
// product exposes an inline family picker, switch this spec to a plain user.
test.describe("Golden path: inline Strategy -> Ready PASS -> RUN SUCCEEDED -> inline Result", () => {
  test("builds a runnable strategy on the Mainboard and follows the run to a succeeded inline Result", async ({
    page,
  }) => {
    test.setTimeout(420_000);
    await ensureAdmin(page);

    const mainboard = new MainboardPage(page);
    await mainboard.goto();
    await expect(page).toHaveURL(/\/$/);

    // 1) Inline create: "+ Add -> Add Strategy" renders the draft row with the
    //    full typed editor, still on "/".
    await mainboard.addStrategyDraft();
    await expect(page).toHaveURL(/\/$/);

    // 2) Typed forms, card by card — pickers only, never hand-typed infra ids.
    const editor = new InlineStrategyEditor(page);
    await editor.fillDataAndExecution();
    await editor.fillPositionEntry();
    await editor.enablePercentageStop();
    await editor.fillPositionSizing();

    // 3) Required rationale family via the live registry read + the admin-gated
    //    Advanced editor (see honest boundary above).
    const familyId = await page.evaluate(async () => {
      const token = window.localStorage.getItem("entropia.sessionToken");
      const base =
        (window as unknown as { __E2E_API_BASE__?: string }).__E2E_API_BASE__ ??
        "http://localhost:8000/api/v1";
      const response = await fetch(`${base}/rationale-families`, {
        headers: { Authorization: `Bearer ${token ?? ""}` },
      });
      const body = (await response.json()) as { data?: Array<{ entity_id: string }> };
      if (!body.data?.length) throw new Error("No rationale families seeded (SEED_E2E_GOLDEN missing?)");
      return body.data[0].entity_id;
    });
    await editor.setRationaleFamilyViaAdvancedEditor(familyId);

    // 4) Validate must be clean, then Save attaches the mirror revision.
    await editor.validateExpectValid();
    await editor.saveAndExpectAttached();
    await expect(page).toHaveURL(/\/$/);

    // RUN is genuinely locked now (F-16): the composition just changed, so no
    // CURRENT Ready Check covers it — the disabled half of the
    // disabled -> enabled transition this spec asserts. (Asserted here rather
    // than at page load so the spec stays rerun-safe on a stack where an
    // earlier run already left a passed check behind.)
    await expect(mainboard.runButton()).toBeDisabled({ timeout: 20_000 });

    // 5) Ready Check — EXPLICIT "Ready", in the in-context modal, no route change.
    await mainboard.runReadyCheckExpectReady();
    await expect(page).toHaveURL(/\/$/);

    // 6) RUN flips to enabled now that a current check passes (F-16).
    await expect(mainboard.runButton()).toBeEnabled({ timeout: 20_000 });

    // 7) Admit the run inline and follow it to the real terminal SUCCEEDED.
    await mainboard.startRunExpectSucceeded();

    // 8) The immutable Result renders inline under the Mainboard with headline
    //    metrics + provenance — and the URL never left "/".
    await mainboard.expectInlineResultWithHeadlineAndProvenance();
    await expect(page).toHaveURL(/\/$/);
  });
});
