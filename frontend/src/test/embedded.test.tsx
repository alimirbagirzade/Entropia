import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import { parseSignatureParams } from "@/lib/esp";
import { Embedded } from "@/pages/Embedded";
import { stubApi } from "./helpers/apiStub";

// Doc 09 §14 / L4: resolver performance is N/A by nature — the availability
// label, never a fabricated zero.
const PERFORMANCE_NA = {
  net_profit: "not_applicable",
  backtest_ready: "not_applicable",
  oos_passed: "not_applicable",
};

const TRUSTED_ROW = {
  registry_id: "reg_1",
  canonical_key: "ta.rsi",
  package_entity_id: "esp_1",
  trusted_active_revision_id: "rev_r1",
  trust_state: "trusted_active",
  runtime_adapter: "python",
  registry_version: 4,
  replacement_revision_id: null,
  visibility_scope: "system",
  ...PERFORMANCE_NA,
};

const DEPRECATED_ROW = {
  ...TRUSTED_ROW,
  registry_id: "reg_2",
  canonical_key: "ta.sma",
  package_entity_id: "esp_2",
  trusted_active_revision_id: null,
  trust_state: "deprecated",
  replacement_revision_id: "rev_r9",
};

const REGISTRY_PAGE = {
  data: [TRUSTED_ROW, DEPRECATED_ROW],
  meta: { cursor: "ta.sma", has_more: true },
};

const ESP_DETAIL = {
  entity_id: "esp_1",
  revision_id: "rev_r1",
  revision_no: 2,
  package_kind: "embedded_system",
  visibility_scope: "system",
  validation_state: "passed",
  approval_state: "approved",
  content_hash: "sha256:esp",
  row_version: 5,
  lifecycle_state: "active",
  owner_principal_id: "u_admin",
  contract: {
    contract_id: "ctr_1",
    canonical_key: "ta.rsi",
    signature: {
      params: [
        { name: "source", type: "series" },
        { name: "length", type: "int" },
      ],
      return: "series",
    },
    runtime_adapter: "python",
    warm_up_period: 14,
    timing_semantics: "bar_close",
    repaint: false,
    evidence: { test_vectors: "tv_1" },
  },
  registry: TRUSTED_ROW,
  created_at: "2026-07-01T10:00:00+00:00",
  ...PERFORMANCE_NA,
};

const RESOLVE_OK = {
  resolved: true,
  canonical_key: "ta.rsi",
  entity_id: "esp_1",
  revision_id: "rev_r1",
  content_hash: "sha256:esp",
  runtime_adapter: "python",
  registry_version: 4,
  signature: ESP_DETAIL.contract.signature,
  evidence: null,
};

// A CANDIDATE resolver (the activate-composer target) + its registry row.
const CANDIDATE_ROW = {
  ...TRUSTED_ROW,
  registry_id: "reg_3",
  canonical_key: "ta.macd",
  package_entity_id: "esp_3",
  trusted_active_revision_id: null,
  trust_state: "candidate",
  registry_version: 2,
};

const CANDIDATE_DETAIL = {
  ...ESP_DETAIL,
  entity_id: "esp_3",
  revision_id: "rev_r3",
  registry: CANDIDATE_ROW,
  contract: { ...ESP_DETAIL.contract, canonical_key: "ta.macd" },
};

// Order matters for the fragment-matching stub: the resolve POST and the
// detail GET must precede the list route ("/embedded-system-packages/esp_1"
// contains "/embedded-system-packages").
const BASE_ROUTES = {
  "POST /embedded-system-packages/resolve": RESOLVE_OK,
  "GET /embedded-system-packages/esp_1": ESP_DETAIL,
  "GET /embedded-system-packages": REGISTRY_PAGE,
};

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/packages/embedded"]}>
        <Embedded />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return client;
}

