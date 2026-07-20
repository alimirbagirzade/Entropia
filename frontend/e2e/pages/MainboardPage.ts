import { expect, type Page } from "@playwright/test";

// Mirrors frontend/src/pages/Mainboard.tsx (doc 01). "Add Strategy" follows the
// strategy-editor family (doc 02 §7): it creates a DRAFT via POST
// /strategy-drafts — the strat_ root is simultaneously the Mainboard work
// object, but NO revision exists until the first Save, so nothing attaches at
// add time. The new draft renders immediately as a horizontal
// .strategy-package row hosting the inline editor; the first Save attaches the
// §7.1 mirror revision. Plus the per-row two-step soft-delete
// ("× Delete" -> "Move to Trash").
export class MainboardPage {
  constructor(private readonly page: Page) {}

  async goto(): Promise<void> {
    await this.page.goto("/");
    await expect(this.page.getByRole("heading", { name: "Mainboard", exact: true })).toBeVisible();
  }

  // "Add Strategy" -> a new unsaved strategy draft row. Returns the strategy
  // root id (from the create response's strategy_root_id) — also the Trash
  // entry's display identity (soft_delete_work_object records no display_name,
  // so queries/trash.py falls back to the entity_id), used by the Trash spec to
  // find this exact entry without depending on list ordering.
  //
  // Single-shot on purpose (no retry loop): unlike the old create+attach path
  // whose attach could transiently 404 on a read-after-write window, a draft
  // create is a single insert that does not 404. Each "Add Strategy" click uses
  // a fresh Idempotency-Key, so a retry would create a SECOND draft — and since
  // the drafts list renders newest-first, deleteLastItem()'s `.last()` would
  // then target the OTHER draft, whose id would not match this returned rootId
  // (the Trash spec searches by this id and would find nothing). One click, one
  // draft, one row keeps the returned id and the deleted row in lockstep.
  async addStrategyDraft(): Promise<string> {
    const before = await this.compositionItemCount().count();
    await this.page.getByRole("button", { name: "+ Add", exact: true }).click();
    // Set the waiter up before clicking so we never miss the response.
    const createResponse = this.page.waitForResponse(
      (r) => /\/strategy-drafts$/.test(r.url()) && r.request().method() === "POST",
      { timeout: 15_000 },
    );
    await this.page.getByRole("button", { name: "Add Strategy", exact: true }).click();
    const response = await createResponse;
    expect(response.ok(), `Add Strategy create HTTP ${response.status()}`).toBeTruthy();
    const rootId = ((await response.json()) as { strategy_root_id: string }).strategy_root_id;
    // The new draft row appears after the ["strategy"] drafts refetch — poll the
    // count up (no re-click, so no duplicate draft is ever created).
    await expect
      .poll(() => this.compositionItemCount().count(), { timeout: 20_000 })
      .toBeGreaterThan(before);
    return rootId;
  }

  compositionItemCount() {
    return this.page.locator(".strategy-package");
  }

  // ---------------------------------------------------------------------------
  // R2-07 — the fixed lower-right Ready Check / RUN shell (UI-14/UI-15).
  // ---------------------------------------------------------------------------

  // F-16: RUN stays a genuinely disabled button until a current Ready Check
  // passes — the golden-path spec asserts the disabled -> enabled transition.
  runButton() {
    return this.page.locator("button.run-button");
  }

  // UI-14: Ready Check opens as an in-context modal, no route change.
  async runReadyCheckExpectReady(): Promise<void> {
    await this.page.getByRole("button", { name: "Backtest Ready Check" }).click();
    const dialog = this.page.getByRole("dialog");
    await expect(dialog.getByRole("heading", { name: "Backtest Ready Check" })).toBeVisible();
    await dialog.getByRole("button", { name: "Run Ready Check" }).click();
    // GAP madde 12: the verdict must be an EXPLICIT green "Ready" — a
    // "Not ready" / blocked report is a hard failure of this spec, never an
    // acceptable "structured outcome". (Commission/spread are set upstream, so
    // not even "Ready with warnings" is expected.)
    await expect(dialog.getByText("Ready", { exact: true }).first()).toBeVisible({
      timeout: 30_000,
    });
    await expect(dialog.getByText("Not ready")).toHaveCount(0);
    await dialog.getByRole("button", { name: "Close" }).click();
  }

