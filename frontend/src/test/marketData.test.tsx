import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import { ingestRefetchInterval, parseMappingLines } from "@/lib/marketData";
import { MarketData, deriveWorkflowSteps } from "@/pages/MarketData";
import { apiErrorRoute, stubApi } from "./helpers/apiStub";
import { stubUpload } from "./helpers/xhrStub";

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

const START_UPLOAD_RESULT = {
  asset_id: "asset_9",
  entity_id: "md_1",
  content_digest: "sha256:deadbeef",
  size_bytes: 42,
  content_type: "text/csv",
  original_filename: "btcusdt.csv",
  deduplicated: false,
};

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

const REVISION_RESULT = {
  entity_id: "md_1",
  revision_id: "rev_3",
  revision_no: 3,
  row_version: 5,
};

const SUCCESSOR_RESULT = {
  entity_id: "md_1",
  revision_id: "rev_4",
  revision_no: 3,
  revision_state: "draft",
};

const APPROVE_RESULT = { entity_id: "md_1", revision_id: "rev_1", revision_state: "approved" };

const DEPRECATE_RESULT = { entity_id: "md_1", revision_id: "rev_1", revision_state: "deprecated" };

// Order matters for the fragment-matching stub: action/detail fragments must
// precede their prefixes (finalize contains /raw-uploads; every md_1 sub-path
// contains /market-datasets; POST /market-datasets prefixes every other POST).
// The raw-uploads POST itself travels over XHR (lib/upload.ts), not fetch —
// it is stubbed separately with stubUpload() in the upload-specific tests.
const ME_USER = {
  principal_id: "hu_user",
  principal_type: "human",
  role: "user",
  is_admin: false,
  is_authenticated: true,
};

const FINALIZE_MD_NEW = {
  entity_id: "md_new",
  asset_id: "asset_new",
  revision_id: "rev_new",
  revision_state: "uploading",
};

const ANALYSIS_MD_NEW = {
  job_id: "job_new",
  entity_id: "md_new",
  revision_id: "rev_new",
  queue: "data",
  status: "queued",
};

const START_UPLOAD_MD_NEW = {
  asset_id: "asset_new",
  entity_id: "md_new",
  content_digest: "sha256:cafebabe4242",
  size_bytes: 24,
  content_type: "text/csv",
  original_filename: "fresh.csv",
  deduplicated: false,
};

const BASE_ROUTES = {
  "POST /market-datasets/md_new/raw-uploads/finalize": FINALIZE_MD_NEW,
  "POST /market-datasets/md_new/analysis": ANALYSIS_MD_NEW,
  "POST /market-datasets/md_1/raw-uploads/finalize": FINALIZE_RESULT,
  "POST /market-datasets/md_1/analysis": ANALYSIS_RESULT,
  "POST /market-datasets/md_1/schema-mapping": MAPPING_RESULT,
  "POST /market-datasets/md_1/revisions": REVISION_RESULT,
  "POST /market-datasets/md_1/successor": SUCCESSOR_RESULT,
  "POST /market-datasets/md_1/approve": APPROVE_RESULT,
  "POST /market-datasets/md_1/deprecate": DEPRECATE_RESULT,
  "GET /market-datasets/md_1/approved-bundle": BUNDLE_RESULT,
  "GET /market-datasets/md_1": DETAIL_MD1,
  "GET /market-datasets/md_new": DETAIL_MD_NEW,
  "POST /market-datasets": CREATE_RESULT,
  "GET /market-datasets": DATASETS_PAGE,
  // R2-09: the Admin approval composer is presentation-gated on /me — the
  // shared baseline is a NON-admin so the historic "hidden for this non-admin
  // actor" assertions stay deterministic.
  "GET /me": ME_USER,
};

