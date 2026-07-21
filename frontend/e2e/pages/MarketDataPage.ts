import { expect, type Locator, type Page } from "@playwright/test";

// A minimal well-formed OHLCV raw source — the analysis job parses these bytes
// for real (no mocks), so the columns must satisfy the canonical schema.
const DEFAULT_RAW_CSV =
  "timestamp,open,high,low,close,volume\n" +
  "2024-01-01T00:00:00Z,1,2,0.5,1.5,100\n" +
  "2024-01-01T00:15:00Z,1.5,2.5,1,2,120\n";

export interface RawFile {
  name: string;
  mimeType: string;
  buffer: Buffer;
}

// Mirrors frontend/src/pages/MarketData.tsx (doc 11 §4 + KALAN-A): the setup
// card's Browse File input STARTS the process — one submit chains create ->
// upload -> finalize -> analysis. Label/role selectors only.
export class MarketDataPage {
  constructor(private readonly page: Page) {}

  async goto(): Promise<void> {
    await this.page.goto("/market-data");
    await expect(this.page.getByRole("heading", { name: "Market Data", exact: true })).toBeVisible();
  }

  // Fills the setup form, selects a REAL raw source file (KALAN-A Browse File)
  // and submits the chained ingest. Resolves with the created entity id once
  // the create stage confirms; the upload/finalize/analysis stages continue —
  // await expectIngestStarted() for the 202 admission.
  async createDataset(opts: {
    title: string;
    instrumentId?: string;
    type?: string;
    file?: RawFile;
  }): Promise<string> {
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
    await this.page
      .locator("#md-setup-file")
      .setInputFiles(
        opts.file ?? { name: "raw.csv", mimeType: "text/csv", buffer: Buffer.from(DEFAULT_RAW_CSV) },
      );
    await this.page.getByRole("button", { name: "Create dataset & upload" }).click();

    const created = this.page.getByText(/Created — /);
    await expect(created).toBeVisible({ timeout: 20_000 });
    const text = await created.innerText();
    const match = /Created — (\S+) /.exec(text);
    if (!match) throw new Error(`Could not parse entity id from "${text}"`);
    return match[1];
  }

  // The chained submit ends with the durable analysis 202 admission.
  async expectIngestStarted(): Promise<void> {
    await expect(this.page.getByText(/Analysis requested — job/)).toBeVisible({ timeout: 30_000 });
  }

  registryRow(title: string): Locator {
    return this.page.locator("table.metrics-table tbody tr", { hasText: title });
  }

  // The auto-opened dataset detail card (aria anchor md-detail-h).
  detailCard(): Locator {
    return this.page.locator('section[aria-labelledby="md-detail-h"]');
  }

  // The detail polls while uploading/analyzing, so the analysis outcome lands
  // without a manual refresh — wait for the given revision state to render.
  async waitForRevisionState(state: string, timeoutMs = 90_000): Promise<void> {
    await expect(this.detailCard().getByText(state, { exact: true }).first()).toBeVisible({
      timeout: timeoutMs,
    });
  }

  // Opens a dataset's detail from the registry by its title.
  async openFromRegistry(title: string): Promise<void> {
    await this.registryRow(title).getByRole("button", { name: "Open" }).click();
    await expect(this.detailCard().getByText("Revision history")).toBeVisible({ timeout: 15_000 });
  }

  // Admin-only: approve the currently selected target revision (defaults to the
  // head) and wait for the exact confirmation — not "any response".
  async approveHeadRevision(): Promise<void> {
    await this.page.getByRole("button", { name: "Approve (Admin)" }).click();
    await expect(this.page.getByText(/Approved — revision .* is now approved/)).toBeVisible({
      timeout: 20_000,
    });
  }

  // Resolve-probe: the exact APPROVED revision a Run would pin right now.
  async resolveApprovedBundle(): Promise<void> {
    await this.page.getByRole("button", { name: "Resolve approved bundle" }).click();
    await expect(this.page.getByText(/Pinned — revision/)).toBeVisible({ timeout: 15_000 });
  }
}
