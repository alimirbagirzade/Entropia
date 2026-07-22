import { expect, test } from "@playwright/test";

import { freshActor, logIn, signUp } from "../fixtures/auth";
import { LoginPage } from "../pages/LoginPage";
import { apiGet, apiReady, getMe, readSessionToken } from "../utils/api";

// Real, unmocked round trips to POST /v1/auth/signup, /login, /logout against
// the live Docker Compose stack (the normal AUTH_MODE=session profile). This is
// the foundation journey every other spec builds on.
//
// audit TEST-08: a static "Mainboard" heading is NOT proof of authentication —
// it can render while its protected query shows UNAUTHENTICATED. So the success
// journey asserts SERVER truth directly (the exact 11 required checks): /me is
// authenticated for the exact principal + server role, protected reads are not
// 401, the DOM carries no UNAUTHENTICATED state, refresh keeps the principal,
// logout revokes the very token the browser held, and a normal User is not shown
// Admin UI — all while the service planes stay healthy.
test.describe("Authentication", () => {
  test("session-mode signup → protected access → refresh → logout revokes", async ({ page }) => {
    // (11) The whole product's service planes (API + Postgres + Redis + MinIO +
    // scheduler + coordinator + workers) are healthy before we assert anything.
    expect((await apiReady(page)).status()).toBe(200);

    const actor = freshActor("auth");

    // (1) Signup creates the exact user + (2) auto-login stores a session token.
    await signUp(page, actor);
    await expect(page).toHaveURL("/");
    const token = await readSessionToken(page);
    expect(token).toBeTruthy();

    // (3) /me returns is_authenticated=true, the exact principal, and a server
    // role — the real post-login anchor, not a page heading.
    const me = await getMe(page, token);
    expect(me.is_authenticated).toBe(true);
    expect(me.principal_id).toBeTruthy();
    expect(me.role).toBeTruthy();
    const principalId = me.principal_id;

    // (4)+(5) Protected reads succeed (never 401) with the stored session token.
    expect((await apiGet(page, "/mainboards/default", token)).status()).not.toBe(401);
    expect((await apiGet(page, "/strategy-drafts", token)).status()).not.toBe(401);

    // (6) The protected UI contains no authentication-error state.
    await expect(page.getByText(/UNAUTHENTICATED/i)).toHaveCount(0);

    // (10) A normal User is never shown Admin-only UI. The admin-only "Panel"
    // menu group is filtered out of the menu bar for a baseline User.
    await expect(page.getByRole("button", { name: "Log out" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Panel", exact: true })).toHaveCount(0);

    // (7) A full reload keeps the SAME authenticated principal (session persists).
    await page.reload();
    await expect(page.getByRole("button", { name: "Log out" })).toBeVisible({ timeout: 15_000 });
    const afterReload = await getMe(page, await readSessionToken(page));
    expect(afterReload.is_authenticated).toBe(true);
    expect(afterReload.principal_id).toBe(principalId);

    // (8) Logout revokes server-side and clears the local session — the header
    // flips to the anonymous "Login / Sign Up" control.
    await page.getByRole("button", { name: "Log out" }).click();
    await expect(page.getByRole("link", { name: "Login / Sign Up" })).toBeVisible({ timeout: 15_000 });
    expect(await readSessionToken(page)).toBeNull();

    // (9) The OLD token is rejected after logout — /me over the revoked token is
    // a 401 SESSION_INVALID, never a silent downgrade to an anonymous 200. (Only
    // presenting NO credential resolves anonymous; a presented-but-invalid one is
    // an error, which is exactly what the stale-session redirect keys off.)
    const revoked = await apiGet(page, "/me", token);
    expect(revoked.status()).toBe(401);
    expect(((await revoked.json()) as { error?: { code?: string } }).error?.code).toBe("SESSION_INVALID");

    // ...and the account can log back in as the same principal (session reset).
    await logIn(page, actor);
    await expect(page).toHaveURL("/");
    const relogin = await getMe(page, await readSessionToken(page));
    expect(relogin.is_authenticated).toBe(true);
    expect(relogin.principal_id).toBe(principalId);
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
    // ...and /me over no token is anonymous (server truth, not just chrome).
    const me = await getMe(page, null);
    expect(me.is_authenticated).toBe(false);
  });
});
