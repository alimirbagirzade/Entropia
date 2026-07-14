import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import { CreatePackage } from "@/pages/CreatePackage";
import { stubApi } from "./helpers/apiStub";

const FAMILIES_PAGE = {
  data: [
    { entity_id: "fam_1", display_name: "Momentum", normalized_name: "momentum", display_color: null },
  ],
  meta: { cursor: null, has_more: false },
};

const REQUESTS_PAGE = {
  data: [
    {
      request_id: "req_1",
      package_type: "indicator",
      state: "requested",
      source_kind: "code",
      package_root_id: null,
    },
  ],
  meta: { cursor: null, has_more: false },
};

const REQUEST_DETAIL = {
  request_id: "req_1",
  package_type: "indicator",
  creation_mode: "translate_existing_code",
  source_kind: "code",
  source_language: "pinescript",
  target_runtime: "python",
  output_contract: { kind: "directional_signal" },
  rationale_family_id: "fam_1",
  compatible_rationale_family_ids: [],
  declared_dependencies: [{ key: "ta.sma", signature: {} }],
  state: "precheck_passed",
  context_hash: "sha256:ctx",
  request_version: 2,
  owner_principal_id: "u_1",
  current_scan: {
    scan_id: "scan_1",
    attempt_no: 1,
    status: "passed",
    detected: ["ta.sma"],
    resolved: ["ta.sma"],
    missing: [],
    scanner_version: "declared-v1",
    registry_fingerprint: "fp_1",
    context_hash: "sha256:ctx",
  },
  precheck_fresh: true,
  package_root_id: null,
  draft_revision_id: null,
  can_generate_candidate: true,
  current_validation_run: null,
  validation_fresh: false,
  claims_equivalence: true,
  current_baseline: null,
  baseline_ready: false,
  baseline_required: true,
  created_at: "2026-07-08T10:00:00+00:00",
};

// The just-created request (no scan yet); the create flow auto-opens its detail.
const REQUEST_DETAIL_NEW = {
  ...REQUEST_DETAIL,
  request_id: "req_new",
  state: "requested",
  declared_dependencies: [],
  current_scan: null,
  precheck_fresh: false,
  can_generate_candidate: false,
};

const CREATE_RESULT = {
  request_id: "req_new",
  package_type: "indicator",
  source_kind: "code",
  state: "requested",
  context_hash: "sha256:new",
  request_version: 1,
};

// Action results (commands/create_package.py return dicts verbatim).
const PRECHECK_RESULT = {
  request_id: "req_1",
  scan_id: "scan_2",
  attempt_no: 2,
  status: "passed",
  state: "precheck_passed",
  resolved: 1,
  missing: [],
  registry_fingerprint: "fp_2",
  job_id: "job_1",
};

const CANDIDATE_RESULT = {
  request_id: "req_1",
  state: "candidate_ready",
  candidate_hash: "sha256:cand",
  job_id: "job_2",
};

const DRAFT_RESULT = {
  request_id: "req_1",
  package_root_id: "root_1",
  draft_revision_id: "rev_1",
  state: "draft_created",
};

const VALIDATION_RESULT = {
  request_id: "req_1",
  validation_run_id: "vr_1",
  attempt_no: 1,
  status: "passed",
  state: "eligible_for_approval",
  checks: [{ name: "output_structure", passed: true }],
  job_id: "job_3",
};

const REVISION_RESULT = {
  request_id: "req_1",
  state: "candidate_ready",
  candidate_hash: "sha256:rev",
};

const BASELINE_UPLOAD_RESULT = {
  request_id: "req_1",
  baseline_asset_id: "ba_1",
  attempt_no: 1,
  parse_status: "uploaded",
  content_digest: "sha256:csv",
  size_bytes: 42,
};

const BASELINE_PARSE_RESULT = {
  request_id: "req_1",
  baseline_asset_id: "ba_1",
  attempt_no: 1,
  parse_status: "passed",
  parser_version: "baseline-parser-v1",
  parse_report: { rows: 3 },
  job_id: "job_4",
};

