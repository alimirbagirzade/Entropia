import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import { CreatePackage } from "@/pages/CreatePackage";
import { stubApi } from "./helpers/apiStub";

// I-17-COV — CP-14 (docs/audit, doc 06 row 14) "Clear boundary": "Clear unsent
// editor'ı temizler; submitted request, candidate, draft, baseline asset,
// validation artifact veya published Package'ı silmez."
//
// `docs/audit/acceptance_id_map.md` §C.1 listed CP-14 as having no test at all.
// Clear is a client-only reset (`pages/CreatePackage.tsx::onClearAll` →
// `setForm(INITIAL_FORM)` + `onClear()`), and the whole acceptance row is about
// what it must NOT reach: the server. So the test asserts both directions — the
// editor really empties, and the click produces no request of any kind, which is
// the only way a submitted request/candidate/draft/baseline/package could be
// destroyed from here.

const FAMILIES_PAGE = {
  data: [
    { entity_id: "fam_1", display_name: "Momentum", normalized_name: "momentum", display_color: null },
  ],
  meta: { cursor: null, has_more: false },
};

const LIBRARY_INDICATORS = { data: [], meta: { cursor: null, has_more: false } };

const REQUESTS_PAGE = {
  data: [
    {
      request_id: "req_1",
      package_type: "indicator",
      state: "precheck_passed",
      source_kind: "code",
      package_root_id: null,
    },
  ],
  meta: { cursor: null, has_more: false },
};

const ROUTES: Record<string, unknown> = {
  "GET /create-package/requests": REQUESTS_PAGE,
  "GET /rationale-families": FAMILIES_PAGE,
  "GET /library": LIBRARY_INDICATORS,
};

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/packages/create"]}>
        <CreatePackage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return client;
}

function requestsAfter(fetchMock: ReturnType<typeof stubApi>, from: number): string[] {
  return fetchMock.mock.calls
    .slice(from)
    .map(([input, init]) => `${String((init as RequestInit | undefined)?.method ?? "GET").toUpperCase()} ${String(input)}`);
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Create Package Clear boundary (CP-14)", () => {
  it("empties the unsent editor and sends nothing to the server", async () => {
    const fetchMock = stubApi(ROUTES);
    renderPage();
    await screen.findByRole("option", { name: "Momentum" });

    fireEvent.change(screen.getByLabelText("Rationale family"), { target: { value: "fam_1" } });
    fireEvent.change(screen.getByLabelText("Source code"), {
      target: { value: "//@version=5\nindicator('unsent draft')" },
    });
    fireEvent.change(screen.getByLabelText("Declared dependencies"), {
      target: { value: "ta.sma\n" },
    });
    expect((screen.getByLabelText("Source code") as HTMLTextAreaElement).value).toContain(
      "unsent draft",
    );

    const callsBeforeClear = fetchMock.mock.calls.length;
    fireEvent.click(screen.getByRole("button", { name: "Clear" }));

    // The unsent editor is back to its initial state…
    expect((screen.getByLabelText("Source code") as HTMLTextAreaElement).value).toBe("");
    expect((screen.getByLabelText("Declared dependencies") as HTMLTextAreaElement).value).toBe("");
    expect((screen.getByLabelText("Rationale family") as HTMLSelectElement).value).toBe("");
    // …and NOTHING left the browser: no DELETE, no POST, no request at all.
    expect(requestsAfter(fetchMock, callsBeforeClear)).toEqual([]);
  });

  it("leaves the already-submitted request listed and selectable", async () => {
    const fetchMock = stubApi(ROUTES);
    renderPage();
    expect(await screen.findByText("req_1")).toBeInTheDocument();
    await screen.findByRole("option", { name: "Momentum" });

    fireEvent.change(screen.getByLabelText("Source code"), {
      target: { value: "throwaway body" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Clear" }));

    // The submitted request is still on the page — Clear touched the editor only.
    expect(screen.getByText("req_1")).toBeInTheDocument();
    expect(screen.getByText("precheck_passed")).toBeInTheDocument();
    const deletes = fetchMock.mock.calls.filter(
      ([, init]) => String((init as RequestInit | undefined)?.method ?? "GET").toUpperCase() === "DELETE",
    );
    expect(deletes).toEqual([]);
  });
});
