import { expect, type Page } from "@playwright/test";

// Mirrors frontend/src/pages/Mainboard.tsx (doc 01) — the generic "Add work
// object" composer (create root+revision, then attach its pinned revision to
// the default Mainboard) and the per-item two-step soft-delete ("× Delete" ->
// "Move to Trash"). Callers use object_kind="strategy": the generic
// work-object create validates available_time and REQUIRES it for
// trading_signal / trade_log (commands/mainboard.py _validate_available_time),
// which the Add-work-object card never sends — only strategy may omit it. An
// empty payload is accepted, so the journey stays self-contained (no upstream
// package/market-data approval chain) while exercising real create + attach.
export class MainboardPage {
  constructor(private readonly page: Page) {}

  async goto(): Promise<void> {
    await this.page.goto("/");
    await expect(this.page.getByRole("heading", { name: "Mainboard", exact: true })).toBeVisible();
  }

  // Returns the created work object's root id (the "Root" dd shown after
  // create) — this is also the Trash entry's display_name fallback
  // (queries/trash.py: entry.display_name or entry.entity_id), used by the
  // Trash spec to find this exact entry without depending on list ordering.
  async createAndAttachWorkObject(objectKind: "strategy" | "trading_signal" | "trade_log"): Promise<string> {
    // UI-06: the Add work object composer is mode-gated behind the small
    // "Add Package" popover in the STRATEGIES header — open it and choose the
    // work-object path before the card renders.
    await this.page.getByRole("button", { name: "+ Add Package" }).click();
    await this.page.getByRole("button", { name: "Strategy / work object" }).click();
    const card = this.page.locator("section", { has: this.page.getByRole("heading", { name: "Add work object", exact: true }) });
    await card.getByRole("combobox").selectOption(objectKind);
    await card.getByRole("button", { name: "Create work object" }).click();

    // Race the success projection ("Root" dd) against an error envelope so a
    // rejected create fails fast with the server's verbatim message instead of
    // a 20s timeout.
    const rootDd = card.locator("dl.kv dt", { hasText: "Root" }).locator("xpath=following-sibling::dd[1]");
    const alert = card.locator('[role="alert"]');
    await expect(rootDd.or(alert).first()).toBeVisible({ timeout: 20_000 });
    if (await alert.isVisible().catch(() => false)) {
      throw new Error(`Create work object failed: ${(await alert.innerText()).trim()}`);
    }
    const rootId = (await rootDd.innerText()).trim();

    await card.getByRole("button", { name: "Attach to Mainboard" }).click();
    await expect(card.locator('[role="alert"]')).toHaveCount(0);
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
