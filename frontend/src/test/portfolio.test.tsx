import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { Portfolio } from "@/pages/Portfolio";
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
      pinned_revision_id: "rev_1",
      position_index: 0,
      is_enabled: true,
      display_label_override: "Momentum A",
      row_version: 1,
    },
    {
      item_id: "item_2",
      item_kind: "trade_log",
      work_object_root_id: "root_2",
      pinned_revision_id: null,
      position_index: 1,
      is_enabled: false,
      display_label_override: null,
      row_version: 1,
    },
  ],
  ready_summary: { state: "not_ready", report_id: null },
  latest_result_summary: null,
};

// No plan row yet — the default independent draft; row_version 0 IS the valid
// PUT creation token (doc 13 §7.2).
const DRAFT_EMPTY = {
  composition_id: "ws_1",
  plan_id: null,
  current_revision_id: null,
  row_version: 0,
  draft: {
    enabled: false,
    initial_capital: null,
    compounding_mode: null,
    reserve_cash_percent: null,
    entries: [],
  },
  candidate_items: [
    {
      composition_item_id: "item_1",
      item_type: "strategy",
      work_object_root_id: "root_1",
      is_enabled: true,
      position_index: 0,
      display_label_override: "Momentum A",
    },
  ],
};

const DRAFT_SAVED = {
  composition_id: "ws_1",
  plan_id: "plan_1",
  current_revision_id: null,
  row_version: 1,
  draft: {
    enabled: true,
    initial_capital: { amount: "10000", currency: "USDT" },
    compounding_mode: "COMPOUND_PORTFOLIO_EQUITY",
    reserve_cash_percent: "10",
    draft_fingerprint: "fp_1",
    entries: [
      {
        entry_id: "pae_1",
        composition_item_id: "item_1",
        item_type: "strategy",
        active: true,
        equity_share_percent: "90",
        position_index: 0,
      },
    ],
  },
  candidate_items: [],
};

const SAVE_RESULT = {
  composition_id: "ws_1",
  plan_id: "plan_1",
  enabled: true,
  row_version: 1,
  draft_fingerprint: "fp_1",
  inline_issues: [
    {
      code: "TOTAL_ALLOCATION_UNDER_100",
      severity: "warning",
      message: "Active shares total 90%; 10% of available capital stays unallocated.",
      field: "entries",
      composition_item_id: null,
    },
  ],
  derived: {
    currency: "USDT",
    portfolio_initial_capital: "10000.00",
    reserved_cash: "1000.00",
    capital_available: "9000.00",
    total_allocated: "8100.00",
    unallocated: "900.00",
    active_share_total: "90",
    sleeves: [
      {
        composition_item_id: "item_1",
        equity_share_percent: "90",
        initial_sleeve_capital: "8100.00",
      },
    ],
  },
  readiness_invalidated: true,
};

const VALIDATION_REPORT = {
  validation_report_id: "parpt_1",
  composition_id: "ws_1",
  enabled: true,
  state: "READY_WITH_WARNINGS",
  valid: true,
  issues: [
    {
      code: "TOTAL_ALLOCATION_UNDER_100",
      severity: "warning",
      message: "Active shares total 90%; 10% of available capital stays unallocated.",
      field: "entries",
      composition_item_id: null,
    },
  ],
  warnings: [],
  derived: SAVE_RESULT.derived,
  config_hash: "cfg_1",
};

const SYNC_PREVIEW = {
  composition_id: "ws_1",
  retained: [
    {
      entry_id: "pae_1",
      composition_item_id: "item_1",
      item_type: "strategy",
      active: true,
      equity_share_percent: "90",
      position_index: 0,
    },
  ],
  missing: [
    {
      entry_id: "pae_9",
      composition_item_id: "item_gone",
      item_type: "strategy",
      active: true,
      equity_share_percent: "10",
      position_index: 1,
    },
  ],
  new_candidates: [
    {
      composition_item_id: "item_2",
      item_type: "trade_log",
      work_object_root_id: "root_2",
      is_enabled: false,
      position_index: 1,
      display_label_override: null,
    },
  ],
  requires_confirmation: true,
};

