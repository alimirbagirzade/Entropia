import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import { Library } from "@/pages/Library";
import { apiErrorRoute, stubApi } from "./helpers/apiStub";

// G-04 — Request Validation on the Package Library detail panel (doc 08 §7).
//
// The backend route has existed since S-L3 and `can_request_validation` was already
// projected; what was missing was any way to reach it. These tests pin the full UI
// state matrix of that surface, and — just as importantly — pin that it starts the
// EXISTING pipeline: the request shape is the wrapper's contract, the durable state is
// read from the shared validation-run read model, and passing never approves anything.

const PERFORMANCE_NA = {
  net_profit: "not_applicable",
  max_drawdown: "not_applicable",
  romad: "not_applicable",
  win_rate: "not_applicable",
  trade_count: "not_applicable",
  out_of_sample: "not_applicable",
};

const VALIDATABLE_PERMISSIONS = {
  can_view: true,
  can_use: true,
  can_derive: true,
  can_create_revision: true,
  can_request_validation: true,
  can_request_approval: true,
  can_approve_publish: false,
  can_deprecate: true,
  can_soft_delete: true,
  can_export: true,
  can_share: true,
};

// A Derived / seeded package: the SERVER already knows there is no originating
// create-package draft, so the capability is false and the action is never offered.
const NO_PIPELINE_PERMISSIONS = { ...VALIDATABLE_PERMISSIONS, can_request_validation: false };

const ROW = {
  entity_id: "pkg_own",
  package_kind: "indicator",
  name: "Owned RSI",
  current_revision_id: "rev_1",
  revision_no: 2,
  lifecycle_state: "active",
  validation_state: "pending",
  approval_state: "draft",
  visibility_scope: "private",
  rationale_family: null,
  output_kinds: ["directional_signal"],
  derived_from_revision_id: null,
  owner_principal_id: "u_owner",
  row_version: 7,
  content_hash: "sha256:own",
  created_at: "2026-07-01T10:00:00+00:00",
  permissions: VALIDATABLE_PERMISSIONS,
  performance: PERFORMANCE_NA,
};

function detailWith(permissions: typeof VALIDATABLE_PERMISSIONS) {
  return {
    ...ROW,
    permissions,
    input_contract: { name: "Owned RSI" },
    output_contract: { kind: "directional_signal" },
    dependency_snapshot: null,
    validation_summary: null,
    change_note: null,
    rationale_family: null,
    provenance: null,
    revisions: [
      {
        revision_id: "rev_1",
        revision_no: 2,
        validation_state: "pending",
        approval_state: "draft",
        change_note: null,
        created_at: "2026-07-01T10:00:00+00:00",
      },
    ],
  };
}

const QUEUED_ADMISSION = {
  entity_id: "pkg_own",
  revision_id: "rev_1",
  request_id: "cpr_7",
  validation_run_id: "vrun_1",
  attempt_no: 1,
  status: "queued",
  state: "validation_running",
  job_id: "job_9",
};

function runRow(status: string) {
  return {
    validation_run_id: "vrun_1",
    attempt_no: 1,
    status,
    validator_version: "cp-validation-v1",
    checks: [],
    candidate_hash: "sha256:cand",
    draft_revision_id: "rev_1",
    request_id: "cpr_7",
    job_id: "job_9",
    completed_at: status === "queued" || status === "running" ? null : "2026-07-01T10:05:00+00:00",
  };
}

const FAMILIES_PAGE = { data: [], meta: { cursor: null, has_more: false } };

// Detail fragment ("/library/pkg_own") precedes the list prefix, as the sibling
// action tests do; method disambiguates the POSTs that also contain "/library".
function routesFor(
  permissions: typeof VALIDATABLE_PERMISSIONS,
  overrides: Record<string, unknown> = {},
) {
  return {
    "GET /library/pkg_own": detailWith(permissions),
    "GET /rationale-families": FAMILIES_PAGE,
    "GET /library": { data: [{ ...ROW, permissions }], meta: { cursor: null, has_more: false } },
    "POST /library/pkg_own/validation-runs": QUEUED_ADMISSION,
    "GET /validation-runs/": runRow("queued"),
    "POST /library/pkg_own/request-approval": {
      entity_id: "pkg_own",
      revision_id: "rev_1",
      approval_state: "approval_requested",
    },
    ...overrides,
  };
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/packages/library"]}>
        <Library />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return client;
}

