import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { Mainboard } from "@/pages/Mainboard";
import { stubApi } from "./helpers/apiStub";

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
  ],
  ready_summary: { state: "not_ready", report_id: null },
  latest_result_summary: null,
};

const PATCH_RESULT = {
  item_id: "item_strat",
  item_kind: "strategy",
  work_object_root_id: "root_strat",
  pinned_revision_id: "wor_2",
  position_index: 0,
  is_enabled: true,
  display_label_override: "Momentum A",
  row_version: 6,
  composition_hash: "hash_def",
};

const DELETE_RESULT = { root_id: "root_strat", deletion_state: "soft_deleted" };
const SNAPSHOT_RESULT = { snapshot_id: "snap_1", composition_hash: "hash_abc", item_count: 1 };
const EXTERNAL_DRAFT = { draft_id: "wodraft_1", kind: "trading_signal", unsaved: true };

// UI-15: a RUN-runnable composition + the durable succeeded run it admits + the
// immutable Result the run produced. RUN admits inline and this Result renders
// under the Mainboard via the shared RunProgress → ResultDetail path.
const READY_MAINBOARD = {
  ...MAINBOARD,
  ready_summary: { state: "ready", report_id: "rr_1" },
};

const ADMISSION = {
  run_id: "btrun_1",
  state: "queued",
  manifest_hash: "mh_1",
  composition_fingerprint: "fp_1",
  ready_report_id: "rr_1",
  retry_of_run_id: null,
  warning_count: 2,
  job_id: "job_1",
};

const SUCCEEDED_RUN = {
  run_id: "btrun_1",
  composition_id: "ws_1",
  state: "succeeded",
  manifest_hash: "mh_1",
  composition_fingerprint: "fp_1",
  composition_snapshot_id: null,
  ready_report_id: "rr_1",
  retry_of_run_id: null,
  result_id: "res_1",
  failure_code: null,
  failure_message: null,
  job_id: "job_1",
  created_at: "2026-07-06T05:30:00+00:00",
  started_at: "2026-07-06T05:30:05+00:00",
  finished_at: "2026-07-06T05:31:00+00:00",
};

const RESULT_DETAIL = {
  result_id: "res_1",
  run_id: "btrun_1",
  composition_id: "ws_1",
  composition_fingerprint: "fp_1",
  manifest_hash: "mh_1",
  engine_version: "backtest-engine-v2",
  summary: {
    symbol: "BTCUSD",
    timeframe: "15m",
    period_start: "2020-01-01",
    period_end: "2025-01-01",
    total_trades: 418,
    headline: "Net profit +84.20%",
  },
  metrics: [
    {
      key: "net_profit",
      label: "Net Profit",
      unit: "percent",
      value_format: "signed_percent",
      value: "84.2",
      availability: "computed",
      formula_version: "v1",
    },
  ],
  manifest: {
    manifest_hash: "mh_1",
    execution_key: "exec_1",
    engine_version: "backtest-engine-v2",
    pinned_item_count: 1,
  },
  manifest_excerpt: {
    result_id: "res_1",
    composition_snapshot_id: "snap_1",
    strategy_revision_refs: [],
    external_work_refs: [],
    package_revision_refs: [],
    market_data_revision: null,
    research_data_revision_refs: [],
    portfolio_allocation_plan_revision_id: null,
    execution_context: {
      execution_key: "exec_1",
      composition_fingerprint: "fp_1",
      capital_execution: null,
    },
    engine_contract_version: "backtest-engine-v2",
    artifact_context: null,
    completed_at_utc: "2025-01-01T00:00:00+00:00",
    artifact_availability: { counts: { trades: 418 }, any_available: true },
  },
  artifact_counts: { trades: 418 },
};

const RESULT_METRICS_VIEW = {
  result_id: "res_1",
  profile: {
    profile_id: "system_default",
    scope: "system_default",
    is_personal: false,
    is_locked: false,
    registry_version: "v1",
  },
  metrics: RESULT_DETAIL.metrics,
};

