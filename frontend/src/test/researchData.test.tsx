import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import { researchStateTone } from "@/lib/researchData";
import { ResearchData } from "@/pages/ResearchData";
import { stubApi } from "./helpers/apiStub";

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

const START_UPLOAD_RESULT = { asset_id: "rasset_9", entity_id: "rd_1" };

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

// Order matters for the fragment-matching stub: action/detail fragments must
// precede their prefixes. finalize contains /upload-session; every rd_1 sub-path
// contains /research-datasets; POST /research-datasets (create) is a substring of
// every rd_1 POST; GET /research-datasets (list) is a substring of every detail.
const BASE_ROUTES = {
  "POST /research-datasets/rd_1/upload-session/finalize": FINALIZE_RESULT,
  "POST /research-datasets/rd_1/upload-session": START_UPLOAD_RESULT,
  "POST /research-datasets/rd_1/analysis": ANALYSIS_RESULT,
  "POST /research-datasets": CREATE_RESULT,
  "GET /research-datasets/rd_1": DETAIL_RD1,
  "GET /research-datasets/rd_new": DETAIL_RD_NEW,
  "GET /research-datasets": DATASETS_PAGE,
};

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/research-data"]}>
        <ResearchData />
      </MemoryRouter>
    </QueryClientProvider>,
  );
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

    fireEvent.change(screen.getByLabelText(/Linked Market Data entity id/), {
      target: { value: "md_1" },
    });
    fireEvent.change(screen.getByLabelText(/Display name/), { target: { value: "Fresh research" } });
    fireEvent.change(screen.getByLabelText(/Provider/), { target: { value: "coinglass" } });
    fireEvent.change(screen.getByLabelText(/Payload/), {
      target: { value: '{"source": "coinglass"}' },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create dataset" }));

    expect(await screen.findByText("Created — rd_new (draft).")).toBeInTheDocument();
    // Auto-open: the new dataset's detail is fetched and rendered.
    expect(await screen.findByText("Revision history")).toBeInTheDocument();

    const call = fetchMock.mock.calls.find(
      ([url, init]) => String(url).endsWith("/research-datasets") && init?.method === "POST",
    );
    expect(call).toBeDefined();
    const init = call?.[1] as RequestInit;
    expect(JSON.parse(String(init.body))).toEqual({
      market_entity_id: "md_1",
      payload: { source: "coinglass" },
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

    fireEvent.change(screen.getByLabelText(/Linked Market Data entity id/), {
      target: { value: "md_1" },
    });
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

  it("blocks an unparseable payload locally instead of sending it", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("Binance OI 8h");

    fireEvent.change(screen.getByLabelText(/Linked Market Data entity id/), {
      target: { value: "md_1" },
    });
    fireEvent.change(screen.getByLabelText(/Payload/), { target: { value: "{not json" } });
    fireEvent.click(screen.getByRole("button", { name: "Create dataset" }));

    expect(await screen.findByText("Payload is not valid JSON.")).toBeInTheDocument();
    const posted = fetchMock.mock.calls.some(([, init]) => init?.method === "POST");
    expect(posted).toBe(false);
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
    expect(screen.getByText("rrev_0")).toBeInTheDocument();
    // rv 4 also appears in the ResearchLifecycle intro (OCC token hint) — scope to
    // the identity table where the row_version is displayed.
    expect(identityTable.getByText(/rv 4/)).toBeInTheDocument();
  });

  it("starts a raw upload then finalizes it with a fresh Idempotency-Key", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    renderPage();
    await openDetail();

    fireEvent.change(screen.getByLabelText("Object key"), {
      target: { value: "raw/oi.csv" },
    });
    fireEvent.change(screen.getByLabelText("Content digest"), { target: { value: "sha256:d" } });
    fireEvent.change(screen.getByLabelText("Size (bytes)"), { target: { value: "2048" } });
    fireEvent.click(screen.getByRole("button", { name: "Start upload" }));

    expect(await screen.findByText(/Upload started/)).toBeInTheDocument();

    const startCall = fetchMock.mock.calls.find(
      ([url, init]) => String(url).endsWith("/upload-session") && init?.method === "POST",
    );
    expect(startCall).toBeDefined();
    const startInit = startCall?.[1] as RequestInit;
    expect(JSON.parse(String(startInit.body))).toEqual({
      object_key: "raw/oi.csv",
      content_digest: "sha256:d",
      size_bytes: 2048,
      content_type: null,
      original_filename: null,
    });
    // Start-upload is not idempotency-wrapped upstream — no key is sent.
    expect((startInit.headers as Record<string, string>)["Idempotency-Key"]).toBeUndefined();

    // The asset id from the start result seeds the finalize input.
    expect(screen.getByLabelText("Asset id to finalize")).toHaveValue("rasset_9");
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

    fireEvent.change(screen.getByLabelText(/Linked Market Data entity id/), {
      target: { value: "md_unapproved" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create dataset" }));

    expect(
      await screen.findByText(
        "DEPENDENCY_BLOCKED: Link this Research Data version to an Approved Market Data dataset first.",
      ),
    ).toBeInTheDocument();
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
