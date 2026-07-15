import { expect, type Page } from "@playwright/test";

// Mirrors frontend/src/pages/PreCheck.tsx (doc 07) — pick an own request from
// the list, run the immutable dependency scan.
export class PreCheckPage {
  constructor(private readonly page: Page) {}

  async goto(): Promise<void> {
    await this.page.goto("/packages/pre-check");
    await expect(this.page.getByRole("heading", { name: "Pre-Check", exact: true })).toBeVisible();
  }

  async selectRequest(requestId: string): Promise<void> {
    const row = this.page.locator("table.metrics-table tbody tr", { hasText: requestId });
    await expect(row).toBeVisible({ timeout: 15_000 });
    await row.getByRole("button", { name: "Select" }).click();
  }

  async runPreCheck(): Promise<void> {
    await this.page.getByRole("button", { name: "Run Pre-Check" }).click();
  }

  errorAlert() {
    return this.page.getByRole("alert");
  }
}