  // UI-15: RUN admits inline; the durable progress + immutable Result render in
  // the BACKTEST RESULTS section on this same page. The run must reach the real
  // terminal SUCCEEDED state — failed/cancelled/timeout are hard failures.
  async startRunExpectSucceeded(): Promise<void> {
    await this.runButton().click();
    const results = this.page.locator("section", {
      has: this.page.getByRole("heading", { name: "BACKTEST RESULTS" }),
    });
    // The worker replays the full bar range for real, so allow generous but
    // bounded headroom. Any terminal non-success surfaces as a failed
    // expectation here (the badge renders the run state verbatim).
    await expect(results.getByText("succeeded", { exact: true }).first()).toBeVisible({
      timeout: 180_000,
    });
  }

  // The inline immutable Result (ResultDetail) under BACKTEST RESULTS must show
  // headline metrics and provenance (manifest hash / execution key) — the doc 15
  // §9.4 surface, inline on "/" and never on a separate page.
  async expectInlineResultWithHeadlineAndProvenance(): Promise<void> {
    const detail = this.page.locator("section", {
      has: this.page.getByRole("heading", { name: /^Backtest Result / }),
    });
    await expect(detail.getByText("Headline")).toBeVisible({ timeout: 30_000 });
    await expect(detail.getByRole("heading", { name: "Manifest", exact: true })).toBeVisible();
    await expect(detail.getByText("Manifest hash")).toBeVisible();
    await expect(detail.getByText("Execution key")).toBeVisible();
  }

  // Soft-deletes the draft just created by addStrategyDraft(). It targets the
  // auto-expanded draft row — NOT `.last()`. The Trash spec runs as the shared
  // ADMIN account, whose board can already carry OTHER admin-owned draft rows
  // from earlier work; the drafts list renders newest-first, so `.last()` would
  // soft-delete a PRE-EXISTING draft while the Trash search looks for `rootId`,
  // and would silently find nothing. Right after goto() + addStrategyDraft()
  // (no navigation in between) exactly one row is expanded — the just-added
  // draft (its box auto-opens via justAddedDraftId) — so the open row is
  // unambiguously the one whose id is `rootId`. We also assert the DELETE hit
  // exactly that id, so a wrong-row deletion fails loudly instead of leaking to
  // the Trash search.
  async deleteLastItem(rootId: string): Promise<void> {
    // The just-added draft's row is the only expanded .strategy-package.
    const target = this.page
      .locator(".strategy-package")
      .filter({ has: this.page.locator('.strategy-arrow[aria-expanded="true"]') });
    await expect(target).toHaveCount(1);
    // The "× Delete" button carries aria-label={`Delete ${label}`}, so its
    // accessible name is "Delete <label>" (the aria-label wins over the visible
    // "× Delete" text) — match that, not the glyph text.
    await target.getByRole("button", { name: /^Delete / }).click();
    const dialog = target.getByRole("alertdialog");
    await expect(dialog).toBeVisible();
    // Set the waiter up before clicking so we never miss the response, and
    // await it before returning — the caller (06-trash-reauth.spec.ts)
    // navigates to /trash immediately after this resolves, and a same-tab
    // navigation can abort an in-flight DELETE, leaving no Trash entry behind.
    const deleteResponse = this.page.waitForResponse(
      (r) => /\/work-objects\/[^/]+$/.test(r.url()) && r.request().method() === "DELETE",
      { timeout: 10_000 },
    );
    await dialog.getByRole("button", { name: "Move to Trash" }).click();
    const response = await deleteResponse;
    expect(response.ok(), `Move to Trash HTTP ${response.status()}`).toBeTruthy();
    expect(
      response.url().endsWith(`/work-objects/${rootId}`),
      `soft-deleted the wrong root: ${response.url()} (expected ${rootId})`,
    ).toBeTruthy();
  }
}
