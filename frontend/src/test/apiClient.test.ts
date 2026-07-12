import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiRequest } from "@/lib/apiClient";

// GAP-15 — the transport-level in-flight single-flight. A same-tick double
// submit fires two apiRequest() calls before React re-renders and disables the
// button; without dedup each would carry its own fresh Idempotency-Key
// (GAP-13) and the backend would apply two side effects. These tests pin the
// contract: concurrent IDENTICAL writes collapse onto one request; distinct
// payloads and reads never merge; a settled request always fires fresh again.

function okResponse(value: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: "OK",
    text: async () => JSON.stringify(value),
  };
}

function errResponse(status: number, code: string) {
  return {
    ok: false,
    status,
    statusText: "ERR",
    text: async () => JSON.stringify({ error: { code, message: code, details: [] } }),
  };
}

// A fetch double whose responses stay pending until release() is called, so a
// test can hold requests in flight while it fires the concurrent duplicate.
function gatedFetch(response: unknown) {
  const releases: Array<() => void> = [];
  const mock = vi.fn(
    () =>
      new Promise((resolve) => {
        releases.push(() => resolve(response));
      }),
  );
  vi.stubGlobal("fetch", mock);
  return { mock, release: () => releases.forEach((r) => r()) };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("apiRequest single-flight (GAP-15)", () => {
  it("collapses concurrent identical writes onto one request and one shared result", async () => {
    const { mock, release } = gatedFetch(okResponse({ id: "r1" }));

    const p1 = apiRequest<{ id: string }>("/work-objects", { method: "POST", body: { a: 1 } });
    const p2 = apiRequest<{ id: string }>("/work-objects", { method: "POST", body: { a: 1 } });

    // The second submit found the first in flight — no second fetch went out.
    expect(mock).toHaveBeenCalledTimes(1);

    release();
    const [r1, r2] = await Promise.all([p1, p2]);
    expect(r1).toEqual({ id: "r1" });
    expect(r2).toBe(r1); // the same shared promise result, not a duplicate
  });

  it("dedups despite a different Idempotency-Key header (signature excludes headers)", async () => {
    const { mock, release } = gatedFetch(okResponse({ id: "r1" }));

    const p1 = apiRequest("/work-objects", {
      method: "POST",
      body: { a: 1 },
      headers: { "Idempotency-Key": "key-1" },
    });
    const p2 = apiRequest("/work-objects", {
      method: "POST",
      body: { a: 1 },
      headers: { "Idempotency-Key": "key-2" },
    });

    expect(mock).toHaveBeenCalledTimes(1);
    // The one request that went out carries the FIRST caller's key. (The mock's
    // impl declares no params, so read the runtime fetch(url, init) args via a
    // cast rather than named — unused — parameters.)
    const call = mock.mock.calls[0] as unknown as [unknown, RequestInit];
    expect((call[1].headers as Record<string, string>)["Idempotency-Key"]).toBe("key-1");

    release();
    await Promise.all([p1, p2]);
  });

  it("does NOT merge concurrent writes with distinct bodies", async () => {
    const { mock, release } = gatedFetch(okResponse({ ok: true }));

    const p1 = apiRequest("/work-objects", { method: "POST", body: { a: 1 } });
    const p2 = apiRequest("/work-objects", { method: "POST", body: { a: 2 } });

    expect(mock).toHaveBeenCalledTimes(2);
    release();
    await Promise.all([p1, p2]);
  });

  it("does NOT merge distinct intents through one endpoint (e.g. mainboard pin vs reorder)", async () => {
    const { mock, release } = gatedFetch(okResponse({ ok: true }));

    const pin = apiRequest("/mainboard-items/it1", { method: "PATCH", body: { intent: "pin_revision" } });
    const reorder = apiRequest("/mainboard-items/it1", { method: "PATCH", body: { intent: "reorder" } });

    expect(mock).toHaveBeenCalledTimes(2);
    release();
    await Promise.all([pin, reorder]);
  });

  it("fires fresh once a prior identical write has settled (a retry is a new attempt)", async () => {
    const mock = vi.fn(async () => okResponse({ id: "r1" }));
    vi.stubGlobal("fetch", mock);

    await apiRequest("/work-objects", { method: "POST", body: { a: 1 } });
    await apiRequest("/work-objects", { method: "POST", body: { a: 1 } });

    expect(mock).toHaveBeenCalledTimes(2);
  });

  it("never dedups reads — two concurrent identical GETs both fetch", async () => {
    const { mock, release } = gatedFetch(okResponse({ ok: true }));

    const g1 = apiRequest("/library", { method: "GET" });
    const g2 = apiRequest("/library", { method: "GET" });

    expect(mock).toHaveBeenCalledTimes(2);
    release();
    await Promise.all([g1, g2]);
  });

  it("shares the rejection and clears the entry so a retry fires fresh", async () => {
    const { mock, release } = gatedFetch(errResponse(409, "STRATEGY_DRAFT_CONFLICT"));

    const p1 = apiRequest("/strategy-drafts/d1/save", { method: "POST", body: { v: 0 } });
    const p2 = apiRequest("/strategy-drafts/d1/save", { method: "POST", body: { v: 0 } });
    expect(mock).toHaveBeenCalledTimes(1);

    release();
    await expect(p1).rejects.toBeInstanceOf(ApiError);
    await expect(p2).rejects.toMatchObject({ status: 409, code: "STRATEGY_DRAFT_CONFLICT" });

    // The failed attempt was dropped from the in-flight map — a real retry
    // (a NEW fetch, a fresh key) can now go out.
    const retry = vi.fn(async () => okResponse({ v: 1 }));
    vi.stubGlobal("fetch", retry);
    await apiRequest("/strategy-drafts/d1/save", { method: "POST", body: { v: 0 } });
    expect(retry).toHaveBeenCalledTimes(1);
  });
});
