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

  requestRunButton() {
    return this.page.getByRole("button", { name: "Request Backtest Run" });
  }

  // F-16: the readiness lock note shown when the composition has not passed a
  // current Ready Check (the admit button is disabled alongside it).
  lockedNote() {
    return this.page.getByText(
      "RUN is available only after a current Backtest Ready Check passes",
    );
  }

  // F-16: admission is gated on the composition's readiness. A generic
  // (non-domain-validated) composition is NOT_READY, so the admit button is
  // genuinely disabled — the client refuses up front instead of round-tripping
  // to a 422 READINESS_BLOCKED. Click only when the button is actually enabled;
  // return false when it is locked (the lock is itself a valid structured
  // outcome). Waits for the button to render first (it appears only once the
  // composition projection has loaded).
  async requestRunIfEnabled(): Promise<boolean> {
    const button = this.requestRunButton();
    await button.waitFor({ state: "visible", timeout: 20_000 });
    if (await button.isDisabled()) return false;
    await button.click();
    return true;
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
