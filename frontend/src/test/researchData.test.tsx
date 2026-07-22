import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import { researchStateTone } from "@/lib/researchData";
import { ResearchData } from "@/pages/ResearchData";
import { apiErrorRoute, stubApi } from "./helpers/apiStub";
import { stubUpload } from "./helpers/xhrStub";

const ROW_OI = {
  entity_id: "rd_1",
  revision_id: "rrev_1",
  revision_no: 2,
  revision_state: "approved",
  validation_status: "passed",
  display_name: "Binance OI 8h",
  category_key: "open_interest",
  custom_category: null,
  provider_name: "coinglass",
  usage_scope: "research_backtest",
  linked_market_dataset_revision_id: "mrev_9",
  event_time_semantics: "provider_snapshot_timestamp",
  available_time_policy: "fixed_delay",
  available_delay_seconds: 120,
  frequency_policy: "8h",
  source_timezone_mode: "utc",
  source_timezone_iana: null,
  content_hash: "sha256:c1",
  manifest_hash: "sha256:m1",
  owner_principal_id: "u_1",
  row_version: 4,
  lifecycle_state: "active",
  created_at: "2026-07-01T09:00:00+00:00",
};

const ROW_CUSTOM = {
  entity_id: "rd_2",
  revision_id: "rrev_2",
  revision_no: 1,
  revision_state: "needs_review",
  validation_status: null,
  display_name: "Exchange Reserves",
  category_key: "exchange_reserves",
  custom_category: "exchange_reserves",
  provider_name: null,
  usage_scope: "agent_research_only",
  linked_market_dataset_revision_id: "mrev_5",
  event_time_semantics: null,
  available_time_policy: null,
  available_delay_seconds: null,
  frequency_policy: null,
  source_timezone_mode: null,
  source_timezone_iana: null,
  content_hash: null,
  manifest_hash: null,
  owner_principal_id: "u_1",
  row_version: 1,
  lifecycle_state: "draft",
  created_at: "2026-07-02T09:00:00+00:00",
};

const DATASETS_PAGE = {
  data: [ROW_OI, ROW_CUSTOM],
  meta: { cursor: null, has_more: false },
};

const DETAIL_RD1 = {
  ...ROW_OI,
  revisions: [
    { revision_id: "rrev_1", revision_no: 2, revision_state: "approved" },
    { revision_id: "rrev_0", revision_no: 1, revision_state: "deprecated" },
  ],
};

const CREATE_RESULT = {
  entity_id: "rd_new",
  revision_id: "rrev_new",
  revision_state: "draft",
};

const DETAIL_RD_NEW = {
  ...ROW_CUSTOM,
  entity_id: "rd_new",
  revision_id: "rrev_new",
  revision_no: 1,
  revision_state: "draft",
  display_name: "Fresh research",
  revisions: [{ revision_id: "rrev_new", revision_no: 1, revision_state: "draft" }],
};

const START_UPLOAD_RESULT = {
  asset_id: "rasset_9",
  entity_id: "rd_1",
  content_digest: "sha256:deadbeef",
  size_bytes: 42,
  content_type: "text/csv",
  original_filename: "oi.csv",
  deduplicated: false,
};

const FINALIZE_RESULT = {
  entity_id: "rd_1",
  asset_id: "rasset_9",
  revision_id: "rrev_1",
  revision_state: "draft",
};

const ANALYSIS_RESULT = {
  job_id: "rjob_7",
  entity_id: "rd_1",
  revision_id: "rrev_1",
  queue: "data",
  status: "queued",
};

// R2-06 — Market Data registry rows for the dependency picker. md_1 is
// approved (eligible); md_dep is deprecated (visible but not selectable).
const MARKET_ROW_APPROVED = {
  entity_id: "md_1",
  revision_id: "mrev_9",
  revision_no: 3,
  revision_state: "approved",
  market_data_type: "ohlcv",
  validation_status: "passed",
  title: "BTCUSDT spot 1m",
  instrument_id: "BTCUSDT",
  content_hash: "sha256:mc1",
  manifest_hash: "sha256:mm1",
  owner_principal_id: "u_1",
  row_version: 6,
  lifecycle_state: "active",
  created_at: "2026-06-01T09:00:00+00:00",
};