// A request with a draft present (validation + approve edges are live).
const REQUEST_DETAIL_DRAFT = {
  ...REQUEST_DETAIL,
  state: "draft_created",
  package_root_id: "root_1",
  draft_revision_id: "rev_1",
};

// A request whose head baseline is uploaded but not yet parsed.
const REQUEST_DETAIL_BASELINE = {
  ...REQUEST_DETAIL_DRAFT,
  current_baseline: {
    baseline_asset_id: "ba_1",
    attempt_no: 1,
    parse_status: "uploaded",
    content_digest: "sha256:csv",
    size_bytes: 42,
    original_filename: "baseline.csv",
    baseline_metadata: { provider: "x", symbol: "BTCUSD" },
    parse_report: null,
    parser_version: null,
  },
};

// Order matters for the fragment-matching stub: the detail routes must precede
// the list route ("/create-package/requests/req_1" contains
// "/create-package/requests"). POST vs GET differ by method, so their order is
// free — but keep POST first for clarity.
const BASE_ROUTES: Record<string, unknown> = {
  "POST /create-package/requests": CREATE_RESULT,
  "GET /create-package/requests/req_new": REQUEST_DETAIL_NEW,
  "GET /create-package/requests/req_1": REQUEST_DETAIL,
  "GET /create-package/requests": REQUESTS_PAGE,
  "GET /rationale-families": FAMILIES_PAGE,
};

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/packages/create"]}>
        <CreatePackage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return client;
}

