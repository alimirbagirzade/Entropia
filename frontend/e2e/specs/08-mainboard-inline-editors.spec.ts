import { expect, test, type Locator, type Page } from "@playwright/test";

import { freshActor, signUp } from "../fixtures/auth";
import { uniqueSuffix } from "../utils/ids";

// R2-01b (GAP items 1–2): the Trading Signal / Trade Log editors mount INLINE
// in the Mainboard horizontal rows. The whole create → upload → import report →
// Save & Add → persisted-row → close journey completes without ever leaving
// "/" — the URL is asserted before and after every step. Requires the full
// stack (backend + worker + Postgres + Redis + MinIO) at E2E_BASE_URL.

function expectMainboardUrl(page: Page): Promise<void> {
  return expect(page).toHaveURL(/\/$/);
}

// Auth-mode-aware bootstrap. AUTH_MODE=session (CI/docker stack): real signup
// through the login form. AUTH_MODE=dev (Docker-free local stack): signup via
// the API, then act as the fresh principal through the dev "act as" control
// (X-Actor-Id) — the same identity path the dev UI itself uses.
async function landAsFreshActor(page: Page, prefix: string): Promise<void> {
  const actor = freshActor(prefix);
  await page.goto("/");
  const devActor = page.locator("#dev-actor");
  if (await devActor.isVisible().catch(() => false)) {
    const apiBase = process.env.E2E_API_BASE_URL ?? "http://localhost:8000/api/v1";
    const response = await page.request.post(`${apiBase}/auth/signup`, {
      data: {
        username: actor.username,
        password: actor.password,
        display_name: actor.displayName,
        email: actor.email,
      },
    });
    const created = (await response.json()) as { user_id: string };
    await devActor.fill(created.user_id);
    await devActor.press("Enter");
  } else {
    await signUp(page, actor);
  }
  await expect(page.getByRole("heading", { name: "Mainboard", exact: true })).toBeVisible({
    timeout: 45_000,
  });
}

// Fill the seeded raw-JSON payload's required identity fields the way a user
// would (the typed form replaces this in R2-04 — this slice moves the existing
// form as-is).
async function completePayload(draftRow: Locator, label: string, name: string): Promise<void> {
  const box = draftRow.getByLabel(label);
  const seeded = JSON.parse((await box.inputValue()) || "{}") as {
    identity?: { display_name?: string };
    source?: { provider_name?: string };
  };
  seeded.identity = { ...seeded.identity, display_name: name };
  seeded.source = { ...seeded.source, provider_name: "e2e-provider" };
  await box.fill(JSON.stringify(seeded, null, 2));
}

const SIGNAL_CSV = (suffix: string) =>
  [
    "event_id,event_time,available_time,instrument_id,direction,signal_type,source_record_id",
    `sig-${suffix}-1,2024-01-01 10:00,2024-01-01 10:05,BTCUSDT,long,entry,ref-${suffix}-1`,
    `sig-${suffix}-2,2024-01-02 09:15,2024-01-02 09:20,BTCUSDT,short,entry,ref-${suffix}-2`,
    "",
  ].join("\n");

const TRADE_LOG_CSV = () =>
  [
    "direction,entry_time,entry_price,exit_time,exit_price,size,symbol",
    "Long,2024-01-01 10:00,42100,2024-01-01 15:30,42850,1.0,BTCUSDT",
    "Short,2024-01-02 09:15,43000,2024-01-02 18:00,41950,1.0,BTCUSDT",
    "",
  ].join("\n");

