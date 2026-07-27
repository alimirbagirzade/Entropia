import { expect, type Page } from "@playwright/test";

// Mirrors frontend/src/pages/CreatePackage.tsx — the CP Agent workspace
// (doc 06 §4-§9). R2-12: drives the FULL request → published lifecycle —
// compose, Pre-Check modal, C.D.P (candidate → draft), typed baseline
// metadata + CSV upload + parse, validation, and (as an Admin session)
// approve & publish. Every step asserts the exact expected server state —
// never "blocked or error also accepted" (GAP item 11).
export class CreatePackagePage {
  constructor(private readonly page: Page) {}

  async goto(): Promise<void> {
    await this.page.goto("/packages/create");
    await expect(
      this.page.getByRole("heading", { name: "Create Package", exact: true }),
    ).toBeVisible();
  }

  // ESP + generate_from_description: needs no Rationale Family / source
  // language, so the compose journey is self-contained.
  async submitEspDescriptionRequest(description: string): Promise<string> {
    await this.page.getByLabel("Package type").selectOption("embedded_system");
    await this.page.getByLabel("Creation mode").selectOption("generate_from_description");
    await this.page.getByLabel("Description").fill(description);
    return await this.send();
  }

  // Indicator + translate_existing_code (the PR #316 proven chain): PineScript
  // source with a declared `ta.sma` dependency + the first ACTIVE Rationale
  // Family from the server-hydrated select (seeded canon families).
  async submitTranslateIndicatorRequest(sourceCode: string, declaredKey: string): Promise<string> {
    await this.page.getByLabel("Package type").selectOption("indicator");
    await this.page.getByLabel("Creation mode").selectOption("translate_existing_code");
    await this.page.getByLabel("Source language").selectOption("pinescript");
    // Wait for the server-hydrated family options, then pick the first real one.
    const family = this.page.getByLabel("Rationale family");
    await expect(async () => {
      expect(await family.locator("option").count()).toBeGreaterThan(1);
    }).toPass({ timeout: 15_000 });
    await family.selectOption({ index: 1 });
    await this.page.getByLabel("Source code").fill(sourceCode);
    await this.page.getByLabel("Declared dependencies").fill(declaredKey);
    return await this.send();
  }

  private async send(): Promise<string> {
    await this.page.getByRole("button", { name: "Send" }).click();
    const created = this.page.getByText(/Request created — /);
    await expect(created).toBeVisible({ timeout: 20_000 });
    const text = await created.innerText();
    const match = /Request created — (\S+)/.exec(text);
    if (!match) throw new Error(`Could not parse request id from "${text}"`);
    return match[1];
  }

  // Select an existing request in the "My requests" switcher strip (an Admin
  // session sees every actor's requests here — doc 06 §2).
  async selectRequest(requestId: string): Promise<void> {
    const button = this.page.getByRole("button", { name: new RegExp(requestId) });
    await expect(button).toBeVisible({ timeout: 15_000 });
    await button.click();
    // The workspace panel head echoes the selected request id once loaded.
    await expect(
      this.page.locator(".cp-panel-head", { hasText: requestId }).first(),
    ).toBeVisible({ timeout: 15_000 });
  }

  // Pre-Check via the workspace overlay (UI-07). Asserts the EXACT passed
  // status line — blocked / failed / not_applicable are journey failures.
  async runPreCheckExpectPassed(): Promise<void> {
    await this.page.getByRole("button", { name: "Pre-Check", exact: true }).click();
    const dialog = this.page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await dialog.getByRole("button", { name: "Run Pre-Check" }).click();
    // The scan runs in the durable worker (F-01a), so this waits on a real
    // background compute + its SSE-driven refetch, not an in-transaction result.
    await expect(
      dialog.getByText("Pre-Check passed. Dependency manifest is ready for candidate generation."),
    ).toBeVisible({ timeout: 30_000 });
    await dialog.getByRole("button", { name: "Close" }).click();
    await expect(dialog).not.toBeVisible();
  }

