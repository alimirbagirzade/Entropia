import { expect, type Page } from "@playwright/test";

// Mirrors frontend/src/pages/Login.tsx verbatim (role/label selectors only —
// no test ids, matching the app's accessibility-first markup).
export class LoginPage {
  constructor(private readonly page: Page) {}

  async goto(): Promise<void> {
    await this.page.goto("/login");
    await expect(this.page.getByText("ENTROPIA")).toBeVisible();
  }

  async switchToSignup(): Promise<void> {
    await this.page.getByRole("tab", { name: "Sign up" }).click();
  }

  async switchToLogin(): Promise<void> {
    await this.page.getByRole("tab", { name: "Log in" }).click();
  }

  async fillCredentials(username: string, password: string): Promise<void> {
    await this.page.getByLabel("Username").fill(username);
    await this.page.getByLabel("Password").fill(password);
  }

  async fillSignupExtras(opts: { displayName?: string; email?: string }): Promise<void> {
    if (opts.displayName) {
      await this.page.getByLabel(/Display name/).fill(opts.displayName);
    }
    if (opts.email) {
      await this.page.getByLabel(/^Email/).fill(opts.email);
    }
  }

  async submitLogin(): Promise<void> {
    await this.page.getByRole("button", { name: "Log in" }).click();
  }

  async submitSignup(): Promise<void> {
    await this.page.getByRole("button", { name: "Create account" }).click();
  }

  errorAlert() {
    return this.page.getByRole("alert");
  }
}
