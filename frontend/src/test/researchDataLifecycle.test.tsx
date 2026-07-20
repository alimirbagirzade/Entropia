import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import { ResearchData } from "@/pages/ResearchData";
import { stubApi } from "./helpers/apiStub";

const ROW = {
  entity_id: "rd_1",
  revision_id: "rrev_2",
  revision_no: 2,
  revision_state: "verified",
  validation_status: "passed",
  display_name: "Binance OI 8h",
  category_key: "open_interest",
  custom_category: null,
  provider_name: "coinglass",
  usage_scope: "research_backtest",
  linked_market_dataset_revision_id: "mrev_9",
  event_time_semantics: "provider_snapshot_timestamp",
  available_time_policy: "fixed_delay",
  available_delay_seconds: 120,
  frequency_policy: "8h",
  source_timezone_mode: "utc",
  source_timezone_iana: null,
  content_hash: "sha256:c1",
  manifest_hash: "sha256:m1",
  owner_principal_id: "u_1",
  row_version: 4,
  lifecycle_state: "active",
  created_at: "2026-07-01T09:00:00+00:00",
};

const DATASETS_PAGE = { data: [ROW], meta: { cursor: null, has_more: false } };

const DETAIL_RD1 = {
  ...ROW,
  revisions: [
    { revision_id: "rrev_2", revision_no: 2, revision_state: "verified" },
    { revision_id: "rrev_1", revision_no: 1, revision_state: "approved" },
  ],
};

const REVISION_RESULT = { entity_id: "rd_1", revision_id: "rrev_3", revision_no: 3, row_version: 5 };
const TIME_POLICY_RESULT = { time_policy_id: "tp_1", entity_id: "rd_1", available_time_policy: "fixed_delay" };
const FIELD_RESULT = { field_definition_id: "fd_1", field_name: "oi_value" };
const FEATURE_RESULT = { feature_definition_id: "ff_1", feature_name: "oi_zscore" };
const APPROVE_RESULT = { entity_id: "rd_1", revision_id: "rrev_2", revision_state: "approved" };
const REVOKE_RESULT = { entity_id: "rd_1", revision_id: "rrev_1", revision_state: "approval_revoked" };

const BUNDLE_MEMBER = {
  research_revision_id: "rrev_2",
  research_content_hash: "sha256:c1",
  usage_scope: "research_backtest",
  market_dataset_revision_id: "mrev_9",
  market_content_hash: "sha256:mh",
};
const AGENT_BUNDLE = {
  bundle_kind: "agent_data_bundle",
  members: [BUNDLE_MEMBER],
  compiler_version: "research-bundle-v1",
  resolved_at: "2026-07-09T10:00:00+00:00",
  bundle_hash: "sha256:agent",
  task_id: "task_7",
};
const EVIDENCE_BUNDLE = {
  bundle_kind: "backtest_evidence_bundle",
  members: [BUNDLE_MEMBER],
  compiler_version: "research-bundle-v1",
  resolved_at: "2026-07-09T10:00:00+00:00",
  bundle_hash: "sha256:evidence",
  run_request_id: "run_3",
};

