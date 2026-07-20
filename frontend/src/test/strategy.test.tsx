import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { StrategyDetails } from "@/pages/StrategyDetails";
import { stubApi } from "./helpers/apiStub";

const MAINBOARD = {
  workspace_id: "ws_1",
  workspace_kind: "human_default",
  composition_hash: "hash_abc",
  row_version: 3,
  items: [
    {
      item_id: "item_1",
      item_kind: "strategy",
      work_object_root_id: "root_1",
      pinned_revision_id: "wor_1",
      position_index: 0,
      is_enabled: true,
      display_label_override: "Momentum A",
      row_version: 1,
    },
  ],
  ready_summary: { state: "not_ready", report_id: null },
  latest_result_summary: null,
};

const FAMILIES = {
  data: [{ entity_id: "fam_1", display_name: "Trend following" }],
  meta: { cursor: null, has_more: false },
};

const DRAFT = {
  draft_id: "draft_1",
  strategy_root_id: "root_1",
  payload: { data: { market_dataset_root_id: "mds_1" } },
  is_dirty: true,
  row_version: 2,
  last_saved_revision_id: "rev_1",
  updated_at: "2026-07-10T08:00:00+00:00",
};

// F-18: default to an empty draft index so existing no-identifier tests render
// the "My drafts" empty state (no text collisions); F-18 tests override this.
const DRAFTS_LIST: unknown[] = [];

const STRATEGY = {
  strategy_root_id: "root_1",
  display_name: "Momentum A",
  lifecycle_state: "validated",
  current_revision_id: "rev_1",
  current_row_version: 1,
  rationale_family_id: "fam_1",
  owner_principal_id: "user_1",
  deletion_state: "active",
};

const REVISIONS = [
  {
    strategy_revision_id: "rev_1",
    revision_number: 1,
    config_hash: "cfg_abc",
    validation_status: "valid",
    created_at: "2026-07-10T07:00:00+00:00",
  },
];

const REVISION_DETAIL = {
  strategy_revision_id: "rev_1",
  strategy_root_id: "root_1",
  revision_number: 1,
  config_hash: "cfg_abc",
  validation_status: "valid",
  lifecycle_snapshot: "validated",
  family_snapshot: "fam_1",
  payload: { data: { market_dataset_root_id: "mds_1" } },
  references: [
    {
      referenced_entity_type: "market_dataset",
      dependency_role: "data_source",
      referenced_root_id: "mds_1",
      referenced_revision_id: "mdr_1",
      referenced_content_hash: "sha256:aaa",
      position_in_graph: 0,
    },
  ],
  created_at: "2026-07-10T07:00:00+00:00",
};

const CREATE_RESULT = {
  draft_id: "draft_1",
  strategy_root_id: "root_1",
  display_name: "Momentum A",
  row_version: 0,
};

const PATCH_RESULT = {
  draft_id: "draft_1",
  strategy_root_id: "root_1",
  row_version: 3,
  is_dirty: true,
};

const VALIDATE_RESULT = {
  draft_id: "draft_1",
  valid: false,
  issues: [
    {
      field: "position_sizing",
      code: "SIZING_METHOD_NOT_EXCLUSIVE",
      message: "Exactly one sizing method must be enabled.",
    },
  ],
  warnings: [],
};

const SAVE_RESULT = {
  strategy_root_id: "root_1",
  strategy_revision_id: "rev_2",
  revision_number: 2,
  config_hash: "cfg_new",
  mirror_revision_id: "wor_9",
  pinned_items: [
    { item_id: "item_1", pinned_revision_id: "wor_9", composition_hash: "comp_2" },
  ],
  ready_state: "STALE",
  warnings: [],
  correlation_id: "corr_1",
};

const CLEAR_RESULT = { draft_id: "draft_1", row_version: 3, cleared: true };

// ORDERED routes: the specific draft-action fragments must precede the bare
// "POST /strategy-drafts" create prefix (the create path is a substring of
// every action URL); likewise the /revisions fragment precedes the root GET.
// R2-05b: the Advanced (raw payload) surfaces are admin-gated via GET /me —
// non-admin is the default; tests that exercise the raw editor opt into admin.
const ME_USER = {
  principal_id: "user_1",
  principal_type: "user",
  role: "user",
  is_admin: false,
  is_authenticated: true,
};
const ME_ADMIN = { ...ME_USER, role: "admin", is_admin: true };

