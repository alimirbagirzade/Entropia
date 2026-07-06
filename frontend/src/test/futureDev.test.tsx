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

// apiStub matches the FIRST fragment contained in the URL — the detail route
// must precede the "/capabilities" list prefix it contains.
function baseRoutes(onTransition?: (init?: RequestInit) => unknown) {
  return {
    "GET /future-dev/graphic_view/overview": OVERVIEW,
    "POST /capabilities/graphic_view/lifecycle-transitions":
      onTransition ?? TRANSITION_RESULT,
    "GET /capabilities/graphic_view": DETAIL,
    "GET /capabilities": CAPABILITIES,
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
});
