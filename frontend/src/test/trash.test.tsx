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

const PURGE_RESULT = {
  purge_job_id: "j_9",
  trash_entry_id: "t_1",
  entity_id: "e_1",
  entity_type: "backtest_result",
  deletion_state: "purge_pending",
  purge_status: "pending",
  row_version: 5,
  correlation_id: "corr-9",
};

const REAUTH_RESULT = {
  reauth_proof: "server-minted-proof-token",
  expires_at: "2026-07-06T10:05:00+00:00",
};

// Order matters for the fragment-matching stub: the purge + restore + detail
// routes must precede the list route (each contains "/trash-entries").
const BASE_ROUTES = {
  "POST /auth/reauth": REAUTH_RESULT,
  "POST /trash-entries/t_1/purge": PURGE_RESULT,
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

  it("opens the UPPER snapshot panel (above the table) with the immutable snapshots", async () => {
    stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("Backtest Alpha");

    fireEvent.click(screen.getAllByRole("button", { name: "Open Snapshot" })[0]);

    expect(await screen.findByText("Deletion snapshot")).toBeInTheDocument();
    expect(screen.getByText("Dependency snapshot")).toBeInTheDocument();
    // The dependency snapshot renders its raw JSON (a ref only in the detail).
    expect(screen.getByText(/"e_9"/)).toBeInTheDocument();
    // UI-20: the snapshot panel sits ABOVE the table, not below it.
    const panelHeading = screen.getByText("Snapshot: Backtest Alpha");
    const table = screen.getByRole("table");
    expect(
      panelHeading.compareDocumentPosition(table) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
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

  it("offers Permanent Delete only on restore-eligible entries", async () => {
    stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("Backtest Alpha");

    // Eligible on the same recoverable statuses as Restore; the purge-pending
    // row (t_2) offers neither.
    expect(screen.getAllByRole("button", { name: "Permanent Delete" })).toHaveLength(1);
  });

  it("gates the purge behind an exact object name and an Admin password", async () => {
    stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("Backtest Alpha");

    fireEvent.click(screen.getByRole("button", { name: "Permanent Delete" }));

    // doc 20 §9 confirmation copy is shown verbatim.
    expect(
      screen.getByText(/This starts an irreversible purge of eligible recoverable payloads/),
    ).toBeInTheDocument();

    const confirm = screen.getByRole("button", { name: "Confirm permanent delete" });
    // Both fields empty -> disabled.
    expect(confirm).toBeDisabled();

    // A wrong phrase shows the mismatch hint and keeps Confirm disabled even
    // once a password is present.
    fireEvent.change(screen.getByLabelText(/Type the object name to confirm/), {
      target: { value: "Wrong Name" },
    });
    fireEvent.change(screen.getByLabelText(/Admin password/), {
      target: { value: "correct-horse-battery" },
    });
    expect(
      screen.getByText("The confirmation phrase must match the object name exactly."),
    ).toBeInTheDocument();
    expect(confirm).toBeDisabled();

    // The exact object name unlocks Confirm.
    fireEvent.change(screen.getByLabelText(/Type the object name to confirm/), {
      target: { value: "Backtest Alpha" },
    });
    expect(confirm).toBeEnabled();
  });

  it("re-authenticates FIRST (F-21), then requests the purge with the server-minted proof, OCC and a fresh Idempotency-Key", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("Backtest Alpha");

    fireEvent.click(screen.getByRole("button", { name: "Permanent Delete" }));
    fireEvent.change(screen.getByLabelText(/Type the object name to confirm/), {
      target: { value: "Backtest Alpha" },
    });
    fireEvent.change(screen.getByLabelText(/Admin password/), {
      target: { value: "correct-horse-battery" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Confirm permanent delete" }));

    // doc 20 §9 accepted toast, echoing the captured object name.
    expect(
      await screen.findByText(
        /Permanent deletion was requested for “Backtest Alpha”\. Track the purge status/,
      ),
    ).toBeInTheDocument();

    const reauthCall = fetchMock.mock.calls.find(
      ([url, init]) => String(url).includes("/auth/reauth") && init?.method === "POST",
    );
    expect(reauthCall).toBeDefined();
    expect(JSON.parse(String((reauthCall?.[1] as RequestInit).body))).toEqual({
      password: "correct-horse-battery",
      purpose: "trash_purge",
    });

    const purgeCall = fetchMock.mock.calls.find(
      ([url, init]) => String(url).includes("/trash-entries/t_1/purge") && init?.method === "POST",
    );
    expect(purgeCall).toBeDefined();
    const init = purgeCall?.[1] as RequestInit;
    expect(JSON.parse(String(init.body))).toEqual({
      confirmation_phrase: "Backtest Alpha",
      // The purge NEVER carries the typed password — only the server-minted
      // proof token returned by /auth/reauth.
      reauth_proof: "server-minted-proof-token",
      // OCC: the body carries the entry's row_version as the expected head.
      expected_head_revision_id: 4,
    });
    expect((init.headers as Record<string, string>)["Idempotency-Key"]).toBeTruthy();

    // The re-auth call happened strictly before the purge call.
    const reauthIndex = fetchMock.mock.calls.indexOf(reauthCall!);
    const purgeIndex = fetchMock.mock.calls.indexOf(purgeCall!);
    expect(reauthIndex).toBeLessThan(purgeIndex);
  });

  it("blocks the purge entirely on a wrong password — the purge endpoint is never called", async () => {
    const fetchMock = stubApi({
      ...BASE_ROUTES,
      "POST /auth/reauth": () => {
        throw new Error("INVALID_CREDENTIALS: Invalid username or password.");
      },
    });
    renderPage();
    await screen.findByText("Backtest Alpha");

    fireEvent.click(screen.getByRole("button", { name: "Permanent Delete" }));
    fireEvent.change(screen.getByLabelText(/Type the object name to confirm/), {
      target: { value: "Backtest Alpha" },
    });
    fireEvent.change(screen.getByLabelText(/Admin password/), {
      target: { value: "wrong-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Confirm permanent delete" }));

    expect(
      await screen.findByText("INVALID_CREDENTIALS: Invalid username or password."),
    ).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.find(([url]) => String(url).includes("/trash-entries/t_1/purge")),
    ).toBeUndefined();
  });

  it("surfaces a purge rejection verbatim (server re-validates OCC)", async () => {
    stubApi({
      ...BASE_ROUTES,
      "POST /trash-entries/t_1/purge": () => {
        throw new Error("STALE_REVISION: The resource was modified by someone else.");
      },
    });
    renderPage();
    await screen.findByText("Backtest Alpha");

    fireEvent.click(screen.getByRole("button", { name: "Permanent Delete" }));
    fireEvent.change(screen.getByLabelText(/Type the object name to confirm/), {
      target: { value: "Backtest Alpha" },
    });
    fireEvent.change(screen.getByLabelText(/Admin password/), {
      target: { value: "correct-horse-battery" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Confirm permanent delete" }));

    expect(
      await screen.findByText("STALE_REVISION: The resource was modified by someone else."),
    ).toBeInTheDocument();
  });
});
