import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import { Library } from "@/pages/Library";
import { stubApi } from "./helpers/apiStub";

const VIEWER_PERMISSIONS = {
  can_view: true,
  can_use: true,
  can_derive: true,
  can_create_revision: false,
  can_request_approval: false,
  can_approve_publish: false,
  can_deprecate: false,
  can_soft_delete: false,
  can_export: true,
};

// Doc 08 §3.2 / L4: no runs are linked, so every performance field is the
// availability label — never a fabricated zero.
const PERFORMANCE_NA = {
  net_profit: "not_applicable",
  max_drawdown: "not_applicable",
  romad: "not_applicable",
  win_rate: "not_applicable",
  trade_count: "not_applicable",
  out_of_sample: "not_applicable",
};

const INDICATOR_ROW = {
  entity_id: "pkg_1",
  package_kind: "indicator",
  name: "RSI Bundle",
  current_revision_id: "rev_11",
  revision_no: 3,
  lifecycle_state: "active",
  validation_state: "passed",
  approval_state: "approved",
  visibility_scope: "published",
  rationale_family: { id: "fam_1", name: "Momentum" },
  output_kinds: ["directional_signal"],
  derived_from_revision_id: null,
  owner_principal_id: "u_1",
  row_version: 7,
  content_hash: "sha256:abc",
  created_at: "2026-07-01T10:00:00+00:00",
  permissions: VIEWER_PERMISSIONS,
  performance: PERFORMANCE_NA,
};

const STRATEGY_ROW = {
  ...INDICATOR_ROW,
  entity_id: "pkg_2",
  package_kind: "strategy",
  name: "Breakout Alpha",
  current_revision_id: "rev_21",
  revision_no: 1,
  lifecycle_state: "deprecated",
  validation_state: "warning",
  approval_state: "draft",
  visibility_scope: "private",
  rationale_family: null,
};

const CATALOG_PAGE = {
  data: [INDICATOR_ROW, STRATEGY_ROW],
  meta: { cursor: "pkg_2", has_more: true },
};

const PACKAGE_DETAIL = {
  ...INDICATOR_ROW,
  input_contract: { name: "RSI Bundle" },
  output_contract: { kind: "directional_signal" },
  dependency_snapshot: { resolved: ["ta.rsi"] },
  validation_summary: { status: "passed" },
  change_note: "tuned",
  // Live family resolution: renamed since pinning, still active (doc 08 §4.3).
  rationale_family: {
    id: "fam_1",
    name: "Momentum Live",
    pinned_name: "Momentum",
    family_active: true,
  },
  provenance: {
    request_entity_id: "req_1",
    creation_mode: "generate_from_description",
    source_kind: "description",
    source_language: null,
    target_runtime: "python",
    draft_revision_id: "rev_d",
    scan: {
      scan_id: "scan_1",
      attempt_no: 1,
      status: "passed",
      detected_calls: ["ta.rsi"],
      resolved_refs: ["ta.rsi"],
      missing_calls: [],
      unsupported_calls: [],
      registry_fingerprint: "fp_1",
      context_hash: "ch_1",
    },
  },
  revisions: [
    {
      revision_id: "rev_11",
      revision_no: 3,
      validation_state: "passed",
      approval_state: "approved",
      change_note: "tuned",
      created_at: "2026-07-01T10:00:00+00:00",
    },
    {
      revision_id: "rev_10",
      revision_no: 2,
      validation_state: "failed",
      approval_state: "rejected",
      change_note: null,
      created_at: "2026-06-20T08:00:00+00:00",
    },
  ],
};

const FAMILIES_PAGE = {
  data: [{ entity_id: "fam_1", display_name: "Momentum" }],
  meta: { cursor: null, has_more: false },
};

// Order matters for the fragment-matching stub: the detail route must precede
// the list route ("/library/pkg_1" contains "/library").
const BASE_ROUTES = {
  "GET /library/pkg_1": PACKAGE_DETAIL,
  "GET /rationale-families": FAMILIES_PAGE,
  "GET /library": CATALOG_PAGE,
};

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/packages/library"]}>
        <Library />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return client;
}