const MARKET_ROW_DEPRECATED = {
  ...MARKET_ROW_APPROVED,
  entity_id: "md_dep",
  revision_id: "mrev_2",
  revision_no: 1,
  revision_state: "deprecated",
  title: "Old ETH feed",
  instrument_id: "ETHUSDT",
};

const MARKET_PAGE = {
  data: [MARKET_ROW_APPROVED, MARKET_ROW_DEPRECATED],
  meta: { cursor: null, has_more: false },
};

// The server-truth dependency projection: the exact APPROVED revision md_1
// resolves to right now (read-only approved-bundle probe).
const MD1_BUNDLE = {
  entity_id: "md_1",
  revision_id: "mrev_9",
  revision_no: 3,
  revision_state: "approved",
  content_hash: "sha256:mc1",
  manifest_hash: "sha256:mm1",
  market_data_type: "ohlcv",
};

// Order matters for the fragment-matching stub: action/detail fragments must
// precede their prefixes. finalize contains /upload-session; every rd_1 sub-path
// contains /research-datasets; POST /research-datasets (create) is a substring of
// every rd_1 POST; GET /research-datasets (list) is a substring of every detail.
// The upload-session POST itself travels over XHR (lib/upload.ts), not fetch —
// it is stubbed separately with stubUpload() in the upload-specific tests.
const BASE_ROUTES = {
  "POST /research-datasets/rd_1/upload-session/finalize": FINALIZE_RESULT,
  "POST /research-datasets/rd_1/analysis": ANALYSIS_RESULT,
  "POST /research-datasets": CREATE_RESULT,
  "GET /research-datasets/rd_1": DETAIL_RD1,
  "GET /research-datasets/rd_new": DETAIL_RD_NEW,
  "GET /research-datasets": DATASETS_PAGE,
  "GET /market-datasets/md_1/approved-bundle": MD1_BUNDLE,
  "GET /market-datasets": MARKET_PAGE,
};

// R2-06 — link the approved market dataset through the picker and wait for the
// server-truth `ready` verdict (the approved-bundle probe) to unlock the form.
async function linkApprovedMarket() {
  fireEvent.click(screen.getByRole("button", { name: "Choose market dataset" }));
  fireEvent.click(await screen.findByRole("button", { name: /BTCUSDT spot 1m/ }));
  await screen.findByText(/Approved for use — revision/);
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/research-data"]}>
        <ResearchData />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  // P-10 (audit): the Dataset Setup form is closed by default (registry-first).
  // These suites drive the create form, so open it via the registry "+ Add
  // Research Dataset" action — the same path a user takes. Registry-only and
  // detail-open tests are unaffected (the registry stays mounted alongside).
  fireEvent.click(screen.getByRole("button", { name: /Add Research Dataset/i }));
  return client;
}

async function openDetail() {
  await screen.findByText("Binance OI 8h");
  fireEvent.click(screen.getAllByRole("button", { name: "Open" })[0]!);
  await screen.findByText("Revision history");
}

describe("researchStateTone", () => {
  it("maps revision states to badge tones without inventing status", () => {
    expect(researchStateTone("approved")).toBe("ok");
    expect(researchStateTone("verified")).toBe("ok");
    expect(researchStateTone("needs_review")).toBe("warn");
    expect(researchStateTone("deprecated")).toBe("down");
    expect(researchStateTone("approval_revoked")).toBe("down");
    expect(researchStateTone("draft")).toBe("neutral");
  });
});

