import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import { FutureDev } from "@/pages/FutureDev";
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

const CAPABILITIES = { capabilities: [SHADOW_CAP, PLACEHOLDER_CAP], count: 2 };

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

const NO_OUTPUT_HISTORY =
  "No output exists because this capability has not produced an operational artifact in the current state.";

// apiStub matches the FIRST fragment contained in the URL — the detail route
// must precede the "/capabilities" list prefix it contains. Output history GETs
// default to empty so every existing test that renders FutureDev stays clean.
function baseRoutes(onTransition?: (init?: RequestInit) => unknown) {
  return {
    "GET /future-dev/graphic_view/overview": OVERVIEW,
    "POST /capabilities/graphic_view/lifecycle-transitions":
      onTransition ?? TRANSITION_RESULT,
    "POST /view-datasets/query": VIEW_DATASET_RESULT,
    "POST /analysis-artifacts": ARTIFACT_RESULT,
    "GET /capabilities/graphic_view": DETAIL,
    "GET /capabilities": CAPABILITIES,
    "GET /view-datasets": EMPTY_VIEW_HISTORY,
    "GET /analysis-artifacts": EMPTY_ARTIFACT_HISTORY,
  };
}

function renderFutureDev() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/future-dev"]}>
        <FutureDev />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return client;
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
    // Shadow badge appears on the registry row AND the Graphic View card.
    expect((await screen.findAllByText("shadow")).length).toBeGreaterThanOrEqual(1);
  });

  it("loads the detail projection with gate states and provenance on View", async () => {
    stubApi(baseRoutes());
    renderFutureDev();
    await openGraphicViewDetail();
    expect((screen.getByRole("checkbox", { name: "domain" }) as HTMLInputElement).checked).toBe(
      true,
    );
    expect((screen.getByRole("checkbox", { name: "ui" }) as HTMLInputElement).checked).toBe(false);
    expect(screen.getByText(/by hu_admin/)).toBeTruthy();
  });

  it("offers only the legal doc-22 targets for the current state", async () => {
    stubApi(baseRoutes());
    renderFutureDev();
    await openGraphicViewDetail();
    const select = screen.getByRole("combobox", { name: "Target state" }) as HTMLSelectElement;
    // shadow -> limited is the single legal edge (doc 22 §9.1).
    expect(Array.from(select.options).map((option) => option.value)).toEqual(["limited"]);
  });

  it("requires a non-empty reason before a transition can be applied", async () => {
    stubApi(baseRoutes());
    renderFutureDev();
    await openGraphicViewDetail();
    const apply = screen.getByRole("button", { name: "Apply transition" }) as HTMLButtonElement;
    expect(apply.disabled).toBe(true);
    fireEvent.change(screen.getByRole("textbox", { name: "Transition reason" }), {
      target: { value: "promote to limited" },
    });
    expect(apply.disabled).toBe(false);
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
    fireEvent.change(screen.getByRole("textbox", { name: "Transition reason" }), {
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
    fireEvent.click(screen.getByRole("checkbox", { name: "ui" }));
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

  it("renders the Graphic View placeholder overview verbatim", async () => {
    stubApi(baseRoutes());
    renderFutureDev();
    await screen.findByText(/reserved for future chart and visual-review development/);
    expect(screen.getByText("Price Chart")).toBeTruthy();
    expect(screen.getByText(/portfolio equity curves/)).toBeTruthy();
  });

  it("POSTs the pinned view-dataset refs with an Idempotency-Key and omits blank optional lists", async () => {
    let captured: RequestInit | undefined;
    stubApi({
      ...baseRoutes(),
      "POST /view-datasets/query": (init?: RequestInit) => {
        captured = init;
        return VIEW_DATASET_RESULT;
      },
    });
    renderFutureDev();
    await screen.findByText("Live Trade");
    fireEvent.change(screen.getByRole("textbox", { name: "Source manifest refs" }), {
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
    stubApi(baseRoutes());
    renderFutureDev();
    await screen.findByText("Live Trade");
    const prepare = screen.getByRole("button", {
      name: "Prepare view dataset",
    }) as HTMLButtonElement;
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
    const keys: string[] = [];
    stubApi({
      ...baseRoutes(),
      "POST /view-datasets/query": (init?: RequestInit) => {
        keys.push((init?.headers as Record<string, string>)["Idempotency-Key"] ?? "");
        throw new Error("CAPABILITY_NOT_ACTIVE: Capability 'graphic_view' is not active.");
      },
    });
    renderFutureDev();
    await screen.findByText("Live Trade");
    fireEvent.change(screen.getByRole("textbox", { name: "Source manifest refs" }), {
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

  it("scopes the gating-capability display to the selected artifact type", async () => {
    stubApi(baseRoutes());
    renderFutureDev();
    await screen.findByText("Live Trade");
    const select = screen.getByRole("combobox", { name: "Artifact type" }) as HTMLSelectElement;
    // Sorted server `allowed` order — first option is backtest_review.
    expect(select.value).toBe("backtest_review");
    expect(screen.getByText("backtest_review", { selector: "code" })).toBeTruthy();
    fireEvent.change(select, { target: { value: "sensitivity" } });
    expect(screen.getByText("parameter_fields", { selector: "code" })).toBeTruthy();
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
    await screen.findByText("Live Trade");
    fireEvent.change(screen.getByRole("combobox", { name: "Artifact type" }), {
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

  it("renders the futureDevNoHistory.empty copy when a capability has no output", async () => {
    stubApi(baseRoutes());
    renderFutureDev();
    await screen.findByText("Live Trade");
    // Both the View Dataset and the Analysis Artifact histories are empty here.
    const empties = await screen.findAllByText(NO_OUTPUT_HISTORY);
    expect(empties.length).toBe(2);
  });

  it("renders the owner's View Dataset history rows", async () => {
    stubApi({ ...baseRoutes(), "GET /view-datasets": VIEW_DATASET_HISTORY });
    renderFutureDev();
    await screen.findByText("vds_01");
    expect(screen.getByText("View Dataset history")).toBeTruthy();
    // The Analysis Artifact history is still empty in this scenario.
    expect(screen.getByText(NO_OUTPUT_HISTORY)).toBeTruthy();
  });

  it("renders the owner's Analysis Artifact history with a type filter", async () => {
    stubApi({ ...baseRoutes(), "GET /analysis-artifacts": ARTIFACT_HISTORY });
    renderFutureDev();
    await screen.findByText("art_01");
    expect(screen.getByRole("combobox", { name: "Filter artifact type" })).toBeTruthy();
  });

  it("opens the owner-scoped View Dataset detail on select", async () => {
    stubApi({
      // The detail fragment MUST precede the list prefix it contains.
      "GET /view-datasets/vds_01": VIEW_DATASET_DETAIL,
      ...baseRoutes(),
      "GET /view-datasets": VIEW_DATASET_HISTORY,
    });
    renderFutureDev();
    await screen.findByText("vds_01");
    // The View Dataset history row's View button is the last one on the page.
    const viewButtons = screen.getAllByRole("button", { name: "View" });
    fireEvent.click(viewButtons[viewButtons.length - 1]);
    // The owner provenance only exists on the detail projection.
    await screen.findByText("hu_user");
  });
});