describe("Package Library page", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders the catalog index with the orthogonal state facets", async () => {
    stubApi(BASE_ROUTES);
    renderPage();

    expect(await screen.findByText("RSI Bundle")).toBeInTheDocument();
    expect(screen.getByText("Breakout Alpha")).toBeInTheDocument();
    // The V18 Status dropdown stays split into orthogonal facets (doc 08 §13).
    // Rows are now grouped into per-type sections, so the state badges are
    // asserted within each section's list (the facet selects list the same
    // values, so scoping to the row lists disambiguates them from the options).
    const strategyList = screen.getByRole("list", { name: /strategy packages rows/i });
    expect(within(strategyList).getByText("warning")).toBeInTheDocument();
    expect(within(strategyList).getByText("deprecated")).toBeInTheDocument();
    const indicatorList = screen.getByRole("list", { name: /indicator packages rows/i });
    expect(within(indicatorList).getByText("passed")).toBeInTheDocument();
  });

  it("applies a facet filter as a server-side query param and never sends empty facets", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("RSI Bundle");

    fireEvent.change(screen.getByLabelText(/^Type/), { target: { value: "indicator" } });

    await waitFor(() => {
      const filtered = fetchMock.mock.calls.find(([url]) =>
        String(url).includes("/library?type=indicator"),
      );
      expect(filtered).toBeDefined();
      // The kind facet travels as the `type` alias; unset facets are absent.
      expect(String(filtered?.[0])).not.toContain("lifecycle_state");
      expect(String(filtered?.[0])).not.toContain("q=");
    });
  });

  it("supports the unassigned rationale-family sentinel filter", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("RSI Bundle");

    fireEvent.change(screen.getByLabelText(/Rationale family/), {
      target: { value: "unassigned" },
    });

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.find(([url]) =>
          String(url).includes("rationale_family_id=unassigned"),
        ),
      ).toBeDefined();
    });
  });

  it("sends the free-text search as the q param", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("RSI Bundle");

    fireEvent.change(screen.getByLabelText(/Search/), { target: { value: "rsi" } });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => {
      expect(fetchMock.mock.calls.find(([url]) => String(url).includes("q=rsi"))).toBeDefined();
    });
  });

  it("opens the detail with permissions, N/A performance (L4), provenance and history", async () => {
    stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("RSI Bundle");

    // Rows are grouped into per-type sections; only pkg_1 (RSI Bundle, indicator)
    // has a stubbed detail route, so scope the Detail toggle to that section.
    const indicatorList = screen.getByRole("list", { name: /indicator packages rows/i });
    fireEvent.click(within(indicatorList).getByRole("button", { name: "Detail" }));

    expect(await screen.findByText("Permissions (server-computed)")).toBeInTheDocument();
    // Server-computed flags render as text, never colour-only.
    expect(screen.getByText("can_use").parentElement?.textContent).toContain("yes");
    expect(screen.getByText("can_create_revision").parentElement?.textContent).toContain("no");
    // L4: every performance metric shows its availability label, never a zero.
    expect(screen.getAllByText("N/A (not applicable)")).toHaveLength(6);
    // Live family name resolution (rename without re-pin).
    expect(screen.getByText(/Momentum Live/)).toBeInTheDocument();
    expect(screen.getByText(/pinned as Momentum/)).toBeInTheDocument();
    // Stage-2e provenance + the immutable scan summary.
    expect(screen.getByText("req_1")).toBeInTheDocument();
    expect(screen.getByText(/1 resolved/)).toBeInTheDocument();
    // Revision history renders every returned revision.
    expect(screen.getByText("v2")).toBeInTheDocument();
  });

  it("pages forward with the opaque keyset cursor", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("RSI Bundle");

    fireEvent.click(screen.getByRole("button", { name: "Next" }));

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.find(([url]) => String(url).includes("cursor=pkg_2")),
      ).toBeDefined();
    });
  });

  it("refetches the catalog when the ['library'] SSE prefix is invalidated", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    const client = renderPage();
    await screen.findByText("RSI Bundle");
    const before = fetchMock.mock.calls.filter(([url]) =>
      String(url).includes("/library"),
    ).length;

    // resource.changed sweeps ["library"] (no dedicated catalog SSE event).
    await client.invalidateQueries({ queryKey: ["library"] });

    await waitFor(() => {
      const after = fetchMock.mock.calls.filter(([url]) =>
        String(url).includes("/library"),
      ).length;
      expect(after).toBeGreaterThan(before);
    });
  });

  it("groups the catalog into per-type sections (doc 08 §3.1)", async () => {
    stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("RSI Bundle");

    expect(screen.getByText("Strategy Packages")).toBeInTheDocument();
    expect(screen.getByText("Indicator Packages")).toBeInTheDocument();
    // Only kinds present on the current page get a section — no empty sections.
    expect(screen.queryByText("Condition Packages")).not.toBeInTheDocument();
    expect(screen.queryByText("Embedded System Packages")).not.toBeInTheDocument();
  });

  it("reorders rows within a section via the client-local Sort By control", async () => {
    const ZETA_ROW = {
      ...INDICATOR_ROW,
      entity_id: "pkg_z",
      name: "Zeta Bands",
      created_at: "2026-07-05T00:00:00+00:00",
    };
    // Two indicator rows so the intra-section order is observable; Sort By is a
    // pure client-local reorder (never a server query param).
    stubApi({
      ...BASE_ROUTES,
      "GET /library": { data: [INDICATOR_ROW, ZETA_ROW], meta: { cursor: null, has_more: false } },
    });
    renderPage();
    await screen.findByText("Zeta Bands");

    const firstRowText = () =>
      within(screen.getByRole("list", { name: /indicator packages rows/i })).getAllByRole(
        "listitem",
      )[0].textContent;
    // Default: Created Date descending → the newer Zeta Bands (07-05) leads.
    expect(firstRowText()).toContain("Zeta Bands");

    fireEvent.change(screen.getByLabelText(/Sort by/), { target: { value: "name" } });
    await waitFor(() => expect(firstRowText()).toContain("RSI Bundle"));
  });

  it("resets every facet with Clear filters (defined state behavior)", async () => {
    stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("RSI Bundle");

    const typeSelect = screen.getByLabelText(/^Type/) as HTMLSelectElement;
    fireEvent.change(typeSelect, { target: { value: "indicator" } });
    expect(typeSelect.value).toBe("indicator");

    fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(typeSelect.value).toBe("");
  });

  it("surfaces the authentication gate verbatim (doc 08 §2 — no catalog for Guests)", async () => {
    stubApi({
      ...BASE_ROUTES,
      "GET /library": () => {
        throw new Error("UNAUTHENTICATED: Sign in to browse the package library.");
      },
    });
    renderPage();

    expect(await screen.findByText("Unable to load")).toBeInTheDocument();
    expect(
      screen.getByText("UNAUTHENTICATED: Sign in to browse the package library."),
    ).toBeInTheDocument();
  });
});