describe("Research Data page", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders the registry with category, usage scope and revision states verbatim", async () => {
    stubApi(BASE_ROUTES);
    renderPage();

    // "Binance OI 8h" is unique to the registry table.
    expect(await screen.findByText("Binance OI 8h")).toBeInTheDocument();
    const registryTable = within(screen.getAllByRole("table")[0]!);
    expect(registryTable.getByText("Exchange Reserves")).toBeInTheDocument();
    expect(registryTable.getByText("open_interest")).toBeInTheDocument();
    expect(registryTable.getByText("exchange_reserves")).toBeInTheDocument();
    expect(registryTable.getByText("research_backtest")).toBeInTheDocument();
    expect(registryTable.getByText("agent_research_only")).toBeInTheDocument();
    expect(registryTable.getByText("approved")).toBeInTheDocument();
    expect(registryTable.getByText("needs_review")).toBeInTheDocument();
  });

  it("creates a dataset without an Idempotency-Key and auto-opens its detail", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("Binance OI 8h");

    await linkApprovedMarket();
    fireEvent.change(screen.getByLabelText(/Dataset Name/), { target: { value: "Fresh research" } });
    fireEvent.change(screen.getByLabelText(/Provider/), { target: { value: "coinglass" } });
    fireEvent.click(screen.getByRole("button", { name: "Create dataset" }));

    expect(await screen.findByText("Created — rd_new (draft).")).toBeInTheDocument();
    // Auto-open: the new dataset's detail is fetched and rendered.
    expect(await screen.findByText("Revision history")).toBeInTheDocument();

    const call = fetchMock.mock.calls.find(
      ([url, init]) => String(url).endsWith("/research-datasets") && init?.method === "POST",
    );
    expect(call).toBeDefined();
    const init = call?.[1] as RequestInit;
    // The v18 §4 descriptive facets fold into the free-form payload; the body
    // shape is unchanged.
    expect(JSON.parse(String(init.body))).toEqual({
      market_entity_id: "md_1",
      payload: {
        field_meaning: null,
        instrument_scope: null,
        frequency: "5m",
        timezone: "UTC",
      },
      category: "open_interest",
      usage_scope: "research_backtest",
      // A built-in category carries no custom value (server rejects a stray one).
      custom_category: null,
      display_name: "Fresh research",
      provider_name: "coinglass",
    });
    // The create route reads no Idempotency-Key — mirrored verbatim.
    expect((init.headers as Record<string, string>)["Idempotency-Key"]).toBeUndefined();
  });

  it("sends custom_category only for the other_custom category", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("Binance OI 8h");

    await linkApprovedMarket();
    fireEvent.change(screen.getByLabelText("Category"), { target: { value: "other_custom" } });
    fireEvent.change(screen.getByLabelText(/Custom category/), {
      target: { value: "exchange_reserves" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create dataset" }));

    await screen.findByText("Created — rd_new (draft).");
    const call = fetchMock.mock.calls.find(
      ([url, init]) => String(url).endsWith("/research-datasets") && init?.method === "POST",
    );
    const body = JSON.parse(String((call?.[1] as RequestInit).body));
    expect(body.category).toBe("other_custom");
    expect(body.custom_category).toBe("exchange_reserves");
  });

  it("folds the v18 §4 descriptive facets into the create payload", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("Binance OI 8h");

    await linkApprovedMarket();
    fireEvent.change(screen.getByLabelText(/Field Meaning/), {
      target: { value: "open interest in USD" },
    });
    fireEvent.change(screen.getByLabelText(/Instrument Scope/), {
      target: { value: "BTCUSDT Perpetual" },
    });
    fireEvent.change(screen.getByLabelText(/Frequency/), { target: { value: "8h" } });
    fireEvent.click(screen.getByRole("button", { name: "Create dataset" }));

    await screen.findByText("Created — rd_new (draft).");
    const call = fetchMock.mock.calls.find(
      ([url, init]) => String(url).endsWith("/research-datasets") && init?.method === "POST",
    );
    const body = JSON.parse(String((call?.[1] as RequestInit).body));
    expect(body.payload).toEqual({
      field_meaning: "open interest in USD",
      instrument_scope: "BTCUSDT Perpetual",
      frequency: "8h",
      timezone: "UTC",
    });
  });

  it("opens the detail with meaning, timing metadata and revision history", async () => {
    stubApi(BASE_ROUTES);
    renderPage();
    await openDetail();

    // Values unique to the detail card (not registry columns). The identity table
    // is table[1] (registry is table[0]); scope event-time semantics there so the
    // ResearchLifecycle time-policy <option> with the same value does not clash.
    expect(screen.getByText("mrev_9")).toBeInTheDocument();
    const identityTable = within(screen.getAllByRole("table")[1]!);
    expect(identityTable.getByText("provider_snapshot_timestamp")).toBeInTheDocument();
    expect(screen.getByText(/fixed_delay · delay 120s/)).toBeInTheDocument();
    expect(screen.getByText("sha256:c1")).toBeInTheDocument();
    // rrev_0 renders in the revision history AND in the bundle checkbox group
    // (R2-08: revisions are picked, not typed).
    expect(screen.getAllByText("rrev_0").length).toBeGreaterThan(0);
    // rv 4 also appears in the ResearchLifecycle intro (OCC token hint) — scope to
    // the identity table where the row_version is displayed.
    expect(identityTable.getByText(/rv 4/)).toBeInTheDocument();
  });

  function pickFile(name = "oi.csv", content = "timestamp,oi\n1,2\n") {
    const file = new File([content], name, { type: "text/csv" });
    const input = screen.getByLabelText("File") as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });
    return file;
  }

  it("uploads a real file (no storage metadata entered) then finalizes with a fresh Idempotency-Key", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    const { calls: uploadCalls } = stubUpload({
      "POST /research-datasets/rd_1/upload-session": START_UPLOAD_RESULT,
    });
    renderPage();
    await openDetail();

    const file = pickFile();
    fireEvent.click(screen.getByRole("button", { name: "Upload file" }));

    expect(await screen.findByText(/Uploaded — asset/)).toBeInTheDocument();
    expect(screen.getByText(/rasset_9/)).toBeInTheDocument();

    // The client supplies only the File — no object key/digest/size fields exist.
    expect(screen.queryByLabelText("Object key")).not.toBeInTheDocument();
    expect(uploadCalls).toHaveLength(1);
    expect(uploadCalls[0]?.url).toContain("/research-datasets/rd_1/upload-session");
    expect(uploadCalls[0]?.file?.name).toBe(file.name);
    // A fresh Idempotency-Key travels alongside the content-addressed dedup
    // guarantee (belt-and-suspenders retry safety, F-02).
    expect(uploadCalls[0]?.headers["Idempotency-Key"]).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Finalize upload" }));

    expect(await screen.findByText(/Upload finalized — revision rrev_1 is now draft/)).toBeInTheDocument();

    const finalizeCall = fetchMock.mock.calls.find(
      ([url, init]) => String(url).includes("/upload-session/finalize") && init?.method === "POST",
    );
    expect(finalizeCall).toBeDefined();
    const finalizeInit = finalizeCall?.[1] as RequestInit;
    expect(JSON.parse(String(finalizeInit.body))).toEqual({ asset_id: "rasset_9" });
    expect((finalizeInit.headers as Record<string, string>)["Idempotency-Key"]).toBeTruthy();
  });

  it("surfaces an unsupported-file-type upload error verbatim and retries successfully", async () => {
    stubApi(BASE_ROUTES);
    let attempt = 0;
    const { calls: uploadCalls } = stubUpload({
      "POST /research-datasets/rd_1/upload-session": () => {
        attempt += 1;
        if (attempt === 1) {
          return {
            status: 422,
            error: {
              code: "RESEARCH_DATA_FILE_TYPE_NOT_ALLOWED",
              message: "Upload a CSV or TXT research data file.",
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
      await screen.findByText(
        "RESEARCH_DATA_FILE_TYPE_NOT_ALLOWED: Upload a CSV or TXT research data file.",
      ),
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
    expect(screen.getByText("rjob_7")).toBeInTheDocument();
    expect(screen.getByText("data")).toBeInTheDocument();

    const call = fetchMock.mock.calls.find(
      ([url, init]) => String(url).includes("/analysis") && init?.method === "POST",
    );
    expect(call).toBeDefined();
    const init = call?.[1] as RequestInit;
    expect((init.headers as Record<string, string>)["Idempotency-Key"]).toBeTruthy();
  });

  it("surfaces a DEPENDENCY_BLOCKED create rejection verbatim (DR3 market link)", async () => {
    stubApi({
      ...BASE_ROUTES,
      "POST /research-datasets": () => {
        throw new Error(
          "DEPENDENCY_BLOCKED: Link this Research Data version to an Approved Market Data dataset first.",
        );
      },
    });
    renderPage();
    await screen.findByText("Binance OI 8h");

    // The client lock precedes — never replaces — the server's DR3 gate: even
    // with a confirmed-approved link, a server rejection renders verbatim.
    await linkApprovedMarket();
    fireEvent.click(screen.getByRole("button", { name: "Create dataset" }));

    expect(
      await screen.findByText(
        "DEPENDENCY_BLOCKED: Link this Research Data version to an Approved Market Data dataset first.",
      ),
    ).toBeInTheDocument();
  });

  it("locks steps 4-5 and Create until a server-confirmed approved link exists (no free-text input)", async () => {
    stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("Binance OI 8h");

    // The free-text id input is gone — the "type anything to unlock" scenario
    // cannot be reconstructed (GAP item 8).
    expect(screen.queryByLabelText(/Linked Market Data entity id/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create dataset" })).toBeDisabled();
    expect(screen.getAllByText("Locked — link approved Market Data")).toHaveLength(2);

    await linkApprovedMarket();

    expect(screen.getByRole("button", { name: "Create dataset" })).toBeEnabled();
    expect(screen.queryByText("Locked — link approved Market Data")).not.toBeInTheDocument();
  });

  it("shows non-approved market datasets as disabled rows in the picker", async () => {
    stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("Binance OI 8h");

    fireEvent.click(screen.getByRole("button", { name: "Choose market dataset" }));
    expect(await screen.findByRole("button", { name: /BTCUSDT spot 1m/ })).toBeEnabled();
    const deprecated = screen.getByRole("button", { name: /Old ETH feed/ });
    expect(deprecated).toBeDisabled();
    expect(deprecated).toHaveTextContent("not eligible — deprecated");
  });

  it("keeps the lock and renders the probe rejection verbatim when the approved-bundle resolve fails", async () => {
    stubApi({
      ...BASE_ROUTES,
      "GET /market-datasets/md_1/approved-bundle": apiErrorRoute(
        404,
        "MARKET_DATA_NOT_APPROVED",
        "No active approved revision for this dataset.",
      ),
    });
    renderPage();
    await screen.findByText("Binance OI 8h");

    fireEvent.click(screen.getByRole("button", { name: "Choose market dataset" }));
    fireEvent.click(await screen.findByRole("button", { name: /BTCUSDT spot 1m/ }));

    expect(
      (await screen.findAllByText(/MARKET_DATA_NOT_APPROVED: No active approved revision/)).length,
    ).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Create dataset" })).toBeDisabled();
    expect(screen.getAllByText("Locked — link approved Market Data")).toHaveLength(2);
  });

  it("keeps the lock and names the denial when the probe returns 403", async () => {
    stubApi({
      ...BASE_ROUTES,
      "GET /market-datasets/md_1/approved-bundle": apiErrorRoute(
        403,
        "ACCESS_DENIED",
        "You cannot read this dataset.",
      ),
    });
    renderPage();
    await screen.findByText("Binance OI 8h");

    fireEvent.click(screen.getByRole("button", { name: "Choose market dataset" }));
    fireEvent.click(await screen.findByRole("button", { name: /BTCUSDT spot 1m/ }));

    expect(
      await screen.findByText(/You do not have access to the linked Market Data dataset/),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create dataset" })).toBeDisabled();
  });

  it("surfaces the server view denial verbatim (role-aware read, not a UI hint)", async () => {
    stubApi({
      ...BASE_ROUTES,
      "GET /research-datasets": () => {
        throw new Error("ACCESS_DENIED: Admin, Supervisor or Agent access required.");
      },
    });
    renderPage();

    expect(await screen.findByText("Unable to load")).toBeInTheDocument();
    expect(
      screen.getByText("ACCESS_DENIED: Admin, Supervisor or Agent access required."),
    ).toBeInTheDocument();
  });

  it("refetches the registry when the ['research-data'] prefix is invalidated (SSE sweep)", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    const client = renderPage();
    await screen.findByText("Binance OI 8h");
    const before = fetchMock.mock.calls.filter(([url]) =>
      String(url).includes("/research-datasets"),
    ).length;

    await client.invalidateQueries({ queryKey: ["research-data"] });

    await waitFor(() => {
      const after = fetchMock.mock.calls.filter(([url]) =>
        String(url).includes("/research-datasets"),
      ).length;
      expect(after).toBeGreaterThan(before);
    });
  });
});