const REVISION_RESULT = {
  composition_id: "ws_1",
  plan_id: "plan_1",
  plan_revision_id: "parev_1",
  revision_no: 1,
  config_hash: "cfg_1",
  current_revision_id: "parev_1",
  row_version: 2,
  derived: SAVE_RESULT.derived,
};

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/portfolio"]}>
        <Routes>
          <Route path="/portfolio" element={<Portfolio />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function callFor(
  fetchMock: ReturnType<typeof stubApi>,
  method: string,
  fragment: string,
): RequestInit {
  const call = fetchMock.mock.calls.find(
    ([url, init]) =>
      String(url).includes(fragment) && ((init?.method ?? "GET") as string) === method,
  );
  expect(call).toBeTruthy();
  return call?.[1] as RequestInit;
}

describe("Portfolio / Equity Allocation page", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders the composition, the independent empty draft and the candidate picker", async () => {
    stubApi({
      // Action/draft routes BEFORE any list-ish prefix (apiStub ordered match).
      "GET /mainboard-compositions/ws_1/portfolio-allocation-draft": DRAFT_EMPTY,
      "GET /mainboards/default": MAINBOARD,
    });
    renderPage();

    expect(await screen.findByText("ws_1")).toBeInTheDocument();
    // The draft loads as a second wave once the composition id resolves.
    expect(await screen.findByText("independent (off)")).toBeInTheDocument();
    expect(screen.getByText(/no plan row yet/)).toBeInTheDocument();
    const picker = screen.getByText("Unrepresented composition items").closest("div");
    expect(within(picker as HTMLElement).getByText("item_1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add" })).toBeInTheDocument();
  });

  it("saves the draft with the body-form OCC token and a fresh Idempotency-Key", async () => {
    let saved = false;
    const fetchMock = stubApi({
      "PUT /mainboard-compositions/ws_1/portfolio-allocation-draft": () => {
        saved = true;
        return SAVE_RESULT;
      },
      "GET /mainboard-compositions/ws_1/portfolio-allocation-draft": () =>
        saved ? DRAFT_SAVED : DRAFT_EMPTY,
      "GET /mainboards/default": MAINBOARD,
    });
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Add" }));
    fireEvent.click(screen.getByLabelText(/Enable shared equity allocation/));
    fireEvent.change(screen.getByLabelText("Initial capital"), { target: { value: "10000" } });
    fireEvent.change(screen.getByLabelText("Currency"), { target: { value: "USDT" } });
    fireEvent.change(screen.getByLabelText("Compounding mode"), {
      target: { value: "COMPOUND_PORTFOLIO_EQUITY" },
    });
    fireEvent.change(screen.getByLabelText("Reserve cash %"), { target: { value: "10" } });
    fireEvent.change(screen.getByLabelText("share item_1"), { target: { value: "90" } });
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));

    // The PUT return renders inline issues + server-derived amounts verbatim.
    expect(await screen.findByText("Draft saved")).toBeInTheDocument();
    expect(screen.getByText("TOTAL_ALLOCATION_UNDER_100")).toBeInTheDocument();
    expect(screen.getByText("9000.00")).toBeInTheDocument();
    expect(screen.getAllByText("8100.00")).toHaveLength(2);

    const init = callFor(fetchMock, "PUT", "/portfolio-allocation-draft");
    const body = JSON.parse(String(init.body));
    // OCC travels BODY-form (0 = creation token); item_type is never sent —
    // the server derives it from the composition item (doc 13 §8.2).
    expect(body).toEqual({
      expected_row_version: 0,
      enabled: true,
      initial_capital: { amount: "10000", currency: "USDT" },
      compounding_mode: "COMPOUND_PORTFOLIO_EQUITY",
      reserve_cash_percent: "10",
      entries: [{ composition_item_id: "item_1", active: true, equity_share_percent: "90" }],
    });
    const headers = init.headers as Record<string, string>;
    expect(headers["Idempotency-Key"]).toBeTruthy();

    // The invalidation refetch re-seeds the editor from the new server head
    // (the DRAFT_SAVED head is enabled → the editor badge flips).
    expect(await screen.findByText("shared allocation")).toBeInTheDocument();
  });

  it("surfaces a stale-draft conflict verbatim", async () => {
    stubApi({
      "PUT /mainboard-compositions/ws_1/portfolio-allocation-draft": () => {
        throw new Error(
          "ALLOCATION_DRAFT_CONFLICT: This allocation draft changed elsewhere. Refresh, compare, then reapply your update.",
        );
      },
      "GET /mainboard-compositions/ws_1/portfolio-allocation-draft": DRAFT_SAVED,
      "GET /mainboards/default": MAINBOARD,
    });
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Save draft" }));

    expect(
      await screen.findByText(
        "ALLOCATION_DRAFT_CONFLICT: This allocation draft changed elsewhere. Refresh, compare, then reapply your update.",
      ),
    ).toBeInTheDocument();
  });

  it("validates the saved draft and renders the immutable report verbatim", async () => {
    const fetchMock = stubApi({
      "POST /portfolio-allocation/validate": VALIDATION_REPORT,
      "GET /mainboard-compositions/ws_1/portfolio-allocation-draft": DRAFT_SAVED,
      "GET /mainboards/default": MAINBOARD,
    });
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Validate saved draft" }));

    expect(await screen.findByText("Ready with warnings")).toBeInTheDocument();
    expect(screen.getByText("parpt_1")).toBeInTheDocument();
    expect(screen.getByText("cfg_1")).toBeInTheDocument();
    expect(screen.getByText("TOTAL_ALLOCATION_UNDER_100")).toBeInTheDocument();

    // The route reads NO body and NO headers — nothing idempotency-shaped travels.
    const init = callFor(fetchMock, "POST", "/portfolio-allocation/validate");
    expect(init.body).toBeUndefined();
    const headers = init.headers as Record<string, string>;
    expect(headers["Idempotency-Key"]).toBeUndefined();
  });

  it("previews sync-from-mainboard as a pure read with a destructive-removal hint", async () => {
    const fetchMock = stubApi({
      "POST /portfolio-allocation/sync": SYNC_PREVIEW,
      "GET /mainboard-compositions/ws_1/portfolio-allocation-draft": DRAFT_SAVED,
      "GET /mainboards/default": MAINBOARD,
    });
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Preview sync" }));

    expect(await screen.findByText("Retained (1)")).toBeInTheDocument();
    expect(screen.getByText("Missing from composition (1)")).toBeInTheDocument();
    expect(screen.getByText("item_gone")).toBeInTheDocument();
    expect(screen.getByText("New candidates (1)")).toBeInTheDocument();
    expect(screen.getByText(/removing them is destructive/)).toBeInTheDocument();

    // PURE READ preview: no Idempotency-Key (the query layer writes nothing).
    const init = callFor(fetchMock, "POST", "/portfolio-allocation/sync");
    const headers = init.headers as Record<string, string>;
    expect(headers["Idempotency-Key"]).toBeUndefined();
  });

  it("creates a plan revision with the OCC token and renders the freeze result", async () => {
    const fetchMock = stubApi({
      "POST /portfolio-allocation/revisions": REVISION_RESULT,
      "GET /mainboard-compositions/ws_1/portfolio-allocation-draft": DRAFT_SAVED,
      "GET /mainboards/default": MAINBOARD,
    });
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Create plan revision" }));

    expect(await screen.findByText("parev_1")).toBeInTheDocument();
    expect(screen.getByText("(no. 1)")).toBeInTheDocument();

    const init = callFor(fetchMock, "POST", "/portfolio-allocation/revisions");
    expect(JSON.parse(String(init.body))).toEqual({ expected_row_version: 1 });
    const headers = init.headers as Record<string, string>;
    expect(headers["Idempotency-Key"]).toBeTruthy();
  });

  it("surfaces a blocker denial on the revision freeze verbatim", async () => {
    stubApi({
      "POST /portfolio-allocation/revisions": () => {
        throw new Error(
          "ALLOCATION_HAS_BLOCKERS: The allocation configuration has blocking issues and cannot become a plan revision.",
        );
      },
      "GET /mainboard-compositions/ws_1/portfolio-allocation-draft": DRAFT_SAVED,
      "GET /mainboards/default": MAINBOARD,
    });
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Create plan revision" }));

    expect(
      await screen.findByText(
        "ALLOCATION_HAS_BLOCKERS: The allocation configuration has blocking issues and cannot become a plan revision.",
      ),
    ).toBeInTheDocument();
  });
});
