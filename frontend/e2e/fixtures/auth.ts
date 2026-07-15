import { expect, type Page } from "@playwright/test";

import { LoginPage } from "../pages/LoginPage";
import { uniqueEmail, uniqueUsername } from "../utils/ids";

export interface Actor {
  username: string;
  password: string;
  displayName: string;
  email: string;
}

const DEFAULT_PASSWORD = "E2e-Passw0rd!23";

export function freshActor(prefix: string): Actor {
  const username = uniqueUsername(prefix);
  return {
    username,
    password: DEFAULT_PASSWORD,
    displayName: `${prefix} E2E`,
    email: uniqueEmail(prefix),
  };
}

// Fixed identity used to bootstrap the first Admin (matches
// ENTROPIA_BOOTSTRAP_ADMIN_EMAIL in the CI/local env — see README.md). Reused
// across specs so only the FIRST run against a fresh DB actually provisions
// Admin; subsequent runs just log the existing account back in.
export const ADMIN_ACTOR: Actor = {
  username: process.env.E2E_ADMIN_USERNAME ?? "e2e_admin",
  password: process.env.E2E_ADMIN_PASSWORD ?? "E2e-Admin-Passw0rd!23",
  displayName: "E2E Admin",
  email: process.env.E2E_ADMIN_EMAIL ?? "e2e_admin@e2e.entropia.test",
};

async function afterAuthLanded(page: Page): Promise<void> {
  // Login.tsx navigates to `from` (default "/") on success — the Mainboard
  // page title is the stable post-auth anchor across both login and signup.
  // First signup after a cold stack boot is slow (argon2id hash + first DB
  // connection + first render), so allow generous headroom here.
  await expect(page.getByRole("heading", { name: "Mainboard", exact: true })).toBeVisible({ timeout: 45_000 });
}

// Signs up a brand-new actor via the real form and lands authenticated.
export async function signUp(page: Page, actor: Actor): Promise<void> {
  const login = new LoginPage(page);
  await login.goto();
  await login.switchToSignup();
  await login.fillCredentials(actor.username, actor.password);
  await login.fillSignupExtras({ displayName: actor.displayName, email: actor.email });
  await login.submitSignup();
  await afterAuthLanded(page);
}

export async function logIn(page: Page, actor: Actor): Promise<void> {
  const login = new LoginPage(page);
  await login.goto();
  await login.fillCredentials(actor.username, actor.password);
  await login.submitLogin();
  await afterAuthLanded(page);
}

// Ensures ADMIN_ACTOR is authenticated: signs up (first run against a fresh
// DB — the matching-email bootstrap in application/commands/auth.py promotes
// this signup to Admin as long as no Admin exists yet) or, if the account
// already exists from a prior run, logs in instead. Either path is a real,
// unmocked round trip to /v1/auth/*.
export async function ensureAdmin(page: Page): Promise<void> {
  const login = new LoginPage(page);
  await login.goto();
  await login.switchToSignup();
  await login.fillCredentials(ADMIN_ACTOR.username, ADMIN_ACTOR.password);
  await login.fillSignupExtras({ displayName: ADMIN_ACTOR.displayName, email: ADMIN_ACTOR.email });
  await login.submitSignup();

  // Username already taken (USERNAME_TAKEN) on a repeat run -> fall back to
  // login with the same fixed credentials instead of failing the journey.
  const alert = login.errorAlert();
  const raced = await Promise.race([
    page
      .getByRole("heading", { name: "Mainboard", exact: true })
      .waitFor({ state: "visible", timeout: 20_000 })
      .then(() => "landed" as const),
    alert.waitFor({ state: "visible", timeout: 20_000 }).then(() => "error" as const),
  ]);

  if (raced === "error") {
    await login.switchToLogin();
    await login.fillCredentials(ADMIN_ACTOR.username, ADMIN_ACTOR.password);
    await login.submitLogin();
    await afterAuthLanded(page);
  }
}
