import { afterEach, describe, expect, it, vi } from "vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import { PreCheck } from "@/pages/PreCheck";
import { stubApi } from "./helpers/apiStub";

// F-07 §4.4: the server composes the request's human label
// (backend `domain/create_package/labels.py::request_display_label`); the browser
// only renders it, and never builds a name out of the request_id.
const REQUEST_LABEL = "Indicator Package · 2026-07-08 10:00:00 UTC";

const REQUESTS_PAGE = {
  data: [
    {
      request_id: "req_1",
      display_label: REQUEST_LABEL,
      package_type: "indicator",
      state: "precheck_blocked",
      source_kind: "code",
      package_root_id: null,
      // F-07 §4.4: this request pins nothing nameable -> the honest fallback path.
      display_label: null,
      created_at: "2026-07-29T09:15:39+00:00",
    },
  ],
  meta: { cursor: null, has_more: false },
};

// The same page with a server-resolved name (a pinned Rationale Family / produced
// package). Used by the F-07 label assertion below.
const LABELLED_REQUESTS_PAGE = {
  ...REQUESTS_PAGE,
  data: [{ ...REQUESTS_PAGE.data[0], display_label: "Momentum Reversal" }],
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
  display_label: REQUEST_LABEL,
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

// F-01a: the POST is an ADMISSION — the scan computes in the durable worker, so
// the wire result is a "checking" envelope (no scan yet), never a fabricated pass.
const PRECHECK_RESULT = {
  request_id: "req_1",
  scan_id: "",
  attempt_no: 0,
  status: "checking",
  state: "requested",
  resolved: 0,
  missing: [],
  registry_fingerprint: "",
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

  it("names the request with a human label instead of a bare id (F-07)", async () => {
    stubApi(BASE_ROUTES);
    renderPage();

    // The picker row is identified by the server-owned label; the raw ULID sits
    // beneath it INSIDE the same row as the secondary binding key — never as the
    // primary identity. Reverting either render to <code>{request_id}</code> fails
    // this assertion.
    const row = (await screen.findByText(REQUEST_LABEL)).closest("tr");
    expect(row).not.toBeNull();
    expect(within(row as HTMLElement).getByText("req_1")).toBeInTheDocument();

    // Selecting it shows the same server-owned label on the detail panel's
    // Request row, so the label ends up rendered twice (picker + detail).
    // `waitFor` on the COUNT, not findAllByText — the latter resolves on the
    // first match, which the picker already satisfies before the detail loads.
    fireEvent.click(screen.getByRole("button", { name: "Select" }));
    await waitFor(() => expect(screen.getAllByText(REQUEST_LABEL)).toHaveLength(2));
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

  it("runs Pre-Check with the OCC version header and shows the background-running line", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    renderPage();
    await selectRequest();

    fireEvent.click(await screen.findByRole("button", { name: "Run Pre-Check" }));

    expect(
      await screen.findByText(
        /Pre-Check is running in the background\./,
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

  // PC-08: once the Source Text moves under a Passed result the UI state becomes
  // Stale, and the server refuses the candidate command until a fresh Pre-Check.
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
  // F-07 §4.4 — choosing your own request must not require recognizing an opaque
  // pkgreq_ id. Scoped with `within` to the request's own row.
  it("names a request instead of showing only its id (F-07)", async () => {
    stubApi({ ...BASE_ROUTES, "GET /create-package/requests": LABELLED_REQUESTS_PAGE });
    renderPage();

    const name = await screen.findByText("Momentum Reversal");
    const row = name.closest("tr");
    expect(row).toBeTruthy();
    // The id survives as the secondary/copyable token, not as the only identification.
    expect(within(row as HTMLElement).getByText("req_1")).toBeInTheDocument();
  });

  // No server label -> the raw id, plus the creation time so the row is still not
  // identified by an opaque token alone. A name is never invented.
  it("falls back to the request id when the server sends no label (F-07)", async () => {
    stubApi(BASE_ROUTES);
    renderPage();

    const id = await screen.findByText("req_1");
    const row = id.closest("tr");
    expect(within(row as HTMLElement).queryByText("Momentum Reversal")).not.toBeInTheDocument();
    expect(within(row as HTMLElement).getByText(/2026/)).toBeInTheDocument();
  });
});