  // C.D.P — generate candidate then create the draft package. F-01b made the
  // generation a DURABLE background job, so this is two server-authoritative
  // phases: the first click admits the job (the button locks while it runs) and
  // the worker lands candidate_ready on the projection; the second click drafts
  // against the hash the worker pinned. Asserts the draft revision confirmation
  // (server dict verbatim) — a synthesised candidate could never produce it.
  async createDraftPackage(): Promise<void> {
    const cdp = this.page.getByRole("button", { name: "C.D.P" });
    await expect(cdp).toBeEnabled({ timeout: 15_000 });
    await cdp.click();
    // Match the C.D.P live region alone: the "Next step:" hint opens with the same
    // "Candidate ready — " phrase, so the assertion pins the notice's own sentence.
    await expect(
      this.page.getByText(/Candidate ready — [\s\S]*Click C\.D\.P again/),
    ).toBeVisible({ timeout: 30_000 });

    const draft = this.page.getByRole("button", { name: "C.D.P" });
    await expect(draft).toBeEnabled({ timeout: 15_000 });
    await draft.click();
    await expect(this.page.getByText(/Draft created — revision/)).toBeVisible({
      timeout: 20_000,
    });
  }

  // R2-12: the parse-required baseline descriptors are typed product fields —
  // the journey never types JSON.
  async fillBaselineMetadata(fields: {
    provider: string;
    symbol: string;
    timeframe: string;
    rangeStart: string;
    rangeEnd: string;
    timezone: string;
    settings: string;
    sourceRevisionContext: string;
  }): Promise<void> {
    await this.page.getByLabel("Baseline provider").fill(fields.provider);
    await this.page.getByLabel("Baseline symbol").fill(fields.symbol);
    await this.page.getByLabel("Baseline timeframe").fill(fields.timeframe);
    await this.page.getByLabel("Baseline range start").fill(fields.rangeStart);
    await this.page.getByLabel("Baseline range end").fill(fields.rangeEnd);
    await this.page.getByLabel("Baseline timezone").fill(fields.timezone);
    await this.page.getByLabel("Baseline settings").fill(fields.settings);
    await this.page.getByLabel("Source revision context").fill(fields.sourceRevisionContext);
  }

  async uploadBaselineCsv(name: string, csv: string): Promise<void> {
    await this.page
      .getByLabel("TradingView baseline CSV file")
      .setInputFiles({ name, mimeType: "text/csv", buffer: Buffer.from(csv) });
    await this.page.getByRole("button", { name: "Upload CSV" }).click();
    await expect(this.page.getByText(/Baseline uploaded — asset/)).toBeVisible({
      timeout: 20_000,
    });
  }

  async runBaselineParseExpectPassed(): Promise<void> {
    const parse = this.page.getByRole("button", { name: "Run baseline parse" });
    await expect(parse).toBeEnabled({ timeout: 15_000 });
    await parse.click();
    await expect(this.page.getByText(/Baseline parse passed/)).toBeVisible({ timeout: 20_000 });
  }

  // F-01b: the click ADMITS a durable run (the row is appended queued); the seven
  // mandatory checks execute in the worker and the PASSED verdict reaches the UI
  // through the projection refetch, so the wait covers a real background compute.
  async runValidationExpectPassed(): Promise<void> {
    const validate = this.page.getByRole("button", { name: "Run Validation Tests" });
    await expect(validate).toBeEnabled({ timeout: 15_000 });
    await validate.click();
    await expect(this.page.getByText(/Validation passed — run/)).toBeVisible({ timeout: 45_000 });
  }

  // Admin-only (AdminGate over /me + CR-02 server-side). Asserts the exact
  // approved & published confirmation.
  async approveExpectPublished(): Promise<void> {
    const approveButton = this.page.getByRole("button", { name: "Approve Package" });
    await expect(approveButton).toBeEnabled({ timeout: 15_000 });
    await approveButton.click();
    await expect(this.page.getByText(/Approved & published — revision/)).toBeVisible({
      timeout: 20_000,
    });
  }

  // The Package Status side panel's "Package Name" row carries the real
  // package_root_id once a draft exists.
  async packageRootId(): Promise<string> {
    const row = this.page.locator(".cp-status-row", { hasText: "Package Name" });
    await expect(async () => {
      const value = (await row.innerText()).replace("Package Name", "").trim();
      expect(value.length).toBeGreaterThan(4);
      expect(value).not.toBe("—");
    }).toPass({ timeout: 15_000 });
    return (await row.innerText()).replace("Package Name", "").trim();
  }

  errorAlert() {
    return this.page.getByRole("alert");
  }

  myRequestsHeading() {
    return this.page.getByRole("heading", { name: "My requests", exact: true });
  }
}
