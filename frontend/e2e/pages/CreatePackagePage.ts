import { expect, type Page } from "@playwright/test";

// Mirrors frontend/src/pages/CreatePackage.tsx "New request" composer
// (doc 06 §4). Uses package_type=embedded_system + creation_mode=
// generate_from_description deliberately: that combination needs no
// pre-seeded Rationale Family and no source-language selection, so the
// journey is self-contained (no cross-page setup) while still exercising a
// real POST /package-requests round trip.
export class CreatePackagePage {
  constructor(private readonly page: Page) {}

  async goto(): Promise<void> {
    await this.page.goto("/packages/create");
    await expect(this.page.getByRole("heading", { name: "Create Package", exact: true })).toBeVisible();
  }

  async submitEspDescriptionRequest(description: string): Promise<string> {
    await this.page.getByLabel("Package type").selectOption("embedded_system");
    await this.page.getByLabel("Creation mode").selectOption("generate_from_description");
    await this.page.getByLabel("Description").fill(description);
    // UI-06: the compose action button is "Send" (was "Create request").
    await this.page.getByRole("button", { name: "Send" }).click();

    const created = this.page.getByText(/Request created — /);
    await expect(created).toBeVisible({ timeout: 20_000 });
    const text = await created.innerText();
    const match = /Request created — (\S+)/.exec(text);
    if (!match) throw new Error(`Could not parse request id from "${text}"`);
    return match[1];
  }

  errorAlert() {
    return this.page.getByRole("alert");
  }

  myRequestsHeading() {
    return this.page.getByRole("heading", { name: "My requests", exact: true });
  }
}