test.describe("R2-01b Mainboard inline TS/TL editors", () => {
  test("Trading Signal: create → upload → import → Save & Add → close, URL stays /", async ({
    page,
  }) => {
    await landAsFreshActor(page, "r2ts");
    await expectMainboardUrl(page);

    // Add menu → nested submenu → Trading Signal opens an inline draft row.
    await page.getByRole("button", { name: "+ Add" }).click();
    await page.getByRole("button", { name: "Add Outsource Signal" }).click();
    await page.getByRole("menuitem", { name: "Trading Signal" }).click();
    const draftRow = page.getByRole("group", { name: "Trading Signal draft" });
    await expect(draftRow).toBeVisible();
    await expectMainboardUrl(page);

    // The REAL workbench editor is mounted inline: upload the source file.
    const suffix = uniqueSuffix();
    await draftRow.getByLabel(/Signal-event file/i).setInputFiles({
      name: "signals.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(SIGNAL_CSV(suffix)),
    });
    await draftRow.getByRole("button", { name: "Upload source asset" }).click();
    await expect(draftRow.getByText(/Source asset stored|already uploaded/i)).toBeVisible({
      timeout: 15_000,
    });

    // Request the durable import and wait for the succeeded report inline.
    await draftRow.getByLabel("Instrument id").fill("BTCUSDT");
    await draftRow.getByRole("button", { name: "Request import" }).click();
    await expect(draftRow.getByText("succeeded", { exact: true })).toBeVisible({
      timeout: 45_000,
    });
    await expectMainboardUrl(page);

    // Save & Add (attach checkbox defaults on) — the create hook invalidates
    // ["mainboard"], the transient draft row hands over to a persisted row.
    await completePayload(draftRow, "TradingSignalConfig payload", "R2 TS E2E");
    await draftRow.getByRole("button", { name: "Save Trading Signal" }).click();
    const persistedEditor = page.getByRole("region", { name: /Trading Signal editor for/ });
    await expect(persistedEditor.first()).toBeVisible({ timeout: 20_000 });
    await expect(page.getByRole("group", { name: "Trading Signal draft" })).toHaveCount(0);
    await expectMainboardUrl(page);

    // Close panel collapses the persisted row's inline editor — no navigation.
    await persistedEditor.first().getByRole("button", { name: "Close panel" }).click();
    await expect(page.getByRole("region", { name: /Trading Signal editor for/ })).toHaveCount(0);
    await expectMainboardUrl(page);

    // Reload: the persisted row survives (server truth), still on "/".
    await page.reload();
    await expect(page.getByRole("heading", { name: "Mainboard", exact: true })).toBeVisible();
    await expect(page.locator(".strategy-row", { hasText: "Trading Signal" }).first()).toBeVisible();
    await expectMainboardUrl(page);
  });

  test("Trade Log: create → upload → import → Save & Add → close, URL stays /", async ({
    page,
  }) => {
    await landAsFreshActor(page, "r2tl");
    await expectMainboardUrl(page);

    await page.getByRole("button", { name: "+ Add" }).click();
    await page.getByRole("button", { name: "Add Outsource Signal" }).click();
    await page.getByRole("menuitem", { name: "Trade Log" }).click();
    const draftRow = page.getByRole("group", { name: "Trade Log draft" });
    await expect(draftRow).toBeVisible();
    await expectMainboardUrl(page);

    await draftRow.getByLabel(/Trade-record file/i).setInputFiles({
      name: "trades.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(TRADE_LOG_CSV()),
    });
    await draftRow.getByRole("button", { name: "Upload source asset" }).click();
    await expect(draftRow.getByText(/Source asset stored|already uploaded/i)).toBeVisible({
      timeout: 15_000,
    });

    await draftRow.getByLabel("Instrument id").fill("BTCUSDT");
    await draftRow.getByRole("button", { name: "Request import" }).click();
    await expect(draftRow.getByText("succeeded", { exact: true })).toBeVisible({
      timeout: 45_000,
    });
    await expectMainboardUrl(page);

    await completePayload(draftRow, "TradeLogConfig payload", "R2 TL E2E");
    await draftRow.getByRole("button", { name: "Save Trade Log" }).click();
    const persistedEditor = page.getByRole("region", { name: /Trade Log editor for/ });
    await expect(persistedEditor.first()).toBeVisible({ timeout: 20_000 });
    await expect(page.getByRole("group", { name: "Trade Log draft" })).toHaveCount(0);
    await expectMainboardUrl(page);

    await persistedEditor.first().getByRole("button", { name: "Close panel" }).click();
    await expect(page.getByRole("region", { name: /Trade Log editor for/ })).toHaveCount(0);
    await expectMainboardUrl(page);

    await page.reload();
    await expect(page.getByRole("heading", { name: "Mainboard", exact: true })).toBeVisible();
    await expect(page.locator(".strategy-row", { hasText: "Trade Log" }).first()).toBeVisible();
    await expectMainboardUrl(page);
  });

  test("Strategy: Add Strategy opens the inline draft editor without navigation", async ({
    page,
  }) => {
    await landAsFreshActor(page, "r2st");
    await expectMainboardUrl(page);

    await page.getByRole("button", { name: "+ Add" }).click();
    await page.getByRole("button", { name: "Add Strategy" }).click();
    // The strategy draft row arrives expanded with the REAL inline Strategy
    // Details editor (UI-02 / PR #314 pattern) — no route change.
    await expect(page.getByText("Unsaved draft").first()).toBeVisible({ timeout: 20_000 });
    await expectMainboardUrl(page);
  });
});
