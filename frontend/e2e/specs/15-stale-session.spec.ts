import { expect, test } from "@playwright/test";

import { freshActor, signUp } from "../fixtures/auth";
import { readSessionToken } from "../utils/api";

// TEST-10 (browser half of the stale-session regression): the session-mode shell
// must survive a server-invalidated token discovered by an unrelated protected
// read with EXACTLY ONE clean return to /login — no redirect loop, no lingering
// authenticated chrome. The frontend unit suite
// (frontend/src/test/staleSession.test.tsx) pins the client contract; this is the
// real-browser proof against the live stack.
const TOKEN_KEY = "entropia.sessionToken";

test.describe("stale session — one clean redirect to login", () => {
  test("a corrupted/revoked stored token lands the user back on /login once", async ({ page }) => {
    const actor = freshActor("stale");
    await signUp(page, actor);
    await expect(page).toHaveURL("/");
    expect(await readSessionToken(page)).toBeTruthy();

    // Corrupt the stored Bearer token in place — the browser now holds a token the
    // server will reject, exactly like an expired/revoked session it never learned
    // about. (A garbage token resolves to the same canonical SESSION_INVALID as an
    // expired or server-revoked one.)
    await page.evaluate((key) => localStorage.setItem(key, "tok_corrupted_not_a_real_session"), TOKEN_KEY);

    // Any protected read now fails. Reloading re-mounts the shell (which gates its
    // protected /me behind /meta), the first 401 SESSION_INVALID clears the local
    // session once, and the shell redirects once.
    await page.reload();

    await expect(page).toHaveURL(/\/login$/, { timeout: 15_000 });
    await expect(page.getByText("ENTROPIA")).toBeVisible();
    // The stale token was cleared as part of the single invalidation.
    await expect.poll(() => readSessionToken(page)).toBeNull();

    // No loop: give any stray re-navigation a beat, then assert we are still on a
    // stable /login (a redirect storm would bounce the URL or never settle).
    await page.waitForTimeout(500);
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole("tab", { name: "Log in" })).toBeVisible();
  });
});
