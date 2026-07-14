import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import { Library } from "@/pages/Library";
import { stubApi } from "./helpers/apiStub";

// GAP-06 (epic slice 1): Deprecate + Move to Trash lifecycle actions on the
// Package Library detail panel (doc 08 §7). The buttons appear ONLY when the
// server marks the capability true; dispatch mirrors the backend contract
// (deprecate = no OCC/Idempotency-Key; soft delete = If-Match "rv-N" OCC).

const PERFORMANCE_NA = {
  net_profit: "not_applicable",
  max_drawdown: "not_applicable",
  romad: "not_applicable",
  win_rate: "not_applicable",
  trade_count: "not_applicable",
  out_of_sample: "not_applicable",
};

const OWNER_PERMISSIONS = {
  can_view: true,
  can_use: true,
  can_derive: true,
  can_create_revision: true,
  can_request_validation: true,
  can_request_approval: true,
  can_approve_publish: false,
  can_deprecate: true,
  can_soft_delete: true,
  can_export: true,
};

const VIEWER_PERMISSIONS = { ...OWNER_PERMISSIONS, can_deprecate: false, can_soft_delete: false };

const ROW = {
  entity_id: "pkg_own",
  package_kind: "indicator",
  name: "Owned RSI",
  current_revision_id: "rev_1",
  revision_no: 2,
  lifecycle_state: "active",
  validation_state: "passed",
  approval_state: "approved",
  visibility_scope: "private",
  rationale_family: null,
  output_kinds: ["directional_signal"],
  derived_from_revision_id: null,
  owner_principal_id: "u_owner",
  row_version: 7,
  content_hash: "sha256:own",
  created_at: "2026-07-01T10:00:00+00:00",
  permissions: OWNER_PERMISSIONS,
  performance: PERFORMANCE_NA,
};

function detailWith(permissions: typeof OWNER_PERMISSIONS) {
  return {
    ...ROW,
    permissions,
    input_contract: { name: "Owned RSI" },
    output_contract: { kind: "directional_signal" },
    dependency_snapshot: null,
    validation_summary: null,
    change_note: null,
    rationale_family: null,
    provenance: null,
    revisions: [
      {
        revision_id: "rev_1",
        revision_no: 2,
        validation_state: "passed",
        approval_state: "approved",
        change_note: null,
        created_at: "2026-07-01T10:00:00+00:00",
      },
    ],
  };
}

const FAMILIES_PAGE = { data: [], meta: { cursor: null, has_more: false } };

// Detail fragment ("/library/pkg_own") precedes the list prefix; method
// disambiguates the POST/DELETE mutations that also contain "/library".
function routesFor(permissions: typeof OWNER_PERMISSIONS) {
  return {
    "GET /library/pkg_own": detailWith(permissions),
    "GET /rationale-families": FAMILIES_PAGE,
    "GET /library": { data: [{ ...ROW, permissions }], meta: { cursor: null, has_more: false } },
    "POST /library/pkg_own/deprecate": { entity_id: "pkg_own", lifecycle_state: "deprecated" },
    "POST /library/pkg_own/derive": {
      entity_id: "pkg_derived",
      current_revision_id: "rev_d1",
      package_kind: "indicator",
      name: "My Copy",
      derived_from_revision_id: "rev_1",
      source_entity_id: "pkg_own",
    },
    "POST /library/pkg_own/revisions": {
      entity_id: "pkg_own",
      revision_id: "rev_2",
      revision_no: 3,
      current_revision_id: "rev_2",
      base_revision_id: "rev_1",
    },
    "DELETE /library/pkg_own": {},
  };
}

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

async function openDetail() {
  await screen.findByText("Owned RSI");
  fireEvent.click(screen.getAllByRole("button", { name: "Detail" })[0]);
  await screen.findByText("Lifecycle actions");
}

