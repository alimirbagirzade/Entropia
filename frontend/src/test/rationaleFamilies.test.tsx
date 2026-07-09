import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import { RationaleFamilies } from "@/pages/RationaleFamilies";
import { stubApi } from "./helpers/apiStub";

const FAMILY_MOMENTUM = {
  entity_id: "fam_1",
  current_revision_id: "rev_f1",
  revision_no: 2,
  display_name: "Momentum",
  normalized_name: "momentum",
  subfamilies: ["trend"],
  compatible_output_types: ["directional_signal"],
  display_color: "#a3c",
  created_by_actor_id: "u_1",
  row_version: 3,
  created_at: "2026-07-01T09:00:00+00:00",
};

const FAMILY_REVERSION = {
  entity_id: "fam_2",
  current_revision_id: "rev_f2",
  revision_no: 1,
  display_name: "Mean Reversion",
  normalized_name: "mean reversion",
  subfamilies: [],
  compatible_output_types: [],
  display_color: "#3ca",
  created_by_actor_id: "u_1",
  row_version: 1,
  created_at: "2026-07-02T09:00:00+00:00",
};

const FAMILIES_PAGE = {
  data: [FAMILY_MOMENTUM, FAMILY_REVERSION],
  meta: { cursor: null, has_more: false },
};

const ASSIGNMENTS_PAGE = {
  data: [
    {
      package_root_id: "pkg_1",
      package_kind: "indicator",
      package_name: "RSI-14",
      current_package_revision_id: "prev_1",
      rationale_family_id: "fam_1",
      rationale_family_revision_id: "rev_f1",
      current_family_name: "Momentum",
      assignment_state: "assigned",
      family_active: true,
    },
    {
      package_root_id: "pkg_2",
      package_kind: "condition",
      package_name: "Cross Up",
      current_package_revision_id: "prev_2",
      rationale_family_id: null,
      rationale_family_revision_id: null,
      current_family_name: null,
      assignment_state: "unassigned",
      family_active: true,
    },
  ],
  meta: { cursor: null, has_more: false, table_version: "tv-1" },
};

const CREATE_RESULT = {
  entity_id: "fam_new",
  revision_id: "rev_new",
  revision_no: 1,
  display_name: "Breakout",
  display_color: "#fed",
  row_version: 0,
};

const REVISE_RESULT = {
  entity_id: "fam_1",
  revision_id: "rev_f1b",
  revision_no: 3,
  display_name: "Momentum X",
  row_version: 3,
};

const DELETE_RESULT = {
  entity_id: "fam_2",
  deletion_state: "soft_deleted",
  display_name: "Mean Reversion",
};

const BATCH_RESULT = {
  created_revisions: [
    { package_root_id: "pkg_2", revision_id: "prev_2b", rationale_family_id: "fam_1" },
  ],
  count: 1,
  warnings: [
    {
      code: "OUTPUT_TYPE_NOT_LISTED",
      package_root_id: "pkg_2",
      message: "Current output type is not listed as compatible; the assignment was saved.",
    },
  ],
  table_version: "tv-2",
};

// Order matters for the fragment-matching stub: the revise + delete + batch action
// routes must precede the list prefixes (POST /rationale-families/fam_1/revisions
// contains /rationale-families; :batch contains /package-rationale-assignments).
const BASE_ROUTES = {
  "POST /rationale-families/fam_1/revisions": REVISE_RESULT,
  "DELETE /rationale-families/fam_2": DELETE_RESULT,
  "POST /rationale-families": CREATE_RESULT,
  "POST /package-rationale-assignments:batch": BATCH_RESULT,
  "GET /rationale-families": FAMILIES_PAGE,
  "GET /package-rationale-assignments": ASSIGNMENTS_PAGE,
};

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/rationale-families"]}>
        <RationaleFamilies />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return client;
}

