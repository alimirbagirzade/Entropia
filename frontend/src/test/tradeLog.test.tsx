import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { TradeLog } from "@/pages/TradeLog";
import { stubApi } from "./helpers/apiStub";
import { stubUpload } from "./helpers/xhrStub";

const MAINBOARD = {
  workspace_id: "ws_1",
  workspace_kind: "human_default",
  composition_hash: "hash_abc",
  row_version: 3,
  items: [
    {
      item_id: "item_tl",
      item_kind: "trade_log",
      work_object_root_id: "root_tl",
      pinned_revision_id: "wor_tl1",
      position_index: 0,
      is_enabled: true,
      display_label_override: "Broker ledger",
      row_version: 1,
    },
    {
      item_id: "item_ts",
      item_kind: "trading_signal",
      work_object_root_id: "root_ts",
      pinned_revision_id: "wor_1",
      position_index: 1,
      is_enabled: true,
      display_label_override: "Provider signals",
      row_version: 1,
    },
  ],
  ready_summary: { state: "not_ready", report_id: null },
  latest_result_summary: null,
};

const DEDUP_UPLOAD_RESULT = {
  source_asset_id: "srcasset_9",
  raw_asset_hash: "sha256:tl",
  size_bytes: 99,
  deduplicated: true,
};

// The twin diff vs the Trading Signal report: the produced evidence key is
// record_batch_revision_id.
const REPORT = {
  job_id: "job_9",
  status: "succeeded",
  record_batch_revision_id: "ctrb_1",
  source_asset_id: "srcasset_9",
  instrument_id: "ETHUSDT",
  accepted_count: 5,
  skipped_count: 0,
  skipped_rows: [],
  validation_summary: null,
  content_hash: "sha256:batch",
};

const CREATE_RESULT = {
  root_id: "root_tl",
  revision_id: "wor_tl1",
  revision_no: 1,
  object_kind: "trade_log",
  config_hash: "cfg_tl",
  row_version: 1,
  attached: true,
  ready_state: "STALE",
  workspace_id: "ws_1",
  item_id: "item_tl",
  composition_hash: "hash_new",
};

// available_time is always null — historical ledger data (doc 05 §10.4).
const DETAIL = {
  root_id: "root_tl",
  object_kind: "trade_log",
  owner_principal_id: "user_1",
  lifecycle_state: "active",
  deletion_state: "active",
  current_revision_id: "wor_tl1",
  row_version: 2,
  current_revision: {
    revision_id: "wor_tl1",
    revision_no: 1,
    payload: { kind: "trade_log" },
    source_provenance: { record_batch_revision_id: "ctrb_1" },
    available_time: null,
    content_hash: "sha256:tlrev",
  },
};

const REVISION_RESULT = {
  root_id: "root_tl",
  revision_id: "wor_tl2",
  revision_no: 2,
  config_hash: "cfg_tl2",
  row_version: 2,
  auto_repinned: false,
};

const EXPORT_RESULT = {
  root_id: "root_tl",
  revision_id: "wor_tl1",
  manifest_hash: "b".repeat(64),
  manifest: { object_kind: "trade_log", available_time: null },
};

// ORDERED routes: the specific POST fragments precede the bare
// "POST /trade-logs" create prefix (a substring of every other POST URL).
function stubRoutes(overrides: Record<string, unknown> = {}) {
  return stubApi({
    "POST /trade-logs/root_tl/revisions": REVISION_RESULT,
    "POST /trade-logs/root_tl/export": EXPORT_RESULT,
    "POST /trade-logs": CREATE_RESULT,
    "GET /trade-logs/imports/job_9": REPORT,
    "GET /trade-logs/root_tl": DETAIL,
    "GET /mainboards/default": MAINBOARD,
    ...overrides,
  });
}

function renderPage(initialEntry = "/trade-log") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/trade-log" element={<TradeLog />} />
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

