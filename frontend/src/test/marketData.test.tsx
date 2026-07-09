import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import { parseMappingLines } from "@/lib/marketData";
import { MarketData } from "@/pages/MarketData";
import { stubApi } from "./helpers/apiStub";

const ROW_OHLCV = {
  entity_id: "md_1",
  revision_id: "rev_1",
  revision_no: 2,
  revision_state: "approved",
  market_data_type: "ohlcv",
  validation_status: "passed",
  title: "Binance 15m OHLCV",
  instrument_id: "BTCUSDT",
  content_hash: "sha256:c1",
  manifest_hash: "sha256:m1",
  owner_principal_id: "u_1",
  row_version: 4,
  lifecycle_state: "active",
  created_at: "2026-07-01T09:00:00+00:00",
};

const ROW_TICK = {
  entity_id: "md_2",
  revision_id: "rev_2",
  revision_no: 1,
  revision_state: "needs_review",
  market_data_type: "tick_trades",
  validation_status: null,
  title: "BTCUSDT Tick Sessions",
  instrument_id: "BTCUSDT",
  content_hash: null,
  manifest_hash: null,
  owner_principal_id: "u_1",
  row_version: 1,
  lifecycle_state: "draft",
  created_at: "2026-07-02T09:00:00+00:00",
};

const DATASETS_PAGE = {
  data: [ROW_OHLCV, ROW_TICK],
  meta: { cursor: null, has_more: false },
};

const DETAIL_MD1 = {
  ...ROW_OHLCV,
  revisions: [
    { revision_id: "rev_1", revision_no: 2, revision_state: "approved" },
    { revision_id: "rev_0", revision_no: 1, revision_state: "deprecated" },
  ],
};

const CREATE_RESULT = {
  entity_id: "md_new",
  revision_id: "rev_new",
  revision_state: "draft",
};

const DETAIL_MD_NEW = {
  ...ROW_TICK,
  entity_id: "md_new",
  revision_id: "rev_new",
  revision_no: 1,
  revision_state: "draft",
  title: "Fresh dataset",
  revisions: [{ revision_id: "rev_new", revision_no: 1, revision_state: "draft" }],
};

const START_UPLOAD_RESULT = { asset_id: "asset_9", entity_id: "md_1" };

const FINALIZE_RESULT = {
  entity_id: "md_1",
  asset_id: "asset_9",
  revision_id: "rev_1",
  revision_state: "uploading",
};

const ANALYSIS_RESULT = {
  job_id: "job_7",
  entity_id: "md_1",
  revision_id: "rev_1",
  queue: "data",
  status: "queued",
};

const MAPPING_RESULT = {
  mapping_id: "map_3",
  review_required: false,
  confirmed_mapping: { timestamp: "ts", close: "last_price", side: null },
};

const BUNDLE_RESULT = {
  entity_id: "md_1",
  revision_id: "rev_1",
  revision_no: 2,
  revision_state: "approved",
  content_hash: "sha256:c1",
  manifest_hash: "sha256:m1",
  market_data_type: "ohlcv",
};

// Order matters for the fragment-matching stub: action/detail fragments must
// precede their prefixes (finalize contains /raw-uploads; every md_1 sub-path
// contains /market-datasets; POST /market-datasets prefixes every other POST).
const BASE_ROUTES = {
  "POST /market-datasets/md_1/raw-uploads/finalize": FINALIZE_RESULT,
  "POST /market-datasets/md_1/raw-uploads": START_UPLOAD_RESULT,
  "POST /market-datasets/md_1/analysis": ANALYSIS_RESULT,
  "POST /market-datasets/md_1/schema-mapping": MAPPING_RESULT,
  "GET /market-datasets/md_1/approved-bundle": BUNDLE_RESULT,
  "GET /market-datasets/md_1": DETAIL_MD1,
  "GET /market-datasets/md_new": DETAIL_MD_NEW,
  "POST /market-datasets": CREATE_RESULT,
  "GET /market-datasets": DATASETS_PAGE,
};

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/market-data"]}>
        <MarketData />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return client;
}

async function openDetail() {
  await screen.findByText("Binance 15m OHLCV");
  fireEvent.click(screen.getAllByRole("button", { name: "Open" })[0]!);
  await screen.findByText("Revision history");
}

describe("parseMappingLines", () => {
  it("parses canonical:source lines, maps an empty source to null and skips junk", () => {
    expect(parseMappingLines("timestamp: ts\nclose:last_price\nside:\n\nnocolon\n: orphan")).toEqual(
      {
        timestamp: "ts",
        close: "last_price",
        side: null,
      },
    );
  });
});

