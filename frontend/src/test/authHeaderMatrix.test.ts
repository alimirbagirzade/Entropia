import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api, apiRequest, authHeaders } from "@/lib/apiClient";
import { resetAuthMode, setAuthMode, type AuthMode } from "@/lib/authMode";
import { setDevActorId } from "@/lib/devActor";
import { getSessionToken, setSession } from "@/lib/session";
import { uploadFile } from "@/lib/upload";
import type { AuthUser } from "@/lib/types";
import { stubUpload } from "./helpers/xhrStub";

// The one invariant this whole slice exists to guarantee: the incompatible human
// credential is NEVER attached in the selected mode. Every case below seeds BOTH
// stale values into storage at once — a session Bearer token AND a dev actor id —
// which is the exact ambiguous state the old fail-open client shipped both from.
// A correct client attaches exactly one (or, when the mode is unknown, neither).

const USER: AuthUser = { user_id: "u1", username: "alice", display_name: "Alice", role: "user" };
const STALE_TOKEN = "tok_stale";
const STALE_ACTOR = "user_admin";

function seedBothStaleCredentials() {
  setSession({ token: STALE_TOKEN, user: USER, expiresAt: null });
  setDevActorId(STALE_ACTOR);
}

type FetchFn = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

function recordingFetch() {
  return vi.fn<FetchFn>(() =>
    Promise.resolve({
      ok: true,
      status: 200,
      statusText: "OK",
      text: () => Promise.resolve(JSON.stringify({ ok: true })),
    } as unknown as Response),
  );
}

function headersOf(mock: ReturnType<typeof recordingFetch>, callIndex = 0): Record<string, string> {
  return (mock.mock.calls[callIndex][1] as RequestInit).headers as Record<string, string>;
}

// The expected header for each mode, plus the header that must be absent.
const MATRIX: Array<{ mode: AuthMode | null; present: Record<string, string>; absent: string[] }> = [
  { mode: "session", present: { Authorization: `Bearer ${STALE_TOKEN}` }, absent: ["X-Actor-Id"] },
  { mode: "dev", present: { "X-Actor-Id": STALE_ACTOR }, absent: ["Authorization"] },
  // Unknown mode fails closed: no human credential at all, even though both are stored.
  { mode: null, present: {}, absent: ["Authorization", "X-Actor-Id"] },
];

function applyMode(mode: AuthMode | null) {
  if (mode) setAuthMode(mode);
}

function assertHeaders(headers: Record<string, string>, entry: (typeof MATRIX)[number]) {
  for (const [key, value] of Object.entries(entry.present)) {
    expect(headers[key]).toBe(value);
  }
  for (const key of entry.absent) {
    expect(headers[key]).toBeUndefined();
  }
}

beforeEach(() => {
  localStorage.clear();
  // The auth-mode store is module-level; reset so a mode never leaks between cases.
  resetAuthMode();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  resetAuthMode();
});

describe("authHeaders() shared selector — mutual exclusivity with both stale values stored", () => {
  for (const entry of MATRIX) {
    it(`${entry.mode ?? "unknown"} mode attaches only the mode-appropriate credential`, () => {
      seedBothStaleCredentials();
      applyMode(entry.mode);
      assertHeaders(authHeaders(), entry);
    });
  }
});

describe("fetch JSON transport (apiRequest GET + POST)", () => {
  for (const entry of MATRIX) {
    it(`${entry.mode ?? "unknown"} mode: GET sends only the permitted credential`, async () => {
      seedBothStaleCredentials();
      applyMode(entry.mode);
      const fetchMock = recordingFetch();
      vi.stubGlobal("fetch", fetchMock);

      await api.get("/mainboards/default");

      assertHeaders(headersOf(fetchMock), entry);
    });

    it(`${entry.mode ?? "unknown"} mode: POST sends only the permitted credential`, async () => {
      seedBothStaleCredentials();
      applyMode(entry.mode);
      const fetchMock = recordingFetch();
      vi.stubGlobal("fetch", fetchMock);

      await apiRequest("/strategy-drafts", { method: "POST", body: { name: "x" } });

      const headers = headersOf(fetchMock);
      assertHeaders(headers, entry);
      // The caller's content headers survive the credential selection.
      expect(headers["Content-Type"]).toBe("application/json");
    });
  }
});

describe("text transport (apiGetText)", () => {
  for (const entry of MATRIX) {
    it(`${entry.mode ?? "unknown"} mode: text GET sends only the permitted credential`, async () => {
      seedBothStaleCredentials();
      applyMode(entry.mode);
      const fetchMock = recordingFetch();
      vi.stubGlobal("fetch", fetchMock);

      await api.getText("/metrics");

      assertHeaders(headersOf(fetchMock), entry);
    });
  }
});

describe("XHR upload transport (uploadFile)", () => {
  for (const entry of MATRIX) {
    it(`${entry.mode ?? "unknown"} mode: multipart upload sends only the permitted credential`, async () => {
      seedBothStaleCredentials();
      applyMode(entry.mode);
      const { calls } = stubUpload({ "POST /market-data": { ok: true } });
      const file = new File(["bytes"], "a.csv", { type: "text/csv" });

      await uploadFile("/market-data", file, {
        idempotencyKey: "idem-1",
        headers: { "X-Request-Version": "3" },
      }).promise;

      const headers = calls[0].headers;
      assertHeaders(headers, entry);
      // OCC + Idempotency-Key survive the shared credential selection.
      expect(headers["Idempotency-Key"]).toBe("idem-1");
      expect(headers["X-Request-Version"]).toBe("3");
    });
  }
});

describe("XHR upload routes SESSION_INVALID through the shared stale-session flow", () => {
  it("clears the local session when an upload is rejected with SESSION_INVALID", async () => {
    setAuthMode("session");
    setSession({ token: "tok_dead", user: USER, expiresAt: null });
    stubUpload({
      "POST /market-data": { status: 401, error: { code: "SESSION_INVALID", message: "Session is not valid." } },
    });
    const file = new File(["bytes"], "a.csv");

    await expect(uploadFile("/market-data", file).promise).rejects.toMatchObject({
      status: 401,
      code: "SESSION_INVALID",
    });

    // Same one-shot handler as fetch: the dead token is gone, so it cannot poison
    // the next request. Layout's invalidation watcher takes it from here.
    expect(getSessionToken()).toBeNull();
  });

  it("keeps the session when an upload is rejected with a 403 ACCESS_DENIED", async () => {
    setAuthMode("session");
    setSession({ token: "tok_live", user: USER, expiresAt: null });
    stubUpload({
      "POST /market-data": { status: 403, error: { code: "ACCESS_DENIED", message: "Admin only." } },
    });
    const file = new File(["bytes"], "a.csv");

    await expect(uploadFile("/market-data", file).promise).rejects.toMatchObject({
      status: 403,
      code: "ACCESS_DENIED",
    });

    // A forbidden upload says nothing about the session's validity — it survives.
    expect(getSessionToken()).toBe("tok_live");
  });
});
