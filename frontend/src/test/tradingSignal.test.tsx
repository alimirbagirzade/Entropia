import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { TradingSignal } from "@/pages/TradingSignal";
import { stubApi } from "./helpers/apiStub";
import { stubUpload } from "./helpers/xhrStub";

const MAINBOARD = {
  workspace_id: "ws_1",
  workspace_kind: "human_default",
  composition_hash: "hash_abc",
  row_version: 3,
  items: [
    {
      item_id: "item_ts",
      item_kind: "trading_signal",
      work_object_root_id: "root_ts",
      pinned_revision_id: "wor_1",
      position_index: 0,
      is_enabled: true,
      display_label_override: "Provider signals",
      row_version: 1,
    },
    {
      item_id: "item_strat",
      item_kind: "strategy",
      work_object_root_id: "root_strat",
      pinned_revision_id: "wor_s",
      position_index: 1,
      is_enabled: true,
      display_label_override: "Momentum A",
      row_version: 1,
    },
  ],
  ready_summary: { state: "not_ready", report_id: null },
  latest_result_summary: null,
};

const UPLOAD_RESULT = {
  source_asset_id: "srcasset_1",
  raw_asset_hash: "sha256:abc",
  size_bytes: 42,
  deduplicated: false,
};

const IMPORT_ACCEPTED = {
  job_id: "job_1",
  source_asset_id: "srcasset_1",
  queue: "data",
  status: "queued",
};

const REPORT = {
  job_id: "job_1",
  status: "succeeded",
  normalized_event_revision_id: "nser_1",
  source_asset_id: "srcasset_1",
  instrument_id: "BTCUSDT",
  accepted_count: 10,
  skipped_count: 2,
  skipped_rows: [{ row: 3, reason: "INVALID_SIGNAL_DIRECTION" }],
  validation_summary: { blocker_code: null },
  content_hash: "sha256:evt",
};

const CREATE_RESULT = {
  root_id: "root_ts",
  revision_id: "wor_1",
  revision_no: 1,
  object_kind: "trading_signal",
  config_hash: "cfg_1",
  row_version: 1,
  attached: true,
  ready_state: "STALE",
  workspace_id: "ws_1",
  item_id: "item_ts",
  composition_hash: "hash_new",
};

// A full canonical §9.2 head payload so the typed revision form round-trips it.
const HEAD_PAYLOAD = {
  kind: "trading_signal",
  identity: { display_name: "Provider signals" },
  source: { provider_name: "acme", source_kind: "file" },
  instrument_scope: { instrument_id: "BTCUSDT", display_symbol: "BTCUSDT" },
  event_model: { resolution_kind: "event_based" },
  data_quality: { mode: "signal_events_only" },
  time_policy: {
    source_timezone: "UTC",
    normalization_timezone: "UTC",
    availability_rule: "row_available_time",
  },
  price_policy: { source: "suggested_signal_price" },
  ohlcv_policy: { use_mode: "ignore" },
  import_binding: { source_asset_id: "srcasset_1", normalized_event_revision_id: "nser_1" },
};

const DETAIL = {
  root_id: "root_ts",
  object_kind: "trading_signal",
  owner_principal_id: "user_1",
  lifecycle_state: "active",
  deletion_state: "active",
  current_revision_id: "wor_1",
  row_version: 3,
  current_revision: {
    revision_id: "wor_1",
    revision_no: 1,
    payload: HEAD_PAYLOAD,
    source_provenance: { source_asset_id: "srcasset_1" },
    available_time: "2026-07-01T00:00:00+00:00",
    content_hash: "sha256:rev",
  },
};

const REVISION_RESULT = {
  root_id: "root_ts",
  revision_id: "wor_2",
  revision_no: 2,
  config_hash: "cfg_2",
  row_version: 3,
  auto_repinned: false,
};

const EXPORT_RESULT = {
  root_id: "root_ts",
  revision_id: "wor_1",
  manifest_hash: "a".repeat(64),
  manifest: { object_kind: "trading_signal", payload: { kind: "trading_signal" } },
};

// R2-04: the Advanced raw disclosure is gated on the /me admin projection —
// the default stub is a normal user (fail-closed hidden).
const ME_USER = {
  principal_id: "user_1",
  principal_type: "human",
  role: "user",
  is_admin: false,
  is_authenticated: true,
};

// ORDERED routes: the specific POST fragments (source-assets / imports /
// {root}/revisions) must precede the bare "POST /trading-signals" create
// prefix — the create path is a substring of every other POST URL.
function stubRoutes(overrides: Record<string, unknown> = {}) {
  return stubApi({
    "POST /trading-signals/imports": IMPORT_ACCEPTED,
    "POST /trading-signals/root_ts/revisions": REVISION_RESULT,
    "POST /trading-signals/root_ts/export": EXPORT_RESULT,
    "POST /trading-signals": CREATE_RESULT,
    "GET /trading-signals/imports/job_1": REPORT,
    "GET /trading-signals/root_ts": DETAIL,
    "GET /mainboards/default": MAINBOARD,
    "GET /me": ME_USER,
    ...overrides,
  });
}