// Order matters for the fragment-matching stub: each action/detail fragment must
// precede shorter prefixes. Every rd_1 sub-path contains /research-datasets, and
// GET /research-datasets (list) is a substring of GET /research-datasets/rd_1.
const ROUTES = {
  "POST /research-datasets/rd_1/revisions": REVISION_RESULT,
  "POST /research-datasets/rd_1/time-policy": TIME_POLICY_RESULT,
  "POST /research-datasets/rd_1/field-definitions": FIELD_RESULT,
  "POST /research-datasets/rd_1/feature-definitions": FEATURE_RESULT,
  "POST /research-datasets/rd_1/approve": APPROVE_RESULT,
  "POST /research-datasets/rd_1/revoke": REVOKE_RESULT,
  "POST /research-datasets/bundles/agent": AGENT_BUNDLE,
  "POST /research-datasets/bundles/backtest-evidence": EVIDENCE_BUNDLE,
  "GET /research-datasets/rd_1": DETAIL_RD1,
  "GET /research-datasets": DATASETS_PAGE,
  // R2-08: the bundle composer picks the agent task from the workspace list and
  // the revise composer role-gates its raw payload via /me (non-admin here).
  "GET /agent-tasks": {
    tasks: [
      {
        task_id: "task_7",
        title: "Scan OI",
        task_type: "research",
        source: "human",
        priority: "normal",
        status: "running",
        stage: null,
        progress: null,
      },
    ],
    next_cursor: null,
  },
  "GET /me": {
    principal_id: "user_1",
    principal_type: "human",
    role: "user",
    is_admin: false,
    is_authenticated: true,
  },
};

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/research-data"]}>
        <ResearchData />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return client;
}

async function openDetail() {
  await screen.findByText("Binance OI 8h");
  fireEvent.click(screen.getAllByRole("button", { name: "Open" })[0]!);
  await screen.findByRole("button", { name: "Append revision" });
}

type Call = [unknown, RequestInit | undefined];

function findPost(fetchMock: { mock: { calls: unknown[][] } }, fragment: string): Call | undefined {
  return fetchMock.mock.calls.find(
    ([url, init]) => String(url).includes(fragment) && (init as RequestInit | undefined)?.method === "POST",
  ) as Call | undefined;
}

function headersOf(call: Call | undefined): Record<string, string> {
  return (call?.[1]?.headers ?? {}) as Record<string, string>;
}

function bodyOf(call: Call | undefined): Record<string, unknown> {
  return JSON.parse(String(call?.[1]?.body)) as Record<string, unknown>;
}

