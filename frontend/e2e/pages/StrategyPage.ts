import { expect, type Page } from "@playwright/test";

// Mirrors frontend/src/pages/StrategyDetails.tsx (doc 02 §7) "Create
// strategy" card — creates the strategy root + its mutable editor draft
// (POST /strategy-drafts). No revision/save is attempted here: a schema-valid
// save needs an Admin-approved indicator package pinned in indicator_blocks
// plus an approved Market Data revision (see README "Honest boundaries").
export class StrategyPage {
  constructor(private readonly page: Page) {}

  async goto(): Promise<void> {
    await this.page.goto("/strategy");
    await expect(this.page.getByRole("heading", { name: "Strategy Details", exact: true })).toBeVisible();
  }

  async createDraft(displayName: string): Promise<void> {
    await this.page.getByPlaceholder("e.g. Momentum breakout A").fill(displayName);
    await this.page.getByRole("button", { name: "Create draft" }).click();
  }

  // Create redirects to ?draft=<id> and renders the workbench.
  async waitForDraftWorkbench(): Promise<void> {
    await this.page.waitForURL(/[?&]draft=/, { timeout: 20_000 });
  }
}
