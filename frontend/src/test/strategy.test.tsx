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
function stubRoutes(overrides: Record<string, unknown> = {}) {
  return stubApi({
    "POST /strategy-drafts/draft_1/validate": VALIDATE_RESULT,
    "POST /strategy-drafts/draft_1/save": SAVE_RESULT,
    "POST /strategy-drafts/draft_1/clear": CLEAR_RESULT,
    "PATCH /strategy-drafts/draft_1": PATCH_RESULT,
    "GET /strategy-drafts/draft_1": DRAFT,
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

    // The create response navigates to ?draft= and the editor loads.
    expect(await screen.findByText("Editor draft")).toBeTruthy();

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
    const fetchMock = stubRoutes();
    renderPage("/strategy?draft=draft_1");

    expect(await screen.findByText("Editor draft")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Apply payload" }));

    expect(await screen.findByText(/Payload applied/)).toBeTruthy();
    const call = fetchMock.mock.calls.find(([, init]) => init?.method === "PATCH");
    expect(call).toBeTruthy();
    const body = JSON.parse(String(call?.[1]?.body)) as Record<string, unknown>;
    expect(body.expected_draft_row_version).toBe(2);
    expect(body.payload).toEqual(DRAFT.payload);
    expect(headersOf(call?.[1])["Idempotency-Key"]).toBeTruthy();
  });

  it("keeps invalid JSON client-side — nothing is sent", async () => {
    const fetchMock = stubRoutes();
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

    expect(await screen.findByText("Editor draft")).toBeTruthy();
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

    expect(await screen.findByText("Editor draft")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Save revision" }));

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

    expect(await screen.findByText("Editor draft")).toBeTruthy();
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
    expect(screen.getAllByText("View").length).toBeGreaterThan(0);
  });

  it("renders the immutable revision deep-link with pinned references", async () => {
    stubRoutes();
    renderPage("/strategy?revision=rev_1");

    expect(await screen.findByText("Strategy revision #1")).toBeTruthy();
    expect(screen.getByText("market_dataset")).toBeTruthy();
    expect(screen.getByText("sha256:aaa")).toBeTruthy();
    expect(screen.getByText(/market_dataset_root_id/)).toBeTruthy();
  });
});
