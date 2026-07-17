import { expect, type Page } from "@playwright/test";

// Mirrors frontend/src/pages/MarketData.tsx "Add market dataset" form
// (doc 11 §4) — label/role selectors only.
export class MarketDataPage {
  constructor(private readonly page: Page) {}

  async goto(): Promise<void> {
    await this.page.goto("/market-data");
    await expect(this.page.getByRole("heading", { name: "Market Data", exact: true })).toBeVisible();
  }

  async createDataset(opts: { title: string; instrumentId?: string; type?: string }): Promise<string> {
    // The Dataset Setup shell is collapsed by default (UI-11) — open it before
    // touching the create form. Idempotent: only clicks when the form is hidden.
    const titleField = this.page.locator("#md-title");
    if (!(await titleField.isVisible().catch(() => false))) {
      await this.page.getByRole("button", { name: "+ Add Market Dataset" }).click();
      await expect(titleField).toBeVisible();
    }
    if (opts.type) {
      await this.page.locator("#md-type").selectOption(opts.type);
    }
    await this.page.locator("#md-title").fill(opts.title);
    if (opts.instrumentId) {
      await this.page.locator("#md-instrument").fill(opts.instrumentId);
    }
    await this.page.getByRole("button", { name: "Create dataset" }).click();

    const created = this.page.getByText(/Created — /);
    await expect(created).toBeVisible({ timeout: 20_000 });
    const text = await created.innerText();
    const match = /Created — (\S+) /.exec(text);
    if (!match) throw new Error(`Could not parse entity id from "${text}"`);
    return match[1];
  }

  registryRow(title: string) {
    return this.page.locator("table.metrics-table tbody tr", { hasText: title });
  }
}