describe("TradeLog", () => {
  it("renders the twin import report keyed by record_batch_revision_id", async () => {
    const fetchMock = stubRoutes();
    renderPage("/trade-log?job=job_9");

    expect(await screen.findByText("ctrb_1")).toBeTruthy();
    expect(screen.getByText("Record batch")).toBeTruthy();
    expect(screen.getByText("succeeded")).toBeTruthy();
    expect(screen.getByText("5 / 0")).toBeTruthy();

    const call = fetchMock.mock.calls.find(([url]) =>
      String(url).includes("/trade-logs/imports/job_9"),
    );
    expect(call).toBeTruthy();
  });

  it("sends an explicit column mapping in the import request body (GAP-22)", async () => {
    const fetchMock = stubRoutes({
      "POST /trade-logs/imports": {
        job_id: "job_9",
        source_asset_id: "srcasset_9",
        queue: "data",
        status: "queued",
      },
    });
    renderPage("/trade-log");

    fireEvent.change(screen.getByLabelText("Source asset id"), {
      target: { value: "srcasset_9" },
    });
    fireEvent.change(screen.getByLabelText("Instrument id"), { target: { value: "BTCUSDT" } });
    fireEvent.change(screen.getByLabelText(/Column mapping/), {
      target: { value: "entry_time = Open Time\nexit_time = Close Time" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Request import" }));

    const call = await vi.waitFor(() => {
      const found = fetchMock.mock.calls.find(
        ([url, init]) => String(url).endsWith("/trade-logs/imports") && init?.method === "POST",
      );
      expect(found).toBeTruthy();
      return found;
    });
    const body = JSON.parse(String(call?.[1]?.body)) as { import_mapping?: Record<string, string> };
    expect(body.import_mapping).toEqual({ entry_time: "Open Time", exit_time: "Close Time" });
  });

  it("saves the trade log with the record-batch import binding", async () => {
    const fetchMock = stubRoutes();
    renderPage("/trade-log?job=job_9");

    expect(await screen.findByText("ctrb_1")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Save Trade Log" }));

    expect(await screen.findByText("Trade Log saved")).toBeTruthy();

    const call = fetchMock.mock.calls.find(
      ([url, init]) => String(url).endsWith("/trade-logs") && init?.method === "POST",
    );
    expect(call).toBeTruthy();
    const body = JSON.parse(String(call?.[1]?.body)) as {
      payload: Record<string, unknown>;
      attach: boolean;
    };
    expect(body.attach).toBe(true);
    expect(body.payload.kind).toBe("trade_log");
    expect(body.payload.import_binding).toEqual({
      source_asset_id: "srcasset_9",
      record_batch_revision_id: "ctrb_1",
    });
    // The twin config shape: time_model (not time_policy + event_model).
    expect(body.payload.time_model).toEqual({
      resolution_kind: "event_based",
      source_timezone: "UTC",
      normalization_timezone: "UTC",
    });
    expect(headersOf(call?.[1])["Idempotency-Key"]).toBeTruthy();
  });

  it("renders the historical (no available_time) detail and appends an OCC-guarded revision", async () => {
    const fetchMock = stubRoutes();
    renderPage("/trade-log?root=root_tl");

    expect(await screen.findByText("Current revision #1")).toBeTruthy();
    expect(screen.getByText(/historical ledger data/)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Save new revision" }));
    expect(await screen.findByText(/Revision #2 saved/)).toBeTruthy();

    const call = fetchMock.mock.calls.find(
      ([url, init]) => String(url).includes("/revisions") && init?.method === "POST",
    );
    expect(call).toBeTruthy();
    const body = JSON.parse(String(call?.[1]?.body)) as Record<string, unknown>;
    expect(body.expected_head_revision_id).toBe("wor_tl1");
    expect(headersOf(call?.[1])["Idempotency-Key"]).toBeTruthy();
  });

  it("surfaces a content-addressed dedup upload as a reuse note", async () => {
    stubRoutes();
    const { calls: uploadCalls } = stubUpload({
      "POST /trade-logs/source-assets": DEDUP_UPLOAD_RESULT,
    });
    renderPage();

    const file = new File(["ts,side,qty\n1,long,2"], "trades.csv", { type: "text/csv" });
    fireEvent.change(await screen.findByLabelText(/Trade-record file/), {
      target: { files: [file] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Upload source asset" }));

    expect(await screen.findByText(/already uploaded/)).toBeTruthy();
    expect(screen.getByDisplayValue("srcasset_9")).toBeTruthy();
    // F-03: the real file travels via multipart XHR.
    expect(uploadCalls[0]?.file?.name).toBe("trades.csv");
    expect(uploadCalls[0]?.headers["Idempotency-Key"]).toBeTruthy();
  });

  it("discovers only trade-log items from the default Mainboard", async () => {
    stubRoutes();
    renderPage();

    expect(await screen.findByText("Broker ledger")).toBeTruthy();
    expect(screen.getByText("root_tl")).toBeTruthy();
    // The trading-signal item on the same Mainboard is filtered out.
    expect(screen.queryByText("Provider signals")).toBeNull();
  });

  it("exports the pinned head manifest with a fresh Idempotency-Key and no OCC token", async () => {
    const fetchMock = stubRoutes();
    renderPage("/trade-log?root=root_tl");

    fireEvent.click(await screen.findByRole("button", { name: "Export manifest" }));

    expect(await screen.findByText("b".repeat(64))).toBeTruthy();

    const call = fetchMock.mock.calls.find(
      ([url, init]) => String(url).includes("/export") && init?.method === "POST",
    );
    expect(call).toBeTruthy();
    const body = JSON.parse(String(call?.[1]?.body)) as Record<string, unknown>;
    expect("revision_id" in body).toBe(false);
    expect(headersOf(call?.[1])["Idempotency-Key"]).toBeTruthy();
  });
});
