import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import { PreCheck } from "@/pages/PreCheck";
import { stubApi } from "./helpers/apiStub";

// I-17-COV — PC-22 (doc 07 §NN): "Result modal content contains untrusted
// package/source string -> UI safely renders text; no HTML/script injection or
// layout corruption occurs."
//
// `docs/audit/acceptance_id_map.md` §E listed PC-22 as a genuine gap: the Pre-Check
// result surface renders server strings the USER supplied (the parsed call, the
// per-dependency message, the canonical key) and nothing asserted they stay text.
// The payloads below are the classic injection shapes — a <script> tag, an <img
// onerror=> handler and a </div> that would tear the row layout open if any of
// them reached innerHTML.

const XSS_SCRIPT = "<script>window.__pwned = 1;</script>";
const XSS_IMG = '<img src=x onerror="window.__pwned = 2">';
const LAYOUT_BREAKER = "</code></div></section><h1>hijacked</h1>";
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
    },
  ],
  meta: { cursor: null, has_more: false },
};

const SCAN = {
  scan_id: "scan_1",
  attempt_no: 1,
  status: "blocked",
  detected: ["ta.sma", XSS_SCRIPT],
  resolved: [
    {
      call: "ta.sma",
      canonical_key: "ta.sma",
      embedded_entity_id: LAYOUT_BREAKER,
      embedded_revision_id: "pkgrev_1",
      content_hash: "sha256:c",
      runtime_adapter: "python",
      registry_version: 3,
    },
  ],
  missing: [
    {
      call: XSS_SCRIPT,
      code: "DEPENDENCY_MISSING",
      message: XSS_IMG,
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
  declared_dependencies: [{ key: "ta.sma" }],
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

const SCAN_DETAIL = {
  ...SCAN,
  request_id: "req_1",
  unsupported: [],
  source_hash: "sha256:src",
  language: "pinescript",
  job_id: "job_0",
  completed_at: "2026-07-08T10:00:00+00:00",
};

const ROUTES: Record<string, unknown> = {
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

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  delete (window as unknown as Record<string, unknown>).__pwned;
});

describe("Pre-Check untrusted string rendering (PC-22)", () => {
  it("renders an injected script/handler as literal text and executes nothing", async () => {
    stubApi(ROUTES);
    renderPage();
    await selectRequest();

    // The hostile call name is on screen — as TEXT, character for character.
    expect(await screen.findByText(XSS_SCRIPT)).toBeInTheDocument();
    expect(screen.getByText(new RegExp(`DEPENDENCY_MISSING: ${XSS_IMG.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`))).toBeInTheDocument();

    // Nothing was parsed as markup: no element was created from the payloads and
    // no handler ran.
    expect(document.querySelector("script")).toBeNull();
    expect(document.querySelector("img")).toBeNull();
    expect((window as unknown as Record<string, unknown>).__pwned).toBeUndefined();
  });

  it("keeps the row layout intact when a value tries to close the surrounding tags", async () => {
    stubApi(ROUTES);
    renderPage();
    await selectRequest();

    expect(await screen.findByText(LAYOUT_BREAKER)).toBeInTheDocument();
    // The closing-tag payload produced no heading and did not escape its <code>.
    expect(screen.queryByRole("heading", { name: "hijacked" })).toBeNull();
    const cell = screen.getByText(LAYOUT_BREAKER);
    expect(cell.tagName.toLowerCase()).toBe("code");
    expect(cell.querySelector("*")).toBeNull();
  });

  it("renders the same values safely in the immutable scan artifact view", async () => {
    stubApi(ROUTES);
    renderPage();
    await selectRequest();

    fireEvent.click(await screen.findByRole("button", { name: "View scan artifact" }));

    expect(await screen.findByText("sha256:src")).toBeInTheDocument();
    expect(document.querySelector("script")).toBeNull();
    expect(document.querySelector("img")).toBeNull();
    expect((window as unknown as Record<string, unknown>).__pwned).toBeUndefined();
  });
});
