import { expect, type Page } from "@playwright/test";

// Mirrors frontend/src/pages/BacktestRun.tsx (doc 15) — admits a backtest run
// for the default Mainboard composition and follows it. A composition built
// from generic (non-domain-validated) work objects is expected to be
// rejected by admission (e.g. NOT_READY / composition has no strategy) —
// callers assert *a* structured outcome (URL run tracking or role=alert), not
// a specific verdict, matching the app's own L4 no-fabricated-success rule.
export class BacktestRunPage {
  constructor(private readonly page: Page) {}

  async goto(): Promise<void> {
    await this.page.goto("/backtest/run");
    await expect(this.page.getByRole("heading", { name: "RUN & Backtest Results", exact: true })).toBeVisible();
  }

  async requestRun(): Promise<void> {
    await this.page.getByRole("button", { name: "Request Backtest Run" }).click();
  }

  errorAlert() {
    return this.page.getByRole("alert");
  }

  // On successful admission the page sets ?run=<id> — the durable handle for
  // the inline run-status/result card (doc 15 §4).
  hasRunQueryParam(): boolean {
    return new URL(this.page.url()).searchParams.has("run");
  }
}
