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

  it("unlocks RUN as a navigable link once the composition is ready", async () => {
    stubRoutes({
      "GET /mainboards/default": {
        ...MAINBOARD,
        ready_summary: { state: "ready", report_id: "rr_1" },
      },
    });
    renderPage();
    const run = await screen.findByRole("link", { name: "RUN" });
    expect(run.getAttribute("href")).toBe("/backtest/run");
    // The disabled placeholder is gone once RUN is a real link.
    expect(screen.queryByRole("button", { name: "RUN" })).toBeNull();
  });

  it("unlocks RUN when the composition is ready with warnings (warnings never block)", async () => {
    stubRoutes({
      "GET /mainboards/default": {
        ...MAINBOARD,
        ready_summary: { state: "ready_with_warnings", report_id: "rr_2" },
      },
    });
    renderPage();
    const run = await screen.findByRole("link", { name: "RUN" });
    expect(run.getAttribute("href")).toBe("/backtest/run");
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
            headline: {},
          },
        },
      },
    });
    renderPage();
    const link = await screen.findByText("btr_1");
    expect(link.getAttribute("href")).toBe("/backtest/run?result=btr_1");
    expect(
      screen.getByText("BTCUSD · 1h · 7 trade(s) · 2026-01-01 → 2026-02-01"),
    ).toBeTruthy();
    // Matching fingerprint -> the result is current; no snapshot-differs badge.
    expect(screen.queryByText(/Result snapshot differs/)).toBeNull();
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

  it("Add Strategy creates + attaches a strategy work object inline (F-15)", async () => {
    const fetchMock = stubRoutes({
      "POST /work-objects": {
        root_id: "root_new",
        revision_id: "wor_new1",
        revision_no: 1,
        object_kind: "strategy",
        row_version: 0,
      },
      "POST /mainboards/ws_1/items": {
        item_id: "item_new",
        item_kind: "strategy",
        work_object_root_id: "root_new",
        pinned_revision_id: "wor_new1",
        position_index: 1,
        is_enabled: true,
        display_label_override: null,
        row_version: 0,
        composition_hash: "hash_ghi",
      },
    });
    renderPage();
    await screen.findByText("Momentum A");
    fireEvent.click(screen.getByRole("button", { name: "+ Add" }));
    fireEvent.click(screen.getByRole("button", { name: "Add Strategy" }));
    // Real create round trip: object_kind=strategy, empty payload, fresh Idempotency-Key.
    await screen.findByText("Momentum A");
    const createCall = fetchMock.mock.calls.find(
      (c) => String(c[0]).endsWith("/work-objects") && (c[1]?.method ?? "") === "POST",
    );
    expect(createCall).toBeTruthy();
    expect(bodyOf(createCall?.[1]).object_kind).toBe("strategy");
    expect(headersOf(createCall?.[1])["Idempotency-Key"]).toBeTruthy();
    // …then attaches the created revision to the default workspace.
    const attachCall = fetchMock.mock.calls.find(
      (c) => String(c[0]).includes("/mainboards/ws_1/items"),
    );
    expect(attachCall).toBeTruthy();
    const attachBody = bodyOf(attachCall?.[1]);
    expect(attachBody.root_id).toBe("root_new");
    expect(attachBody.revision_id).toBe("wor_new1");
    expect(headersOf(attachCall?.[1])["Idempotency-Key"]).toBeTruthy();
  });
});
