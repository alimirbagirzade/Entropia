import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import { FUTURE_DEV_SUBPAGES } from "@/app/nav";
import { FutureDev } from "@/pages/FutureDev";
import { FutureDevCapability } from "@/pages/FutureDevCapability";
import { FutureDevGraphicView } from "@/pages/FutureDevGraphicView";
import { stubApi } from "./helpers/apiStub";

const SHADOW_CAP = {
  capability_key: "graphic_view",
  title: "Graphic View",
  menu_path: "Future Dev > Graphic View",
  lifecycle_state: "shadow",
  is_operational: false,
  ui_surface_version: "v18-placeholder",
  domain_contract_version: "v1",
  registry_version: 4,
  enabled_at: null,
  retirement_at: null,
  status_message: "Shadow-state capability — internal parity runs only.",
};

const PLACEHOLDER_CAP = {
  capability_key: "live_trade",
  title: "Live Trade",
  menu_path: "Future Dev > Live Trade",
  lifecycle_state: "placeholder",
  is_operational: false,
  ui_surface_version: "v18-placeholder",
  domain_contract_version: null,
  registry_version: 1,
  enabled_at: null,
  retirement_at: null,
  status_message: "This capability is currently a controlled Future Dev placeholder.",
};

// §UI-22 gating fixtures: two OPERATIONAL gating capabilities so the Analysis
// Artifact composer renders (backtest_review + parameter_fields gate 5 of the
// 7 artifact types; signal_intelligence/regime_research stay non-operational).
const BACKTEST_CAP = {
  capability_key: "backtest_review",
  title: "Backtest Review",
  menu_path: "Future Dev > AI Operations > Backtest Review",
  lifecycle_state: "active",
  is_operational: true,
  ui_surface_version: "v18-placeholder",
  domain_contract_version: "v1",
  registry_version: 6,
  enabled_at: "2026-07-01T09:00:00+00:00",
  retirement_at: null,
  status_message: "Active capability — operational commands enabled.",
};

const PARAM_CAP = {
  capability_key: "parameter_fields",
  title: "Parameter Fields",
  menu_path: "Future Dev > Research > Parameter Fields",
  lifecycle_state: "limited",
  is_operational: true,
  ui_surface_version: "v18-placeholder",
  domain_contract_version: "v1",
  registry_version: 3,
  enabled_at: "2026-07-02T09:00:00+00:00",
  retirement_at: null,
  status_message: "Limited-use capability — approved surfaces only.",
};

const CAPABILITIES = {
  capabilities: [SHADOW_CAP, PLACEHOLDER_CAP, BACKTEST_CAP, PARAM_CAP],
  count: 4,
};

// No operational gating capability at all — §UI-22: the composer must hide.
const INACTIVE_CAPABILITIES = { capabilities: [SHADOW_CAP, PLACEHOLDER_CAP], count: 2 };

// Server-truth identity projections (/me) — the §UI-22 permission gates.
const ME_ADMIN = {
  principal_id: "hu_admin",
  principal_type: "human",
  role: "admin",
  is_admin: true,
  is_authenticated: true,
};
const ME_USER = {
  principal_id: "hu_user",
  principal_type: "human",
  role: "researcher",
  is_admin: false,
  is_authenticated: true,
};
const ME_ANON = {
  principal_id: null,
  principal_type: "anonymous",
  role: null,
  is_admin: false,
  is_authenticated: false,
};

const DETAIL = {
  ...SHADOW_CAP,
  dependency_snapshot: {
    gates: {
      domain: true,
      data: { complete: true, note: "parquet lineage pinned" },
      policy: true,
      ui: false,
      backend: true,
      verification: true,
      rollback: true,
    },
  },
  changed_by_actor_id: "hu_admin",
  change_reason: "shadow rollout",
};

const OVERVIEW = {
  capability_key: "graphic_view",
  title: "Graphic View",
  lifecycle_state: "shadow",
  is_operational: false,
  registry_version: 4,
  intro: "Graphic View is reserved for future chart and visual-review development.",
  cards: [
    { title: "Price Chart", text: "Future: entry and exit markers." },
    { title: "Equity Curve", text: "Future: portfolio equity curves." },
  ],
  status_message: "Shadow-state capability — internal parity runs only.",
};

