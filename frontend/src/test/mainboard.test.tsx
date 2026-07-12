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
const CREATE_RESULT = {
  root_id: "root_new",
  revision_id: "wor_new1",
  revision_no: 1,
  object_kind: "strategy",
  row_version: 0,
};
const REVISION_RESULT = {
  root_id: "root_new",
  revision_id: "wor_new2",
  revision_no: 2,
  row_version: 1,
};
const ATTACH_RESULT = {
  item_id: "item_new",
  item_kind: "strategy",
  work_object_root_id: "root_new",
  pinned_revision_id: "wor_new1",
  position_index: 1,
  is_enabled: true,
  display_label_override: null,
  row_version: 0,
  composition_hash: "hash_ghi",
};

// ORDERED routes: the {root}/revisions POST fragment must precede the bare
// "POST /work-objects" create prefix (the create path is a substring of it).
function stubRoutes(overrides: Record<string, unknown> = {}) {
  return stubApi({
    "POST /work-objects/root_new/revisions": REVISION_RESULT,
    "POST /work-objects": CREATE_RESULT,
    "POST /mainboards/ws_1/items": ATTACH_RESULT,
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

  it("pins a revision with the item row_version OCC and a fresh Idempotency-Key", async () => {
    const fetchMock = stubRoutes();
    renderPage();
    await expandRow();
    fireEvent.change(screen.getByLabelText("Revision id for Momentum A"), {
      target: { value: "wor_2" },
    });
    fireEvent.click(screen.getByText("Use This Revision"));
    await screen.findByText("Momentum A");
    const call = fetchMock.mock.calls.find(
      (c) => String(c[0]).includes("/mainboard-items/item_strat"),
    );
    expect(call).toBeTruthy();
    const body = bodyOf(call?.[1]);
    expect(body.intent).toBe("pin_revision");
    expect(body.expected_row_version).toBe(5);
    expect(body.revision_id).toBe("wor_2");
    expect(headersOf(call?.[1])["Idempotency-Key"]).toBeTruthy();
  });

  it("toggles enable/disable via set_enabled", async () => {
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

  it("starts an external work-object draft and links to the workbench", async () => {
    const fetchMock = stubRoutes();
    renderPage();
    await screen.findByText("Momentum A");
    fireEvent.click(screen.getByRole("button", { name: "Trading Signal" }));
    expect(await screen.findByText(/Trading Signal draft opened/)).toBeTruthy();
    const link = screen.getByRole("link", { name: /Continue in the Trading Signal workbench/ });
    expect(link.getAttribute("href")).toBe("/trading-signal");
    const call = fetchMock.mock.calls.find(
      (c) => String(c[0]).includes("/external-work-object-drafts/trading_signal"),
    );
    expect(call).toBeTruthy();
  });

  it("creates a generic work object then attaches its revision", async () => {
    const fetchMock = stubRoutes();
    renderPage();
    fireEvent.click(await screen.findByText("Create work object"));
    expect(await screen.findByText("root_new")).toBeTruthy();
    fireEvent.click(screen.getByText("Attach to Mainboard"));
    await screen.findByText("Momentum A");
    const createCall = fetchMock.mock.calls.find(
      (c) => String(c[0]).endsWith("/work-objects") && (c[1]?.method ?? "") === "POST",
    );
    expect(createCall).toBeTruthy();
    expect(headersOf(createCall?.[1])["Idempotency-Key"]).toBeTruthy();
    const attachCall = fetchMock.mock.calls.find(
      (c) => String(c[0]).includes("/mainboards/ws_1/items"),
    );
    expect(attachCall).toBeTruthy();
    const body = bodyOf(attachCall?.[1]);
    expect(body.root_id).toBe("root_new");
    expect(body.revision_id).toBe("wor_new1");
  });
});
