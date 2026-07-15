import { expect, type Page } from "@playwright/test";

// Mirrors frontend/src/pages/Trash.tsx (UI-20, doc 20) — "Panel / Trash" +
// Admin-only recoverable index + OCC restore + the F-21 real-re-auth-gated
// Permanent Delete (purge) composer.
export class TrashPage {
  constructor(private readonly page: Page) {}

  async goto(): Promise<void> {
    await this.page.goto("/trash");
    await expect(
      this.page.getByRole("heading", { name: "Panel / Trash", exact: true }),
    ).toBeVisible();
  }

  async search(query: string): Promise<void> {
    await this.page.locator("#trash-q").fill(query);
    await this.page.getByRole("button", { name: "Search" }).click();
  }

  rowByName(displayName: string) {
    return this.page.locator("table.database-table tbody tr", { hasText: displayName });
  }

  async openPurgeComposer(row: ReturnType<TrashPage["rowByName"]>): Promise<void> {
    await row.getByRole("button", { name: "Permanent Delete" }).click();
  }

  // `password` is the Admin's REAL account password (F-21): Confirm first
  // calls POST /auth/reauth to re-verify it and only forwards the
  // server-minted proof to the purge command — no arbitrary string works here.
  async confirmPurge(displayName: string, password: string): Promise<void> {
    await this.page.locator("#purge-phrase").fill(displayName);
    await this.page.locator("#purge-reauth").fill(password);
    await this.page.getByRole("button", { name: "Confirm permanent delete" }).click();
  }

  purgeAcceptedToast() {
    return this.page.getByText(/Permanent deletion was requested for/);
  }

  errorAlert() {
    return this.page.getByRole("alert");
  }
}
