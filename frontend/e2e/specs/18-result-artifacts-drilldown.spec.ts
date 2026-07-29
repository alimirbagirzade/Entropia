import { expect, test } from "@playwright/test";

import { ensureAdmin } from "../fixtures/auth";
import { apiGet, readSessionToken } from "../utils/api";

// I-02 — the Filtered Events artifact, proven against the deployed stack.
//
// Doc 15 §3.2 exposes "View Signal Events" and "View Filtered Events" as two
// DISTINCT drill-downs, and §16 forbids folding the no-entry/filtered decision
// trace into the shape of a real fill. The backend integration test proves the
// engine -> DB -> query chain; this spec proves the surface is actually WIRED in
// a deployed image: the route resolves, the alias resolves, the two artifacts
// are disjoint, the cursor terminates, and an unknown type is fail-closed.
//
// Data dependency (deliberate, matches how this suite already works): the
// journeys share ONE Compose stack and Playwright runs them serially in file
// order, so `05-mainboard-ready-check-run.spec.ts` has already driven a run to
// SUCCEEDED and left an immutable Result behind — the same way spec 04's
// approved package feeds spec 05's picker. If no Result exists the spec says so
// explicitly instead of failing on a confusing downstream assertion.
interface ArtifactPage {
  result_id: string;
  artifact_type: string;
  items: Array<{ seq: number; event_type: string; detail: Record<string, unknown> | null }>;
  next_cursor: string | null;
  row_count: number | null;
  checksum: string | null;
  checksum_schema_version: string | null;
}

const HEX64 = /^[0-9a-f]{64}$/;

test.describe("Result artifact drill-down: Filtered Events is its own artifact (I-02)", () => {
  test("serves filtered_events separately from signal_events, with a terminating cursor and a checksum", async ({
    page,
  }) => {
    test.setTimeout(180_000);
    await ensureAdmin(page);
    const token = await readSessionToken(page);
    expect(token, "browser holds no session token").toBeTruthy();

    const listed = await apiGet(page, "/backtest-results?limit=1", token);
    expect(listed.status()).toBe(200);
    const list = (await listed.json()) as { data?: Array<{ result_id: string }> };
    const resultId = list.data?.[0]?.result_id;
    expect(
      resultId,
      "no Backtest Result on the stack — the golden-path journey (spec 05) must run first",
    ).toBeTruthy();

    // 1) The new artifact type resolves at all (this is the wiring that did not
    //    exist before I-02 — it used to be a 422 ARTIFACT_TYPE_INVALID).
    const filteredRes = await apiGet(
      page,
      `/backtest-results/${resultId}/artifacts/filtered_events`,
      token,
    );
    expect(filteredRes.status()).toBe(200);
    const filtered = (await filteredRes.json()) as ArtifactPage;
    expect(filtered.artifact_type).toBe("filtered_events");

    // 2) The V18 label alias resolves to the SAME artifact, not to a fallback.
    const aliasRes = await apiGet(
      page,
      `/backtest-results/${resultId}/artifacts/filtered`,
      token,
    );
    expect(aliasRes.status()).toBe(200);
    expect(((await aliasRes.json()) as ArtifactPage).artifact_type).toBe("filtered_events");

    // 3) The two journals are DISJOINT — the split doc 15 §16 requires. A filter
    //    veto must never also appear in the signal journal.
    const signalsRes = await apiGet(
      page,
      `/backtest-results/${resultId}/artifacts/signal_events`,
      token,
    );
    expect(signalsRes.status()).toBe(200);
    const signals = (await signalsRes.json()) as ArtifactPage;
    expect(signals.artifact_type).toBe("signal_events");
    expect(signals.items.map((row) => row.event_type)).not.toContain("filtered_no_entry");
    for (const row of filtered.items) {
      expect(row.event_type).toBe("filtered_no_entry");
    }

    // 4) Keyset pagination terminates and never repeats a row (the shipped Trade
    //    Ledger contract, now honoured by the new artifact too).
    const walked: number[] = [];
    let cursor: string | null = null;
    for (let guard = 0; guard < 50; guard += 1) {
      const path =
        `/backtest-results/${resultId}/artifacts/filtered_events?limit=2` +
        (cursor ? `&cursor=${encodeURIComponent(cursor)}` : "");
      const pageRes = await apiGet(page, path, token);
      expect(pageRes.status()).toBe(200);
      const body = (await pageRes.json()) as ArtifactPage;
      walked.push(...body.items.map((row) => row.seq));
      cursor = body.next_cursor;
      if (!cursor) break;
    }
    expect(cursor, "filtered_events pagination did not terminate").toBeNull();
    expect(new Set(walked).size).toBe(walked.length);
    expect(walked).toEqual([...walked].sort((a, b) => a - b));

    // 5) doc 15 §7 artifact checksum verification: the artifact carries a stored
    //    checksum whose row_count matches what the cursor actually served, and it
    //    is PINNED to the artifact type (the signal journal hashes differently).
    expect(filtered.checksum_schema_version).toBe("artifact-checksum-v1");
    expect(filtered.checksum ?? "").toMatch(HEX64);
    expect(filtered.row_count).toBe(walked.length);
    expect(signals.checksum ?? "").toMatch(HEX64);
    expect(signals.checksum).not.toBe(filtered.checksum);
  });

  test("rejects an unknown artifact type fail-closed instead of falling back", async ({ page }) => {
    await ensureAdmin(page);
    const token = await readSessionToken(page);

    const listed = await apiGet(page, "/backtest-results?limit=1", token);
    const list = (await listed.json()) as { data?: Array<{ result_id: string }> };
    const resultId = list.data?.[0]?.result_id;
    test.skip(!resultId, "no Backtest Result on the stack yet");

    const bogus = await apiGet(
      page,
      `/backtest-results/${resultId}/artifacts/regime_table`,
      token,
    );
    // REGIME_TABLE is a doc 22 Future-Dev boundary, deliberately NOT an artifact
    // type (see docs/PROJECT_HISTORY.md, I-02): asking for it is an explicit
    // rejection, never an empty page that reads as "computed, no data".
    expect(bogus.status()).toBe(422);
    const body = (await bogus.json()) as { error?: { code?: string } };
    expect(body.error?.code).toBe("ARTIFACT_TYPE_INVALID");
  });
});
