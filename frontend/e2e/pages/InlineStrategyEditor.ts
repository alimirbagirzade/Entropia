import { expect, type Page } from "@playwright/test";

// R2-07 — drives the INLINE Strategy Details editor mounted inside a Mainboard
// draft row (StrategyDraftBox -> StrategyDetailsPanel). Every interaction is a
// real typed-form edit against the running stack; each numbered card persists
// through its own "Apply … changes" button (a full-payload PATCH under OCC), so
// the flow applies card by card exactly like a human user.
//
// The golden fixture names below must match backend/src/entropia/apps/seed.py
// (SEED_E2E_GOLDEN=1): the approved market dataset and the approved+published
// indicator package are seeded there as REAL records.
export const GOLDEN_DATASET_TITLE = "E2E Golden BTCUSDT 1h";
export const GOLDEN_INDICATOR_NAME = "E2E Golden SMA";
export const GOLDEN_INSTRUMENT = "BTCUSDT";
// Must stay inside the fixture's bar window (2024-01-01 + 1500 hourly bars).
export const GOLDEN_RANGE_START = "2024-01-05T00:00:00Z";
export const GOLDEN_RANGE_END = "2024-02-25T00:00:00Z";

export class InlineStrategyEditor {
  constructor(private readonly page: Page) {}

  // The editor lives inside the expanded draft row; scope every lookup there so
  // stray rows from other tests can never satisfy a locator.
  private get root() {
    return this.page
      .locator(".strategy-package")
      .filter({ has: this.page.getByRole("button", { name: "Save Strategy Revision" }) })
      .first();
  }

  private async applyCard(buttonName: string): Promise<void> {
    // Every Apply is a real full-payload PATCH under OCC. Waiting on the actual
    // HTTP response (not on the "Payload applied" note, which may already be
    // visible from the PREVIOUS card's apply) guarantees the next card edits a
    // draft that already contains this card's fields — a stale read here would
    // silently wipe them on the next full-payload replace.
    const patchResponse = this.page.waitForResponse(
      (r) => /\/strategy-drafts\/[^/]+$/.test(r.url()) && r.request().method() === "PATCH",
      { timeout: 15_000 },
    );
    await this.root.getByRole("button", { name: buttonName }).click();
    const response = await patchResponse;
    expect(response.ok(), `${buttonName} PATCH HTTP ${response.status()}`).toBeTruthy();
    // The applied patch triggers a draft refetch that REMOUNTS every card
    // (each re-seeds from the fresh payload, wiping unapplied local edits).
    // Wait for that refetch to land before the caller types into the next
    // card, so nothing is typed into a node that is about to be replaced.
    await this.page
      .waitForResponse(
        (r) => /\/strategy-drafts\/[^/]+$/.test(r.url()) && r.request().method() === "GET",
        { timeout: 15_000 },
      )
      .catch(() => undefined);
    await this.page.waitForTimeout(300);
  }

  // Card 2 — Data & Execution: instrument, capital, range, execution timing,
  // realistic cost assumptions (commission/spread set so Ready Check has no
  // EXECUTION_ASSUMPTIONS_DEFAULT warning) and the APPROVED market dataset
  // pinned through the picker (never a hand-typed infra id).
  async fillDataAndExecution(): Promise<void> {
    const root = this.root;
    await root.getByLabel("Market (instrument)").fill(GOLDEN_INSTRUMENT);
    await root.getByLabel("Initial capital").fill("10000");
    await root.getByLabel("Backtest range — start").fill(GOLDEN_RANGE_START);
    await root.getByLabel("Backtest range — end").fill(GOLDEN_RANGE_END);
    await root.getByLabel("Entry execution").selectOption("next_candle_open");
    await root.getByLabel("Exit execution").selectOption("next_candle_open");
    await root.getByLabel("Commission").fill("0.04");
    await root.getByLabel("Spread").fill("0.01");
    await root.getByLabel("Slippage value").fill("0.05");
    await root.getByRole("button", { name: "Choose market dataset" }).click();
    await this.page
      .locator(".pkg-picker-row")
      .filter({ hasText: GOLDEN_DATASET_TITLE })
      .first()
      .click();
    // The pinned summary replaces the browser — the picker never leaves a raw
    // id input behind.
    await expect(root.getByText(GOLDEN_DATASET_TITLE).first()).toBeVisible();
    await this.applyCard("Apply Data & Execution changes");
  }