// The same overview once graphic_view is operational — the View Dataset
// surface may render (§UI-22: capability active + authenticated identity).
const OPERATIONAL_OVERVIEW = {
  ...OVERVIEW,
  lifecycle_state: "limited",
  is_operational: true,
  registry_version: 5,
  status_message: "Limited-use capability — approved surfaces only.",
};

const TRANSITION_RESULT = {
  capability_id: "fcap_graphic_view",
  capability_key: "graphic_view",
  title: "Graphic View",
  menu_path: "Future Dev > Graphic View",
  lifecycle_state: "limited",
  ui_surface_version: "v18-placeholder",
  domain_contract_version: "v1",
  registry_version: 5,
  enabled_at: "2026-07-06T12:00:00+00:00",
  retirement_at: null,
  activation_event_id: "cev_01",
  correlation_id: "corr_1",
};

const VIEW_DATASET_RESULT = {
  view_dataset_id: "vds_01",
  capability_key: "graphic_view",
  source_manifest_refs: ["man_1", "man_2"],
  series_refs: [],
  marker_refs: ["mk_1"],
  range_spec: null,
  schema_version: "v1",
  correlation_id: "corr_2",
};

const ARTIFACT_RESULT = {
  artifact_id: "art_01",
  artifact_type: "monte_carlo",
  capability_key: "backtest_review",
  input_manifest_refs: ["man_9"],
  method_version: "mc-v1",
  output_ref: null,
  correlation_id: "corr_3",
};

// Output-history projections (doc 22 §7) — row/detail mirror queries/capability.py.
const VIEW_DATASET_ROW = {
  view_dataset_id: "vds_01",
  capability_key: "graphic_view",
  schema_version: "v1",
  source_manifest_refs: ["man_1", "man_2"],
  series_refs: [],
  marker_refs: ["mk_1"],
  range_spec: null,
  deletion_state: "active",
  row_version: 1,
  created_at: "2026-07-06T12:00:00+00:00",
};
const VIEW_DATASET_DETAIL = {
  ...VIEW_DATASET_ROW,
  owner_principal_id: "hu_user",
  created_by_principal_id: "hu_user",
};
const VIEW_DATASET_HISTORY = {
  data: [VIEW_DATASET_ROW],
  meta: { cursor: null, has_more: false, limit: 20 },
};
const EMPTY_VIEW_HISTORY = { data: [], meta: { cursor: null, has_more: false, limit: 20 } };

const ARTIFACT_ROW = {
  artifact_id: "art_01",
  artifact_type: "monte_carlo",
  capability_key: "backtest_review",
  input_manifest_refs: ["man_9"],
  method_version: "mc-v1",
  output_ref: null,
  deletion_state: "active",
  row_version: 1,
  created_at: "2026-07-06T12:05:00+00:00",
};
const ARTIFACT_HISTORY = {
  data: [ARTIFACT_ROW],
  meta: { cursor: null, has_more: false, limit: 20, artifact_type: null },
};
const EMPTY_ARTIFACT_HISTORY = {
  data: [],
  meta: { cursor: null, has_more: false, limit: 20, artifact_type: null },
};

// Lifecycle-transition timeline (doc 22 §9, §13) — mirrors queries/capability.py
// `_activation_event_view` + the {capability_key, capability_id, transitions,
// count} envelope.
const TRANSITIONS = {
  capability_key: "graphic_view",
  capability_id: "fcap_graphic_view",
  transitions: [
    {
      event_id: "cev_1",
      capability_key: "graphic_view",
      from_state: "internal",
      to_state: "shadow",
      actor_principal_id: "hu_admin",
      reason: "internal parity complete",
      snapshot_checksum: "sum_1",
      prior_registry_version: 3,
      resulting_registry_version: 4,
      correlation_id: "corr_9",
      occurred_at: "2026-07-06T11:00:00+00:00",
    },
  ],
  count: 1,
};
const EMPTY_TRANSITIONS = {
  capability_key: "graphic_view",
  capability_id: "fcap_graphic_view",
  transitions: [],
  count: 0,
};

