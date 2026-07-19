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