describe("Create Package page", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders the actor's requests with the flow-state badge", async () => {
    stubApi(BASE_ROUTES);
    renderPage();

    expect(await screen.findByText("req_1")).toBeInTheDocument();
    expect(screen.getByText("requested")).toBeInTheDocument();
  });

  it("submits the composed request body and a fresh Idempotency-Key", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    renderPage();
    // Wait for the rationale family selector to hydrate from the server.
    await screen.findByRole("option", { name: "Momentum" });

    fireEvent.change(screen.getByLabelText("Rationale family"), { target: { value: "fam_1" } });
    fireEvent.change(screen.getByLabelText("Source code"), {
      target: { value: "//@version=5\nindicator('x')" },
    });
    fireEvent.change(screen.getByLabelText("Declared dependencies"), {
      target: { value: "ta.sma\nta.rsi\n" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Create request" }));

    expect(await screen.findByText(/Request created/)).toBeInTheDocument();

    const createCall = fetchMock.mock.calls.find(
      ([url, init]) =>
        String(url).endsWith("/create-package/requests") && init?.method === "POST",
    );
    expect(createCall).toBeDefined();
    const init = createCall?.[1] as RequestInit;
    expect(JSON.parse(String(init.body))).toEqual({
      package_type: "indicator",
      creation_mode: "translate_existing_code",
      target_runtime: "python",
      request_body: "//@version=5\nindicator('x')",
      output_contract: { kind: "directional_signal" },
      source_language: "pinescript",
      other_language_label: null,
      rationale_family_id: "fam_1",
      declared_dependencies: [{ key: "ta.sma" }, { key: "ta.rsi" }],
    });
    expect((init.headers as Record<string, string>)["Idempotency-Key"]).toBeTruthy();
  });

  it("sends source_language null for a Generate From Description request", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByRole("option", { name: "Momentum" });

    fireEvent.change(screen.getByLabelText("Creation mode"), {
      target: { value: "generate_from_description" },
    });
    // The code-language selector is gone; the description note is shown instead.
    expect(screen.queryByLabelText("Source language")).not.toBeInTheDocument();
    expect(
      screen.getByText("Not applicable — Generate From Description carries no code."),
    ).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Rationale family"), { target: { value: "fam_1" } });
    fireEvent.change(screen.getByLabelText("Description"), {
      target: { value: "A momentum crossover" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create request" }));

    await screen.findByText(/Request created/);
    const createCall = fetchMock.mock.calls.find(
      ([url, init]) =>
        String(url).endsWith("/create-package/requests") && init?.method === "POST",
    );
    const body = JSON.parse(String((createCall?.[1] as RequestInit).body));
    expect(body.source_language).toBeNull();
    expect(body.creation_mode).toBe("generate_from_description");
  });

  it("scopes the output-contract kinds to the selected package type", async () => {
    stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByRole("option", { name: "Momentum" });

    // Indicator offers directional_signal; Condition collapses to boolean_condition.
    expect(screen.getByRole("option", { name: "directional_signal" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Package type"), { target: { value: "condition" } });
    expect(screen.getByRole("option", { name: "boolean_condition" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "directional_signal" })).not.toBeInTheDocument();
  });

  it("opens the request detail with the read-only projection", async () => {
    stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("req_1");

    fireEvent.click(screen.getByRole("button", { name: "View" }));

    expect(await screen.findByText("Current Pre-Check scan")).toBeInTheDocument();
    expect(screen.getByText("scan_1")).toBeInTheDocument();
    expect(screen.getByText("precheck_passed")).toBeInTheDocument();
    // The can-generate hint mirrors the server-side Send gate.
    expect(screen.getByText("Can generate candidate")).toBeInTheDocument();
  });

  it("refetches the requests index when ['package-requests'] is invalidated", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    const client = renderPage();
    await screen.findByText("req_1");
    const countListGets = () =>
      fetchMock.mock.calls.filter(
        ([url, init]) =>
          String(url).endsWith("/create-package/requests") &&
          (init?.method ?? "GET").toUpperCase() === "GET",
      ).length;
    const before = countListGets();

    await client.invalidateQueries({ queryKey: ["package-requests"] });

    await waitFor(() => {
      expect(countListGets()).toBeGreaterThan(before);
    });
  });

  it("surfaces the server denial verbatim (server policy, not a UI hint)", async () => {
    stubApi({
      ...BASE_ROUTES,
      "GET /create-package/requests": () => {
        throw new Error("FORBIDDEN: Guests cannot create packages.");
      },
    });
    renderPage();

    expect(await screen.findByText("Unable to load")).toBeInTheDocument();
    expect(screen.getByText("FORBIDDEN: Guests cannot create packages.")).toBeInTheDocument();
  });

  it("runs Pre-Check with the OCC version header and a fresh Idempotency-Key", async () => {
    // Action routes precede the create-POST fragment ("/create-package/requests"
    // is contained in the action URL, so ordering decides the match).
    const fetchMock = stubApi({
      "POST /create-package/requests/req_1/pre-check": PRECHECK_RESULT,
      ...BASE_ROUTES,
    });
    renderPage();
    await screen.findByText("req_1");
    fireEvent.click(screen.getByRole("button", { name: "View" }));

    fireEvent.click(await screen.findByRole("button", { name: "Run Pre-Check" }));

    expect(await screen.findByText("scan_2")).toBeInTheDocument();
    const call = fetchMock.mock.calls.find(
      ([url, init]) => String(url).endsWith("/pre-check") && init?.method === "POST",
    );
    expect(call).toBeDefined();
    const headers = (call?.[1] as RequestInit).headers as Record<string, string>;
    expect(headers["X-Request-Version"]).toBe("2");
    expect(headers["Idempotency-Key"]).toBeTruthy();
  });

  it("gates Generate candidate on the server-side hint, never a UI guess", async () => {
    stubApi({
      ...BASE_ROUTES,
      "GET /create-package/requests/req_1": { ...REQUEST_DETAIL, can_generate_candidate: false },
    });
    renderPage();
    await screen.findByText("req_1");
    fireEvent.click(screen.getByRole("button", { name: "View" }));

    expect(await screen.findByRole("button", { name: "Generate candidate" })).toBeDisabled();
  });

  it("passes the accepted candidate hash as the draft staleness token", async () => {
    let generated = false;
    const fetchMock = stubApi({
      "POST /create-package/requests/req_1/generate-candidate": () => {
        generated = true;
        return CANDIDATE_RESULT;
      },
      "POST /create-package/requests/req_1/draft": DRAFT_RESULT,
      ...BASE_ROUTES,
      // The refetched projection reaches candidate_ready after generation.
      "GET /create-package/requests/req_1": () =>
        generated ? { ...REQUEST_DETAIL, state: "candidate_ready" } : REQUEST_DETAIL,
    });
    renderPage();
    await screen.findByText("req_1");
    fireEvent.click(screen.getByRole("button", { name: "View" }));

    fireEvent.click(await screen.findByRole("button", { name: "Generate candidate" }));
    expect(await screen.findByText("sha256:cand")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Create draft" })).toBeEnabled();
    });
    fireEvent.click(screen.getByRole("button", { name: "Create draft" }));
    expect(await screen.findByText(/Draft created/)).toBeInTheDocument();

    const draftCall = fetchMock.mock.calls.find(
      ([url, init]) => String(url).endsWith("/draft") && init?.method === "POST",
    );
    expect(draftCall).toBeDefined();
    const init = draftCall?.[1] as RequestInit;
    expect(JSON.parse(String(init.body))).toEqual({ expected_candidate_hash: "sha256:cand" });
    expect((init.headers as Record<string, string>)["Idempotency-Key"]).toBeTruthy();
  });

  it("sends approve with the draft head token and shows the Admin denial verbatim", async () => {
    const fetchMock = stubApi({
      "POST /create-package/requests/req_1/approve": () => {
        throw new Error("APPROVAL_REQUIRES_ADMIN: Only an Admin may approve and publish.");
      },
      ...BASE_ROUTES,
      "GET /create-package/requests/req_1": {
        ...REQUEST_DETAIL,
        state: "draft_created",
        package_root_id: "root_1",
        draft_revision_id: "rev_1",
      },
    });
    renderPage();
    await screen.findByText("req_1");
    fireEvent.click(screen.getByRole("button", { name: "View" }));

    fireEvent.click(await screen.findByRole("button", { name: "Approve & publish" }));

    expect(
      await screen.findByText("APPROVAL_REQUIRES_ADMIN: Only an Admin may approve and publish."),
    ).toBeInTheDocument();
    const approveCall = fetchMock.mock.calls.find(
      ([url, init]) => String(url).endsWith("/approve") && init?.method === "POST",
    );
    expect(approveCall).toBeDefined();
    const body = JSON.parse(String((approveCall?.[1] as RequestInit).body));
    expect(body.expected_head_revision_id).toBe("rev_1");
  });

  it("runs validation with the OCC version header and a fresh Idempotency-Key", async () => {
    const fetchMock = stubApi({
      "POST /create-package/requests/req_1/validate": VALIDATION_RESULT,
      ...BASE_ROUTES,
      "GET /create-package/requests/req_1": REQUEST_DETAIL_DRAFT,
    });
    renderPage();
    await screen.findByText("req_1");
    fireEvent.click(screen.getByRole("button", { name: "View" }));

    fireEvent.click(await screen.findByRole("button", { name: "Run Validation Tests" }));

    expect(await screen.findByText("vr_1")).toBeInTheDocument();
    const call = fetchMock.mock.calls.find(
      ([url, init]) => String(url).endsWith("/validate") && init?.method === "POST",
    );
    expect(call).toBeDefined();
    const headers = (call?.[1] as RequestInit).headers as Record<string, string>;
    expect(headers["X-Request-Version"]).toBe("2");
    expect(headers["Idempotency-Key"]).toBeTruthy();
  });

  it("gates Run Validation Tests on a server-truth draft, never a UI guess", async () => {
    // No draft present -> the server-truth draft_revision_id is null.
    stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("req_1");
    fireEvent.click(screen.getByRole("button", { name: "View" }));

    expect(await screen.findByRole("button", { name: "Run Validation Tests" })).toBeDisabled();
  });

  it("requests a revision with the OCC header (legal state enforced server-side)", async () => {
    const fetchMock = stubApi({
      "POST /create-package/requests/req_1/request-revision": REVISION_RESULT,
      ...BASE_ROUTES,
      "GET /create-package/requests/req_1": { ...REQUEST_DETAIL, state: "revision_required" },
    });
    renderPage();
    await screen.findByText("req_1");
    fireEvent.click(screen.getByRole("button", { name: "View" }));

    fireEvent.click(await screen.findByRole("button", { name: "Request Revision" }));

    expect(await screen.findByText("sha256:rev")).toBeInTheDocument();
    const call = fetchMock.mock.calls.find(
      ([url, init]) => String(url).endsWith("/request-revision") && init?.method === "POST",
    );
    expect(call).toBeDefined();
    expect((call?.[1] as RequestInit).headers as Record<string, string>).toMatchObject({
      "X-Request-Version": "2",
    });
  });

  it("uploads a baseline with the OCC header + composed CSV body and metadata", async () => {
    const fetchMock = stubApi({
      "POST /create-package/requests/req_1/baseline": BASELINE_UPLOAD_RESULT,
      ...BASE_ROUTES,
      "GET /create-package/requests/req_1": REQUEST_DETAIL_DRAFT,
    });
    renderPage();
    await screen.findByText("req_1");
    fireEvent.click(screen.getByRole("button", { name: "View" }));

    fireEvent.change(await screen.findByLabelText("Baseline filename"), {
      target: { value: "baseline.csv" },
    });
    fireEvent.change(screen.getByLabelText("Baseline CSV content"), {
      target: { value: "time,close\n1,2\n" },
    });
    fireEvent.change(screen.getByLabelText("Baseline metadata"), {
      target: { value: '{"provider":"x","symbol":"BTCUSD"}' },
    });
    fireEvent.click(screen.getByRole("button", { name: "Upload baseline" }));

    expect(await screen.findByText("ba_1")).toBeInTheDocument();
    const call = fetchMock.mock.calls.find(
      ([url, init]) => String(url).endsWith("/baseline") && init?.method === "POST",
    );
    expect(call).toBeDefined();
    const init = call?.[1] as RequestInit;
    expect((init.headers as Record<string, string>)["X-Request-Version"]).toBe("2");
    expect((init.headers as Record<string, string>)["Idempotency-Key"]).toBeTruthy();
    expect(JSON.parse(String(init.body))).toEqual({
      content: "time,close\n1,2\n",
      baseline_metadata: { provider: "x", symbol: "BTCUSD" },
      content_type: "text/csv",
      original_filename: "baseline.csv",
    });
  });

  it("blocks a baseline upload with malformed metadata before dispatch", async () => {
    const fetchMock = stubApi({ ...BASE_ROUTES, "GET /create-package/requests/req_1": REQUEST_DETAIL_DRAFT });
    renderPage();
    await screen.findByText("req_1");
    fireEvent.click(screen.getByRole("button", { name: "View" }));

    fireEvent.change(await screen.findByLabelText("Baseline filename"), {
      target: { value: "baseline.csv" },
    });
    fireEvent.change(screen.getByLabelText("Baseline CSV content"), {
      target: { value: "time,close\n1,2\n" },
    });
    fireEvent.change(screen.getByLabelText("Baseline metadata"), {
      target: { value: "{not json" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Upload baseline" }));

    expect(await screen.findByText("Baseline metadata is not valid JSON.")).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.find(([url]) => String(url).endsWith("/baseline")),
    ).toBeUndefined();
  });

  it("runs baseline parse only when a baseline exists and surfaces the report", async () => {
    const fetchMock = stubApi({
      "POST /create-package/requests/req_1/baseline-parse": BASELINE_PARSE_RESULT,
      ...BASE_ROUTES,
      "GET /create-package/requests/req_1": REQUEST_DETAIL_BASELINE,
    });
    renderPage();
    await screen.findByText("req_1");
    fireEvent.click(screen.getByRole("button", { name: "View" }));

    const parseButton = await screen.findByRole("button", { name: "Run baseline parse" });
    expect(parseButton).toBeEnabled();
    fireEvent.click(parseButton);

    expect(await screen.findByText(/baseline-parser-v1/)).toBeInTheDocument();
    const call = fetchMock.mock.calls.find(
      ([url, init]) => String(url).endsWith("/baseline-parse") && init?.method === "POST",
    );
    expect(call).toBeDefined();
    expect((call?.[1] as RequestInit).headers as Record<string, string>).toMatchObject({
      "X-Request-Version": "2",
    });
  });
});
