import { expect, type Page } from "@playwright/test";

// Mirrors frontend/src/pages/ResearchData.tsx setup form (doc 12 §4). Since
// R2-06 the DR3 market link is server-truth: there is NO free-text entity-id
// input — the Market Data link is chosen through MarketLinkPicker, only an
// APPROVED head revision is selectable, and Create stays disabled until the
// approved-bundle probe confirms the link.
export class ResearchDataPage {
  constructor(private readonly page: Page) {}

  async goto(): Promise<void> {
    await this.page.goto("/research-data");
    await expect(this.page.getByRole("heading", { name: "Research Data", exact: true })).toBeVisible();
  }

  createButton() {
    return this.page.getByRole("button", { name: "Create dataset" });
  }

  freeTextMarketInput() {
    return this.page.locator("#rd-market");
  }

  async openMarketPicker(): Promise<void> {
    await this.page.getByRole("button", { name: "Choose market dataset" }).click();
    await expect(this.page.getByLabel("Search market datasets")).toBeVisible();
  }

  async searchMarketDatasets(needle: string): Promise<void> {
    await this.page.getByLabel("Search market datasets").fill(needle);
  }

  // The picker row carrying the given title (button; disabled when the head
  // revision is not approved).
  pickerRow(title: string) {
    return this.page.locator(".pkg-picker-row", { hasText: title });
  }
}
