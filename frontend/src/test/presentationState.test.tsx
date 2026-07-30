import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { Mainboard } from "@/pages/Mainboard";
import { stubApi } from "./helpers/apiStub";

// I-17-COV — TS-16 (doc 04 §15) / TL-18 (doc 05 §15) / AOS-16 (doc 03 §NN):
// "Expanding/collapsing a row creates no revision, no audit, no composition hash
// change and leaves the Ready report valid for the same fingerprint."
//
// `docs/audit/acceptance_id_map.md` §E listed all three as genuine gaps: the
// behaviour is presentational today but nothing pinned it, so a future refactor
// could quietly make the disclosure write. The single expand/collapse control for
// all three object kinds is the Mainboard row arrow (`pages/Mainboard.tsx`
// ItemRow) — the standalone /trading-signal and /trade-log pages have no
// disclosure at all — so one test covers the three IDs.
//
// The assertion is the strongest one available at this layer: after expanding AND
// collapsing every row kind, the client has issued no write request of any method
// (no POST/PATCH/PUT/DELETE), and the composition projection it holds — the
// composition_hash and each item's pinned revision — is byte-identical to the one
// it rendered before the toggles. A revision, an audit row or a Ready-report
// invalidation can only originate from such a request.

const MAINBOARD = {
  workspace_id: "ws_1",
  workspace_kind: "human_default",
  composition_hash: "hash_abc",
  row_version: 7,
  items: [
    {
      item_id: "item_strat",
      item_kind: "strategy",
      work_object_root_id: "root_strat",
      pinned_revision_id: "wor_1",
      position_index: 0,
      is_enabled: true,
      display_label_override: "Momentum A",
      row_version: 5,
    },
    {
      item_id: "item_signal",
      item_kind: "trading_signal",
      work_object_root_id: "root_signal",
      pinned_revision_id: "wor_2",
      position_index: 1,
      is_enabled: true,
      display_label_override: "Copy Signal A",
      row_version: 2,
    },
    {
      item_id: "item_tl",
      item_kind: "trade_log",
      work_object_root_id: "root_tl",
      pinned_revision_id: "wor_3",
      position_index: 2,
      is_enabled: true,
      display_label_override: "Binance Q1 Log",
      row_version: 3,
    },
  ],
  ready_summary: { state: "ready", report_id: "rr_1" },
  latest_result_summary: null,
};

const ME_USER = { principal_id: "user_1", principal_type: "human", role: "user" };

const ALLOC_DRAFT_OFF = {
  plan_id: null,
  row_version: 0,
  draft: { enabled: false, entries: [] },
};

const REVISION_VIEW = {
  revision_id: "wor_2",
  revision_no: 1,
  payload: { kind: "trading_signal", identity: { display_name: "Copy Signal A" } },
  source_provenance: null,
  available_time: "2024-05-01T10:03:00Z",
  content_hash: "c".repeat(64),
};

const SIGNAL_DETAIL = {
  root_id: "root_signal",
  object_kind: "trading_signal",
  owner_principal_id: "user_1",
  lifecycle_state: "active",
  deletion_state: "active",
  current_revision_id: "wor_2",
  row_version: 2,
  current_revision: REVISION_VIEW,
};

const TRADE_LOG_DETAIL = {
  ...SIGNAL_DETAIL,
  root_id: "root_tl",
  object_kind: "trade_log",
  current_revision_id: "wor_3",
  row_version: 3,
  current_revision: {
    ...REVISION_VIEW,
    revision_id: "wor_3",
    payload: { kind: "trade_log", identity: { display_name: "Binance Q1 Log" } },
    available_time: null,
  },
};

const STRATEGY_DETAIL = {
  strategy_root_id: "root_strat",
  display_name: "Momentum A",
  lifecycle_state: "validated",
  current_revision_id: "wor_1",
  current_row_version: 3,
  rationale_family_id: null,
  owner_principal_id: "user_1",
  deletion_state: "active",
};

const STRATEGY_REVISION = {
  strategy_revision_id: "wor_1",
  strategy_root_id: "root_strat",
  revision_number: 3,
  config_hash: "cfg_xyz",
  validation_status: "valid",
  lifecycle_snapshot: "validated",
  family_snapshot: null,
  payload: {},
  references: [],
  created_at: "2026-07-01T00:00:00Z",
};

function stubRoutes() {
  return stubApi({
    "GET /me": ME_USER,
    "GET /mainboards/default": MAINBOARD,
    "GET /mainboard-compositions/ws_1/portfolio-allocation-draft": ALLOC_DRAFT_OFF,
    "GET /trading-signals/root_signal": SIGNAL_DETAIL,
    "GET /trade-logs/root_tl": TRADE_LOG_DETAIL,
    "GET /strategies/root_strat/revisions": [],
    "GET /strategies/root_strat": STRATEGY_DETAIL,
    "GET /strategy-revisions/wor_1": STRATEGY_REVISION,
    "GET /instruments": { data: [], meta: { cursor: null, has_more: false } },
  });
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="/" element={<Mainboard />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function writeRequests(fetchMock: ReturnType<typeof stubApi>): string[] {
  return fetchMock.mock.calls
    .map(([input, init]) => [String(input), String((init as RequestInit | undefined)?.method ?? "GET").toUpperCase()] as const)
    .filter(([, method]) => method !== "GET")
    .map(([url, method]) => `${method} ${url}`);
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Mainboard row presentation state (TS-16 / TL-18 / AOS-16)", () => {
  it("expands and collapses every row kind without issuing a single write request", async () => {
    const fetchMock = stubRoutes();
    renderPage();
    expect(await screen.findByText("Momentum A")).toBeTruthy();

    const labels = ["Momentum A", "Copy Signal A", "Binance Q1 Log"];
    for (const label of labels) {
      fireEvent.click(await screen.findByLabelText(`Expand ${label}`));
      // The disclosure really opened — the row is showing its editor section.
      expect(await screen.findByLabelText(new RegExp(`editor for ${label}$`))).toBeTruthy();
      fireEvent.click(await screen.findByLabelText(`Collapse ${label}`));
      expect(await screen.findByLabelText(`Expand ${label}`)).toBeTruthy();
    }

    expect(writeRequests(fetchMock)).toEqual([]);
  });

  it("leaves the composition hash and every pinned revision untouched across the toggles", async () => {
    const fetchMock = stubRoutes();
    renderPage();
    // The composition hash the page renders is the server projection's, verbatim.
    expect(await screen.findByText("hash_abc")).toBeTruthy();

    fireEvent.click(await screen.findByLabelText("Expand Copy Signal A"));
    expect(await screen.findByLabelText(/editor for Copy Signal A$/)).toBeTruthy();
    fireEvent.click(await screen.findByLabelText("Collapse Copy Signal A"));

    // Same hash, and no PATCH/POST could have re-pinned an item: the only
    // mainboard traffic is the read.
    expect(screen.getByText("hash_abc")).toBeTruthy();
    expect(writeRequests(fetchMock)).toEqual([]);
    const mainboardWrites = fetchMock.mock.calls.filter(
      ([input, init]) =>
        String(input).includes("/mainboard") &&
        String((init as RequestInit | undefined)?.method ?? "GET").toUpperCase() !== "GET",
    );
    expect(mainboardWrites).toEqual([]);
    // The Ready summary the row group renders still reflects the same report.
    expect(screen.getByText(/Backtest Ready: Ready/)).toBeTruthy();
  });
});
