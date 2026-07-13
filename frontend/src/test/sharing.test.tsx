import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import { Library } from "@/pages/Library";
import { stubApi } from "./helpers/apiStub";

// GAP-17: explicit package sharing on the Package Library detail panel. The
// Sharing panel appears ONLY when the server marks `can_share`; grant/revoke
// mirror the backend contract (If-Match "rv-N" OCC + a fresh Idempotency-Key),
// and the grantee email travels in the POST body.

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
  can_share: true,
};

const VIEWER_PERMISSIONS = { ...OWNER_PERMISSIONS, can_deprecate: false, can_share: false };

const ROW = {
  entity_id: "pkg_own",
  package_kind: "indicator",
  name: "Owned RSI",
  current_revision_id: "rev_1",
  revision_no: 2,
  lifecycle_state: "active",
  validation_state: "passed",
  approval_state: "approved",
  visibility_scope: "explicitly_shared",
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
    revisions: [],
  };
}

const SHARES = {
  entity_id: "pkg_own",
  visibility_scope: "explicitly_shared",
  row_version: 7,
  shares: [
    {
      share_id: "shr_1",
      grantee_principal_id: "u_grantee",
      grantee_email: "grantee@example.com",
      grantee_display_name: "Grantee",
      granted_by_principal_id: "u_owner",
      created_at: "2026-07-02T10:00:00+00:00",
    },
  ],
};

const FAMILIES_PAGE = { data: [], meta: { cursor: null, has_more: false } };

// The "/shares" routes MUST precede "/library/pkg_own" (a substring): the stub
// returns the first fragment match, and method disambiguates POST/DELETE.
function routesFor(permissions: typeof OWNER_PERMISSIONS) {
  return {
    "GET /library/pkg_own/shares": SHARES,
    "POST /library/pkg_own/shares": {
      entity_id: "pkg_own",
      share_id: "shr_2",
      grantee_principal_id: "u_new",
      grantee_email: "new@example.com",
      grantee_display_name: "New",
      visibility_scope: "explicitly_shared",
      active_share_count: 2,
      row_version: 8,
    },
    "DELETE /library/pkg_own/shares": {
      entity_id: "pkg_own",
      share_id: "shr_1",
      revoked: true,
      visibility_scope: "private",
      active_share_count: 0,
      row_version: 8,
    },
    "GET /library/pkg_own": detailWith(permissions),
    "GET /rationale-families": FAMILIES_PAGE,
    "GET /library": { data: [{ ...ROW, permissions }], meta: { cursor: null, has_more: false } },
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
  await screen.findByRole("heading", { name: "Sharing" });
}

describe("Package Library explicit sharing (GAP-17)", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("shows the Sharing panel and current grantees when the server marks can_share", async () => {
    stubApi(routesFor(OWNER_PERMISSIONS));
    renderPage();
    await openDetail();

    expect(await screen.findByText("grantee@example.com")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Revoke" })).toBeInTheDocument();
  });

  it("dispatches a share POST with the grantee email + If-Match rv-N + Idempotency-Key", async () => {
    const fetchMock = stubApi(routesFor(OWNER_PERMISSIONS));
    renderPage();
    await openDetail();

    fireEvent.change(screen.getByLabelText(/share with/i), {
      target: { value: "new@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Share" }));

    await waitFor(() => {
      const call = fetchMock.mock.calls.find(
        ([url, init]) =>
          String(url).includes("/library/pkg_own/shares") &&
          (init?.method ?? "").toUpperCase() === "POST",
      );
      expect(call).toBeDefined();
      const headers = (call?.[1]?.headers ?? {}) as Record<string, string>;
      expect(headers["If-Match"]).toBe('"rv-7"');
      expect(headers["Idempotency-Key"]).toBeTruthy();
      expect(JSON.parse(String(call?.[1]?.body))).toEqual({ grantee_email: "new@example.com" });
    });
  });

  it("revokes a grant carrying the If-Match rv-N OCC token", async () => {
    const fetchMock = stubApi(routesFor(OWNER_PERMISSIONS));
    renderPage();
    await openDetail();
    await screen.findByText("grantee@example.com");

    fireEvent.click(screen.getByRole("button", { name: "Revoke" }));

    await waitFor(() => {
      const call = fetchMock.mock.calls.find(
        ([url, init]) =>
          String(url).includes("/library/pkg_own/shares/shr_1") &&
          (init?.method ?? "").toUpperCase() === "DELETE",
      );
      expect(call).toBeDefined();
      const headers = (call?.[1]?.headers ?? {}) as Record<string, string>;
      expect(headers["If-Match"]).toBe('"rv-7"');
      expect(headers["Idempotency-Key"]).toBeTruthy();
    });
  });

  it("hides the Sharing panel when the server denies can_share", async () => {
    stubApi(routesFor(VIEWER_PERMISSIONS));
    renderPage();
    await screen.findByText("Owned RSI");
    fireEvent.click(screen.getAllByRole("button", { name: "Detail" })[0]);
    await screen.findByText("Permissions (server-computed)");

    expect(screen.queryByRole("heading", { name: "Sharing" })).not.toBeInTheDocument();
  });
});