// Server-truth identity projections (/me) — the R2-09 presentation gates.
const ME_ADMIN = {
  principal_id: "hu_admin",
  principal_type: "human",
  role: "admin",
  is_admin: true,
  is_authenticated: true,
};
// The Admin-visible variant: the approve/deprecate wire tests run under a
// server-confirmed Admin; the 403 test then models the STALE-CACHE projection
// (client believes admin, server denies) — the envelope must render verbatim.
const ADMIN_ROUTES = { ...BASE_ROUTES, "GET /me": ME_ADMIN };

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

describe("ingestRefetchInterval (KALAN-A detail polling)", () => {
  it("polls only the transient pipeline states", () => {
    expect(ingestRefetchInterval("uploading")).toBeGreaterThan(0);
    expect(ingestRefetchInterval("analyzing")).toBeGreaterThan(0);
    for (const state of ["draft", "needs_review", "verified", "approved", "rejected", "deprecated"]) {
      expect(ingestRefetchInterval(state), state).toBe(false);
    }
    expect(ingestRefetchInterval(null)).toBe(false);
    expect(ingestRefetchInterval(undefined)).toBe(false);
  });
});

describe("deriveWorkflowSteps (UI-11 ingest ribbon)", () => {
  const statuses = (state: string | null) => deriveWorkflowSteps(state).map((s) => s.status);

  it("is idle when no dataset is in focus", () => {
    expect(statuses(null)).toEqual(["pending", "pending", "pending", "pending"]);
  });

  it("marks the current pipeline step active as the dataset advances", () => {
    expect(statuses("draft")).toEqual(["active", "pending", "pending", "pending"]);
    expect(statuses("uploading")).toEqual(["complete", "active", "pending", "pending"]);
    expect(statuses("analyzing")).toEqual(["complete", "active", "pending", "pending"]);
    expect(statuses("verified")).toEqual(["complete", "complete", "complete", "active"]);
  });

  it("reflects the real terminal backend states as blocked / error / complete", () => {
    // needs_review gates the "create version" step (blocked, not active).
    expect(statuses("needs_review")).toEqual(["complete", "complete", "blocked", "pending"]);
    // a rejected verify decision surfaces as an error on the final gate.
    expect(statuses("rejected")).toEqual(["complete", "complete", "complete", "error"]);
    // approved = every gate cleared.
    expect(statuses("approved")).toEqual(["complete", "complete", "complete", "complete"]);
    // deprecated reached approval but is retired → final gate blocked.
    expect(statuses("deprecated")).toEqual(["complete", "complete", "complete", "blocked"]);
  });

  it("treats an unknown state as the pipeline start (fail-open to idle)", () => {
    expect(statuses("unknown_state")).toEqual(["active", "pending", "pending", "pending"]);
  });
});

