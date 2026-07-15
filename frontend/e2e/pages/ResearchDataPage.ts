import { expect, type Page } from "@playwright/test";

// Mirrors frontend/src/pages/ResearchData.tsx "Add research dataset" form
// (doc 12 §4). Create is DR3-gated — it requires marketEntityId to reference
// an ACTIVE+APPROVED Market Data dataset, else the server rejects with
// DEPENDENCY_BLOCKED (verbatim in a role=alert). Both outcomes are asserted
// by callers; this page object never assumes success.
export class ResearchDataPage {
  constructor(private readonly page: Page) {}

  async goto(): Promise<void> {
    await this.page.goto("/research-data");
    await expect(this.page.getByRole("heading", { name: "Research Data", exact: true })).toBeVisible();
  }

  async submitCreate(opts: { marketEntityId: string; displayName: string }): Promise<void> {
    await this.page.locator("#rd-market").fill(opts.marketEntityId);
    await this.page.locator("#rd-display").fill(opts.displayName);
    await this.page.getByRole("button", { name: "Create dataset" }).click();
  }

  successMessage() {
    return this.page.getByText(/Created — /);
  }

  errorAlert() {
    return this.page.getByRole("alert");
  }
}
