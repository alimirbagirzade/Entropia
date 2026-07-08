import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import { PreCheck } from "@/pages/PreCheck";
import { stubApi } from "./helpers/apiStub";

const REQUESTS_PAGE = {
  data: [
    {
      request_id: "req_1",
      package_type: "indicator",
      state: "precheck_blocked",
      source_kind: "code",
      package_root_id: null,
    },
  ],
  meta: { cursor: null, has_more: false },
};

// A blocked scan carrying one resolved + one missing call (§7.1 row fixtures).
const SCAN = {
  scan_id: "scan_1",
  attempt_no: 1,
  status: "blocked",
  detected: ["ta.sma", "ta.supertrend"],
  resolved: [
    {
      call: "ta.sma",
      canonical_key: "ta.sma",
      embedded_entity_id: "esp_1",
      embedded_revision_id: "pkgrev_1",
      content_hash: "sha256:c",
      runtime_adapter: "python",
      registry_version: 3,
    },
  ],
  missing: [
    {
      call: "ta.supertrend",
      code: "DEPENDENCY_MISSING",
      message: "Missing canonical Embedded System Package.",
    },
  ],
  scanner_version: "declared-v1",
  registry_fingerprint: "fp_1",
  context_hash: "sha256:ctx",
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
  declared_dependencies: [{ key: "ta.sma" }, { key: "ta.supertrend" }],
  state: "precheck_blocked",
  context_hash: "sha256:ctx",
  request_version: 2,
  owner_principal_id: "u_1",
  current_scan: SCAN,
  precheck_fresh: false,
  package_root_id: null,
  draft_revision_id: null,
  can_generate_candidate: false,
  created_at: "2026-07-08T10:00:00+00:00",
};

const PRECHECK_RESULT = {
  request_id: "req_1",
  scan_id: "scan_2",
  attempt_no: 2,
  status: "passed",
  state: "precheck_passed",
  resolved: 2,
  missing: [],
  registry_fingerprint: "fp_2",
  job_id: "job_1",
};

// The immutable artifact detail (queries/create_package.py::get_dependency_scan).
const SCAN_DETAIL = {
  ...SCAN,
  request_id: "req_1",
  unsupported: [],
  source_hash: "sha256:src",
  language: "pinescript",
  job_id: "job_0",
  completed_at: "2026-07-08T10:00:00+00:00",
};

// Ordered for the fragment-matching stub: the action POST and the detail GET
// must precede the "/create-package/requests" list prefix they contain.
const BASE_ROUTES: Record<string, unknown> = {
  "POST /create-package/requests/req_1/pre-check": PRECHECK_RESULT,
  "GET /dependency-scans/scan_1": SCAN_DETAIL,
  "GET /create-package/requests/req_1": REQUEST_DETAIL,
  "GET /create-package/requests": REQUESTS_PAGE,
};

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/packages/pre-check"]}>
        <PreCheck />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return client;
}

async function selectRequest() {
  await screen.findByText("req_1");
  fireEvent.click(screen.getByRole("button", { name: "Select" }));
}

describe("Pre-Check page", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders the dependency result rows with literal Resolved / Missing text", async () => {
    stubApi(BASE_ROUTES);
    renderPage();
    await selectRequest();

    expect(await screen.findByText("✓ Resolved")).toBeInTheDocument();
    expect(screen.getByText("✕ Missing")).toBeInTheDocument();
    expect(screen.getByText("ta.supertrend")).toBeInTheDocument();
    expect(
      screen.getByText(/DEPENDENCY_MISSING: Missing canonical Embedded System Package\./),
    ).toBeInTheDocument();
    expect(screen.getByText("pkgrev_1")).toBeInTheDocument();
  });

  it("runs Pre-Check with the OCC version header and shows the canonical passed line", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    renderPage();
    await selectRequest();

    fireEvent.click(await screen.findByRole("button", { name: "Run Pre-Check" }));

    expect(
      await screen.findByText(
        /Pre-Check passed\. Dependency manifest is ready for candidate generation\./,
      ),
    ).toBeInTheDocument();
    const call = fetchMock.mock.calls.find(
      ([url, init]) => String(url).endsWith("/pre-check") && init?.method === "POST",
    );
    expect(call).toBeDefined();
    const headers = (call?.[1] as RequestInit).headers as Record<string, string>;
    expect(headers["X-Request-Version"]).toBe("2");
    expect(headers["Idempotency-Key"]).toBeTruthy();
  });

  it("opens the immutable scan artifact viewer via GET /dependency-scans/{scan_id}", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    renderPage();
    await selectRequest();

    fireEvent.click(await screen.findByRole("button", { name: "View scan artifact" }));

    expect(await screen.findByText("sha256:src")).toBeInTheDocument();
    expect(screen.getByText("job_0")).toBeInTheDocument();
    const scanCall = fetchMock.mock.calls.find(([url]) =>
      String(url).includes("/dependency-scans/scan_1"),
    );
    expect(scanCall).toBeDefined();
  });

  it("warns that a passed scan is stale when the request context moved", async () => {
    stubApi({
      ...BASE_ROUTES,
      "GET /create-package/requests/req_1": {
        ...REQUEST_DETAIL,
        state: "precheck_stale",
        current_scan: { ...SCAN, status: "passed", missing: [] },
        precheck_fresh: false,
      },
    });
    renderPage();
    await selectRequest();

    expect(
      await screen.findByText(
        "Pre-Check is stale because the source changed. Run it again before sending.",
      ),
    ).toBeInTheDocument();
  });

  it("surfaces the server denial verbatim (server policy, not a UI hint)", async () => {
    stubApi({
      ...BASE_ROUTES,
      "GET /create-package/requests": () => {
        throw new Error("FORBIDDEN: Sign in to run Pre-Check.");
      },
    });
    renderPage();

    expect(await screen.findByText("Unable to load")).toBeInTheDocument();
    expect(screen.getByText("FORBIDDEN: Sign in to run Pre-Check.")).toBeInTheDocument();
  });
});