// The family display name "Momentum" appears in the registry row, the assignment
// current-family cell AND every select option, so it is deliberately NOT used as a
// ready-check. "trend" (fam_1's only subfamily) is unique to the registry table.
describe("Rationale Families page", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders the family registry and the package assignment table (two shared projections)", async () => {
    stubApi(BASE_ROUTES);
    renderPage();

    // Registry: unique metadata cells + family names scoped to the registry table.
    expect(await screen.findByText("trend")).toBeInTheDocument();
    expect(screen.getByText("directional_signal")).toBeInTheDocument();
    const registryTable = within(screen.getAllByRole("table")[0]!);
    expect(registryTable.getByText("Momentum")).toBeInTheDocument();
    expect(registryTable.getByText("Mean Reversion")).toBeInTheDocument();

    // Assignment rows with their current-projection states.
    expect(await screen.findByText("RSI-14")).toBeInTheDocument();
    expect(screen.getByText("Cross Up")).toBeInTheDocument();
    expect(screen.getByText("assigned")).toBeInTheDocument();
    expect(screen.getByText("unassigned")).toBeInTheDocument();
  });

  it("creates a family with a fresh Idempotency-Key and no OCC token", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("trend");

    fireEvent.change(screen.getByLabelText(/Display name/), { target: { value: "Breakout" } });
    fireEvent.click(screen.getByRole("button", { name: "Create family" }));

    expect(await screen.findByText("Saved — Breakout.")).toBeInTheDocument();

    const call = fetchMock.mock.calls.find(
      ([url, init]) => String(url).endsWith("/rationale-families") && init?.method === "POST",
    );
    expect(call).toBeDefined();
    const init = call?.[1] as RequestInit;
    expect(JSON.parse(String(init.body))).toEqual({
      display_name: "Breakout",
      subfamilies: [],
      compatible_output_types: [],
      change_note: null,
    });
    expect((init.headers as Record<string, string>)["Idempotency-Key"]).toBeTruthy();
  });

  it("revises a family pinning the current head revision as the OCC token", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("trend");

    // Edit the first registry row (Momentum) -> the editor seeds from its card.
    fireEvent.click(screen.getAllByRole("button", { name: "Edit" })[0]!);
    fireEvent.change(screen.getByLabelText(/Display name/), { target: { value: "Momentum X" } });
    fireEvent.click(screen.getByRole("button", { name: "Save revision" }));

    expect(await screen.findByText("Saved — Momentum X.")).toBeInTheDocument();

    const call = fetchMock.mock.calls.find(
      ([url, init]) =>
        String(url).includes("/rationale-families/fam_1/revisions") && init?.method === "POST",
    );
    expect(call).toBeDefined();
    const init = call?.[1] as RequestInit;
    const body = JSON.parse(String(init.body));
    expect(body.display_name).toBe("Momentum X");
    // OCC: the current head revision id is the concurrency token (doc 10 §5 Save).
    expect(body.expected_head_revision_id).toBe("rev_f1");
    expect((init.headers as Record<string, string>)["Idempotency-Key"]).toBeTruthy();
  });

  it("soft-deletes a family with a two-step confirm and the rv-N If-Match ETag", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("trend");

    // Second registry row is Mean Reversion (row_version 1).
    fireEvent.click(screen.getAllByRole("button", { name: "Delete" })[1]!);
    fireEvent.click(screen.getByRole("button", { name: "Confirm delete" }));

    expect(await screen.findByText(/Deleted — Mean Reversion/)).toBeInTheDocument();

    const call = fetchMock.mock.calls.find(
      ([url, init]) => String(url).includes("/rationale-families/fam_2") && init?.method === "DELETE",
    );
    expect(call).toBeDefined();
    const init = call?.[1] as RequestInit;
    // OCC: the root row_version travels as the strong "rv-N" ETag.
    expect((init.headers as Record<string, string>)["If-Match"]).toBe('"rv-1"');
  });

  it("stages a reassignment and saves the batch with the table_version token + warnings", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("Cross Up");

    // Reassign the unassigned Condition package to Momentum (fam_1).
    fireEvent.change(screen.getByLabelText("Reassign Cross Up"), { target: { value: "fam_1" } });
    expect(screen.getByText("1 pending change(s)")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Save assignments" }));

    expect(await screen.findByText("Saved — 1 package revision(s) created.")).toBeInTheDocument();
    // The non-blocking output-mismatch warning renders verbatim.
    expect(screen.getByText("OUTPUT_TYPE_NOT_LISTED")).toBeInTheDocument();

    const call = fetchMock.mock.calls.find(
      ([url, init]) =>
        String(url).includes("/package-rationale-assignments:batch") && init?.method === "POST",
    );
    expect(call).toBeDefined();
    const body = JSON.parse(String((call?.[1] as RequestInit).body));
    expect(body.expected_table_version).toBe("tv-1");
    expect(body.changes).toEqual([
      {
        package_root_id: "pkg_2",
        expected_head_revision_id: "prev_2",
        rationale_family_id: "fam_1",
        expected_family_current_revision_id: "rev_f1",
      },
    ]);
  });

  it("refetches the registry when the ['rationale-families'] SSE prefix is invalidated", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    const client = renderPage();
    await screen.findByText("trend");
    const before = fetchMock.mock.calls.filter(([url]) =>
      String(url).includes("/rationale-families"),
    ).length;

    await client.invalidateQueries({ queryKey: ["rationale-families"] });

    await waitFor(() => {
      const after = fetchMock.mock.calls.filter(([url]) =>
        String(url).includes("/rationale-families"),
      ).length;
      expect(after).toBeGreaterThan(before);
    });
  });

  it("surfaces the server denial verbatim (shared-editing gate, not a UI hint)", async () => {
    stubApi({
      ...BASE_ROUTES,
      "GET /rationale-families": () => {
        throw new Error("AUTHENTICATION_REQUIRED: Sign in to view rationale families.");
      },
    });
    renderPage();

    expect(await screen.findByText("Unable to load")).toBeInTheDocument();
    expect(
      screen.getByText("AUTHENTICATION_REQUIRED: Sign in to view rationale families."),
    ).toBeInTheDocument();
  });
});