describe("Market Data page", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders the ingest ribbon reflecting the opened dataset's real state", async () => {
    stubApi(BASE_ROUTES);
    renderPage();

    // Before any selection the ribbon is idle (four Pending gates).
    const idleRibbon = within(
      screen.getByRole("list", { name: "Market data ingestion workflow" }),
    );
    expect(idleRibbon.getAllByText("Pending")).toHaveLength(4);

    await openDetail(); // opens md_1 (revision_state "approved")

    const ribbon = within(screen.getByRole("list", { name: "Market data ingestion workflow" }));
    await waitFor(() => expect(ribbon.getAllByText("Complete")).toHaveLength(4));
    expect(ribbon.getByText("Upload raw source")).toBeInTheDocument();
    // Two sequential fetches (registry + detail) plus a full a11y-name scan of the
    // guide's lists — generous timeout keeps it stable under parallel file load.
  }, 15000);

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

  // KALAN-A: the Browse File input in the setup card is what STARTS the
  // process — one submit chains create -> upload -> finalize -> analysis.
  function pickSetupFile(name = "fresh.csv", content = "timestamp,close\n1,2\n") {
    const file = new File([content], name, { type: "text/csv" });
    const input = screen.getByLabelText(/Raw source file/) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });
    return file;
  }

  it("chains create → upload → finalize → analysis from one Browse File submit", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    const { calls: uploadCalls } = stubUpload({
      "POST /market-datasets/md_new/raw-uploads": START_UPLOAD_MD_NEW,
    });
    renderPage();
    await screen.findByText("Binance 15m OHLCV");

    // The Dataset Setup shell is collapsed by default (UI-11) — open it first.
    fireEvent.click(screen.getByRole("button", { name: "+ Add Market Dataset" }));
    fireEvent.change(screen.getByLabelText(/Dataset Name/), { target: { value: "Fresh dataset" } });
    fireEvent.change(screen.getByLabelText(/Instrument Scope/), { target: { value: "ETHUSDT" } });
    const file = pickSetupFile();
    fireEvent.click(screen.getByRole("button", { name: "Create dataset & upload" }));

    expect(await screen.findByText("Created — md_new (draft).")).toBeInTheDocument();
    expect(await screen.findByText(/Raw source stored/)).toBeInTheDocument();
    expect(await screen.findByText(/Analysis requested — job/)).toBeInTheDocument();
    // Auto-open: the new dataset's detail is fetched and rendered.
    expect(await screen.findByText("Revision history")).toBeInTheDocument();

    const call = fetchMock.mock.calls.find(
      ([url, init]) => String(url).endsWith("/market-datasets") && init?.method === "POST",
    );
    expect(call).toBeDefined();
    const init = call?.[1] as RequestInit;
    // The v18 §4 descriptive facets fold into the free-form payload; the body
    // shape (market_data_type / payload / title / instrument_id) is unchanged.
    expect(JSON.parse(String(init.body))).toEqual({
      market_data_type: "ohlcv",
      payload: {
        market: "Crypto",
        source_provider: null,
        resolution: "15m",
        timezone: "UTC",
        record_time_basis: "Bar Close / End Time",
      },
      title: "Fresh dataset",
      instrument_id: "ETHUSDT",
    });
    // The create route reads no Idempotency-Key — mirrored verbatim.
    expect((init.headers as Record<string, string>)["Idempotency-Key"]).toBeUndefined();

    // The real bytes travelled once, with a fresh Idempotency-Key.
    expect(uploadCalls).toHaveLength(1);
    expect(uploadCalls[0]?.url).toContain("/market-datasets/md_new/raw-uploads");
    expect(uploadCalls[0]?.file?.name).toBe(file.name);
    expect(uploadCalls[0]?.headers["Idempotency-Key"]).toBeTruthy();

    // Finalize + analysis each carried their own fresh Idempotency-Key.
    for (const fragment of ["/md_new/raw-uploads/finalize", "/md_new/analysis"]) {
      const chained = fetchMock.mock.calls.find(
        ([url, i]) => String(url).includes(fragment) && i?.method === "POST",
      );
      expect(chained, fragment).toBeDefined();
      const headers = (chained?.[1] as RequestInit).headers as Record<string, string>;
      expect(headers["Idempotency-Key"]).toBeTruthy();
    }
  });

  it("blocks the submit without a selected file — the file starts the process", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("Binance 15m OHLCV");

    fireEvent.click(screen.getByRole("button", { name: "+ Add Market Dataset" }));
    fireEvent.click(screen.getByRole("button", { name: "Create dataset & upload" }));

    expect(
      await screen.findByText(/Select the raw source file \(Browse File\) first/),
    ).toBeInTheDocument();
    const createCall = fetchMock.mock.calls.find(
      ([url, init]) => String(url).endsWith("/market-datasets") && init?.method === "POST",
    );
    expect(createCall).toBeUndefined();
  });

  it("retries a failed upload from the failed stage without re-creating the dataset", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    let attempt = 0;
    const { calls: uploadCalls } = stubUpload({
      "POST /market-datasets/md_new/raw-uploads": () => {
        attempt += 1;
        if (attempt === 1) {
          return {
            status: 422,
            error: {
              code: "MARKET_DATA_FILE_TYPE_NOT_ALLOWED",
              message: "Upload a CSV or TXT market data file.",
            },
          };
        }
        return START_UPLOAD_MD_NEW;
      },
    });
    renderPage();
    await screen.findByText("Binance 15m OHLCV");

    fireEvent.click(screen.getByRole("button", { name: "+ Add Market Dataset" }));
    pickSetupFile();
    fireEvent.click(screen.getByRole("button", { name: "Create dataset & upload" }));

    expect(
      await screen.findByText(
        "MARKET_DATA_FILE_TYPE_NOT_ALLOWED: Upload a CSV or TXT market data file.",
      ),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Retry from failed step" }));

    expect(await screen.findByText(/Analysis requested — job/)).toBeInTheDocument();
    // The dataset was created exactly ONCE; the retry resumed at the upload.
    const createCalls = fetchMock.mock.calls.filter(
      ([url, init]) => String(url).endsWith("/market-datasets") && init?.method === "POST",
    );
    expect(createCalls).toHaveLength(1);
    expect(uploadCalls).toHaveLength(2);
  });

  it("folds the v18 §4 descriptive facets into the create payload", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    stubUpload({ "POST /market-datasets/md_new/raw-uploads": START_UPLOAD_MD_NEW });
    renderPage();
    await screen.findByText("Binance 15m OHLCV");

    fireEvent.click(screen.getByRole("button", { name: "+ Add Market Dataset" }));
    // Anchor on the required-field label ("Market *") — a bare /Market/ also
    // matches the ribbon's aria-label ("Market data ingestion workflow").
    fireEvent.change(screen.getByLabelText(/Market \*/), { target: { value: "Forex" } });
    fireEvent.change(screen.getByLabelText(/Source \/ Provider/), {
      target: { value: "Binance Futures" },
    });
    fireEvent.change(screen.getByLabelText(/Resolution/), { target: { value: "1h" } });
    pickSetupFile();
    fireEvent.click(screen.getByRole("button", { name: "Create dataset & upload" }));

    expect(await screen.findByText("Created — md_new (draft).")).toBeInTheDocument();

    const call = fetchMock.mock.calls.find(
      ([url, init]) => String(url).endsWith("/market-datasets") && init?.method === "POST",
    );
    const body = JSON.parse(String((call?.[1] as RequestInit).body));
    expect(body.payload).toEqual({
      market: "Forex",
      source_provider: "Binance Futures",
      resolution: "1h",
      timezone: "UTC",
      record_time_basis: "Bar Close / End Time",
    });
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

  function pickFile(name = "btcusdt.csv", content = "timestamp,close\n1,2\n") {
    const file = new File([content], name, { type: "text/csv" });
    const input = screen.getByLabelText("File") as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });
    return file;
  }

  it("uploads a real file (no storage metadata entered) then finalizes with a fresh Idempotency-Key", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    const { calls: uploadCalls } = stubUpload({
      "POST /market-datasets/md_1/raw-uploads": START_UPLOAD_RESULT,
    });
    renderPage();
    await openDetail();

    const file = pickFile();
    fireEvent.click(screen.getByRole("button", { name: "Upload file" }));

    expect(await screen.findByText(/Uploaded — asset/)).toBeInTheDocument();
    expect(screen.getByText(/asset_9/)).toBeInTheDocument();

    expect(uploadCalls).toHaveLength(1);
    expect(uploadCalls[0]?.url).toContain("/market-datasets/md_1/raw-uploads");
    expect(uploadCalls[0]?.file?.name).toBe(file.name);
    // A fresh Idempotency-Key travels alongside the content-addressed dedup
    // guarantee (belt-and-suspenders retry safety, F-01).
    expect(uploadCalls[0]?.headers["Idempotency-Key"]).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Finalize upload" }));

    expect(
      await screen.findByText(/Upload finalized — revision rev_1 is now uploading/),
    ).toBeInTheDocument();

    const finalizeCall = fetchMock.mock.calls.find(
      ([url, init]) => String(url).includes("/raw-uploads/finalize") && init?.method === "POST",
    );
    expect(finalizeCall).toBeDefined();
    const finalizeInit = finalizeCall?.[1] as RequestInit;
    expect(JSON.parse(String(finalizeInit.body))).toEqual({ asset_id: "asset_9" });
    expect((finalizeInit.headers as Record<string, string>)["Idempotency-Key"]).toBeTruthy();
  });

  it("surfaces an unsupported-file-type upload error and retries successfully", async () => {
    stubApi(BASE_ROUTES);
    let attempt = 0;
    const { calls: uploadCalls } = stubUpload({
      "POST /market-datasets/md_1/raw-uploads": () => {
        attempt += 1;
        if (attempt === 1) {
          return {
            status: 422,
            error: {
              code: "MARKET_DATA_FILE_TYPE_NOT_ALLOWED",
              message: "Upload a CSV or TXT market data file.",
            },
          };
        }
        return START_UPLOAD_RESULT;
      },
    });
    renderPage();
    await openDetail();

    pickFile();
    fireEvent.click(screen.getByRole("button", { name: "Upload file" }));

    expect(
      await screen.findByText("MARKET_DATA_FILE_TYPE_NOT_ALLOWED: Upload a CSV or TXT market data file."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    expect(await screen.findByText(/Uploaded — asset/)).toBeInTheDocument();
    expect(uploadCalls).toHaveLength(2);
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

  it("appends a revision with the If-Match rv token, a fresh Idempotency-Key and default fields", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    renderPage();
    await openDetail();

    // R2-08 (GAP item 7): there is no free-text instrument id input — the
    // instrument comes from the registry picker; the raw payload textarea is
    // Admin-only under Advanced (hidden for this non-admin actor).
    expect(screen.queryByLabelText(/Instrument id/)).toBeNull();
    expect(screen.getByRole("button", { name: "Choose instrument" })).toBeInTheDocument();
    expect(screen.queryByLabelText(/Payload \(optional JSON object\)/)).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Append revision" }));

    expect(await screen.findByText(/Revision appended/)).toBeInTheDocument();
    expect(screen.getByText("rev_3")).toBeInTheDocument();

    const call = fetchMock.mock.calls.find(
      ([url, init]) => String(url).includes("/revisions") && init?.method === "POST",
    );
    expect(call).toBeDefined();
    const init = call?.[1] as RequestInit;
    const headers = init.headers as Record<string, string>;
    // If-Match "rv-N" mirrors etag_for_row_version(detail.row_version = 4).
    expect(headers["If-Match"]).toBe('"rv-4"');
    expect(headers["Idempotency-Key"]).toBeTruthy();
    expect(JSON.parse(String(init.body))).toEqual({
      market_data_type: "ohlcv",
      payload: {},
      title: null,
      instrument_id: null,
      timezone_mode: "exchange",
      timezone_iana: null,
    });
  });

  it("creates a successor without an If-Match or Idempotency-Key header", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    renderPage();
    await openDetail();

    fireEvent.click(screen.getByRole("button", { name: "Create successor" }));

    expect(await screen.findByText(/Successor created/)).toBeInTheDocument();
    expect(screen.getByText("rev_4")).toBeInTheDocument();

    const call = fetchMock.mock.calls.find(
      ([url, init]) => String(url).includes("/successor") && init?.method === "POST",
    );
    expect(call).toBeDefined();
    const headers = (call?.[1] as RequestInit).headers as Record<string, string>;
    // The successor route reads neither header — mirrored verbatim.
    expect(headers["If-Match"]).toBeUndefined();
    expect(headers["Idempotency-Key"]).toBeUndefined();
  });

  it("approves the chosen revision with the If-Match rv token and a fresh Idempotency-Key", async () => {
    const fetchMock = stubApi(ADMIN_ROUTES);
    renderPage();
    await openDetail();

    fireEvent.click(await screen.findByRole("button", { name: "Approve (Admin)" }));

    expect(await screen.findByText(/Approved — revision/)).toBeInTheDocument();

    const call = fetchMock.mock.calls.find(
      ([url, init]) => String(url).includes("/approve") && init?.method === "POST",
    );
    expect(call).toBeDefined();
    const init = call?.[1] as RequestInit;
    const headers = init.headers as Record<string, string>;
    expect(headers["If-Match"]).toBe('"rv-4"');
    expect(headers["Idempotency-Key"]).toBeTruthy();
    // The picker defaults to the current head revision (rev_1) with no note.
    expect(JSON.parse(String(init.body))).toEqual({ revision_id: "rev_1", note: null });
  });

  it("deprecates the chosen revision without an If-Match or Idempotency-Key header", async () => {
    const fetchMock = stubApi(ADMIN_ROUTES);
    renderPage();
    await openDetail();

    fireEvent.click(await screen.findByRole("button", { name: "Deprecate (Admin)" }));

    expect(await screen.findByText(/Deprecated — revision/)).toBeInTheDocument();

    const call = fetchMock.mock.calls.find(
      ([url, init]) => String(url).includes("/deprecate") && init?.method === "POST",
    );
    expect(call).toBeDefined();
    const init = call?.[1] as RequestInit;
    const headers = init.headers as Record<string, string>;
    expect(headers["If-Match"]).toBeUndefined();
    expect(headers["Idempotency-Key"]).toBeUndefined();
    expect(JSON.parse(String(init.body))).toEqual({ revision_id: "rev_1", note: null });
  });

  // R2-09 stale-cache scenario: the /me projection still says admin (so the
  // composer renders) but the server has demoted the actor — the denial must
  // render verbatim; client visibility is never authorization.
  it("surfaces an Admin-only approval denial verbatim (server is the sole authority)", async () => {
    stubApi({
      ...ADMIN_ROUTES,
      "POST /market-datasets/md_1/approve": () => {
        throw new Error("APPROVAL_REQUIRES_ADMIN: Only an administrator may approve a revision.");
      },
    });
    renderPage();
    await openDetail();

    fireEvent.click(await screen.findByRole("button", { name: "Approve (Admin)" }));

    expect(
      await screen.findByText("APPROVAL_REQUIRES_ADMIN: Only an administrator may approve a revision."),
    ).toBeInTheDocument();
  });

  // R2-09 (GAP item 10): the approval composer never renders as a primary
  // control for a non-admin — the read-only note replaces it.
  it("hides approve/deprecate from a non-admin and shows the Admin approval note", async () => {
    stubApi(BASE_ROUTES); // /me -> non-admin user
    renderPage();
    await openDetail();

    expect(screen.queryByRole("button", { name: "Approve (Admin)" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Deprecate (Admin)" })).toBeNull();
    expect(screen.getByText(/Admin approval required/)).toBeInTheDocument();
  });

  // Fail-closed: while the identity projection is unknown (/me unavailable),
  // the Admin controls stay hidden — unknown never opens the gate.
  it("fail-closed: hides approve/deprecate while /me is unavailable", async () => {
    stubApi({
      ...BASE_ROUTES,
      "GET /me": apiErrorRoute(503, "SERVICE_UNAVAILABLE", "identity projection unavailable"),
    });
    renderPage();
    await openDetail();

    expect(screen.queryByRole("button", { name: "Approve (Admin)" })).toBeNull();
    expect(screen.getByText(/Admin approval required/)).toBeInTheDocument();
  });

  it("sends the IANA zone only for custom timezone mode", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    renderPage();
    await openDetail();

    fireEvent.change(screen.getByLabelText("Timezone mode"), { target: { value: "custom" } });
    fireEvent.change(screen.getByLabelText(/IANA timezone/), {
      target: { value: "America/New_York" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Append revision" }));

    expect(await screen.findByText(/Revision appended/)).toBeInTheDocument();

    const call = fetchMock.mock.calls.find(
      ([url, init]) => String(url).includes("/revisions") && init?.method === "POST",
    );
    const body = JSON.parse(String((call?.[1] as RequestInit).body));
    expect(body.timezone_mode).toBe("custom");
    expect(body.timezone_iana).toBe("America/New_York");
  });
});