describe("Market Data page", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders the registry with revision states and validation verbatim", async () => {
    stubApi(BASE_ROUTES);
    renderPage();

    // "Binance 15m OHLCV" is unique to the registry table (ready-check).
    expect(await screen.findByText("Binance 15m OHLCV")).toBeInTheDocument();
    const registryTable = within(screen.getAllByRole("table")[0]!);
    expect(registryTable.getByText("BTCUSDT Tick Sessions")).toBeInTheDocument();
    expect(registryTable.getByText("approved")).toBeInTheDocument();
    expect(registryTable.getByText("needs_review")).toBeInTheDocument();
    expect(registryTable.getByText("passed")).toBeInTheDocument();
    expect(registryTable.getByText("tick_trades")).toBeInTheDocument();
  });

  it("creates a dataset without an Idempotency-Key and auto-opens its detail", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("Binance 15m OHLCV");

    fireEvent.change(screen.getByLabelText(/Title/), { target: { value: "Fresh dataset" } });
    fireEvent.change(screen.getByLabelText(/Instrument id/), { target: { value: "ETHUSDT" } });
    fireEvent.change(screen.getByLabelText(/Payload/), {
      target: { value: '{"source": "binance"}' },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create dataset" }));

    expect(await screen.findByText("Created — md_new (draft).")).toBeInTheDocument();
    // Auto-open: the new dataset's detail is fetched and rendered.
    expect(await screen.findByText("Revision history")).toBeInTheDocument();

    const call = fetchMock.mock.calls.find(
      ([url, init]) => String(url).endsWith("/market-datasets") && init?.method === "POST",
    );
    expect(call).toBeDefined();
    const init = call?.[1] as RequestInit;
    expect(JSON.parse(String(init.body))).toEqual({
      market_data_type: "ohlcv",
      payload: { source: "binance" },
      title: "Fresh dataset",
      instrument_id: "ETHUSDT",
    });
    // The create route reads no Idempotency-Key — mirrored verbatim.
    expect((init.headers as Record<string, string>)["Idempotency-Key"]).toBeUndefined();
  });

  it("blocks an unparseable payload locally instead of sending it", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("Binance 15m OHLCV");

    fireEvent.change(screen.getByLabelText(/Payload/), { target: { value: "{not json" } });
    fireEvent.click(screen.getByRole("button", { name: "Create dataset" }));

    expect(await screen.findByText("Payload is not valid JSON.")).toBeInTheDocument();
    const posted = fetchMock.mock.calls.some(([, init]) => init?.method === "POST");
    expect(posted).toBe(false);
  });

  it("opens the detail with identity, hashes and revision history", async () => {
    stubApi(BASE_ROUTES);
    renderPage();
    await openDetail();

    expect(screen.getByText("sha256:c1")).toBeInTheDocument();
    expect(screen.getByText("sha256:m1")).toBeInTheDocument();
    expect(screen.getByText("rev_0")).toBeInTheDocument();
    expect(screen.getByText(/rv 4/)).toBeInTheDocument();
  });

  it("starts a raw upload then finalizes it with a fresh Idempotency-Key", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    renderPage();
    await openDetail();

    fireEvent.change(screen.getByLabelText("Object key"), {
      target: { value: "raw/btcusdt.csv" },
    });
    fireEvent.change(screen.getByLabelText("Content digest"), { target: { value: "sha256:d" } });
    fireEvent.change(screen.getByLabelText("Size (bytes)"), { target: { value: "1024" } });
    fireEvent.click(screen.getByRole("button", { name: "Start upload" }));

    expect(await screen.findByText(/Upload started/)).toBeInTheDocument();

    const startCall = fetchMock.mock.calls.find(
      ([url, init]) => String(url).endsWith("/raw-uploads") && init?.method === "POST",
    );
    expect(startCall).toBeDefined();
    const startInit = startCall?.[1] as RequestInit;
    expect(JSON.parse(String(startInit.body))).toEqual({
      object_key: "raw/btcusdt.csv",
      content_digest: "sha256:d",
      size_bytes: 1024,
      content_type: null,
      original_filename: null,
    });
    // Start-upload is not idempotency-wrapped upstream — no key is sent.
    expect((startInit.headers as Record<string, string>)["Idempotency-Key"]).toBeUndefined();

    // The asset id from the start result seeds the finalize input.
    expect(screen.getByLabelText("Asset id to finalize")).toHaveValue("asset_9");
    fireEvent.click(screen.getByRole("button", { name: "Finalize upload" }));

    expect(await screen.findByText(/Upload finalized — revision rev_1 is now uploading/)).toBeInTheDocument();

    const finalizeCall = fetchMock.mock.calls.find(
      ([url, init]) => String(url).includes("/raw-uploads/finalize") && init?.method === "POST",
    );
    expect(finalizeCall).toBeDefined();
    const finalizeInit = finalizeCall?.[1] as RequestInit;
    expect(JSON.parse(String(finalizeInit.body))).toEqual({ asset_id: "asset_9" });
    expect((finalizeInit.headers as Record<string, string>)["Idempotency-Key"]).toBeTruthy();
  });

  it("requests analysis with a fresh Idempotency-Key and renders the 202 admission", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    renderPage();
    await openDetail();

    fireEvent.click(screen.getByRole("button", { name: "Request analysis" }));

    expect(await screen.findByText(/Analysis accepted/)).toBeInTheDocument();
    expect(screen.getByText("job_7")).toBeInTheDocument();
    expect(screen.getByText("data")).toBeInTheDocument();

    const call = fetchMock.mock.calls.find(
      ([url, init]) => String(url).includes("/analysis") && init?.method === "POST",
    );
    expect(call).toBeDefined();
    const init = call?.[1] as RequestInit;
    expect((init.headers as Record<string, string>)["Idempotency-Key"]).toBeTruthy();
  });

  it("confirms a schema mapping, omitting confirmed_mapping when left blank", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    renderPage();
    await openDetail();

    fireEvent.change(screen.getByLabelText(/Source columns/), {
      target: { value: "timestamp\nopen\nclose" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Confirm mapping" }));

    expect(await screen.findByText(/Mapping saved/)).toBeInTheDocument();
    // The confirmed mapping echo renders verbatim, null = unmapped.
    expect(screen.getByText("last_price")).toBeInTheDocument();
    expect(screen.getByText(/unmapped/)).toBeInTheDocument();

    const call = fetchMock.mock.calls.find(
      ([url, init]) => String(url).includes("/schema-mapping") && init?.method === "POST",
    );
    expect(call).toBeDefined();
    const body = JSON.parse(String((call?.[1] as RequestInit).body));
    expect(body).toEqual({
      market_data_type: "ohlcv",
      source_columns: ["timestamp", "open", "close"],
    });
    expect("confirmed_mapping" in body).toBe(false);
  });

  it("surfaces a MAPPING_REVIEW_REQUIRED rejection verbatim", async () => {
    stubApi({
      ...BASE_ROUTES,
      "POST /market-datasets/md_1/schema-mapping": () => {
        throw new Error("MAPPING_REVIEW_REQUIRED: Essential fields are ambiguous or unmapped: side.");
      },
    });
    renderPage();
    await openDetail();

    fireEvent.change(screen.getByLabelText(/Source columns/), { target: { value: "ts" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirm mapping" }));

    expect(
      await screen.findByText("MAPPING_REVIEW_REQUIRED: Essential fields are ambiguous or unmapped: side."),
    ).toBeInTheDocument();
  });

  it("resolves the approved bundle only on demand and pins the exact revision", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    renderPage();
    await openDetail();

    // The probe is on-demand: no bundle GET before the click.
    const before = fetchMock.mock.calls.filter(([url]) =>
      String(url).includes("/approved-bundle"),
    ).length;
    expect(before).toBe(0);

    fireEvent.click(screen.getByRole("button", { name: "Resolve approved bundle" }));

    expect(await screen.findByText(/Pinned — revision/)).toBeInTheDocument();
    // rev_1 renders in the revision history AND in the pinned-bundle line.
    expect(screen.getAllByText("rev_1").length).toBeGreaterThan(1);
  });

  it("refetches the registry when the ['market-data'] prefix is invalidated (SSE sweep)", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    const client = renderPage();
    await screen.findByText("Binance 15m OHLCV");
    const before = fetchMock.mock.calls.filter(([url]) =>
      String(url).includes("/market-datasets"),
    ).length;

    await client.invalidateQueries({ queryKey: ["market-data"] });

    await waitFor(() => {
      const after = fetchMock.mock.calls.filter(([url]) =>
        String(url).includes("/market-datasets"),
      ).length;
      expect(after).toBeGreaterThan(before);
    });
  });

  it("surfaces the server view denial verbatim (role-aware read, not a UI hint)", async () => {
    stubApi({
      ...BASE_ROUTES,
      "GET /market-datasets": () => {
        throw new Error("AUTHENTICATION_REQUIRED: Sign in to view market datasets.");
      },
    });
    renderPage();

    expect(await screen.findByText("Unable to load")).toBeInTheDocument();
    expect(
      screen.getByText("AUTHENTICATION_REQUIRED: Sign in to view market datasets."),
    ).toBeInTheDocument();
  });
});