const NO_OUTPUT_HISTORY =
  "No output exists because this capability has not produced an operational artifact in the current state.";

// apiStub matches the FIRST fragment contained in the URL — the detail route
// must precede the "/capabilities" list prefix it contains. Output history GETs
// default to empty so every existing test that renders FutureDev stays clean.
function baseRoutes(onTransition?: (init?: RequestInit) => unknown) {
  return {
    "POST /capabilities/graphic_view/lifecycle-transitions":
      onTransition ?? TRANSITION_RESULT,
    "POST /analysis-artifacts": ARTIFACT_RESULT,
    // The lifecycle-transitions GET must precede the "/capabilities/graphic_view"
    // detail prefix it contains (apiStub matches the first fragment in the URL).
    "GET /capabilities/graphic_view/lifecycle-transitions": EMPTY_TRANSITIONS,
    "GET /capabilities/graphic_view": DETAIL,
    "GET /capabilities": CAPABILITIES,
    "GET /analysis-artifacts": EMPTY_ARTIFACT_HISTORY,
    "GET /me": ME_ADMIN,
  };
}

// Routes for the /future-dev/graphic-view page (overview + gated View Dataset
// surface). Operational + authenticated by default; tests override per case.
function graphicViewRoutes(onPrepare?: (init?: RequestInit) => unknown) {
  return {
    "GET /future-dev/graphic-view/overview": OPERATIONAL_OVERVIEW,
    "POST /view-datasets/query": onPrepare ?? VIEW_DATASET_RESULT,
    "GET /view-datasets": EMPTY_VIEW_HISTORY,
    "GET /me": ME_ADMIN,
  };
}

function renderWithProviders(ui: JSX.Element, initialEntry: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialEntry]}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
  return client;
}

function renderFutureDev() {
  return renderWithProviders(<FutureDev />, "/future-dev");
}

function renderGraphicView() {
  return renderWithProviders(<FutureDevGraphicView />, "/future-dev/graphic-view");
}

async function openGraphicViewDetail() {
  await screen.findByText("Live Trade");
  fireEvent.click(screen.getAllByRole("button", { name: "View" })[0]);
  await screen.findByText(/shadow rollout/);
}