describe("parseSignatureParams", () => {
  it("parses name:type lines and bare types in order, skipping blanks", () => {
    expect(parseSignatureParams("source:series\n\nlength : int\nbool")).toEqual([
      { name: "source", type: "series" },
      { name: "length", type: "int" },
      { type: "bool" },
    ]);
  });
});

describe("Embedded System Packages page", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders the registry index with trust badges", async () => {
    stubApi(BASE_ROUTES);
    renderPage();

    expect(await screen.findByText("ta.rsi")).toBeInTheDocument();
    expect(screen.getByText("ta.sma")).toBeInTheDocument();
    // Trust states render as text badges — scoped to the registry list because
    // the trust facet select lists the same values (the registry is now an
    // expandable .package-row list, not a table).
    const list = screen.getByRole("list", { name: /resolver registry/i });
    expect(within(list).getByText("trusted_active")).toBeInTheDocument();
    expect(within(list).getByText("deprecated")).toBeInTheDocument();
    // Each row surfaces its own visibility scope alongside the trust badge.
    expect(within(list).getAllByText("system")).toHaveLength(2);
  });

  it("applies the trust facet as a server-side query param and never sends empty facets", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("ta.rsi");

    // The initial load must not carry an empty trust_state param.
    expect(
      fetchMock.mock.calls.find(([url]) => String(url).includes("trust_state=")),
    ).toBeUndefined();

    fireEvent.change(screen.getByLabelText(/Trust state/), {
      target: { value: "trusted_active" },
    });

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.find(([url]) =>
          String(url).includes("trust_state=trusted_active"),
        ),
      ).toBeDefined();
    });
  });

  it("applies the scope facet as a server-side query param and never sends empty facets", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("ta.rsi");

    expect(
      fetchMock.mock.calls.find(([url]) => String(url).includes("visibility_scope=")),
    ).toBeUndefined();

    fireEvent.change(screen.getByLabelText(/Scope/), { target: { value: "system" } });

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.find(([url]) => String(url).includes("visibility_scope=system")),
      ).toBeDefined();
    });
  });

  it("pages forward with the opaque keyset cursor", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("ta.rsi");

    fireEvent.click(screen.getByRole("button", { name: "Next" }));

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.find(([url]) => String(url).includes("cursor=ta.sma")),
      ).toBeDefined();
    });
  });

  it("opens the detail with contract, registry snapshot and N/A performance (L4)", async () => {
    stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("ta.rsi");

    fireEvent.click(screen.getAllByRole("button", { name: "Detail" })[0]);

    expect(await screen.findByText("Resolver contract")).toBeInTheDocument();
    // Contract identity + semantics render as text.
    expect(screen.getByText(/bar_close/)).toBeInTheDocument();
    expect(screen.getByText(/no repaint/)).toBeInTheDocument();
    // The exact signature payload is shown verbatim.
    expect(screen.getByText(/"return": "series"/)).toBeInTheDocument();
    // L4: every resolver performance field shows its availability label.
    expect(screen.getAllByText("N/A (not applicable)")).toHaveLength(3);
    // Registry snapshot with the OCC-ready registry version.
    expect(screen.getByText(/registry v4/)).toBeInTheDocument();
  });

  it("keeps Propose resolver and Resolve probe out of the DOM until opened, catalog first", async () => {
    stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("ta.rsi");

    // The catalog renders unconditionally; the secondary actions are dialogs
    // opened on demand, not always-visible cards (UI-09: catalog first).
    expect(screen.queryByRole("region", { name: "Propose resolver" })).toBeNull();
    expect(screen.queryByRole("region", { name: "Resolve probe" })).toBeNull();
    expect(screen.getByRole("heading", { name: "Resolver registry" })).toBeInTheDocument();
  });

  it("opens Resolve probe in a dialog, closes on Escape, and restores focus to the trigger", async () => {
    stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("ta.rsi");

    const trigger = screen.getByRole("button", { name: "Resolve probe" });
    // jsdom's fireEvent.click does not perform the browser's default
    // focus-on-click for buttons, so focus explicitly first (mirrors a real
    // click) — the Modal captures document.activeElement as the trigger.
    trigger.focus();
    fireEvent.click(trigger);

    const dialog = await screen.findByRole("dialog", { name: "Resolve probe" });
    expect(within(dialog).getByRole("region", { name: "Resolve probe" })).toBeInTheDocument();

    fireEvent.keyDown(dialog, { key: "Escape" });

    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: "Resolve probe" })).toBeNull();
    });
    expect(trigger).toHaveFocus();
  });

  it("submits the resolve probe with the parsed-call payload and renders the pinned revision", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("ta.rsi");

    fireEvent.click(screen.getByRole("button", { name: "Resolve probe" }));
    const probe = await screen.findByRole("region", { name: "Resolve probe" });
    fireEvent.change(within(probe).getByLabelText(/Canonical key/), {
      target: { value: "ta.rsi" },
    });
    fireEvent.change(within(probe).getByLabelText(/Signature params/), {
      target: { value: "source:series\nlength:int" },
    });
    fireEvent.change(within(probe).getByLabelText(/Return shape/), {
      target: { value: "series" },
    });
    fireEvent.click(within(probe).getByRole("button", { name: "Resolve" }));

    // Success renders the EXACT pinned revision (P4/L5 — never latest).
    expect(await screen.findByText("rev_r1")).toBeInTheDocument();

    const resolveCall = fetchMock.mock.calls.find(
      ([url, init]) =>
        String(url).includes("/embedded-system-packages/resolve") &&
        (init?.method ?? "GET") === "POST",
    );
    expect(resolveCall).toBeDefined();
    const body = JSON.parse(String(resolveCall?.[1]?.body));
    expect(body).toEqual({
      parsed_call: {
        key: "ta.rsi",
        signature: {
          params: [
            { name: "source", type: "series" },
            { name: "length", type: "int" },
          ],
          return: "series",
        },
      },
      target_runtime: "python",
    });
    // The probe is a pure read: no Idempotency-Key header is sent.
    const headers = (resolveCall?.[1]?.headers ?? {}) as Record<string, string>;
    expect(Object.keys(headers)).not.toContain("Idempotency-Key");
  });

  it("surfaces a typed resolve failure verbatim (doc 09 §9.2)", async () => {
    stubApi({
      ...BASE_ROUTES,
      "POST /embedded-system-packages/resolve": () => {
        throw new Error(
          "RESOLVER_NOT_RESOLVED: No trusted Embedded System Package matched this dependency.",
        );
      },
    });
    renderPage();
    await screen.findByText("ta.rsi");

    fireEvent.click(screen.getByRole("button", { name: "Resolve probe" }));
    const probe = await screen.findByRole("region", { name: "Resolve probe" });
    fireEvent.change(within(probe).getByLabelText(/Canonical key/), {
      target: { value: "ta.unknown" },
    });
    fireEvent.click(within(probe).getByRole("button", { name: "Resolve" }));

    expect(
      await screen.findByText(
        "RESOLVER_NOT_RESOLVED: No trusted Embedded System Package matched this dependency.",
      ),
    ).toBeInTheDocument();
  });

  it("refetches the registry when the ['esp'] SSE prefix is invalidated", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    const client = renderPage();
    await screen.findByText("ta.rsi");
    const before = fetchMock.mock.calls.filter(([url]) =>
      String(url).includes("/embedded-system-packages"),
    ).length;

    // resource.changed sweeps ["esp"] (no dedicated resolver SSE event).
    await client.invalidateQueries({ queryKey: ["esp"] });

    await waitFor(() => {
      const after = fetchMock.mock.calls.filter(([url]) =>
        String(url).includes("/embedded-system-packages"),
      ).length;
      expect(after).toBeGreaterThan(before);
    });
  });

  it("activates a candidate with the X-Registry-Version OCC header + a fresh Idempotency-Key", async () => {
    const ACTIVATE_OK = {
      entity_id: "esp_3",
      revision_id: "rev_r3",
      canonical_key: "ta.macd",
      trust_state: "trusted_active",
      registry_version: 3,
    };
    // Action fragments precede the detail GET, which precedes the bare list.
    const fetchMock = stubApi({
      "POST /embedded-system-packages/esp_3/activate": ACTIVATE_OK,
      "GET /embedded-system-packages/esp_3": CANDIDATE_DETAIL,
      "GET /embedded-system-packages": {
        data: [CANDIDATE_ROW],
        meta: { cursor: null, has_more: false },
      },
    });
    renderPage();
    await screen.findByText("ta.macd");

    fireEvent.click(screen.getByRole("button", { name: "Detail" }));

    // A candidate offers Activate — never Deprecate (state-machine UI hint).
    const activateBtn = await screen.findByRole("button", { name: "Activate resolver" });
    expect(screen.queryByRole("button", { name: "Deprecate resolver" })).toBeNull();

    fireEvent.click(activateBtn);

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.find(
          ([url, init]) =>
            String(url).includes("/embedded-system-packages/esp_3/activate") &&
            (init?.method ?? "GET") === "POST",
        ),
      ).toBeDefined();
    });

    const call = fetchMock.mock.calls.find(
      ([url, init]) => String(url).includes("/esp_3/activate") && init?.method === "POST",
    );
    const headers = (call?.[1]?.headers ?? {}) as Record<string, string>;
    // OCC is the plain registry version (candidate = 2) — NOT an If-Match ETag.
    expect(headers["X-Registry-Version"]).toBe("2");
    expect(headers).toHaveProperty("Idempotency-Key");
    const body = JSON.parse(String(call?.[1]?.body));
    // The head revision + registry canonical_key; an empty note is omitted.
    expect(body).toEqual({ revision_id: "rev_r3", canonical_key: "ta.macd" });
  });

  it("deprecates a trusted_active resolver, requiring a reason, with OCC + Idempotency-Key", async () => {
    const DEPRECATE_OK = {
      canonical_key: "ta.rsi",
      entity_id: "esp_1",
      trust_state: "deprecated",
      replacement_revision_id: null,
      registry_version: 5,
    };
    const fetchMock = stubApi({
      "POST /embedded-system-packages/esp_1/deprecate": DEPRECATE_OK,
      "GET /embedded-system-packages/esp_1": ESP_DETAIL,
      "GET /embedded-system-packages": REGISTRY_PAGE,
    });
    renderPage();
    await screen.findByText("ta.rsi");

    fireEvent.click(screen.getAllByRole("button", { name: "Detail" })[0]);

    // A trusted_active resolver offers Deprecate — never Activate.
    const depBtn = await screen.findByRole("button", { name: "Deprecate resolver" });
    expect(screen.queryByRole("button", { name: "Activate resolver" })).toBeNull();
    // Reason required: the button stays disabled until a reason is typed.
    expect(depBtn).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/Deprecation reason/), {
      target: { value: "Superseded by v2" },
    });
    expect(depBtn).toBeEnabled();

    fireEvent.click(depBtn);

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.find(
          ([url, init]) => String(url).includes("/esp_1/deprecate") && init?.method === "POST",
        ),
      ).toBeDefined();
    });

    const call = fetchMock.mock.calls.find(
      ([url, init]) => String(url).includes("/esp_1/deprecate") && init?.method === "POST",
    );
    const headers = (call?.[1]?.headers ?? {}) as Record<string, string>;
    expect(headers["X-Registry-Version"]).toBe("4"); // TRUSTED_ROW.registry_version
    expect(headers).toHaveProperty("Idempotency-Key");
    const body = JSON.parse(String(call?.[1]?.body));
    expect(body).toEqual({ canonical_key: "ta.rsi", reason: "Superseded by v2" });
  });

  it("proposes a resolver via create — no OCC / Idempotency-Key header, signature verbatim", async () => {
    const CREATE_OK = {
      entity_id: "esp_9",
      revision_id: "rev_r9",
      canonical_key: "ta.macd",
      trust_state: "candidate",
      runtime_adapter: "python",
    };
    // The create fragment is the bare path; it never matches a sub-path POST.
    const fetchMock = stubApi({ ...BASE_ROUTES, "POST /embedded-system-packages": CREATE_OK });
    renderPage();
    await screen.findByText("ta.rsi");

    // Scope to the propose region: the resolve probe reuses the same labels.
    fireEvent.click(screen.getByRole("button", { name: "Propose resolver" }));
    const section = await screen.findByRole("region", { name: "Propose resolver" });
    fireEvent.change(within(section).getByLabelText(/Canonical key/), {
      target: { value: "ta.macd" },
    });
    fireEvent.change(within(section).getByLabelText(/Signature params/), {
      target: { value: "source:series\nlength:int" },
    });
    fireEvent.change(within(section).getByLabelText(/Return shape/), {
      target: { value: "series" },
    });
    fireEvent.click(within(section).getByRole("button", { name: "Propose resolver" }));

    expect(await screen.findByText(/Proposed/)).toBeInTheDocument();

    const call = fetchMock.mock.calls.find(
      ([url, init]) =>
        String(url).endsWith("/embedded-system-packages") && init?.method === "POST",
    );
    expect(call).toBeDefined();
    const headers = (call?.[1]?.headers ?? {}) as Record<string, string>;
    // A create has no head to race — neither OCC nor Idempotency-Key travels.
    expect(Object.keys(headers)).not.toContain("Idempotency-Key");
    expect(Object.keys(headers)).not.toContain("X-Registry-Version");
    const body = JSON.parse(String(call?.[1]?.body));
    expect(body.canonical_key).toBe("ta.macd");
    expect(body.signature).toEqual({
      params: [
        { name: "source", type: "series" },
        { name: "length", type: "int" },
      ],
      return: "series",
    });
    expect(body.runtime_adapter).toBe("python");
    expect(body.visibility_scope).toBe("private");
  });

  it("keeps Propose disabled until a key and a signature are present", async () => {
    stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("ta.rsi");

    fireEvent.click(screen.getByRole("button", { name: "Propose resolver" }));
    const section = await screen.findByRole("region", { name: "Propose resolver" });
    const proposeBtn = within(section).getByRole("button", { name: "Propose resolver" });
    expect(proposeBtn).toBeDisabled();

    // A key alone is not enough — the signature needs params or a return shape.
    fireEvent.change(within(section).getByLabelText(/Canonical key/), {
      target: { value: "ta.macd" },
    });
    expect(proposeBtn).toBeDisabled();

    fireEvent.change(within(section).getByLabelText(/Return shape/), {
      target: { value: "series" },
    });
    expect(proposeBtn).toBeEnabled();
  });

  it("surfaces a 403 verbatim when a non-Admin activates (doc 09 §10.3)", async () => {
    stubApi({
      "POST /embedded-system-packages/esp_3/activate": () => {
        throw new Error(
          "APPROVAL_REQUIRES_ADMIN: Activating a trusted resolver requires the Admin role.",
        );
      },
      "GET /embedded-system-packages/esp_3": CANDIDATE_DETAIL,
      "GET /embedded-system-packages": {
        data: [CANDIDATE_ROW],
        meta: { cursor: null, has_more: false },
      },
    });
    renderPage();
    await screen.findByText("ta.macd");

    fireEvent.click(screen.getByRole("button", { name: "Detail" }));
    fireEvent.click(await screen.findByRole("button", { name: "Activate resolver" }));

    expect(
      await screen.findByText(
        "APPROVAL_REQUIRES_ADMIN: Activating a trusted resolver requires the Admin role.",
      ),
    ).toBeInTheDocument();
  });
});