async function openDetail() {
  await screen.findByText("Owned RSI");
  fireEvent.click(screen.getAllByRole("button", { name: "Detail" })[0]);
  await screen.findByText("Lifecycle actions");
}

// Idle -> confirm -> submit, the three steps every mutating action on this page takes.
async function submitValidation() {
  fireEvent.click(screen.getByRole("button", { name: "Request Validation" }));
  fireEvent.click(screen.getByRole("button", { name: "Confirm request validation" }));
}

function statusRegion() {
  return screen.getByRole("status", { name: "Validation run status" });
}

describe("Package Library — Request Validation (G-04)", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  // --- projection-level availability -------------------------------------------------

  it("offers no action when the server says the package has no validation pipeline", async () => {
    stubApi(routesFor(NO_PIPELINE_PERMISSIONS));
    renderPage();
    await openDetail();

    // The whole block is absent — an un-performable action is never advertised.
    expect(screen.queryByRole("button", { name: "Request Validation" })).not.toBeInTheDocument();
    expect(
      screen.queryByRole("status", { name: "Validation run status" }),
    ).not.toBeInTheDocument();
  });

  it("shows the idle action when the server marks can_request_validation", async () => {
    stubApi(routesFor(VALIDATABLE_PERMISSIONS));
    renderPage();
    await openDetail();

    expect(screen.getByRole("button", { name: "Request Validation" })).toBeInTheDocument();
    // Idle means idle: no confirm affordance and no run being followed yet.
    expect(
      screen.queryByRole("button", { name: "Confirm request validation" }),
    ).not.toBeInTheDocument();
    expect(statusRegion()).toBeEmptyDOMElement();
  });

  // --- confirm step ------------------------------------------------------------------

  it("requires a confirm step and fires nothing when it is cancelled", async () => {
    const fetchMock = stubApi(routesFor(VALIDATABLE_PERMISSIONS));
    renderPage();
    await openDetail();

    fireEvent.click(screen.getByRole("button", { name: "Request Validation" }));
    expect(screen.getByRole("button", { name: "Confirm request validation" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await screen.findByRole("button", { name: "Request Validation" });

    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/validation-runs"))).toBe(
      false,
    );
  });

  // --- the exact wire contract -------------------------------------------------------

  it("dispatches the wrapper's exact request: body-form OCC + a fresh Idempotency-Key", async () => {
    const fetchMock = stubApi(routesFor(VALIDATABLE_PERMISSIONS));
    renderPage();
    await openDetail();
    await submitValidation();

    await waitFor(() => {
      const call = fetchMock.mock.calls.find(
        ([url, init]) =>
          String(url).includes("/library/pkg_own/validation-runs") &&
          (init?.method ?? "").toUpperCase() === "POST",
      );
      expect(call).toBeDefined();
      const init = call![1]!;
      const headers = new Headers(init.headers);
      // A fresh key per submit — a retry is a new decision, not a silent replay.
      expect(headers.get("Idempotency-Key")).toBeTruthy();
      // OCC is the BODY-form expected_head_revision_id pinned to the head on screen.
      expect(JSON.parse(String(init.body))).toEqual({
        revision_id: "rev_1",
        expected_head_revision_id: "rev_1",
      });
    });
  });

  it("surfaces the queued admission's run, request and job identifiers", async () => {
    stubApi(routesFor(VALIDATABLE_PERMISSIONS));
    renderPage();
    await openDetail();
    await submitValidation();

    const region = await screen.findByRole("status", { name: "Validation run status" });
    await waitFor(() => expect(region).toHaveTextContent("queued"));
    // Both planes are named, because ONE run owns all of these.
    expect(region).toHaveTextContent("vrun_1");
    expect(region).toHaveTextContent("cpr_7");
    expect(region).toHaveTextContent("job_9");
    expect(region).toHaveTextContent("rev_1");
    expect(region).toHaveTextContent("attempt 1");
    // The RUN's status and the REQUEST's state are reported separately, never collapsed.
    expect(region).toHaveTextContent("validation_running");
  });

  it("moves the caret to the live status region once the run is admitted", async () => {
    stubApi(routesFor(VALIDATABLE_PERMISSIONS));
    renderPage();
    await openDetail();
    await submitValidation();

    await waitFor(() => expect(statusRegion()).toHaveFocus());
  });

  // --- durable state: queued -> running -> passed -------------------------------------

  it("follows the durable run from queued through running to passed on invalidation", async () => {
    let status = "queued";
    stubApi(routesFor(VALIDATABLE_PERMISSIONS, { "GET /validation-runs/": () => runRow(status) }));
    const client = renderPage();
    await openDetail();
    await submitValidation();

    const region = await screen.findByRole("status", { name: "Validation run status" });
    await waitFor(() => expect(region).toHaveTextContent("queued"));
    // Progress is legible without colour: the status word AND a sentence.
    expect(region).toHaveTextContent("the durable job is accepted and has not started yet");

    // The `resource.changed` SSE catch-all refetches every mounted query — this is that
    // signal, not a bespoke Library poll.
    status = "running";
    await act(async () => {
      await client.invalidateQueries();
    });
    await waitFor(() =>
      expect(region).toHaveTextContent("the seven mandatory checks are executing"),
    );

    status = "passed";
    await act(async () => {
      await client.invalidateQueries();
    });
    await waitFor(() => expect(region).toHaveTextContent("this revision is certified"));
    // PASS is not approval — the panel says so and Request Approval stays its own step.
    expect(region).toHaveTextContent("passing does not approve or publish anything");
    expect(screen.getByRole("button", { name: "Request Approval" })).toBeInTheDocument();
    // A settled run is no longer advertised as in flight.
    expect(region).not.toHaveTextContent("closing it does not stop the run");
  });

  it("renders a failed verdict with its repair path", async () => {
    stubApi(routesFor(VALIDATABLE_PERMISSIONS, { "GET /validation-runs/": runRow("failed") }));
    renderPage();
    await openDetail();
    await submitValidation();

    const region = await screen.findByRole("status", { name: "Validation run status" });
    await waitFor(() => expect(region).toHaveTextContent("failed"));
    expect(region).toHaveTextContent("repair it in a new revision or derive your own");
  });

  it("renders a stale verdict as evidence that no longer certifies", async () => {
    stubApi(routesFor(VALIDATABLE_PERMISSIONS, { "GET /validation-runs/": runRow("stale") }));
    renderPage();
    await openDetail();
    await submitValidation();

    const region = await screen.findByRole("status", { name: "Validation run status" });
    await waitFor(() =>
      expect(region).toHaveTextContent("no longer certifies the current candidate"),
    );
  });

  // --- refusals ----------------------------------------------------------------------

  it("renders the 409 stale-head conflict and follows no run", async () => {
    stubApi(
      routesFor(VALIDATABLE_PERMISSIONS, {
        "POST /library/pkg_own/validation-runs": apiErrorRoute(
          409,
          "PACKAGE_REVISION_CONFLICT",
          "The package head has moved since this page was loaded.",
        ),
      }),
    );
    renderPage();
    await openDetail();
    await submitValidation();

    // ErrorState renders the canonical envelope verbatim, code first — the UI invents
    // no message of its own for a conflict.
    await screen.findByText(
      "PACKAGE_REVISION_CONFLICT: The package head has moved since this page was loaded.",
    );
    // Nothing was started, so nothing is followed.
    expect(statusRegion()).toBeEmptyDOMElement();
  });

  it("turns the already-running 409 into a link to the run that is actually in flight", async () => {
    stubApi(
      routesFor(VALIDATABLE_PERMISSIONS, {
        "POST /library/pkg_own/validation-runs": apiErrorRoute(
          409,
          "VALIDATION_ALREADY_RUNNING",
          "A validation run is already in progress for this draft.",
          [{ entity_id: "pkg_own", request_id: "cpr_7", validation_run_id: "vrun_1" }],
        ),
        "GET /validation-runs/": runRow("running"),
      }),
    );
    renderPage();
    await openDetail();
    await submitValidation();

    await screen.findByText(
      "VALIDATION_ALREADY_RUNNING: A validation run is already in progress for this draft.",
    );
    const region = statusRegion();
    // The existing run is followed rather than a duplicate being offered.
    await waitFor(() => expect(region).toHaveTextContent("running"));
    expect(region).toHaveTextContent("vrun_1");
    expect(region).toHaveTextContent("Nothing new was started");
  });

  it("renders the 422 when the server refuses a package with no validation pipeline", async () => {
    stubApi(
      routesFor(VALIDATABLE_PERMISSIONS, {
        "POST /library/pkg_own/validation-runs": apiErrorRoute(
          422,
          "VALIDATION_PIPELINE_UNAVAILABLE",
          "This package has no validation pipeline; validation cannot be requested for it.",
        ),
      }),
    );
    renderPage();
    await openDetail();
    await submitValidation();

    await screen.findByText(
      "VALIDATION_PIPELINE_UNAVAILABLE: This package has no validation pipeline; " +
        "validation cannot be requested for it.",
    );
    expect(statusRegion()).toBeEmptyDOMElement();
  });

  it("renders the 403 verbatim — a visible button is never the authorization", async () => {
    stubApi(
      routesFor(VALIDATABLE_PERMISSIONS, {
        "POST /library/pkg_own/validation-runs": apiErrorRoute(
          403,
          "ACCESS_DENIED",
          "You can only edit resources you own.",
        ),
      }),
    );
    renderPage();
    await openDetail();
    await submitValidation();

    await screen.findByText("You can only edit resources you own.");
    expect(statusRegion()).toBeEmptyDOMElement();
  });

  // --- boundaries this slice must NOT cross ------------------------------------------

  it("refetches the catalog list and detail after a successful admission", async () => {
    const fetchMock = stubApi(routesFor(VALIDATABLE_PERMISSIONS));
    renderPage();
    await openDetail();
    const readsBefore = fetchMock.mock.calls.filter(
      ([url, init]) =>
        String(url).includes("/library") && (init?.method ?? "GET").toUpperCase() === "GET",
    ).length;

    await submitValidation();

    await waitFor(() => {
      const readsAfter = fetchMock.mock.calls.filter(
        ([url, init]) =>
          String(url).includes("/library") && (init?.method ?? "GET").toUpperCase() === "GET",
      ).length;
      expect(readsAfter).toBeGreaterThan(readsBefore);
    });
  });

  it("leaves Request Approval a separate action with its own unchanged request", async () => {
    const fetchMock = stubApi(routesFor(VALIDATABLE_PERMISSIONS));
    renderPage();
    await openDetail();
    await submitValidation();
    await waitFor(() => expect(statusRegion()).toHaveTextContent("queued"));

    // Validation did not approve anything; approval is still an explicit, separate call.
    fireEvent.click(screen.getByRole("button", { name: "Request Approval" }));
    await waitFor(() => {
      const call = fetchMock.mock.calls.find(
        ([url, init]) =>
          String(url).includes("/library/pkg_own/request-approval") &&
          (init?.method ?? "").toUpperCase() === "POST",
      );
      expect(call).toBeDefined();
      expect(JSON.parse(String(call![1]!.body))).toEqual({
        revision_id: "rev_1",
        expected_head_revision_id: "rev_1",
      });
    });
  });
});
