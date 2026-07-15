import { expect, test } from "@playwright/test";

import { freshActor, signUp } from "../fixtures/auth";
import { uniqueSuffix } from "../utils/ids";

// F-03: real native file selection for the text-asset upload surfaces (Trading
// Signal / Trade Log source assets, Create Package baseline, User Manual). These
// journeys exercise the full round trip — native <input type=file> selection ->
// multipart transfer -> server-side size/encoding/schema validation -> content-
// addressed persistence — with NO pasted-textarea fallback.
//
// Requires the full stack (backend + frontend + Postgres + MinIO) at E2E_BASE_URL.
test.describe("F-03 native file uploads", () => {
  test("Trading Signal: selecting a CSV stores a content-addressed source asset", async ({
    page,
  }) => {
    await signUp(page, freshActor("tsupload"));

    await page.goto("/trading-signal");

    const csv = `time,side\n${uniqueSuffix()},buy\n`;
    await page
      .getByLabel(/Signal-event file/i)
      .setInputFiles({ name: "signals.csv", mimeType: "text/csv", buffer: Buffer.from(csv) });
    await page.getByRole("button", { name: "Upload source asset" }).click();

    await expect(page.getByText(/Source asset stored/i)).toBeVisible({ timeout: 15_000 });
  });

  test("Trading Signal: a non-CSV file is rejected with a typed error", async ({ page }) => {
    await signUp(page, freshActor("tsbadtype"));

    await page.goto("/trading-signal");

    await page
      .getByLabel(/Signal-event file/i)
      .setInputFiles({ name: "signals.pdf", mimeType: "application/pdf", buffer: Buffer.from("x,y\n1,2\n") });
    await page.getByRole("button", { name: "Upload source asset" }).click();

    // The server extension gate fires (FILE_TYPE_NOT_ALLOWED) — no asset is stored.
    await expect(page.getByText(/FILE_TYPE_NOT_ALLOWED|TXT or CSV/i)).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByText(/Source asset stored/i)).toHaveCount(0);
  });

  test("Trade Log: selecting a CSV stores a content-addressed source asset", async ({ page }) => {
    await signUp(page, freshActor("tlupload"));

    await page.goto("/trade-log");

    const csv = `time,side,qty\n${uniqueSuffix()},buy,1\n`;
    await page
      .getByLabel(/Trade-record file/i)
      .setInputFiles({ name: "trades.csv", mimeType: "text/csv", buffer: Buffer.from(csv) });
    await page.getByRole("button", { name: "Upload source asset" }).click();

    await expect(page.getByText(/Source asset stored|already uploaded/i)).toBeVisible({
      timeout: 15_000,
    });
  });
});
