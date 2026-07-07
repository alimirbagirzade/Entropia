import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import { Trash } from "@/pages/Trash";
import { stubApi } from "./helpers/apiStub";

const ELIGIBLE_ENTRY = {
  trash_entry_id: "t_1",
  entity_id: "e_1",
  object_type: "backtest_result",
  display_name: "Backtest Alpha",
  original_location: "Backtest Results",
  original_owner: "u_2",
  deleted_by: "u_9",
  deleted_at: "2026-07-06T10:00:00+00:00",
  delete_reason: "cleanup",
  status: "soft_deleted",
  purge_status: null,
  purge_job_id: null,
  restore_eligible: true,
  row_version: 4,
  correlation_id: "corr-1",
};

const PURGING_ENTRY = {
  trash_entry_id: "t_2",
  entity_id: "e_2",
  object_type: "strategy",
  display_name: "Strat Beta",
  original_location: "Strategies",
  original_owner: "u_3",
  deleted_by: "u_9",
  deleted_at: "2026-07-05T09:00:00+00:00",
  delete_reason: null,
  status: "purge_pending",
  purge_status: "pending",
  purge_job_id: "j_1",
  restore_eligible: false,
  row_version: 2,
  correlation_id: "corr-2",
};

const ENTRIES_PAGE = {
  data: [ELIGIBLE_ENTRY, PURGING_ENTRY],
  meta: {
    cursor: null,
    has_more: false,
    limit: 20,
    recoverable_total: 1,
    object_types: ["backtest_result", "strategy"],
  },
};

const ENTRY_DETAIL = {
  ...ELIGIBLE_ENTRY,
  deletion_snapshot: { name: "Backtest Alpha", size: 3 },
  dependency_snapshot: { refs: ["e_9"] },
  purge_error: null,
  purge_requested_by: null,
  restored_at: null,
  restored_by: null,
  current_deletion_state: "soft_deleted",
  tombstone: null,
};

const RESTORE_RESULT = {
  trash_entry_id: "t_1",
  entity_id: "e_1",
  entity_type: "backtest_result",
  display_name: "Backtest Alpha",
  status: "active",
  deletion_state: "active",
  current_revision_id: "rev_1",
  row_version: 5,
  correlation_id: "corr-3",
};

// Order matters for the fragment-matching stub: the restore + detail routes
// must precede the list route ("/trash-entries/t_1" contains "/trash-entries").
const BASE_ROUTES = {
  "POST /trash-entries/t_1/restore": RESTORE_RESULT,
  "GET /trash-entries/t_1": ENTRY_DETAIL,
  "GET /trash-entries": ENTRIES_PAGE,
};

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/trash"]}>
        <Trash />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return client;
}

describe("Trash page", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders the recoverable index with the server recoverable total", async () => {
    stubApi(BASE_ROUTES);
    renderPage();

    expect(await screen.findByText("Backtest Alpha")).toBeInTheDocument();
    expect(screen.getByText("Strat Beta")).toBeInTheDocument();
    expect(screen.getByText("(1 recoverable)")).toBeInTheDocument();
  });

  it("only offers Restore on restore-eligible entries (server truth)", async () => {
    stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("Backtest Alpha");

    // Exactly one Restore button (t_1); the purge-pending row is not restorable.
    expect(screen.getAllByRole("button", { name: "Restore" })).toHaveLength(1);
    expect(screen.getByText("not restorable")).toBeInTheDocument();
  });

  it("restores with the row-version OCC guard and a fresh Idempotency-Key", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("Backtest Alpha");

    fireEvent.click(screen.getByRole("button", { name: "Restore" }));

    expect(
      await screen.findByText("Restored — Backtest Alpha (backtest_result) back to active (v5)."),
    ).toBeInTheDocument();

    const restoreCall = fetchMock.mock.calls.find(
      ([url, init]) =>
        String(url).includes("/trash-entries/t_1/restore") && init?.method === "POST",
    );
    expect(restoreCall).toBeDefined();
    const init = restoreCall?.[1] as RequestInit;
    // OCC: the body carries the entry's row_version as the expected head.
    expect(JSON.parse(String(init.body))).toEqual({ expected_head_revision_id: 4 });
    // A fresh Idempotency-Key makes a retry a new decision, not a replay.
    expect((init.headers as Record<string, string>)["Idempotency-Key"]).toBeTruthy();
  });

  it("applies an object_type filter as a server-side query parameter", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("Backtest Alpha");

    fireEvent.change(screen.getByLabelText(/Object type/), { target: { value: "strategy" } });

    await waitFor(() => {
      const filtered = fetchMock.mock.calls.find(([url]) =>
        String(url).includes("/trash-entries?object_type=strategy"),
      );
      expect(filtered).toBeDefined();
    });
  });

  it("opens the entry detail with the immutable snapshots", async () => {
    stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("Backtest Alpha");

    fireEvent.click(screen.getAllByRole("button", { name: "Detail" })[0]);

    expect(await screen.findByText("Deletion snapshot")).toBeInTheDocument();
    expect(screen.getByText("Dependency snapshot")).toBeInTheDocument();
    // The dependency snapshot renders its raw JSON (a ref only in the detail).
    expect(screen.getByText(/"e_9"/)).toBeInTheDocument();
  });

  it("refetches the index when the ['trash'] SSE prefix is invalidated", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    const client = renderPage();
    await screen.findByText("Backtest Alpha");
    const before = fetchMock.mock.calls.filter(([url]) =>
      String(url).includes("/trash-entries"),
    ).length;

    // resource.changed sweeps ["trash"]; a restore also invalidates it same-tab.
    await client.invalidateQueries({ queryKey: ["trash"] });

    await waitFor(() => {
      const after = fetchMock.mock.calls.filter(([url]) =>
        String(url).includes("/trash-entries"),
      ).length;
      expect(after).toBeGreaterThan(before);
    });
  });

  it("surfaces the server denial verbatim (server policy, not a UI hint)", async () => {
    stubApi({
      ...BASE_ROUTES,
      "GET /trash-entries": () => {
        throw new Error("FORBIDDEN: Trash requires the Admin role.");
      },
    });
    renderPage();

    expect(await screen.findByText("Unable to load")).toBeInTheDocument();
    expect(screen.getByText("FORBIDDEN: Trash requires the Admin role.")).toBeInTheDocument();
  });
});