function renderPage(initialEntry = "/trading-signal") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/trading-signal" element={<TradingSignal />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function headersOf(init: RequestInit | undefined): Record<string, string> {
  return (init?.headers ?? {}) as Record<string, string>;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("TradingSignal", () => {
  it("uploads the chosen file (multipart, fresh Idempotency-Key) and carries the asset id as read-only provenance", async () => {
    stubRoutes();
    const { calls: uploadCalls } = stubUpload({
      "POST /trading-signals/source-assets": UPLOAD_RESULT,
    });
    renderPage();

    // R2-04 / GAP item 3 fix #3: the source asset id is never an editable input.
    expect(screen.queryByLabelText(/Source asset id/)).toBeNull();
    const requestButton = screen.getByRole("button", { name: "Request import" });
    expect((requestButton as HTMLButtonElement).disabled).toBe(true);

    const file = new File(["ts,direction\n1,long"], "signals.csv", { type: "text/csv" });
    fireEvent.change(await screen.findByLabelText(/Signal-event file/), {
      target: { files: [file] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Upload source asset" }));

    expect(await screen.findByText(/Source asset stored/)).toBeTruthy();
    // The identity card shows the stored asset id as read-only provenance and
    // the import action unlocks.
    expect(screen.getAllByText("srcasset_1").length).toBeGreaterThan(0);
    expect((requestButton as HTMLButtonElement).disabled).toBe(false);

    // F-03: the real file bytes travel via multipart XHR (no pasted content).
    expect(uploadCalls).toHaveLength(1);
    expect(uploadCalls[0]?.url).toContain("/trading-signals/source-assets");
    expect(uploadCalls[0]?.file?.name).toBe("signals.csv");
    expect(uploadCalls[0]?.headers["Idempotency-Key"]).toBeTruthy();
  });

  it("requests the import (202) with the system-carried asset id and lands on the durable ?job= report", async () => {
    const fetchMock = stubRoutes();
    stubUpload({ "POST /trading-signals/source-assets": UPLOAD_RESULT });
    renderPage();

    const file = new File(["ts,direction\n1,long"], "signals.csv", { type: "text/csv" });
    fireEvent.change(await screen.findByLabelText(/Signal-event file/), {
      target: { files: [file] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Upload source asset" }));
    expect(await screen.findByText(/Source asset stored/)).toBeTruthy();

    // Two "Instrument id" controls exist now (identity card + typed form) —
    // the identity card renders first.
    fireEvent.change(screen.getAllByLabelText(/Instrument id/)[0]!, {
      target: { value: "BTCUSDT" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Request import" }));

    // The accepted job id enters the URL and the report card loads (second wave).
    expect((await screen.findAllByText("nser_1")).length).toBeGreaterThan(0);
    expect(screen.getByText("succeeded")).toBeTruthy();
    expect(screen.getByText("10 / 2")).toBeTruthy();
    expect(screen.getByText(/INVALID_SIGNAL_DIRECTION/)).toBeTruthy();

    const call = fetchMock.mock.calls.find(
      ([url, init]) => String(url).includes("/imports") && init?.method === "POST",
    );
    expect(call).toBeTruthy();
    const body = JSON.parse(String(call?.[1]?.body)) as Record<string, unknown>;
    expect(body).toEqual({
      source_asset_id: "srcasset_1",
      instrument_id: "BTCUSDT",
      source_timezone: "UTC",
    });
    expect(headersOf(call?.[1])["Idempotency-Key"]).toBeTruthy();
  });

  it("saves the trading signal from the typed form with the report-seeded import binding and attach", async () => {
    const fetchMock = stubRoutes();
    renderPage("/trading-signal?job=job_1");

    // Editor reseeds once the succeeded report arrives.
    expect((await screen.findAllByText("nser_1")).length).toBeGreaterThan(0);
    fireEvent.change(screen.getByLabelText("Display name"), {
      target: { value: "Provider signals" },
    });
    fireEvent.change(screen.getByLabelText("Provider name"), {
      target: { value: "acme" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save Trading Signal" }));

    expect(await screen.findByText("Trading Signal saved")).toBeTruthy();
    expect(screen.getByText("STALE")).toBeTruthy();

    const call = fetchMock.mock.calls.find(
      ([url, init]) => String(url).endsWith("/trading-signals") && init?.method === "POST",
    );
    expect(call).toBeTruthy();
    const body = JSON.parse(String(call?.[1]?.body)) as {
      payload: Record<string, unknown>;
      attach: boolean;
      [key: string]: unknown;
    };
    expect(body.attach).toBe(true);
    expect("workspace_id" in body).toBe(false);
    // The typed form PRODUCED the payload (no JSON was typed anywhere).
    expect(body.payload.identity).toEqual({ display_name: "Provider signals" });
    expect(body.payload.source).toEqual({ provider_name: "acme", source_kind: "file" });
    expect(body.payload.import_binding).toEqual({
      source_asset_id: "srcasset_1",
      normalized_event_revision_id: "nser_1",
    });
    expect(body.payload.instrument_scope).toEqual({
      instrument_id: "BTCUSDT",
      display_symbol: "BTCUSDT",
    });
    expect(headersOf(call?.[1])["Idempotency-Key"]).toBeTruthy();
  });

  it("blocks Save client-side with field-level errors — nothing is sent", async () => {
    const fetchMock = stubRoutes();
    renderPage("/trading-signal?job=job_1");
    expect((await screen.findAllByText("nser_1")).length).toBeGreaterThan(0);

    // Display name / provider left blank → the typed validation blocks the send
    // and the blockers render next to their fields (GAP item 9 last rule).
    fireEvent.click(screen.getByRole("button", { name: "Save Trading Signal" }));

    expect(await screen.findByText(/Display name must be 1\.\.160 characters\./)).toBeTruthy();
    expect(screen.getByText(/Provider name must be 1\.\.200 characters\./)).toBeTruthy();
    const createCall = fetchMock.mock.calls.find(
      ([url, init]) => String(url).endsWith("/trading-signals") && init?.method === "POST",
    );
    expect(createCall).toBeUndefined();
  });

  it("appends a revision from the head-seeded typed form with the rendered head as the BODY OCC token", async () => {
    const fetchMock = stubRoutes();
    renderPage("/trading-signal?root=root_ts");

    expect(await screen.findByText("Current revision #1")).toBeTruthy();
    // The typed form arrives seeded from the head revision payload.
    expect(screen.getByLabelText("Display name")).toHaveProperty("value", "Provider signals");
    fireEvent.click(screen.getByRole("button", { name: "Save new revision" }));

    expect(await screen.findByText(/Revision #2 saved/)).toBeTruthy();
    expect(screen.getByText(/Not auto-repinned/)).toBeTruthy();

    const call = fetchMock.mock.calls.find(
      ([url, init]) => String(url).includes("/revisions") && init?.method === "POST",
    );
    expect(call).toBeTruthy();
    const body = JSON.parse(String(call?.[1]?.body)) as Record<string, unknown>;
    expect(body.expected_head_revision_id).toBe("wor_1");
    // Round-trip: the form regenerates the head payload byte-for-byte.
    expect(body.payload).toEqual(DETAIL.current_revision.payload);
    expect(headersOf(call?.[1])["Idempotency-Key"]).toBeTruthy();
  });

  it("hides the Advanced raw payload from a normal user and shows it to an admin (fail-closed)", async () => {
    stubRoutes();
    renderPage("/trading-signal?job=job_1");
    expect((await screen.findAllByText("nser_1")).length).toBeGreaterThan(0);
    expect(screen.queryByText("Advanced (raw payload)")).toBeNull();
    cleanup();

    stubRoutes({ "GET /me": { ...ME_USER, role: "admin", is_admin: true } });
    renderPage("/trading-signal?job=job_1");
    expect((await screen.findAllByText("nser_1")).length).toBeGreaterThan(0);
    expect(await screen.findByText("Advanced (raw payload)")).toBeTruthy();
  });

  it("discovers only trading-signal items from the default Mainboard", async () => {
    stubRoutes();
    renderPage();

    expect(await screen.findByText("Provider signals")).toBeTruthy();
    expect(screen.getByText("root_ts")).toBeTruthy();
    // The strategy item on the same Mainboard is filtered out.
    expect(screen.queryByText("Momentum A")).toBeNull();
  });

  it("exports the pinned head manifest with a fresh Idempotency-Key and no OCC token", async () => {
    const fetchMock = stubRoutes();
    renderPage("/trading-signal?root=root_ts");

    fireEvent.click(await screen.findByRole("button", { name: "Export manifest" }));

    // The manifest hash renders after the synchronous export resolves.
    expect(await screen.findByText("a".repeat(64))).toBeTruthy();

    const call = fetchMock.mock.calls.find(
      ([url, init]) => String(url).includes("/export") && init?.method === "POST",
    );
    expect(call).toBeTruthy();
    const body = JSON.parse(String(call?.[1]?.body)) as Record<string, unknown>;
    // Default export omits revision_id (server exports the pinned head); no OCC token.
    expect("revision_id" in body).toBe(false);
    expect(headersOf(call?.[1])["Idempotency-Key"]).toBeTruthy();
  });
});