describe("Research Data revision lifecycle", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("appends a revision under OCC (If-Match rv-4 + Idempotency-Key)", async () => {
    const fetchMock = stubApi(ROUTES);
    renderPage();
    await openDetail();

    // R2-08 (GAP item 7): the md_…/rrev_… free-text inputs are gone — re-link
    // goes through the approved-market picker and the base revision through a
    // select over this dataset's own revisions.
    expect(screen.queryByLabelText(/Re-link market entity id/)).toBeNull();
    // Two market pickers render (setup card + re-link) — both are pickers,
    // neither is a free-text id input.
    expect(screen.getAllByRole("button", { name: "Choose market dataset" }).length).toBeGreaterThan(
      0,
    );
    expect(screen.getByLabelText("Base revision (optional)").tagName).toBe("SELECT");

    fireEvent.click(screen.getByRole("button", { name: "Append revision" }));
    expect(await screen.findByText(/Revision appended — rrev_3/)).toBeInTheDocument();

    const call = findPost(fetchMock, "/rd_1/revisions");
    const headers = headersOf(call);
    expect(headers["If-Match"]).toBe('"rv-4"');
    expect(headers["Idempotency-Key"]).toBeTruthy();
    const body = bodyOf(call);
    // The OCC token + entity id travel as the path/header, never in the body.
    expect(body.row_version).toBeUndefined();
    expect(body.entity_id).toBeUndefined();
    expect(body).toMatchObject({
      category: "open_interest",
      usage_scope: "research_backtest",
      timezone_mode: "utc",
      custom_category: null,
      timezone_iana: null,
      market_entity_id: null,
      display_name: null,
      provider_name: null,
      base_revision_id: null,
    });
  });

  it("sends custom_category + IANA only for other_custom / custom timezone", async () => {
    const fetchMock = stubApi(ROUTES);
    renderPage();
    await openDetail();

    fireEvent.change(screen.getByLabelText("Revision category"), { target: { value: "other_custom" } });
    fireEvent.change(screen.getByLabelText("Revision custom category"), {
      target: { value: "exchange_reserves" },
    });
    fireEvent.change(screen.getByLabelText("Revision timezone"), { target: { value: "custom" } });
    fireEvent.change(screen.getByLabelText("Revision IANA zone"), { target: { value: "America/New_York" } });
    fireEvent.click(screen.getByRole("button", { name: "Append revision" }));

    await screen.findByText(/Revision appended/);
    const body = bodyOf(findPost(fetchMock, "/rd_1/revisions"));
    expect(body.category).toBe("other_custom");
    expect(body.custom_category).toBe("exchange_reserves");
    expect(body.timezone_mode).toBe("custom");
    expect(body.timezone_iana).toBe("America/New_York");
  });

  it("sets a fixed-delay time policy with delay_seconds and no OCC header", async () => {
    const fetchMock = stubApi(ROUTES);
    renderPage();
    await openDetail();

    fireEvent.change(screen.getByLabelText("Available time policy"), { target: { value: "fixed_delay" } });
    fireEvent.change(screen.getByLabelText("Delay (seconds)"), { target: { value: "300" } });
    fireEvent.click(screen.getByRole("button", { name: "Set time policy" }));

    expect(await screen.findByText(/Time policy set/)).toBeInTheDocument();
    const call = findPost(fetchMock, "/rd_1/time-policy");
    const headers = headersOf(call);
    expect(headers["If-Match"]).toBeUndefined();
    expect(headers["Idempotency-Key"]).toBeUndefined();
    expect(bodyOf(call)).toMatchObject({
      event_time_semantics: "provider_event_timestamp",
      available_time_policy: "fixed_delay",
      timezone_mode: "utc",
      delay_seconds: 300,
      timezone_iana: null,
    });
  });

  it("sends delay_seconds null for a non-fixed available policy", async () => {
    const fetchMock = stubApi(ROUTES);
    renderPage();
    await openDetail();

    // The default policy (same_as_event_time) shows no delay input.
    expect(screen.queryByLabelText("Delay (seconds)")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Set time policy" }));

    await screen.findByText(/Time policy set/);
    const body = bodyOf(findPost(fetchMock, "/rd_1/time-policy"));
    expect(body.available_time_policy).toBe("same_as_event_time");
    expect(body.delay_seconds).toBeNull();
  });

  it("defines a field with all required metadata (no OCC header)", async () => {
    const fetchMock = stubApi(ROUTES);
    renderPage();
    await openDetail();

    fireEvent.change(screen.getByLabelText("Field name"), { target: { value: "oi_value" } });
    fireEvent.change(screen.getByLabelText("Semantic type"), { target: { value: "float" } });
    fireEvent.change(screen.getByLabelText("Measurement method"), { target: { value: "sum" } });
    fireEvent.change(screen.getByLabelText("Null semantics"), { target: { value: "missing" } });
    fireEvent.change(screen.getByLabelText("Event time source"), { target: { value: "snapshot" } });
    fireEvent.change(screen.getByLabelText("Availability rule"), { target: { value: "t+2m" } });
    fireEvent.change(screen.getByLabelText("Allowed usage"), { target: { value: "backtest" } });
    fireEvent.click(screen.getByRole("button", { name: "Define field" }));

    expect(await screen.findByText(/Field defined — oi_value/)).toBeInTheDocument();
    const call = findPost(fetchMock, "/rd_1/field-definitions");
    expect(headersOf(call)["Idempotency-Key"]).toBeUndefined();
    expect(bodyOf(call)).toMatchObject({
      field_name: "oi_value",
      semantic_type: "float",
      measurement_method: "sum",
      null_semantics: "missing",
      event_time_source: "snapshot",
      availability_rule: "t+2m",
      allowed_usage: "backtest",
      unit_or_scale: null,
    });
  });

  it("defines a feature with a JSON definition object", async () => {
    const fetchMock = stubApi(ROUTES);
    renderPage();
    await openDetail();

    fireEvent.change(screen.getByLabelText("Feature name"), { target: { value: "oi_zscore" } });
    fireEvent.change(screen.getByLabelText("Feature definition (JSON object)"), {
      target: { value: '{"window":14}' },
    });
    fireEvent.click(screen.getByRole("button", { name: "Define feature" }));

    expect(await screen.findByText(/Feature defined — oi_zscore/)).toBeInTheDocument();
    expect(bodyOf(findPost(fetchMock, "/rd_1/feature-definitions"))).toMatchObject({
      feature_name: "oi_zscore",
      definition: { window: 14 },
      feature_version: 1,
      approval_state: null,
    });
  });

  it("approves a revision under OCC (Admin, If-Match rv-4 + Idempotency-Key)", async () => {
    const fetchMock = stubApi(ROUTES);
    renderPage();
    await openDetail();

    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    expect(
      await screen.findByText((_, node) => node?.textContent === "rrev_2 is now approved."),
    ).toBeInTheDocument();

    const call = findPost(fetchMock, "/rd_1/approve");
    const headers = headersOf(call);
    expect(headers["If-Match"]).toBe('"rv-4"');
    expect(headers["Idempotency-Key"]).toBeTruthy();
    expect(bodyOf(call)).toEqual({ revision_id: "rrev_2", note: null });
  });

  it("revokes an approval under OCC on the selected revision", async () => {
    const fetchMock = stubApi(ROUTES);
    renderPage();
    await openDetail();

    fireEvent.change(screen.getByLabelText("Revision to decide"), { target: { value: "rrev_1" } });
    fireEvent.click(screen.getByRole("button", { name: "Revoke" }));
    expect(
      await screen.findByText((_, node) => node?.textContent === "rrev_1 is now approval_revoked."),
    ).toBeInTheDocument();

    const call = findPost(fetchMock, "/rd_1/revoke");
    expect(headersOf(call)["If-Match"]).toBe('"rv-4"');
    expect(bodyOf(call)).toEqual({ revision_id: "rrev_1", note: null });
  });

  it("surfaces the Admin denial verbatim on approve (403)", async () => {
    stubApi({
      ...ROUTES,
      "POST /research-datasets/rd_1/approve": () => {
        throw new Error("APPROVAL_REQUIRES_ADMIN: Approval requires Admin privileges.");
      },
    });
    renderPage();
    await openDetail();

    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    expect(
      await screen.findByText("APPROVAL_REQUIRES_ADMIN: Approval requires Admin privileges."),
    ).toBeInTheDocument();
  });

  it("compiles an agent bundle (no Idempotency-Key) and renders the sealed hash + members", async () => {
    const fetchMock = stubApi(ROUTES);
    renderPage();
    await openDetail();

    // R2-08: the task is PICKED from the agent workspace list — the option must
    // load before the select can change; the immutable id travels system-side.
    await screen.findByRole("option", { name: "Scan OI · running" });
    fireEvent.change(screen.getByLabelText("Agent task (optional)"), {
      target: { value: "task_7" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Compile agent bundle" }));

    expect(await screen.findByText(/agent_data_bundle sealed/)).toBeInTheDocument();
    expect(screen.getByText("sha256:agent")).toBeInTheDocument();
    const call = findPost(fetchMock, "/bundles/agent");
    expect(headersOf(call)["Idempotency-Key"]).toBeUndefined();
    expect(bodyOf(call)).toEqual({ research_revision_ids: ["rrev_2"], task_id: "task_7" });
  });

  it("compiles an evidence bundle with the run request id", async () => {
    const fetchMock = stubApi(ROUTES);
    renderPage();
    await openDetail();

    fireEvent.change(screen.getByLabelText("Run request id (optional)"), { target: { value: "run_3" } });
    fireEvent.click(screen.getByRole("button", { name: "Compile evidence bundle" }));

    expect(await screen.findByText(/backtest_evidence_bundle sealed/)).toBeInTheDocument();
    expect(bodyOf(findPost(fetchMock, "/bundles/backtest-evidence"))).toEqual({
      research_revision_ids: ["rrev_2"],
      run_request_id: "run_3",
    });
  });
});
