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
    // Trust states render as text badges — scoped to the table because the
    // trust facet select lists the same values.
    const table = screen.getByRole("table");
    expect(within(table).getByText("trusted_active")).toBeInTheDocument();
    expect(within(table).getByText("deprecated")).toBeInTheDocument();
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

  it("submits the resolve probe with the parsed-call payload and renders the pinned revision", async () => {
    const fetchMock = stubApi(BASE_ROUTES);
    renderPage();
    await screen.findByText("ta.rsi");

    fireEvent.change(screen.getByLabelText(/Canonical key/), {
      target: { value: "ta.rsi" },
    });
    fireEvent.change(screen.getByLabelText(/Signature params/), {
      target: { value: "source:series\nlength:int" },
    });
    fireEvent.change(screen.getByLabelText(/Return shape/), {
      target: { value: "series" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Resolve" }));

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

    fireEvent.change(screen.getByLabelText(/Canonical key/), {
      target: { value: "ta.unknown" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Resolve" }));

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
});
