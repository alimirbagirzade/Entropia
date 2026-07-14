import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { Library } from "@/pages/Library";
import { stubApi } from "./helpers/apiStub";

// GAP-03: "Create Strategy Draft from Package (Strategy only)" (doc 08 §4.3). The
// affordance is offered only for a Strategy-kind package the server marks usable
// (permissions.can_use); the derive POST pins the exact source revision and the UI
// deep-links to the new draft. Server re-validates — the UI never authorizes.

const PERMS = (over: Record<string, boolean> = {}) => ({
  can_view: true,
  can_use: true,
  can_derive: true,
  can_create_revision: false,
  can_request_validation: false,
  can_request_approval: false,
  can_approve_publish: false,
  can_deprecate: false,
  can_soft_delete: false,
  can_export: true,
  ...over,
});

const PERF_NA = {
  net_profit: "not_applicable",
  max_drawdown: "not_applicable",
  romad: "not_applicable",
  win_rate: "not_applicable",
  trade_count: "not_applicable",
  out_of_sample: "not_applicable",
};

const row = (over: Record<string, unknown>) => ({
  entity_id: "pkg_x",
  package_kind: "strategy",
  name: "Reusable Trend",
  current_revision_id: "pkgrev_1",
  revision_no: 1,
  lifecycle_state: "active",
  validation_state: "passed",
  approval_state: "approved",
  visibility_scope: "published",
  rationale_family: null,
  output_kinds: ["strategy"],
  derived_from_revision_id: null,
  owner_principal_id: "u_owner",
  row_version: 1,
  content_hash: "sha256:src",
  created_at: "2026-07-01T10:00:00+00:00",
  permissions: PERMS(),
  performance: PERF_NA,
  ...over,
});

const detail = (over: Record<string, unknown>) => ({
  ...row(over),
  input_contract: { name: "Reusable Trend" },
  output_contract: { output_kinds: ["strategy"] },
  dependency_snapshot: { resolved: [{ canonical_key: "ta.sma" }] },
  validation_summary: null,
  change_note: null,
  provenance: null,
  revisions: [
    {
      revision_id: "pkgrev_1",
      revision_no: 1,
      validation_state: "passed",
      approval_state: "approved",
      change_note: null,
      created_at: "2026-07-01T10:00:00+00:00",
    },
  ],
  ...over,
});

const STRATEGY_USABLE = row({ entity_id: "pkg_str", name: "Reusable Trend" });
const INDICATOR = row({
  entity_id: "pkg_ind",
  package_kind: "indicator",
  name: "RSI Bundle",
  current_revision_id: "pkgrev_ind",
});
const STRATEGY_UNUSABLE = row({
  entity_id: "pkg_dep",
  name: "Deprecated Strategy",
  current_revision_id: "pkgrev_dep",
  permissions: PERMS({ can_use: false }),
});

const CATALOG = {
  data: [STRATEGY_USABLE, INDICATOR, STRATEGY_UNUSABLE],
  meta: { cursor: null, has_more: false },
};

const DERIVE_RESULT = {
  draft_id: "stratdraft_new",
  strategy_root_id: "strat_new",
  display_name: "Reusable Trend",
  row_version: 0,
  source_provenance: {
    source_package_root_id: "pkg_str",
    source_package_revision_id: "pkgrev_1",
    source_content_hash: "sha256:src",
    source_package_kind: "strategy",
    source_display_name: "Reusable Trend",
    inherited_dependencies: { resolved: [{ canonical_key: "ta.sma" }] },
  },
};

// Detail fragments must precede the "/library" list fragment (substring match).
const ROUTES = {
  "GET /library/pkg_str": detail({ entity_id: "pkg_str", name: "Reusable Trend" }),
  "GET /library/pkg_ind": detail({
    entity_id: "pkg_ind",
    package_kind: "indicator",
    name: "RSI Bundle",
    current_revision_id: "pkgrev_ind",
  }),
  "GET /library/pkg_dep": detail({
    entity_id: "pkg_dep",
    name: "Deprecated Strategy",
    current_revision_id: "pkgrev_dep",
    permissions: PERMS({ can_use: false }),
  }),
  "GET /rationale-families": { data: [], meta: { cursor: null, has_more: false } },
  "GET /library": CATALOG,
};

function renderPage(routes: Record<string, unknown>) {
  const fetchMock = stubApi(routes);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/packages/library"]}>
        <Routes>
          <Route path="/packages/library" element={<Library />} />
          <Route path="/strategy" element={<div>STRATEGY DRAFT LANDING</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return fetchMock;
}

async function openDetail(name: RegExp) {
  const rowEl = (await screen.findByText(name)).closest("[role='listitem']") as HTMLElement;
  fireEvent.click(within(rowEl).getByRole("button", { name: "Detail" }));
}

describe("GAP-03 derive Strategy Draft from Package", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("offers the action for a usable Strategy package and derives with the pinned source, then deep-links", async () => {
    const fetchMock = renderPage({ ...ROUTES, "POST /strategy-drafts": DERIVE_RESULT });
    await openDetail(/Reusable Trend/);

    const deriveBtn = await screen.findByRole("button", {
      name: "Create Strategy Draft from Package",
    });
    fireEvent.click(deriveBtn);

    // Deep-link: the new draft lands on /strategy.
    expect(await screen.findByText("STRATEGY DRAFT LANDING")).toBeInTheDocument();

    // The derive POST pinned the exact source root + head revision (no "latest").
    const call = fetchMock.mock.calls.find(
      ([url, init]) =>
        String(url).includes("/strategy-drafts") &&
        (init as RequestInit | undefined)?.method === "POST",
    );
    expect(call).toBeDefined();
    const body = JSON.parse(String((call?.[1] as RequestInit).body));
    expect(body.source_package_root_id).toBe("pkg_str");
    expect(body.source_package_revision_id).toBe("pkgrev_1");
    // A create has no head to race → an Idempotency-Key travels but no OCC token.
    const headers = (call?.[1] as RequestInit).headers as Record<string, string>;
    expect(headers["Idempotency-Key"]).toBeTruthy();
  });

  it("hides the action for a non-Strategy (indicator) package", async () => {
    renderPage(ROUTES);
    await openDetail(/RSI Bundle/);
    expect(await screen.findByText(/Permissions/)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Create Strategy Draft from Package" }),
    ).toBeNull();
  });

  it("hides the action for a Strategy package the server marks not usable", async () => {
    renderPage(ROUTES);
    await openDetail(/Deprecated Strategy/);
    expect(await screen.findByText(/Permissions/)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Create Strategy Draft from Package" }),
    ).toBeNull();
  });
});
