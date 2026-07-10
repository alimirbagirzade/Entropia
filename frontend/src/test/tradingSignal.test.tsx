import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { TradingSignal } from "@/pages/TradingSignal";
import { stubApi } from "./helpers/apiStub";

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
    payload: { kind: "trading_signal" },
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

// ORDERED routes: the specific POST fragments (source-assets / imports /
// {root}/revisions) must precede the bare "POST /trading-signals" create
// prefix — the create path is a substring of every other POST URL.
function stubRoutes(overrides: Record<string, unknown> = {}) {
  return stubApi({
    "POST /trading-signals/source-assets": UPLOAD_RESULT,
    "POST /trading-signals/imports": IMPORT_ACCEPTED,
    "POST /trading-signals/root_ts/revisions": REVISION_RESULT,
    "POST /trading-signals": CREATE_RESULT,
    "GET /trading-signals/imports/job_1": REPORT,
    "GET /trading-signals/root_ts": DETAIL,
    "GET /mainboards/default": MAINBOARD,
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
  it("uploads the source asset with a fresh Idempotency-Key and prefills the import form", async () => {
    const fetchMock = stubRoutes();
    renderPage();

    fireEvent.change(await screen.findByLabelText(/File content/), {
      target: { value: "ts,direction\n1,long" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Upload source asset" }));

    expect(await screen.findByText(/Source asset stored/)).toBeTruthy();
    // The import composer picks up the stored asset id.
    expect(screen.getByDisplayValue("srcasset_1")).toBeTruthy();

    const call = fetchMock.mock.calls.find(
      ([url, init]) => String(url).includes("/source-assets") && init?.method === "POST",
    );
    expect(call).toBeTruthy();
    const body = JSON.parse(String(call?.[1]?.body)) as Record<string, unknown>;
    expect(body.content).toBe("ts,direction\n1,long");
    expect(body.content_type).toBe("text/csv");
    expect("original_filename" in body).toBe(false);
    expect(headersOf(call?.[1])["Idempotency-Key"]).toBeTruthy();
  });

  it("requests the import (202) and lands on the durable ?job= report", async () => {
    const fetchMock = stubRoutes();
    renderPage();

    fireEvent.change(await screen.findByLabelText(/Source asset id/), {
      target: { value: "srcasset_1" },
    });
    fireEvent.change(screen.getByLabelText(/Instrument id/), {
      target: { value: "BTCUSDT" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Request import" }));

    // The accepted job id enters the URL and the report card loads (second wave).
    expect(await screen.findByText("nser_1")).toBeTruthy();
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

  it("saves the trading signal with the report-seeded import binding and attach", async () => {
    const fetchMock = stubRoutes();
    renderPage("/trading-signal?job=job_1");

    // Editor reseeds once the succeeded report arrives.
    expect(await screen.findByText("nser_1")).toBeTruthy();
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

  it("keeps invalid JSON client-side — nothing is sent", async () => {
    const fetchMock = stubRoutes();
    renderPage();

    fireEvent.change(await screen.findByLabelText(/TradingSignalConfig payload/), {
      target: { value: "not json {" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save Trading Signal" }));

    expect(await screen.findByText(/Not sent — invalid JSON/)).toBeTruthy();
    const createCall = fetchMock.mock.calls.find(
      ([url, init]) => String(url).endsWith("/trading-signals") && init?.method === "POST",
    );
    expect(createCall).toBeUndefined();
  });

  it("appends a revision with the rendered head as the BODY OCC token", async () => {
    const fetchMock = stubRoutes();
    renderPage("/trading-signal?root=root_ts");

    expect(await screen.findByText("Current revision #1")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Save new revision" }));

    expect(await screen.findByText(/Revision #2 saved/)).toBeTruthy();
    expect(screen.getByText(/Not auto-repinned/)).toBeTruthy();

    const call = fetchMock.mock.calls.find(
      ([url, init]) => String(url).includes("/revisions") && init?.method === "POST",
    );
    expect(call).toBeTruthy();
    const body = JSON.parse(String(call?.[1]?.body)) as Record<string, unknown>;
    expect(body.expected_head_revision_id).toBe("wor_1");
    expect(body.payload).toEqual(DETAIL.current_revision.payload);
    expect(headersOf(call?.[1])["Idempotency-Key"]).toBeTruthy();
  });

  it("discovers only trading-signal items from the default Mainboard", async () => {
    stubRoutes();
    renderPage();

    expect(await screen.findByText("Provider signals")).toBeTruthy();
    expect(screen.getByText("root_ts")).toBeTruthy();
    // The strategy item on the same Mainboard is filtered out.
    expect(screen.queryByText("Momentum A")).toBeNull();
  });
});