describe("Package Library lifecycle actions (GAP-06)", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("shows Deprecate + Move to Trash when the server marks the package editable", async () => {
    stubApi(routesFor(OWNER_PERMISSIONS));
    renderPage();
    await openDetail();

    expect(screen.getByRole("button", { name: "Deprecate" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Move to Trash" })).toBeInTheDocument();
  });

  it("dispatches a deprecate POST with no If-Match / Idempotency-Key", async () => {
    const fetchMock = stubApi(routesFor(OWNER_PERMISSIONS));
    renderPage();
    await openDetail();

    fireEvent.click(screen.getByRole("button", { name: "Deprecate" }));

    await waitFor(() => {
      const call = fetchMock.mock.calls.find(
        ([url, init]) =>
          String(url).includes("/library/pkg_own/deprecate") &&
          (init?.method ?? "").toUpperCase() === "POST",
      );
      expect(call).toBeDefined();
      const headers = (call?.[1]?.headers ?? {}) as Record<string, string>;
      expect(headers["If-Match"]).toBeUndefined();
      expect(headers["Idempotency-Key"]).toBeUndefined();
    });
  });

  it("soft-deletes under a two-step confirm carrying the If-Match rv-N OCC token", async () => {
    const fetchMock = stubApi(routesFor(OWNER_PERMISSIONS));
    renderPage();
    await openDetail();

    // First click only arms the destructive confirm — no request yet.
    fireEvent.click(screen.getByRole("button", { name: "Move to Trash" }));
    const confirm = await screen.findByRole("button", { name: "Confirm delete" });
    expect(
      fetchMock.mock.calls.some(([url, init]) => (init?.method ?? "") === "DELETE" && String(url).includes("/library/pkg_own")),
    ).toBe(false);

    fireEvent.click(confirm);

    await waitFor(() => {
      const call = fetchMock.mock.calls.find(
        ([url, init]) =>
          String(url).includes("/library/pkg_own") &&
          (init?.method ?? "").toUpperCase() === "DELETE",
      );
      expect(call).toBeDefined();
      const headers = (call?.[1]?.headers ?? {}) as Record<string, string>;
      expect(headers["If-Match"]).toBe('"rv-7"');
      expect(headers["Idempotency-Key"]).toBeTruthy();
    });
  });

  it("hides the lifecycle actions when the server denies them", async () => {
    stubApi(routesFor(VIEWER_PERMISSIONS));
    renderPage();
    await screen.findByText("Owned RSI");
    fireEvent.click(screen.getAllByRole("button", { name: "Detail" })[0]);

    expect(await screen.findByText("Permissions (server-computed)")).toBeInTheDocument();
    expect(screen.queryByText("Lifecycle actions")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Deprecate" })).not.toBeInTheDocument();
  });
});

// GAP-06 (epic R2a): Derive + Create Revision revision-plane actions (doc 08 §7).
// Both dispatch a POST with a fresh Idempotency-Key; Create Revision carries the
// BODY-form expected_head_revision_id OCC (the detail current_revision_id) and no
// If-Match. Derive has no OCC token (it creates a new root).
const NO_REVISION_PERMISSIONS = {
  ...OWNER_PERMISSIONS,
  can_derive: false,
  can_create_revision: false,
};

async function openRevisionActions() {
  await screen.findByText("Owned RSI");
  fireEvent.click(screen.getAllByRole("button", { name: "Detail" })[0]);
  await screen.findByText("Revision actions");
}

describe("Package Library revision actions (R2a)", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("shows Derive + Create Revision when the server marks the flags true", async () => {
    stubApi(routesFor(OWNER_PERMISSIONS));
    renderPage();
    await openRevisionActions();

    expect(screen.getByRole("button", { name: "Derive" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create Revision" })).toBeInTheDocument();
  });

  it("dispatches a Derive POST with an Idempotency-Key, no If-Match, and the source revision", async () => {
    const fetchMock = stubApi(routesFor(OWNER_PERMISSIONS));
    renderPage();
    await openRevisionActions();

    fireEvent.change(screen.getByLabelText(/Derive as/), { target: { value: "My Copy" } });
    fireEvent.click(screen.getByRole("button", { name: "Derive" }));

    await waitFor(() => {
      const call = fetchMock.mock.calls.find(
        ([url, init]) =>
          String(url).includes("/library/pkg_own/derive") &&
          (init?.method ?? "").toUpperCase() === "POST",
      );
      expect(call).toBeDefined();
      const headers = (call?.[1]?.headers ?? {}) as Record<string, string>;
      expect(headers["Idempotency-Key"]).toBeTruthy();
      expect(headers["If-Match"]).toBeUndefined();
      const body = JSON.parse(String(call?.[1]?.body ?? "{}"));
      expect(body.source_revision_id).toBe("rev_1"); // the current head revision
      expect(body.name).toBe("My Copy");
    });
    // Success surfaces the new derived root id.
    expect(await screen.findByText(/pkg_derived/)).toBeInTheDocument();
  });

  it("dispatches a Create Revision POST carrying the BODY-form expected_head_revision_id OCC", async () => {
    const fetchMock = stubApi(routesFor(OWNER_PERMISSIONS));
    renderPage();
    await openRevisionActions();

    fireEvent.click(screen.getByRole("button", { name: "Create Revision" }));

    await waitFor(() => {
      const call = fetchMock.mock.calls.find(
        ([url, init]) =>
          String(url).includes("/library/pkg_own/revisions") &&
          (init?.method ?? "").toUpperCase() === "POST",
      );
      expect(call).toBeDefined();
      const headers = (call?.[1]?.headers ?? {}) as Record<string, string>;
      expect(headers["Idempotency-Key"]).toBeTruthy();
      expect(headers["If-Match"]).toBeUndefined(); // OCC travels in the body, not If-Match
      const body = JSON.parse(String(call?.[1]?.body ?? "{}"));
      expect(body.expected_head_revision_id).toBe("rev_1");
    });
  });

  it("hides the revision actions when the server denies both flags", async () => {
    stubApi(routesFor(NO_REVISION_PERMISSIONS));
    renderPage();
    await screen.findByText("Owned RSI");
    fireEvent.click(screen.getAllByRole("button", { name: "Detail" })[0]);

    expect(await screen.findByText("Permissions (server-computed)")).toBeInTheDocument();
    expect(screen.queryByText("Revision actions")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Derive" })).not.toBeInTheDocument();
  });
});