function stubRoutes(overrides: Record<string, unknown> = {}) {
  return stubApi({
    "GET /me": ME_USER,
    "POST /strategy-drafts/draft_1/validate": VALIDATE_RESULT,
    "POST /strategy-drafts/draft_1/save": SAVE_RESULT,
    "POST /strategy-drafts/draft_1/clear": CLEAR_RESULT,
    "PATCH /strategy-drafts/draft_1": PATCH_RESULT,
    "GET /strategy-drafts/draft_1": DRAFT,
    "GET /strategy-drafts": DRAFTS_LIST,
    "POST /strategy-drafts": CREATE_RESULT,
    "GET /strategies/root_1/revisions": REVISIONS,
    "GET /strategies/root_1": STRATEGY,
    "GET /strategy-revisions/rev_1": REVISION_DETAIL,
    "GET /mainboards/default": MAINBOARD,
    "GET /rationale-families": FAMILIES,
    ...overrides,
  });
}

function renderPage(initialEntry = "/strategy") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/strategy" element={<StrategyDetails />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function headersOf(init: RequestInit | undefined): Record<string, string> {
  return (init?.headers ?? {}) as Record<string, string>;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("StrategyDetails", () => {
  it("creates a draft (no OCC token, fresh Idempotency-Key) and opens the editor", async () => {
    const fetchMock = stubRoutes();
    renderPage();

    // Discovery card lists the attached strategy from the default Mainboard.
    expect(await screen.findByText("Momentum A")).toBeTruthy();

    fireEvent.change(screen.getByLabelText(/Display name/), {
      target: { value: "Momentum A" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create draft" }));

    // The create response navigates to ?draft= and the panel's editor grid loads.
    expect(await screen.findByRole("heading", { name: /Data & Execution/ })).toBeTruthy();

    const call = fetchMock.mock.calls.find(
      ([url, init]) =>
        String(url).endsWith("/strategy-drafts") && init?.method === "POST",
    );
    expect(call).toBeTruthy();
    const body = JSON.parse(String(call?.[1]?.body)) as Record<string, unknown>;
    expect(body.display_name).toBe("Momentum A");
    expect("rationale_family_id" in body).toBe(false);
    expect("expected_draft_row_version" in body).toBe(false);
    expect(headersOf(call?.[1])["Idempotency-Key"]).toBeTruthy();
  });

  it("applies the payload with the rendered row_version as the BODY OCC token", async () => {
    // The Advanced raw-payload editor is admin-only (R2-05b) — the OCC contract
    // it exercises is unchanged.
    const fetchMock = stubRoutes({ "GET /me": ME_ADMIN });
    renderPage("/strategy?draft=draft_1");

    expect(await screen.findByRole("heading", { name: /Data & Execution/ })).toBeTruthy();
    // The admin gate renders the Advanced editor only after /me resolves.
    fireEvent.click(await screen.findByRole("button", { name: "Apply payload" }));

    expect(await screen.findByText(/Payload applied/)).toBeTruthy();
    const call = fetchMock.mock.calls.find(([, init]) => init?.method === "PATCH");
    expect(call).toBeTruthy();
    const body = JSON.parse(String(call?.[1]?.body)) as Record<string, unknown>;
    expect(body.expected_draft_row_version).toBe(2);
    // R2-05a: the server-owned Section-1 identity is overlaid onto the payload
    // so Validate never needs a hand-typed root id; the OCC token above and the
    // Idempotency-Key below are byte-identical to the pre-R2-05a contract.
    expect(body.payload).toEqual({
      ...DRAFT.payload,
      strategy_root_id: "root_1",
      display_name: "Momentum A",
      rationale_family_id: "fam_1",
    });
    expect(headersOf(call?.[1])["Idempotency-Key"]).toBeTruthy();
  });

  it("keeps invalid JSON client-side — nothing is sent", async () => {
    const fetchMock = stubRoutes({ "GET /me": ME_ADMIN });
    renderPage("/strategy?draft=draft_1");

    const textarea = await screen.findByLabelText(/StrategyConfig payload/);
    fireEvent.change(textarea, { target: { value: "not json {" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply payload" }));

    expect(await screen.findByText(/Not sent — invalid JSON/)).toBeTruthy();
    const patchCall = fetchMock.mock.calls.find(([, init]) => init?.method === "PATCH");
    expect(patchCall).toBeUndefined();
  });

  it("validate is a bare POST (no body, no Idempotency-Key) and renders issues verbatim", async () => {
    const fetchMock = stubRoutes();
    renderPage("/strategy?draft=draft_1");

    expect(await screen.findByRole("heading", { name: /Data & Execution/ })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Validate" }));

    expect(await screen.findByText("SIZING_METHOD_NOT_EXCLUSIVE")).toBeTruthy();
    expect(screen.getByText("Exactly one sizing method must be enabled.")).toBeTruthy();
    const call = fetchMock.mock.calls.find(
      ([url, init]) => String(url).includes("/validate") && init?.method === "POST",
    );
    expect(call).toBeTruthy();
    expect(call?.[1]?.body).toBeUndefined();
    expect(headersOf(call?.[1])["Idempotency-Key"]).toBeUndefined();
  });

  it("save sends the OCC body token + Idempotency-Key and renders the revision result", async () => {
    const fetchMock = stubRoutes();
    renderPage("/strategy?draft=draft_1");

    expect(await screen.findByRole("heading", { name: /Data & Execution/ })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Save Strategy Revision" }));

    expect(await screen.findByText("Revision saved")).toBeTruthy();
    expect(screen.getByText("rev_2")).toBeTruthy();
    expect(screen.getByText("STALE")).toBeTruthy();
    expect(screen.getByText("comp_2")).toBeTruthy();
    const call = fetchMock.mock.calls.find(
      ([url, init]) => String(url).includes("/save") && init?.method === "POST",
    );
    const body = JSON.parse(String(call?.[1]?.body)) as Record<string, unknown>;
    expect(body).toEqual({ expected_draft_row_version: 2 });
    expect(headersOf(call?.[1])["Idempotency-Key"]).toBeTruthy();
  });

  it("clear requires a two-step confirm before posting the OCC body token", async () => {
    const fetchMock = stubRoutes();
    renderPage("/strategy?draft=draft_1");

    expect(await screen.findByRole("heading", { name: /Data & Execution/ })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Clear draft…" }));
    // Nothing sent yet — the confirm step is explicit.
    expect(
      fetchMock.mock.calls.find(([url]) => String(url).includes("/clear")),
    ).toBeUndefined();

    fireEvent.click(screen.getByRole("button", { name: /Confirm clear/ }));
    expect(await screen.findByText(/Draft cleared/)).toBeTruthy();
    const call = fetchMock.mock.calls.find(
      ([url, init]) => String(url).includes("/clear") && init?.method === "POST",
    );
    const body = JSON.parse(String(call?.[1]?.body)) as Record<string, unknown>;
    expect(body).toEqual({ expected_draft_row_version: 2 });
  });

  it("renders the strategy header + revision history for ?strategy=", async () => {
    stubRoutes();
    renderPage("/strategy?strategy=root_1");

    expect(await screen.findByText("Momentum A")).toBeTruthy();
    expect(screen.getByText("Validated")).toBeTruthy();
    expect(await screen.findByText("cfg_abc")).toBeTruthy();
    expect(screen.getAllByText(/Open full page/).length).toBeGreaterThan(0);
  });

  it("renders the immutable revision deep-link with pinned references", async () => {
    stubRoutes();
    renderPage("/strategy?revision=rev_1");

    expect(await screen.findByText(/revision #1/)).toBeTruthy();
    expect(screen.getByText("market_dataset")).toBeTruthy();
    expect(screen.getByText("sha256:aaa")).toBeTruthy();
    // R2-05b: the raw payload dump is admin-only — a non-admin never sees raw
    // JSON keys on the revision summary.
    expect(screen.queryByText(/market_dataset_root_id/)).toBeNull();
    expect(screen.queryByText("Advanced (raw payload)")).toBeNull();
  });

  it("shows the revision raw payload dump only to an admin (R2-05b)", async () => {
    stubRoutes({ "GET /me": ME_ADMIN });
    renderPage("/strategy?revision=rev_1");

    expect(await screen.findByText(/revision #1/)).toBeTruthy();
    expect(await screen.findByText("Advanced (raw payload)")).toBeTruthy();
    expect(screen.getByText(/market_dataset_root_id/)).toBeTruthy();
  });

  // -------------------------------------------------------------------------
  // F-18 — durable/discoverable drafts (My drafts card)
  // -------------------------------------------------------------------------

  const NEVER_SAVED_DRAFT = {
    draft_id: "draft_never",
    strategy_root_id: "root_never",
    display_name: "Fresh idea",
    lifecycle_state: "draft",
    is_dirty: true,
    row_version: 0,
    last_saved_revision_id: null,
    has_revision: false,
    is_attached: false,
    owner_principal_id: "user_1",
    updated_at: "2026-07-14T09:00:00+00:00",
  };
  const SAVED_UNATTACHED_DRAFT = {
    draft_id: "draft_saved",
    strategy_root_id: "root_saved",
    display_name: "Saved not attached",
    lifecycle_state: "validated",
    is_dirty: false,
    row_version: 3,
    last_saved_revision_id: "rev_9",
    has_revision: true,
    is_attached: false,
    owner_principal_id: "user_1",
    updated_at: "2026-07-15T09:00:00+00:00",
  };
  const ATTACHED_DRAFT = {
    draft_id: "draft_attached",
    strategy_root_id: "root_attached",
    display_name: "Live on board",
    lifecycle_state: "validated",
    is_dirty: false,
    row_version: 4,
    last_saved_revision_id: "rev_live",
    has_revision: true,
    is_attached: true,
    owner_principal_id: "user_1",
    updated_at: "2026-07-16T09:00:00+00:00",
  };

  it("lists the actor's drafts and opens one without a retained ?draft= URL", async () => {
    // The listed row points at the fully-stubbed draft_1/root_1 so Open drives the
    // real editor path; the point under test is discovery, not a kept URL.
    const fetchMock = stubRoutes({
      "GET /strategy-drafts": [{ ...NEVER_SAVED_DRAFT, draft_id: "draft_1", strategy_root_id: "root_1" }],
    });
    renderPage();

    // Discoverable from a fresh page load — no create-time URL was kept.
    expect(await screen.findByText("Fresh idea")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Open" }));

    // Opening navigates to the editor, which fetches the draft by id.
    expect(await screen.findByRole("heading", { name: /Data & Execution/ })).toBeTruthy();
    expect(
      fetchMock.mock.calls.find(([url]) => String(url).includes("/strategy-drafts/draft_1")),
    ).toBeTruthy();
  });

  it("deletes an unattached draft via a two-step confirm (DELETE /work-objects + Idempotency-Key)", async () => {
    const fetchMock = stubRoutes({
      "GET /strategy-drafts": [SAVED_UNATTACHED_DRAFT],
      "DELETE /work-objects/root_saved": { root_id: "root_saved", deletion_state: "soft_deleted" },
    });
    renderPage();

    expect(await screen.findByText("Saved not attached")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    // Nothing sent until the explicit confirm step.
    expect(
      fetchMock.mock.calls.find(([url, init]) => String(url).includes("/work-objects/") && init?.method === "DELETE"),
    ).toBeUndefined();

    fireEvent.click(screen.getByRole("button", { name: /Confirm delete/ }));
    const call = await vi.waitFor(() => {
      const found = fetchMock.mock.calls.find(
        ([url, init]) => String(url).includes("/work-objects/root_saved") && init?.method === "DELETE",
      );
      if (!found) throw new Error("delete not sent yet");
      return found;
    });
    expect(headersOf(call?.[1])["Idempotency-Key"]).toBeTruthy();
    expect(call?.[1]?.body).toBeUndefined(); // DELETE carries no body / no OCC token
  });

  it("offers Attach-on-Mainboard for a saved-unattached draft and hides Delete for an attached one", async () => {
    stubRoutes({ "GET /strategy-drafts": [SAVED_UNATTACHED_DRAFT, ATTACHED_DRAFT] });
    renderPage();

    expect(await screen.findByText("Saved not attached")).toBeTruthy();
    // Saved + unattached → an attach link; attached → a view link, never Delete.
    expect(screen.getByRole("link", { name: /Attach Saved not attached on the Mainboard/ })).toBeTruthy();
    expect(screen.getByRole("link", { name: "View on Mainboard" })).toBeTruthy();
    // The attached draft exposes no destructive Delete affordance in this list.
    const deletes = screen.getAllByRole("button", { name: "Delete" });
    expect(deletes.length).toBe(1); // only the unattached row
  });
});
