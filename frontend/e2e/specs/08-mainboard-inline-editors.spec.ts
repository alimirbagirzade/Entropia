import { expect, test, type Locator, type Page } from "@playwright/test";

import { freshActor, logIn, signUp } from "../fixtures/auth";
import { uniqueSuffix } from "../utils/ids";

// R2-01b (GAP items 1–2): the Trading Signal / Trade Log editors mount INLINE
// in the Mainboard horizontal rows. The whole create → upload → import report →
// Save & Add → persisted-row → close journey completes without ever leaving
// "/" — the URL is asserted before and after every step. Requires the full
// stack (backend + worker + Postgres + Redis + MinIO) at E2E_BASE_URL.

function expectMainboardUrl(page: Page): Promise<void> {
  return expect(page).toHaveURL(/\/$/);
}

const API_BASE = process.env.E2E_API_BASE_URL ?? "http://localhost:8000/api/v1";

// R2-08 (GAP item 7): the TS/TL identity cards pick an instrument from the
// canonical registry instead of typing an id — the registry has no default
// seed, so the fixture registers BTCUSDT once via the real API before the UI
// step needs to find it in the picker. Idempotent: a prior run (or the other
// test in this file) may have already registered it — 409
// INSTRUMENT_ALREADY_REGISTERED is treated as success, never a silent skip of
// a real failure.
async function ensureBtcusdtInstrument(page: Page): Promise<void> {
  const token = await page.evaluate(() => localStorage.getItem("entropia.sessionToken"));
  const devActorId = await page
    .locator("#dev-actor")
    .inputValue()
    .catch(() => "");
  const headers: Record<string, string> = { "Idempotency-Key": `e2e-instr-${uniqueSuffix()}` };
  if (token) headers.Authorization = `Bearer ${token}`;
  else if (devActorId) headers["X-Actor-Id"] = devActorId;

  const res = await page.request.post(`${API_BASE}/instruments`, {
    headers,
    data: {
      venue_id: "binance",
      symbol: "BTCUSDT",
      contract_type: "perpetual",
      display_name: "BTCUSDT Perpetual",
      aliases: ["BTCUSDT"],
    },
  });
  if (!res.ok() && res.status() !== 409) {
    throw new Error(`Failed to ensure the BTCUSDT instrument exists: ${res.status()} ${await res.text()}`);
  }
}

// Picks BTCUSDT from the registry picker within the given scope (draft row).
// `.first()` targets the identity card's picker — it renders before the typed
// config form's picker in DOM order (details-grid two-col, then CreatePanel).
async function selectBtcusdtInstrument(scope: Locator): Promise<void> {
  await scope.getByRole("button", { name: "Choose instrument" }).first().click();
  await scope.getByLabel("Search instruments").fill("BTCUSDT");
  await scope.getByRole("button", { name: /BTCUSDT Perpetual/ }).first().click();
}

// Auth-mode-aware bootstrap. AUTH_MODE=session (CI/docker stack): real signup
// through the login form. AUTH_MODE=dev (Docker-free local stack): signup via
// the API, then act as the fresh principal through the dev "act as" control
// (X-Actor-Id) — the same identity path the dev UI itself uses.
async function landAsFreshActor(page: Page, prefix: string): Promise<void> {
  const actor = freshActor(prefix);
  // The dev "act as" control renders whenever no session token exists — in BOTH
  // auth modes — so visibility cannot tell the modes apart. Probe the API
  // instead: only AUTH_MODE=dev honours X-Actor-Id.
  // CI docker stack exposes the API on :8000 next to the :8080 frontend (see
  // e2e/README.md); the Docker-free local stack uses the same port.
  const apiBase = process.env.E2E_API_BASE_URL ?? "http://localhost:8000/api/v1";
  const signup = await page.request
    .post(`${apiBase}/auth/signup`, {
      data: {
        username: actor.username,
        password: actor.password,
        display_name: actor.displayName,
        email: actor.email,
      },
    })
    .catch(() => null);
  const created = signup?.ok() ? ((await signup.json()) as { user_id?: string }) : null;
  const devProbe =
    created?.user_id !== undefined &&
    (await page.request
      .get(`${apiBase}/mainboards/default`, { headers: { "X-Actor-Id": created.user_id } })
      .then((r) => r.ok())
      .catch(() => false));
  if (devProbe && created?.user_id !== undefined) {
    await page.goto("/");
    const devActor = page.locator("#dev-actor");
    await devActor.fill(created.user_id);
    await devActor.press("Enter");
  } else if (created !== null) {
    // Account already exists (API signup succeeded) — session mode: log it in.
    await logIn(page, actor);
  } else {
    await signUp(page, actor);
  }
  await expect(page.getByRole("heading", { name: "Mainboard", exact: true })).toBeVisible({
    timeout: 45_000,
  });
}

// R2-04: the config payload is produced by the TYPED form — the journey fills
// the two identity fields; the import binding is system-carried from the
// report, so no JSON / root id / revision id / source asset id is ever typed.
async function completePayload(draftRow: Locator, _label: string, name: string): Promise<void> {
  await draftRow.getByLabel("Display name").fill(name);
  await draftRow.getByLabel("Provider name").fill("e2e-provider");
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
    await ensureBtcusdtInstrument(page);
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
    await selectBtcusdtInstrument(draftRow);
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
    await ensureBtcusdtInstrument(page);
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

    await selectBtcusdtInstrument(draftRow);
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
