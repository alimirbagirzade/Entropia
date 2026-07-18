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
  async addStrategyDraft(): Promise<string> {
    // Retry the whole action until a new row lands — each attempt uses a fresh
    // Idempotency-Key and creates its own draft, which is fine here (the
    // journey only needs one row on the board).
    let rootId = "";
    await expect(async () => {
      const before = await this.compositionItemCount().count();
      await this.page.getByRole("button", { name: "+ Add", exact: true }).click();
      // Set the waiter up before clicking so we never miss the response.
      const createResponse = this.page.waitForResponse(
        (r) => /\/strategy-drafts$/.test(r.url()) && r.request().method() === "POST",
        { timeout: 10_000 },
      );
      await this.page.getByRole("button", { name: "Add Strategy", exact: true }).click();
      const response = await createResponse;
      expect(response.ok(), `Add Strategy create HTTP ${response.status()}`).toBeTruthy();
      rootId = ((await response.json()) as { strategy_root_id: string }).strategy_root_id;
      // The new draft row appears after the ["strategy"] drafts refetch.
      expect(await this.compositionItemCount().count()).toBeGreaterThan(before);
    }).toPass({ timeout: 40_000, intervals: [500, 1_000, 2_000, 4_000] });
    return rootId;
  }

  compositionItemCount() {
    return this.page.locator(".strategy-package");
  }

  // Deletes the most recently attached item — new items are appended to the
  // tail of the composition, so immediately after createAndAttachWorkObject
  // the last .strategy-package is the one just attached.
  async deleteLastItem(): Promise<void> {
    const lastItem = this.page.locator(".strategy-package").last();
    // Ensure the row is expanded so the per-item ops (including delete) render.
    // A freshly added row auto-opens its inline editor (F-15), so a blind arrow
    // click would TOGGLE it shut — expand idempotently by reading aria-expanded.
    const arrow = lastItem.locator(".strategy-arrow");
    if ((await arrow.getAttribute("aria-expanded")) !== "true") {
      await arrow.click();
    }
    await expect(arrow).toHaveAttribute("aria-expanded", "true");
    // The "× Delete" button carries aria-label={`Delete ${label}`}, so its
    // accessible name is "Delete <label>" (the aria-label wins over the visible
    // "× Delete" text) — match that, not the glyph text.
    await lastItem.getByRole("button", { name: /^Delete / }).click();
    const dialog = lastItem.getByRole("alertdialog");
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
  }
}
