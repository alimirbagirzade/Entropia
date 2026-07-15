import { expect, test } from "@playwright/test";

import { freshActor, logIn, signUp } from "../fixtures/auth";
import { LoginPage } from "../pages/LoginPage";

// Real, unmocked round trips to POST /v1/auth/signup, /login, /logout against
// the live Docker Compose stack (AUTH_MODE=session). This is the foundation
// journey every other spec in this suite builds on.
test.describe("Authentication", () => {
  test("sign up, log out, log back in", async ({ page }) => {
    const actor = freshActor("auth");

    await signUp(page, actor);
    await expect(page).toHaveURL("/");

    // Logout — Layout's AuthControl renders "Log out" once a session exists,
    // and "Login / Sign Up" once the token is cleared.
    await page.getByRole("button", { name: "Log out" }).click();
    await expect(page.getByRole("link", { name: "Login / Sign Up" })).toBeVisible({ timeout: 15_000 });

    await logIn(page, actor);
    await expect(page).toHaveURL("/");
    await expect(page.getByRole("button", { name: "Log out" })).toBeVisible();
  });

  test("rejects an unknown login with the server's canonical error envelope", async ({ page }) => {
    const login = new LoginPage(page);
    await login.goto();
    await login.fillCredentials("nonexistent_e2e_user_xyz", "wrong-password");
    await login.submitLogin();

    const alert = login.errorAlert();
    await expect(alert).toBeVisible({ timeout: 15_000 });
    // The client renders "<CODE>: <message>" verbatim from the API — never a
    // fabricated client-side message (Login.tsx errMsg).
    await expect(alert).toContainText(":");
  });

  test("a guest sees the unauthenticated Layout state, not a session", async ({ page }) => {
    // Fresh, unauthenticated browser context (no prior signIn in this test).
    // The app deliberately does NOT client-side redirect anonymous users
    // (documented honest boundary in Login.tsx: "no anonymous -> /login route
    // guard"); the real auth boundary is enforced server-side and reflected in
    // the Layout AuthControl. Deterministic guest assertion: the header offers
    // "Login / Sign Up" and never exposes a signed-in "Log out".
    await page.goto("/panel");
    await expect(page.getByRole("link", { name: "Login / Sign Up" })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("button", { name: "Log out" })).toHaveCount(0);
  });
});
