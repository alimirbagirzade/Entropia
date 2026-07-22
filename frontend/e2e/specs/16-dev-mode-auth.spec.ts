import { expect, test, type APIResponse, type Page } from "@playwright/test";

import { API_BASE, getMe } from "../utils/api";

// TEST-09 / audit §9.6 — the real dev-mode browser acceptance flow. An adaptive
// helper that works around either mode is NOT proof that dev mode satisfies its
// own contract, so this spec asserts the dev contract explicitly. It self-skips
// unless the stack under test actually reports AUTH_MODE=dev (the CI dev-auth job
// brings up that profile in its own Compose project — see .github/workflows/e2e.yml),
// so it is a harmless no-op inside the default session-mode job.
const TOKEN_KEY = "entropia.sessionToken";
const DEV_PRINCIPAL = "user_admin"; // the credentialless dev Admin seeded in dev mode

function apiGetWithActor(page: Page, path: string, actorId: string): Promise<APIResponse> {
  return page.request.get(`${API_BASE}${path}`, { headers: { "X-Actor-Id": actorId } });
}

test.describe("dev-mode acceptance (X-Actor-Id, no login)", () => {
  test("dev mode hides login, keeps the actor control, and authenticates via X-Actor-Id", async ({
    page,
  }) => {
    const meta = (await (await page.request.get(`${API_BASE}/meta`)).json()) as {
      auth_mode: string;
      environment: string;
    };
    test.skip(meta.auth_mode !== "dev", "dev-mode acceptance runs only against the AUTH_MODE=dev stack");

    // /meta is the runtime source of truth: dev, and dev is only legal in local —
    // the backend refuses to boot dev outside local (F-22), so a live dev stack is
    // necessarily local. Together these assert "dev mode is impossible in prod".
    expect(meta.auth_mode).toBe("dev");
    expect(meta.environment).toBe("local");

    await page.goto("/");

    // Login / Sign Up is neither functional nor advertised; the actor control is.
    await expect(page.getByRole("link", { name: "Login / Sign Up" })).toHaveCount(0);
    await expect(page.getByText("local dev — identity via")).toBeVisible();
    await expect(page.locator("#dev-actor")).toBeVisible();

    // Direct /login shows the dev explanation, not a working form.
    await page.goto("/login");
    await expect(page.getByText("Local development mode")).toBeVisible();

    // A stale Bearer token from a previous session-mode run must NOT hide the only
    // control dev mode honours.
    await page.evaluate((key) => localStorage.setItem(key, "tok_stale_from_session_run"), TOKEN_KEY);
    await page.goto("/");
    await expect(page.locator("#dev-actor")).toBeVisible();

    // Select the dev principal — applying it refetches identity-bound data. Capture
    // the app's OWN /me request to prove the credential mechanism.
    const meRequest = page.waitForRequest((r) => r.url().includes("/api/v1/me") && r.method() === "GET");
    await page.locator("#dev-actor").fill(DEV_PRINCIPAL);
    await page.locator("#dev-actor").press("Enter");
    const req = await meRequest;
    const headers = req.headers();
    // Requests carry X-Actor-Id and NEVER a Bearer, even with the stale token stored.
    expect(headers["x-actor-id"]).toBe(DEV_PRINCIPAL);
    expect(headers["authorization"]).toBeUndefined();

    // Sanity: no credential at all resolves anonymous (no ambient cookie/session).
    const anon = await getMe(page, null);
    expect(anon.is_authenticated).toBe(false);

    // /me authenticates that exact principal through X-Actor-Id (server truth).
    const meAsActor = (await (await apiGetWithActor(page, "/me", DEV_PRINCIPAL)).json()) as {
      is_authenticated: boolean;
      principal_id: string | null;
      is_admin: boolean;
    };
    expect(meAsActor.is_authenticated).toBe(true);
    expect(meAsActor.principal_id).toBe(DEV_PRINCIPAL);
    expect(meAsActor.is_admin).toBe(true);

    // Protected pages work: a protected read resolves (never 401) via X-Actor-Id.
    const mainboard = await apiGetWithActor(page, "/mainboards/default", DEV_PRINCIPAL);
    expect(mainboard.status()).not.toBe(401);
  });
});