// F-15: the generic create/revise/attach work-object routes are no longer wired
// to any user-facing control (the raw-JSON "Advanced" card was removed), so the
// stub set no longer needs them.
function stubRoutes(overrides: Record<string, unknown> = {}) {
  return stubApi({
    "POST /mainboards/ws_1/snapshots": SNAPSHOT_RESULT,
    "POST /external-work-object-drafts/trading_signal": EXTERNAL_DRAFT,
    "PATCH /mainboard-items/item_strat": PATCH_RESULT,
    "DELETE /work-objects/root_strat": DELETE_RESULT,
    "GET /mainboards/default": MAINBOARD,
    ...overrides,
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

function headersOf(init: RequestInit | undefined): Record<string, string> {
  return (init?.headers ?? {}) as Record<string, string>;
}
function bodyOf(init: RequestInit | undefined): Record<string, unknown> {
  return JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
}
async function expandRow() {
  fireEvent.click(await screen.findByLabelText("Expand Momentum A"));
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Mainboard", () => {
  it("renders the composition projection and ready status line", async () => {
    stubRoutes();
    renderPage();
    expect(await screen.findByText("Momentum A")).toBeTruthy();
    expect(screen.getByText("Backtest Ready: Not Ready")).toBeTruthy();
    expect(screen.getByText("hash_abc")).toBeTruthy();
    expect(screen.getByText(/No succeeded Backtest Result is available/)).toBeTruthy();
    expect(screen.getAllByText("Enabled").length).toBeGreaterThan(0);
  });

  it("shows the empty-state text when the workspace has no items", async () => {
    stubRoutes({ "GET /mainboards/default": { ...MAINBOARD, items: [] } });
    renderPage();
    expect(await screen.findByText("Your Mainboard is empty.")).toBeTruthy();
    expect(screen.getByText(/Add a Strategy, Trading Signal, or Trade Log/)).toBeTruthy();
  });

  it("shows 'not checked yet' for a never-checked composition (not a false Not Ready)", async () => {
    stubRoutes({
      "GET /mainboards/default": {
        ...MAINBOARD,
        ready_summary: { state: "not_checked", report_id: null },
      },
    });
    renderPage();
    expect(await screen.findByText("Backtest Ready: Not checked yet")).toBeTruthy();
  });

  it("locks RUN until a current Ready Check passes (not_ready → disabled button, not a link)", async () => {
    // MAINBOARD ships not_ready, so RUN must be a genuinely disabled control —
    // out of the tab order and unreachable by pointer OR keyboard (F-16).
    stubRoutes();
    renderPage();
    const run = await screen.findByRole("button", { name: "RUN" });
    expect(run).toBeDisabled();
    // No navigable RUN link exists in the locked state.
    expect(screen.queryByRole("link", { name: "RUN" })).toBeNull();
    expect(
      screen.getByText("RUN is available only after a current Backtest Ready Check passes."),
    ).toBeTruthy();
  });

  it("unlocks RUN as an inline-admission button once the composition is ready (UI-15)", async () => {
    stubRoutes({
      "GET /mainboards/default": {
        ...MAINBOARD,
        ready_summary: { state: "ready", report_id: "rr_1" },
      },
    });
    renderPage();
    // UI-15: RUN no longer navigates to a separate page — it admits the run in
    // place, so the unlocked control is an enabled button, never a link.
    const run = await screen.findByRole("button", { name: "RUN" });
    expect(run).not.toBeDisabled();
    expect(screen.queryByRole("link", { name: "RUN" })).toBeNull();
  });

  it("unlocks RUN when the composition is ready with warnings (warnings never block)", async () => {
    stubRoutes({
      "GET /mainboards/default": {
        ...MAINBOARD,
        ready_summary: { state: "ready_with_warnings", report_id: "rr_2" },
      },
    });
    renderPage();
    const run = await screen.findByRole("button", { name: "RUN" });
    expect(run).not.toBeDisabled();
    expect(screen.queryByRole("link", { name: "RUN" })).toBeNull();
  });

  it("renders the latest succeeded result with its summary line and deep-link", async () => {
    stubRoutes({
      "GET /mainboards/default": {
        ...MAINBOARD,
        latest_result_summary: {
          result_id: "btr_1",
          manifest_hash: "mh_1",
          composition_fingerprint: "hash_abc",
          engine_version: "backtest-engine-v2",
          created_at: "2026-07-01T12:00:00Z",
          snapshot_differs: false,
          summary: {
            symbol: "BTCUSD",
            timeframe: "1h",
            period_start: "2026-01-01",
            period_end: "2026-02-01",
            total_trades: 7,
            headline: {
              net_profit_pct: 84.2,
              max_drawdown_pct: -18.1,
              romad: 4.65,
              win_rate: 54,
              profit_factor: 1.72,
            },
          },
        },
      },
    });
    renderPage();
    const link = await screen.findByText("btr_1");
    expect(link.getAttribute("href")).toBe("/backtest/run?result=btr_1");
    // Symbol / timeframe / trade count / date preserved (F-17).
    expect(
      screen.getByText("BTCUSD · 1h · 7 trade(s) · 2026-01-01 → 2026-02-01"),
    ).toBeTruthy();
    // F-17: the five required headline metrics render inline, formatted by the
    // same presentation formatter the Result detail uses (values must match).
    const metrics = screen.getByRole("group", { name: "Headline metrics" });
    for (const [label, value] of [
      ["Net Profit", "+84.20%"],
      ["Max Drawdown", "-18.10%"],
      ["ROMAD", "4.65"],
      ["Win Rate", "54.00%"],
      ["Profit Factor", "1.72"],
    ] as const) {
      expect(within(metrics).getByText(label)).toBeTruthy();
      expect(within(metrics).getByText(value)).toBeTruthy();
    }
    // Matching fingerprint -> the result is current; no snapshot-differs badge.
    expect(screen.queryByText(/Result snapshot differs/)).toBeNull();
  });

  it("renders an explicit N/A for a headline metric the projection omits (L4)", async () => {
    stubRoutes({
      "GET /mainboards/default": {
        ...MAINBOARD,
        latest_result_summary: {
          result_id: "btr_3",
          manifest_hash: "mh_3",
          composition_fingerprint: "hash_abc",
          engine_version: "backtest-engine-v2",
          created_at: "2026-07-03T12:00:00Z",
          snapshot_differs: false,
          summary: {
            symbol: "ETHUSD",
            timeframe: "4h",
            period_start: null,
            period_end: null,
            total_trades: 4,
            // The engine omitted the three ratio metrics; they must show an
            // explicit N/A, never a fabricated 0 (L4).
            headline: { net_profit_pct: 12.5, max_drawdown_pct: -5 },
          },
        },
      },
    });
    renderPage();
    const metrics = await screen.findByRole("group", { name: "Headline metrics" });
    expect(within(metrics).getByText("+12.50%")).toBeTruthy();
    expect(within(metrics).getByText("-5.00%")).toBeTruthy();
    // ROMAD, Win Rate, Profit Factor were omitted -> three explicit N/A cells.
    expect(within(metrics).getAllByText("N/A").length).toBe(3);
  });

  it("labels the latest result when its snapshot differs from the current composition", async () => {
    stubRoutes({
      "GET /mainboards/default": {
        ...MAINBOARD,
        latest_result_summary: {
          result_id: "btr_2",
          manifest_hash: "mh_2",
          composition_fingerprint: "stale_hash",
          engine_version: "backtest-engine-v2",
          created_at: "2026-07-02T12:00:00Z",
          snapshot_differs: true,
          summary: null,
        },
      },
    });
    renderPage();
    expect(await screen.findByText("btr_2")).toBeTruthy();
    expect(
      screen.getByText("Result snapshot differs from current Mainboard composition"),
    ).toBeTruthy();
    // No summary row -> honest fallback, never a fabricated 0-trade line (L4).
    expect(screen.getByText("Summary not available for this result.")).toBeTruthy();
  });

  it("expands a row into the real inline Strategy Details editor (UI-02)", async () => {
    const REVISION_DETAIL = {
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
    stubRoutes({
      "GET /strategy-revisions/wor_1": REVISION_DETAIL,
      "GET /strategies/root_strat/revisions": [],
      "GET /strategies/root_strat": STRATEGY_DETAIL,
    });
    renderPage();
    await expandRow();

    // The expand reveals the real 3-column Strategy Details editor inline —
    // not just a raw technical panel or a deep-link-only stub — keyed by the
    // work-object root id (never the label, §14 rule 3).
    expect(await screen.findByRole("heading", { name: /Strategy Context/ })).toBeTruthy();
    expect(screen.getByText(/revision #3/)).toBeTruthy();
    // A back-compat deep-link into the standalone /strategy page remains reachable.
    const openLink = screen.getByRole("link", { name: "Open full page ↗" });
    expect(openLink.getAttribute("href")).toBe("/strategy?strategy=root_strat");
    // The Mainboard-owned composition controls remain reachable in the same row.
    expect(screen.getByLabelText("Composition controls for Momentum A")).toBeTruthy();
  });

  it("offers the prototype Add menu with Strategy / Package / Portfolio actions (UI-01)", async () => {
    stubRoutes();
    renderPage();
    await screen.findByText("Momentum A");
    fireEvent.click(screen.getByRole("button", { name: "+ Add" }));
    // F-15: Add Strategy is an inline create+attach action (a button), not a
    // deep-link — the new object appears as a Mainboard row without navigation.
    expect(screen.getByRole("button", { name: "Add Strategy" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Add Package" }).getAttribute("href")).toBe(
      "/packages/create",
    );
    expect(
      screen.getByRole("link", { name: "Portfolio / Equity Allocation →" }).getAttribute("href"),
    ).toBe("/portfolio");
    // The nested Add Outsource Signal submenu reveals its two options (UI-03).
    const submenuToggle = screen.getByRole("button", { name: "Add Outsource Signal" });
    expect(submenuToggle.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(submenuToggle);
    expect(submenuToggle.getAttribute("aria-expanded")).toBe("true");
    expect(screen.getByRole("menuitem", { name: "Trading Signal" })).toBeTruthy();
    expect(screen.getByRole("menuitem", { name: "Trade Log" })).toBeTruthy();
  });

  it("has no manual revision-id (wor_…) pin input — revision selection is user-facing (F-15)", async () => {
    stubRoutes();
    renderPage();
    await expandRow();
    // F-15: the raw "Revision id" text input + "Use This Revision" button are gone.
    expect(screen.queryByLabelText("Revision id for Momentum A")).toBeNull();
    expect(screen.queryByText("Use This Revision")).toBeNull();
    // The row instead points the user at the type-specific editor (no manual id).
    expect(
      screen.getByText(/saving re-pins this item automatically/),
    ).toBeTruthy();
  });

  it("toggles enable/disable via set_enabled with OCC + a fresh Idempotency-Key", async () => {
    const fetchMock = stubRoutes();
    renderPage();
    await expandRow();
    fireEvent.click(screen.getByText("Disable"));
    await screen.findByText("Momentum A");
    const call = fetchMock.mock.calls.find(
      (c) => String(c[0]).includes("/mainboard-items/item_strat"),
    );
    const body = bodyOf(call?.[1]);
    expect(body.intent).toBe("set_enabled");
    expect(body.is_enabled).toBe(false);
    expect(body.expected_row_version).toBe(5);
    // The PATCH OCC + Idempotency contract is unchanged by F-15.
    expect(headersOf(call?.[1])["Idempotency-Key"]).toBeTruthy();
  });

  it("reorders an item via move down (position_index + 1)", async () => {
    const fetchMock = stubRoutes();
    renderPage();
    await expandRow();
    fireEvent.click(screen.getByText("Move down"));
    await screen.findByText("Momentum A");
    const call = fetchMock.mock.calls.find(
      (c) => String(c[0]).includes("/mainboard-items/item_strat"),
    );
    const body = bodyOf(call?.[1]);
    expect(body.intent).toBe("reorder");
    expect(body.position_index).toBe(1);
  });

  it("soft-deletes a work object behind a two-step confirmation", async () => {
    const fetchMock = stubRoutes();
    renderPage();
    await expandRow();
    fireEvent.click(screen.getByLabelText("Delete Momentum A"));
    const dialog = screen.getByRole("alertdialog");
    expect(within(dialog).getByText(/Only an Admin can restore/)).toBeTruthy();
    fireEvent.click(within(dialog).getByText("Move to Trash"));
    await screen.findByText("Momentum A");
    const call = fetchMock.mock.calls.find(
      (c) => String(c[0]).includes("/work-objects/root_strat") && (c[1]?.method ?? "") === "DELETE",
    );
    expect(call).toBeTruthy();
    expect(headersOf(call?.[1])["Idempotency-Key"]).toBeTruthy();
  });

  it("exposes the × delete in the collapsed row header (v18 box format: text + ▼/▲ + ×)", async () => {
    // The v18 mockup row header (.strategy-actions) carries both the expand arrow
    // AND the × delete — the delete is reachable WITHOUT first expanding the row.
    const fetchMock = stubRoutes();
    renderPage();
    fireEvent.click(await screen.findByLabelText("Delete Momentum A"));
    const dialog = screen.getByRole("alertdialog");
    fireEvent.click(within(dialog).getByText("Move to Trash"));
    await screen.findByText("Momentum A");
    const call = fetchMock.mock.calls.find(
      (c) => String(c[0]).includes("/work-objects/root_strat") && (c[1]?.method ?? "") === "DELETE",
    );
    expect(call).toBeTruthy();
  });

  it("freezes the composition into a snapshot", async () => {
    const fetchMock = stubRoutes();
    renderPage();
    fireEvent.click(await screen.findByText("Freeze composition"));
    expect(await screen.findByText(/Snapshot snap_1/)).toBeTruthy();
    const call = fetchMock.mock.calls.find(
      (c) => String(c[0]).includes("/mainboards/ws_1/snapshots"),
    );
    expect(call).toBeTruthy();
    expect(headersOf(call?.[1])["Idempotency-Key"]).toBeTruthy();
  });

  it("adds an inline Trading Signal draft row from the nested Add submenu (UI-03)", async () => {
    const fetchMock = stubRoutes();
    renderPage();
    await screen.findByText("Momentum A");
    // Open the Add menu, expand the nested "Add Outsource Signal" submenu, then
    // choose Trading Signal — the correct new row is created inline, without
    // leaving Mainboard (UI-03 acceptance).
    fireEvent.click(screen.getByRole("button", { name: "+ Add" }));
    fireEvent.click(screen.getByRole("button", { name: "Add Outsource Signal" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Trading Signal" }));
    // The popover closed (its menuitem is gone) and a new inline draft row opened.
    expect(screen.queryByRole("menuitem", { name: "Trading Signal" })).toBeNull();
    const row = await screen.findByRole("group", { name: "Trading Signal draft" });
    expect(within(row).getByText(/New Trading Signal draft added to this Mainboard/)).toBeTruthy();
    // The "Unsaved draft" badge lives in the row header (sibling of the details group).
    expect(screen.getByText("Unsaved draft")).toBeTruthy();
    const link = within(row).getByRole("link", {
      name: /Continue in the Trading Signal workbench/,
    });
    expect(link.getAttribute("href")).toBe("/trading-signal");
    // The transient opener still fires (doc 03 §7.1) — data flow unchanged.
    const call = fetchMock.mock.calls.find((c) =>
      String(c[0]).includes("/external-work-object-drafts/trading_signal"),
    );
    expect(call).toBeTruthy();
  });

  it("adds a Trade Log draft row inline and lets the user remove it (UI-03)", async () => {
    stubRoutes({
      "POST /external-work-object-drafts/trade_log": {
        draft_id: "wodraft_2",
        kind: "trade_log",
        unsaved: true,
      },
    });
    renderPage();
    await screen.findByText("Momentum A");
    fireEvent.click(screen.getByRole("button", { name: "+ Add" }));
    fireEvent.click(screen.getByRole("button", { name: "Add Outsource Signal" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Trade Log" }));
    const row = await screen.findByRole("group", { name: "Trade Log draft" });
    expect(
      within(row).getByRole("link", { name: /Continue in the Trade Log workbench/ }).getAttribute(
        "href",
      ),
    ).toBe("/trade-log");
    // Removing the transient row discards it (no Trash — nothing was persisted).
    fireEvent.click(within(row).getByRole("button", { name: "Remove draft" }));
    expect(screen.queryByRole("group", { name: "Trade Log draft" })).toBeNull();
  });

  it("removes the generic Add-work-object / object-kind / raw-JSON path from the flow (F-15)", async () => {
    stubRoutes();
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "+ Add" }));
    // The Add menu offers only typed, product-level choices — no raw path.
    expect(screen.queryByRole("button", { name: "Advanced: create work object" })).toBeNull();
    expect(screen.queryByText("Create work object")).toBeNull();
    expect(screen.queryByText(/Object kind/)).toBeNull();
    expect(screen.queryByText(/Payload \(JSON\)/)).toBeNull();
    // The separate typed actions remain (Add Strategy / Add Package / Outsource).
    expect(screen.getByRole("button", { name: "Add Strategy" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Add Package" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Add Outsource Signal" })).toBeTruthy();
  });

  it("Add Strategy creates a strategy-editor draft and renders an unsaved draft row (F-15)", async () => {
    // Doc 02 §7: the strat_ root has NO revision until the first Save, so the
    // add action creates a DRAFT (editor family) and attaches nothing yet.
    let draftsServed = 0;
    const fetchMock = stubRoutes({
      "GET /strategy-drafts/stratdraft_1": {
        draft_id: "stratdraft_1",
        strategy_root_id: "strat_1",
        payload: {},
        is_dirty: true,
        row_version: 0,
        last_saved_revision_id: null,
        source_provenance: null,
        updated_at: null,
      },
      "POST /strategy-drafts": {
        draft_id: "stratdraft_1",
        strategy_root_id: "strat_1",
        display_name: "STRATEGY 2",
        row_version: 0,
      },
      "GET /strategy-drafts": () => {
        draftsServed += 1;
        return draftsServed === 1
          ? []
          : [
              {
                draft_id: "stratdraft_1",
                strategy_root_id: "strat_1",
                display_name: "STRATEGY 2",
                lifecycle_state: "draft",
                is_dirty: true,
                row_version: 0,
                last_saved_revision_id: null,
                has_revision: false,
                is_attached: false,
                owner_principal_id: "user_admin",
                updated_at: null,
              },
            ];
      },
      "GET /strategies/strat_1/revisions": [],
      "GET /strategies/strat_1": {
        strategy_root_id: "strat_1",
        display_name: "STRATEGY 2",
        lifecycle_state: "draft",
        current_revision_id: null,
        current_row_version: 1,
        rationale_family_id: null,
        owner_principal_id: "user_admin",
        deletion_state: "active",
      },
    });
    renderPage();
    await screen.findByText("Momentum A");
    fireEvent.click(screen.getByRole("button", { name: "+ Add" }));
    fireEvent.click(screen.getByRole("button", { name: "Add Strategy" }));
    // Editor-family create: numbered display name + fresh Idempotency-Key.
    await vi.waitFor(() => {
      const createCall = fetchMock.mock.calls.find(
        (c) => String(c[0]).endsWith("/strategy-drafts") && (c[1]?.method ?? "") === "POST",
      );
      expect(createCall).toBeTruthy();
      expect(String(bodyOf(createCall?.[1]).display_name)).toMatch(/^STRATEGY \d+$/);
      expect(headersOf(createCall?.[1])["Idempotency-Key"]).toBeTruthy();
    });
    // The legacy generic work-object create is gone…
    expect(
      fetchMock.mock.calls.find(
        (c) => String(c[0]).endsWith("/work-objects") && (c[1]?.method ?? "") === "POST",
      ),
    ).toBeFalsy();
    // …and nothing attaches before the first Save (no revision exists yet).
    expect(
      fetchMock.mock.calls.find(
        (c) => String(c[0]).includes("/items") && (c[1]?.method ?? "") === "POST",
      ),
    ).toBeFalsy();
    // The draft renders as a horizontal unsaved-draft row (the name shows in
    // the row header AND inside the auto-expanded inline editor).
    await screen.findByText("Unsaved draft");
    expect((await screen.findAllByText("STRATEGY 2")).length).toBeGreaterThan(0);
  });

  it("first Save of a draft row attaches the §7.1 mirror revision as a real item", async () => {
    // An unattached server draft renders as a draft row; expanding hosts the
    // inline editor, and Save Strategy Revision returns the mirror revision the
    // page then attaches to the CURRENT workspace (root strat_1 + worev_m1).
    const fetchMock = stubRoutes({
      "POST /strategy-drafts/stratdraft_1/save": {
        strategy_root_id: "strat_1",
        strategy_revision_id: "strev_1",
        revision_number: 1,
        config_hash: "cfg_1",
        mirror_revision_id: "worev_m1",
        pinned_items: [],
        ready_state: "STALE",
        warnings: [],
        correlation_id: null,
      },
      "GET /strategy-drafts/stratdraft_1": {
        draft_id: "stratdraft_1",
        strategy_root_id: "strat_1",
        payload: {},
        is_dirty: true,
        row_version: 0,
        last_saved_revision_id: null,
        source_provenance: null,
        updated_at: null,
      },
      "GET /strategy-drafts": [
        {
          draft_id: "stratdraft_1",
          strategy_root_id: "strat_1",
          display_name: "STRATEGY 2",
          lifecycle_state: "draft",
          is_dirty: true,
          row_version: 0,
          last_saved_revision_id: null,
          has_revision: false,
          is_attached: false,
          owner_principal_id: "user_admin",
          updated_at: null,
        },
      ],
      "GET /strategies/strat_1/revisions": [],
      "GET /strategies/strat_1": {
        strategy_root_id: "strat_1",
        display_name: "STRATEGY 2",
        lifecycle_state: "draft",
        current_revision_id: null,
        current_row_version: 1,
        rationale_family_id: null,
        owner_principal_id: "user_admin",
        deletion_state: "active",
      },
      "POST /mainboards/ws_1/items": {
        item_id: "item_new",
        item_kind: "strategy",
        work_object_root_id: "strat_1",
        pinned_revision_id: "worev_m1",
        position_index: 1,
        is_enabled: true,
        display_label_override: null,
        row_version: 0,
        composition_hash: "hash_ghi",
      },
    });
    renderPage();
    await screen.findByText("Momentum A");
    // The unattached draft arrives from GET /strategy-drafts as a draft row.
    fireEvent.click(await screen.findByRole("button", { name: "Expand STRATEGY 2" }));
    // The inline editor loads on the draft; Save returns the mirror revision…
    fireEvent.click(await screen.findByRole("button", { name: "Save Strategy Revision" }));
    // …which the page attaches (root strat_1 pinned at worev_m1, fresh Idem key).
    await vi.waitFor(() => {
      const attachCall = fetchMock.mock.calls.find(
        (c) =>
          String(c[0]).includes("/mainboards/ws_1/items") && (c[1]?.method ?? "") === "POST",
      );
      expect(attachCall).toBeTruthy();
      const body = bodyOf(attachCall?.[1]);
      expect(body.root_id).toBe("strat_1");
      expect(body.revision_id).toBe("worev_m1");
      expect(headersOf(attachCall?.[1])["Idempotency-Key"]).toBeTruthy();
    });
  });

  it("admits a run inline from RUN and renders progress + the full result under the Mainboard (UI-15)", async () => {
    // Route-aware order: the artifacts + metrics fragments both contain the bare
    // result fragment, so they must precede "GET /backtest-results/res_1".
    const fetchMock = stubRoutes({
      "GET /mainboards/default": READY_MAINBOARD,
      "POST /mainboard-compositions/ws_1/backtest-runs": ADMISSION,
      "GET /backtest-runs/btrun_1": SUCCEEDED_RUN,
      "GET /backtest-results/res_1/artifacts/trade_ledger": {
        result_id: "res_1",
        artifact_type: "trade_ledger",
        items: [],
        next_cursor: null,
      },
      "GET /backtest-results/res_1/artifacts/diagnostics": {
        result_id: "res_1",
        artifact_type: "diagnostics",
        items: [],
        next_cursor: null,
      },
      "GET /backtest-results/res_1/metrics": RESULT_METRICS_VIEW,
      "GET /backtest-results/res_1": RESULT_DETAIL,
    });
    renderPage();

    // RUN is admittable in place; clicking it fires the 202 admission (never a
    // navigation) with a fresh Idempotency-Key — the contract is unchanged.
    fireEvent.click(await screen.findByRole("button", { name: "RUN" }));
    await vi.waitFor(() => {
      const call = fetchMock.mock.calls.find(
        (c) =>
          String(c[0]).includes("/mainboard-compositions/ws_1/backtest-runs") &&
          (c[1]?.method ?? "") === "POST",
      );
      expect(call).toBeTruthy();
      expect(headersOf(call?.[1])["Idempotency-Key"]).toBeTruthy();
    });

    // The durable run progress renders inline under the Mainboard (not a page).
    expect(await screen.findByText("Run status")).toBeTruthy();
    expect(await screen.findByText("succeeded")).toBeTruthy();
    // Readiness warnings surface beside the inline panel (warnings never block).
    expect(screen.getByText("2 readiness warning(s)")).toBeTruthy();

    // The full immutable Result is preserved inline — Metrics + Charts + Trade
    // List + Diagnostics + Data Export all render via the shared ResultDetail.
    expect(await screen.findByRole("heading", { name: /Backtest Result/ })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Metrics" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Charts" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Trade List" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Diagnostics" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Data Export" })).toBeTruthy();
  });
});
