import { expect, type Page } from "@playwright/test";

// Mirrors frontend/src/pages/ReadyCheck.tsx (doc 14) — runs a readiness check
// against the default Mainboard composition. A real composition assembled
// from generic (non-domain-validated) work objects is not expected to pass —
// the report can legitimately come back "blocked"; callers assert *a*
// structured outcome landed, not a specific verdict (L4: never fabricate
// success).
export class ReadyCheckPage {
  constructor(private readonly page: Page) {}

  async goto(): Promise<void> {
    await this.page.goto("/backtest/ready-check");
    await expect(this.page.getByRole("heading", { name: "Backtest Ready Check", exact: true })).toBeVisible();
  }

  async runCheck(): Promise<void> {
    await this.page.getByRole("button", { name: "Run Ready Check" }).click();
  }

  errorAlert() {
    return this.page.getByRole("alert");
  }

  // The readiness card renders once a check has run (either from history or
  // from this run) — its container replaces the "Not checked yet" empty state.
  notCheckedYetEmptyState() {
    return this.page.getByText("Not checked yet");
  }
}
