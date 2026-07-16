import { expect, type Page } from "@playwright/test";

// Mirrors frontend/src/pages/Mainboard.tsx (doc 01). F-15 removed the raw
// "Advanced: create work object" composer; the product path to put an item on
// the Mainboard is the typed "Add Strategy" action, which creates an empty
// Strategy work object and attaches it as a new inline row (real create +
// attach round trip — commands/mainboard.py; strategy may omit available_time,
// and an empty payload is accepted, so the journey stays self-contained with no
// upstream package/market-data approval chain). Plus the per-item two-step
// soft-delete ("× Delete" -> "Move to Trash").
export class MainboardPage {
  constructor(private readonly page: Page) {}

  async goto(): Promise<void> {
    await this.page.goto("/");
    await expect(this.page.getByRole("heading", { name: "Mainboard", exact: true })).toBeVisible();
  }

  // Returns the attached work object's root id (read from the attach response's
  // work_object_root_id) — also the Trash entry's display_name fallback
  // (queries/trash.py: entry.display_name or entry.entity_id), used by the Trash
  // spec to find this exact entry without depending on list ordering.
  async createAndAttachWorkObject(objectKind: "strategy" | "trading_signal" | "trade_log"): Promise<string> {
    // F-15: only "strategy" is creatable inline from the product Add menu (the
    // external kinds go through their own TS/TL workbench save). The callers use
    // "strategy"; guard so a mistaken kind fails loudly rather than silently.
    if (objectKind !== "strategy") {
      throw new Error(
        `createAndAttachWorkObject: only "strategy" is supported via the product Add menu (got "${objectKind}")`,
      );
    }
    const before = await this.compositionItemCount().count();
    await this.page.getByRole("button", { name: "+ Add", exact: true }).click();

    // The attach POST returns the created item incl. work_object_root_id. Set up
    // the waiter before clicking so we never miss the response.
    const attachResponse = this.page.waitForResponse(
      (r) => /\/mainboards\/[^/]+\/items$/.test(r.url()) && r.request().method() === "POST",
    );
    await this.page.getByRole("button", { name: "Add Strategy", exact: true }).click();
    const response = await attachResponse;
    if (!response.ok()) {
      throw new Error(`Add Strategy failed: HTTP ${response.status()} ${(await response.text()).slice(0, 200)}`);
    }
    const rootId = ((await response.json()) as { work_object_root_id: string }).work_object_root_id;

    // The new row appears after the ["mainboard"] refetch.
    await expect(async () => {
      expect(await this.compositionItemCount().count()).toBeGreaterThan(before);
    }).toPass({ timeout: 15_000 });
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
    // Expand the row so the per-item ops (including delete) render.
    await lastItem.locator(".strategy-arrow").click();
    // The "× Delete" button carries aria-label={`Delete ${label}`}, so its
    // accessible name is "Delete <label>" (the aria-label wins over the visible
    // "× Delete" text) — match that, not the glyph text.
    await lastItem.getByRole("button", { name: /^Delete / }).click();
    const dialog = lastItem.getByRole("alertdialog");
    await expect(dialog).toBeVisible();
    await dialog.getByRole("button", { name: "Move to Trash" }).click();
  }
}
