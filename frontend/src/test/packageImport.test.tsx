import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import { Library } from "@/pages/Library";
import { stubApi } from "./helpers/apiStub";

const EMPTY_CATALOG = { data: [], meta: { cursor: null, has_more: false } };
const EMPTY_FAMILIES = { data: [], meta: { cursor: null, has_more: false } };

const SUCCEEDED_REPORT = {
  import_job_id: "pkgimp_1",
  status: "succeeded",
  package_kind: "indicator",
  manifest_hash: "a".repeat(64),
  origin_package_id: "pkg_origin",
  origin_revision_id: "pkgrev_origin",
  result_package_root_id: "pkg_local",
  diagnostics: { resolved_count: 0 },
  job_id: "job_1",
  created_at: "2026-07-14T00:00:00Z",
  completed_at: "2026-07-14T00:00:01Z",
};

const BLOCKED_LIST = {
  items: [
    {
      import_job_id: "pkgimp_2",
      status: "blocked",
      package_kind: "indicator",
      manifest_hash: "b".repeat(64),
      origin_package_id: null,
      origin_revision_id: null,
      result_package_root_id: "pkg_blocked",
      diagnostics: { missing_dependencies: [{ call: "ta.unknown", code: "RESOLVER_NOT_RESOLVED" }] },
      job_id: "job_2",
      created_at: "2026-07-14T00:00:00Z",
      completed_at: "2026-07-14T00:00:01Z",
    },
  ],
};

function renderLibrary() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Library />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const VALID_MANIFEST = JSON.stringify({
  package_kind: "indicator",
  input_contract: { name: "Imported" },
  output_contract: { kind: "directional_signal" },
  dependency_snapshot: { resolved: [] },
});

describe("Library package import", () => {
  it("submits a manifest and shows the succeeded report", async () => {
    const fetchMock = stubApi({
      "GET /library": EMPTY_CATALOG,
      "GET /rationale-families": EMPTY_FAMILIES,
      "GET /package-imports/pkgimp_1": SUCCEEDED_REPORT,
      "GET /package-imports": { items: [] },
      "POST /package-imports": {
        import_job_id: "pkgimp_1",
        job_id: "job_1",
        queue: "data",
        status: "queued",
      },
    });
    renderLibrary();

    fireEvent.change(screen.getByLabelText("Export manifest JSON"), {
      target: { value: VALID_MANIFEST },
    });
    fireEvent.click(screen.getByRole("button", { name: "Import manifest" }));

    await waitFor(() => expect(screen.getByText("succeeded")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "View in catalog" })).toBeInTheDocument();
    const posted = fetchMock.mock.calls.find(
      ([, init]) => (init as RequestInit)?.method === "POST",
    );
    expect(posted).toBeTruthy();
    const body = JSON.parse(String((posted?.[1] as RequestInit).body));
    expect(body.manifest.package_kind).toBe("indicator");
    expect((posted?.[1] as RequestInit).headers).toMatchObject({
      "Idempotency-Key": expect.any(String),
    });
  });

  it("rejects invalid JSON without calling the server", async () => {
    const fetchMock = stubApi({
      "GET /library": EMPTY_CATALOG,
      "GET /rationale-families": EMPTY_FAMILIES,
      "GET /package-imports": { items: [] },
    });
    renderLibrary();

    fireEvent.change(screen.getByLabelText("Export manifest JSON"), {
      target: { value: "{ not json" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Import manifest" }));

    await waitFor(() =>
      expect(screen.getByText("The manifest is not valid JSON.")).toBeInTheDocument(),
    );
    const posted = fetchMock.mock.calls.find(
      ([, init]) => (init as RequestInit)?.method === "POST",
    );
    expect(posted).toBeUndefined();
  });

  it("lists recent imports and opens a blocked report on click", async () => {
    stubApi({
      "GET /library": EMPTY_CATALOG,
      "GET /rationale-families": EMPTY_FAMILIES,
      "GET /package-imports/pkgimp_2": BLOCKED_LIST.items[0],
      "GET /package-imports": BLOCKED_LIST,
    });
    renderLibrary();

    await waitFor(() => expect(screen.getByText("pkgimp_2")).toBeInTheDocument());
    fireEvent.click(screen.getByText("pkgimp_2"));

    await waitFor(() =>
      expect(
        screen.getByText(/Blocked: the DRAFT was created but is not executable/),
      ).toBeInTheDocument(),
    );
    expect(screen.getByText(/RESOLVER_NOT_RESOLVED/)).toBeInTheDocument();
  });
});