  // Card 3 — Position Entry: signal rule + the APPROVED indicator package
  // pinned from the Library picker (server-truth can_use gating).
  async fillPositionEntry(): Promise<void> {
    const root = this.root;
    await root.getByLabel("Entry signal block rule").selectOption("required_indicator_blocks_only");
    await root.getByLabel("Trigger source").first().selectOption("indicator_native_trigger");
    await root.getByRole("button", { name: "Choose indicator" }).first().click();
    await this.page
      .locator(".pkg-picker-row")
      .filter({ hasText: GOLDEN_INDICATOR_NAME })
      .first()
      .click();
    await expect(root.getByText(GOLDEN_INDICATOR_NAME).first()).toBeVisible();
    await this.applyCard("Apply Position Entry changes");
  }

  // Card 5 — Protection/Stop: a strategy with neither exit logic nor an active
  // stop is a readiness blocker (STRATEGY_NO_EXIT_OR_STOP), so the golden path
  // enables the percentage stop.
  async enablePercentageStop(): Promise<void> {
    await this.root.getByLabel("Percentage stop", { exact: true }).check();
    await this.applyCard("Apply Protection / Stop changes");
  }

  // Card 6 — Position Sizing: base size is required for base_position_size.
  async fillPositionSizing(): Promise<void> {
    // The required-field label carries a trailing "*" in its accessible name and
    // two sibling fields substring-match "position size" — anchor + first().
    await this.root.getByLabel(/^Base position size/).first().fill("1000");
    await this.applyCard("Apply Position Sizing changes");
  }

  // Honest boundary (R2-07 finding, reported separately): the Mainboard inline
  // flow exposes NO control for the REQUIRED StrategyConfig.rationale_family_id
  // (the Strategy Context card is read-only and "+ Add -> Add Strategy" creates
  // the draft with no family). Until the product grows an inline family picker,
  // the golden path runs as the bootstrap Admin and sets the family through the
  // admin-gated Advanced (raw payload) editor — a REAL product surface, no
  // mocking. `familyId` comes from the live /rationale-families read.
  async setRationaleFamilyViaAdvancedEditor(familyId: string): Promise<void> {
    const root = this.root;
    await root.locator("summary", { hasText: "Advanced (raw payload)" }).click();
    const textarea = root.getByLabel(/StrategyConfig payload/);
    // The editor re-seeds from the server draft on each applied patch — wait
    // until it reflects the LAST card apply (position sizing) before editing,
    // so the full-payload replace below never resurrects a stale draft.
    await expect
      .poll(async () => (await textarea.inputValue()).includes('"base_position_size"'), {
        timeout: 15_000,
      })
      .toBe(true);
    const current = JSON.parse(await textarea.inputValue()) as Record<string, unknown>;
    current.rationale_family_id = familyId;
    await textarea.fill(JSON.stringify(current));
    await root.getByRole("button", { name: "Apply payload" }).click();
    await expect(this.page.getByText(/Payload applied — draft now at row version/).last()).toBeVisible({
      timeout: 15_000,
    });
  }

  // Validate must come back with NO blockers — a blocker list here is a hard
  // failure of the golden path (GAP madde 12: blocked is NOT success).
  async validateExpectValid(): Promise<void> {
    await this.root.getByRole("button", { name: "Validate" }).click();
    await expect(this.page.getByText("Valid config")).toBeVisible({ timeout: 15_000 });
  }

  // Save the immutable revision; the Mainboard auto-attaches the mirror
  // revision, so the draft box is replaced by a persisted, enabled ItemRow.
  async saveAndExpectAttached(): Promise<void> {
    await this.root.getByRole("button", { name: "Save Strategy Revision" }).click();
    await expect(
      this.page
        .locator(".strategy-package")
        .filter({ has: this.page.getByRole("button", { name: /^Edit this strategy/ }) })
        .first(),
    ).toBeVisible({ timeout: 20_000 });
  }
}