describe("Future Dev page", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders the capability registry rows from the server projection", async () => {
    stubApi(baseRoutes());
    renderFutureDev();
    await screen.findByText("Live Trade");
    expect(screen.getByText("Future Dev > Live Trade")).toBeTruthy();
    expect(screen.getByText("placeholder")).toBeTruthy();
    expect((await screen.findAllByText("shadow")).length).toBeGreaterThanOrEqual(1);
    // UI-22: a capability with a dedicated sub-page links there from its row.
    const graphicLink = screen.getByRole("link", { name: "Graphic View" });
    expect(graphicLink.getAttribute("href")).toBe("/future-dev/graphic-view");
  });

  it("loads the detail projection with gate states and provenance on View", async () => {
    stubApi(baseRoutes());
    renderFutureDev();
    await openGraphicViewDetail();
    expect(
      ((await screen.findByRole("checkbox", { name: "domain" })) as HTMLInputElement).checked,
    ).toBe(true);
    expect((screen.getByRole("checkbox", { name: "ui" }) as HTMLInputElement).checked).toBe(false);
    expect(screen.getByText(/by hu_admin/)).toBeTruthy();
  });

  it("offers only the legal doc-22 targets for the current state", async () => {
    stubApi(baseRoutes());
    renderFutureDev();
    await openGraphicViewDetail();
    const select = (await screen.findByRole("combobox", {
      name: "Target state",
    })) as HTMLSelectElement;
    // shadow -> limited is the single legal edge (doc 22 §9.1).
    expect(Array.from(select.options).map((option) => option.value)).toEqual(["limited"]);
  });

  it("requires a non-empty reason before a transition can be applied", async () => {
    stubApi(baseRoutes());
    renderFutureDev();
    await openGraphicViewDetail();
    const apply = (await screen.findByRole("button", {
      name: "Apply transition",
    })) as HTMLButtonElement;
    expect(apply.disabled).toBe(true);
    fireEvent.change(screen.getByRole("textbox", { name: "Transition reason" }), {
      target: { value: "promote to limited" },
    });
    expect(apply.disabled).toBe(false);
  });

  it("hides the lifecycle transition composer for a non-Admin identity", async () => {
    stubApi({ ...baseRoutes(), "GET /me": ME_USER });
    renderFutureDev();
    await openGraphicViewDetail();
    // §UI-22: the registry OPERATION is exposed only with Admin permission —
    // the detail read surface (gate provenance, timeline) stays visible.
    expect(await screen.findByText(/Lifecycle transitions are an Admin operation/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Apply transition" })).toBeNull();
    expect(screen.queryByRole("checkbox", { name: "domain" })).toBeNull();
  });

  it("POSTs the OCC registry version with an Idempotency-Key and omits an untouched snapshot", async () => {
    let captured: RequestInit | undefined;
    stubApi(
      baseRoutes((init) => {
        captured = init;
        return TRANSITION_RESULT;
      }),
    );
    renderFutureDev();
    await openGraphicViewDetail();
    fireEvent.change(await screen.findByRole("textbox", { name: "Transition reason" }), {
      target: { value: "promote to limited" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Apply transition" }));
    await screen.findByText(/Transition accepted/);
    const body = JSON.parse(String(captured?.body)) as Record<string, unknown>;
    expect(body.to_state).toBe("limited");
    expect(body.expected_registry_version).toBe(4);
    expect(body.reason).toBe("promote to limited");
    expect("dependency_snapshot" in body).toBe(false);
    expect((captured?.headers as Record<string, string>)["Idempotency-Key"]).toBeTruthy();
  });

  it("sends an edited gate checklist while preserving server-side note objects", async () => {
    let captured: RequestInit | undefined;
    stubApi(
      baseRoutes((init) => {
        captured = init;
        return TRANSITION_RESULT;
      }),
    );
    renderFutureDev();
    await openGraphicViewDetail();
    fireEvent.click(await screen.findByRole("checkbox", { name: "ui" }));
    fireEvent.change(screen.getByRole("textbox", { name: "Transition reason" }), {
      target: { value: "ui gate complete" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Apply transition" }));
    await screen.findByText(/Transition accepted/);
    const body = JSON.parse(String(captured?.body)) as {
      dependency_snapshot: { gates: Record<string, unknown> };
    };
    expect(body.dependency_snapshot.gates.ui).toBe(true);
    expect(body.dependency_snapshot.gates.data).toEqual({
      complete: true,
      note: "parquet lineage pinned",
    });
  });

  it("offers only artifact types whose gating capability is operational", async () => {
    stubApi(baseRoutes());
    renderFutureDev();
    const region = await screen.findByRole("region", { name: "Analysis Artifacts" });
    const select = (await within(region).findByRole("combobox", {
      name: "Artifact type",
    })) as HTMLSelectElement;
    // backtest_review (active) + parameter_fields (limited) gate exactly these
    // five types; signal_intelligence/regime_research types never appear.
    expect(Array.from(select.options).map((option) => option.value)).toEqual([
      "backtest_review",
      "monte_carlo",
      "parameter_fields",
      "sensitivity",
      "walk_forward",
    ]);
    expect(select.value).toBe("backtest_review");
    expect(within(region).getByText("backtest_review", { selector: "code" })).toBeTruthy();
    fireEvent.change(select, { target: { value: "sensitivity" } });
    expect(within(region).getByText("parameter_fields", { selector: "code" })).toBeTruthy();
  });

  it("hides the analysis artifact composer while no gating capability is operational", async () => {
    stubApi({ ...baseRoutes(), "GET /capabilities": INACTIVE_CAPABILITIES });
    renderFutureDev();
    await screen.findByText("Live Trade");
    // §UI-22 acceptance: an inactive capability exposes no usable operational
    // control — no composer, no submit; the doc 22 §7 read surface stays.
    expect(await screen.findByText(/Analysis Artifact commands are hidden/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Create analysis artifact" })).toBeNull();
    expect(screen.queryByRole("combobox", { name: "Artifact type" })).toBeNull();
    expect(await screen.findByText(NO_OUTPUT_HISTORY)).toBeTruthy();
  });

  it("POSTs the analysis artifact with an Idempotency-Key and reports the created id", async () => {
    let captured: RequestInit | undefined;
    stubApi({
      ...baseRoutes(),
      "POST /analysis-artifacts": (init?: RequestInit) => {
        captured = init;
        return ARTIFACT_RESULT;
      },
    });
    renderFutureDev();
    fireEvent.change(await screen.findByRole("combobox", { name: "Artifact type" }), {
      target: { value: "monte_carlo" },
    });
    fireEvent.change(screen.getByRole("textbox", { name: "Input manifest refs" }), {
      target: { value: "man_9" },
    });
    fireEvent.change(screen.getByRole("textbox", { name: "Method version" }), {
      target: { value: "mc-v1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create analysis artifact" }));
    await screen.findByText(/Analysis artifact created/);
    expect(screen.getByText("art_01")).toBeTruthy();
    const body = JSON.parse(String(captured?.body)) as Record<string, unknown>;
    expect(body.artifact_type).toBe("monte_carlo");
    expect(body.input_manifest_refs).toEqual(["man_9"]);
    expect(body.method_version).toBe("mc-v1");
    // A blank output ref never travels.
    expect("output_ref" in body).toBe(false);
    expect((captured?.headers as Record<string, string>)["Idempotency-Key"]).toBeTruthy();
  });

  it("renders the futureDevNoHistory.empty copy when the capability has no output", async () => {
    stubApi(baseRoutes());
    renderFutureDev();
    await screen.findByText("Live Trade");
    // The root page hosts exactly one output history (Analysis Artifacts);
    // the View Dataset history lives on /future-dev/graphic-view.
    const empties = await screen.findAllByText(NO_OUTPUT_HISTORY);
    expect(empties.length).toBe(1);
  });

  it("renders the owner's Analysis Artifact history with a type filter", async () => {
    stubApi({ ...baseRoutes(), "GET /analysis-artifacts": ARTIFACT_HISTORY });
    renderFutureDev();
    await screen.findByText("art_01");
    expect(screen.getByRole("combobox", { name: "Filter artifact type" })).toBeTruthy();
  });

  it("renders the immutable transition timeline in the capability detail", async () => {
    stubApi({
      ...baseRoutes(),
      "GET /capabilities/graphic_view/lifecycle-transitions": TRANSITIONS,
    });
    renderFutureDev();
    await openGraphicViewDetail();
    // The reason cell only appears once the timeline query resolves.
    expect(await screen.findByText("internal parity complete")).toBeTruthy();
    expect(screen.getByText("Transition history")).toBeTruthy();
    // The from-state badge renders from the server projection.
    expect(screen.getByText("internal")).toBeTruthy();
  });

  it("shows the empty transition state for a never-transitioned capability", async () => {
    // baseRoutes defaults the lifecycle-transitions GET to EMPTY_TRANSITIONS.
    stubApi(baseRoutes());
    renderFutureDev();
    await openGraphicViewDetail();
    expect(
      await screen.findByText("No lifecycle transition has been recorded for this capability yet."),
    ).toBeTruthy();
  });
});

describe("Future Dev / Graphic View page", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders the documented intro and the static placeholder cards verbatim", async () => {
    stubApi({ ...graphicViewRoutes(), "GET /future-dev/graphic-view/overview": OVERVIEW });
    renderGraphicView();
    await screen.findByText(/reserved for future chart and visual-review development/);
    expect(screen.getByText("Price Chart")).toBeTruthy();
    expect(screen.getByText(/portfolio equity curves/)).toBeTruthy();
  });

  it("renders a pure placeholder while the capability is not operational", async () => {
    stubApi({ ...graphicViewRoutes(), "GET /future-dev/graphic-view/overview": OVERVIEW });
    renderGraphicView();
    await screen.findByText(/reserved for future chart and visual-review development/);
    // §UI-22: in placeholder state the page renders NO input, table,
    // lifecycle control or operational form — not a single control.
    expect(screen.queryAllByRole("button")).toHaveLength(0);
    expect(screen.queryAllByRole("textbox")).toHaveLength(0);
    expect(screen.queryAllByRole("table")).toHaveLength(0);
    expect(screen.queryByText("Prepare View Dataset")).toBeNull();
    expect(
      screen.getByText(/Operational View Dataset commands unlock when this capability reaches/),
    ).toBeTruthy();
  });

  it("hides the View Dataset surface from an unauthenticated identity", async () => {
    stubApi({ ...graphicViewRoutes(), "GET /me": ME_ANON });
    renderGraphicView();
    await screen.findByText(/reserved for future chart and visual-review development/);
    expect(screen.queryByText("Prepare View Dataset")).toBeNull();
    expect(screen.queryAllByRole("textbox")).toHaveLength(0);
  });

  it("POSTs the pinned view-dataset refs with an Idempotency-Key and omits blank optional lists", async () => {
    let captured: RequestInit | undefined;
    stubApi(
      graphicViewRoutes((init) => {
        captured = init;
        return VIEW_DATASET_RESULT;
      }),
    );
    renderGraphicView();
    fireEvent.change(await screen.findByRole("textbox", { name: "Source manifest refs" }), {
      target: { value: "man_1\n  man_2  \n\n" },
    });
    fireEvent.change(screen.getByRole("textbox", { name: "Schema version" }), {
      target: { value: "v1" },
    });
    fireEvent.change(screen.getByRole("textbox", { name: "Marker refs" }), {
      target: { value: "mk_1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Prepare view dataset" }));
    await screen.findByText(/View dataset prepared/);
    expect(screen.getByText("vds_01")).toBeTruthy();
    const body = JSON.parse(String(captured?.body)) as Record<string, unknown>;
    expect(body.source_manifest_refs).toEqual(["man_1", "man_2"]);
    expect(body.schema_version).toBe("v1");
    expect(body.marker_refs).toEqual(["mk_1"]);
    // Blank optional lists never travel — absent, not empty.
    expect("series_refs" in body).toBe(false);
    expect("range_spec" in body).toBe(false);
    expect((captured?.headers as Record<string, string>)["Idempotency-Key"]).toBeTruthy();
  });

  it("blocks a view-dataset submit until source refs and schema version are pinned", async () => {
    stubApi(graphicViewRoutes());
    renderGraphicView();
    const prepare = (await screen.findByRole("button", {
      name: "Prepare view dataset",
    })) as HTMLButtonElement;
    expect(prepare.disabled).toBe(true);
    fireEvent.change(screen.getByRole("textbox", { name: "Source manifest refs" }), {
      target: { value: "man_1" },
    });
    expect(prepare.disabled).toBe(true);
    fireEvent.change(screen.getByRole("textbox", { name: "Schema version" }), {
      target: { value: "v1" },
    });
    expect(prepare.disabled).toBe(false);
  });

  it("surfaces CAPABILITY_NOT_ACTIVE verbatim and retries with a fresh Idempotency-Key", async () => {
    // The client-side gate is display only over a cached projection — a stale
    // cache still dispatches and the SERVER denial renders verbatim (FD-02).
    const keys: string[] = [];
    stubApi(
      graphicViewRoutes((init) => {
        keys.push((init?.headers as Record<string, string>)["Idempotency-Key"] ?? "");
        throw new Error("CAPABILITY_NOT_ACTIVE: Capability 'graphic_view' is not active.");
      }),
    );
    renderGraphicView();
    fireEvent.change(await screen.findByRole("textbox", { name: "Source manifest refs" }), {
      target: { value: "man_1" },
    });
    fireEvent.change(screen.getByRole("textbox", { name: "Schema version" }), {
      target: { value: "v1" },
    });
    const prepare = screen.getByRole("button", { name: "Prepare view dataset" });
    fireEvent.click(prepare);
    await screen.findByText(/CAPABILITY_NOT_ACTIVE: Capability 'graphic_view' is not active\./);
    fireEvent.click(prepare);
    // A retry after a rejection is a NEW decision — never a replay of the key.
    await vi.waitFor(() => expect(keys).toHaveLength(2));
    expect(keys[0]).toBeTruthy();
    expect(keys[1]).toBeTruthy();
    expect(keys[0]).not.toBe(keys[1]);
  });

  it("renders the owner's View Dataset history and opens the owner-scoped detail", async () => {
    stubApi({
      // The detail fragment MUST precede the list prefix it contains.
      "GET /view-datasets/vds_01": VIEW_DATASET_DETAIL,
      ...graphicViewRoutes(),
      "GET /view-datasets": VIEW_DATASET_HISTORY,
    });
    renderGraphicView();
    await screen.findByText("vds_01");
    expect(screen.getByText("View Dataset history")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "View" }));
    // The owner provenance only exists on the detail projection.
    await screen.findByText("hu_user");
  });

  it("renders the futureDevNoHistory.empty copy for an operational capability with no output", async () => {
    stubApi(graphicViewRoutes());
    renderGraphicView();
    expect(await screen.findByText(NO_OUTPUT_HISTORY)).toBeTruthy();
  });
});

describe("Future Dev capability placeholder page", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  const BACKTEST_SUBPAGE = FUTURE_DEV_SUBPAGES.find(
    (subpage) => subpage.capabilityKey === "backtest_review",
  )!;
  const SIGNAL_SUBPAGE = FUTURE_DEV_SUBPAGES.find(
    (subpage) => subpage.capabilityKey === "signal_intelligence",
  )!;

  const SIGNAL_CAP = {
    ...PLACEHOLDER_CAP,
    capability_key: "signal_intelligence",
    title: "Signal Intelligence",
    menu_path: "Future Dev > AI Operations > Signal Intelligence",
    lifecycle_state: "designed",
    status_message: "Designed capability — implementation has not begun.",
  };

  function renderSubpage(subpage: typeof BACKTEST_SUBPAGE) {
    return renderWithProviders(<FutureDevCapability subpage={subpage} />, subpage.path);
  }

  it("renders the documented placeholder with zero operational controls", async () => {
    stubApi({
      "GET /capabilities": { capabilities: [SIGNAL_CAP], count: 1 },
      "GET /me": ME_ADMIN,
    });
    renderSubpage(SIGNAL_SUBPAGE);
    await screen.findByText(/Designed capability — implementation has not begun\./);
    expect(screen.getByText(/intentionally inactive in this prototype stage/)).toBeTruthy();
    // §UI-22: no input, table, lifecycle control or operational form — the
    // page renders no control at all in placeholder state.
    expect(screen.queryAllByRole("button")).toHaveLength(0);
    expect(screen.queryAllByRole("textbox")).toHaveLength(0);
    expect(screen.queryAllByRole("table")).toHaveLength(0);
    expect(screen.getByRole("link", { name: "Future Dev registry" })).toBeTruthy();
  });

  it("points at the registry for an operational capability instead of embedding controls", async () => {
    stubApi({
      "GET /capabilities": CAPABILITIES,
      "GET /me": ME_ADMIN,
    });
    renderSubpage(BACKTEST_SUBPAGE);
    await screen.findByText(/Active capability — operational commands enabled\./);
    expect(screen.getByText(/This capability is operational/)).toBeTruthy();
    expect(screen.queryAllByRole("textbox")).toHaveLength(0);
    expect(screen.queryAllByRole("table")).toHaveLength(0);
  });

  it("shows an honest empty state for a capability the server registry does not know", async () => {
    stubApi({
      "GET /capabilities": { capabilities: [], count: 0 },
      "GET /me": ME_ADMIN,
    });
    renderSubpage(SIGNAL_SUBPAGE);
    expect(await screen.findByText("Not registered")).toBeTruthy();
  });
});
