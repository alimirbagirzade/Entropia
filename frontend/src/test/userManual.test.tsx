import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { UserManual } from "@/pages/UserManual";
import { stubApi } from "./helpers/apiStub";

// One stream page: the immutable baseline guide first (UM-10 — no admin
// actions), then an appended non-baseline section with every block type.
const STREAM = {
  data: [
    {
      document_id: "mdoc_baseline_entropia_guide",
      is_baseline: true,
      title: "Entropia Guide",
      revision_id: "mrev_base_1",
      revision_no: 1,
      source_type: "built_in",
      source_label: "Built-in Manual",
      stream_position: 1,
      anchor: "sec-baseline",
      blocks: [
        { block_id: "b1", block_type: "heading", anchor: "h-intro", payload: { level: 1, text: "Introduction" } },
        { block_id: "b2", block_type: "paragraph", anchor: "h-intro", payload: { text: "Welcome to Entropia." } },
        { block_id: "b3", block_type: "bullet_list", anchor: "h-intro", payload: { items: ["First item", "Second item"] } },
        { block_id: "b4", block_type: "code", anchor: "h-intro", payload: { code_text: "print('hi')", language: "python" } },
        { block_id: "b5", block_type: "callout", anchor: "h-intro", payload: { tone: "note", title: "Note", text: "Be careful." } },
        { block_id: "b6", block_type: "divider", anchor: "h-intro", payload: {} },
      ],
    },
    {
      document_id: "mdoc_2",
      is_baseline: false,
      title: "Appendix",
      revision_id: "mrev_2_3",
      revision_no: 3,
      source_type: "added_text",
      source_label: "Added text document",
      stream_position: 2,
      anchor: "sec-mdoc-2",
      blocks: [{ block_id: "b7", block_type: "paragraph", anchor: "sec-mdoc-2", payload: { text: "Appendix body." } }],
    },
  ],
  meta: { stream_version: 7, cursor: null, has_more: false, limit: 20 },
};

const SEARCH = {
  data: [
    {
      chunk_id: "chk_1",
      document_id: "mdoc_2",
      revision_id: "mrev_2_3",
      revision_no: 3,
      title: "Appendix",
      heading_path: "Appendix › Details",
      excerpt: "…the appendix body…",
      anchor: "sec-mdoc-2",
      block_ids: ["b7"],
      source_label: "Added text document",
    },
  ],
  meta: { stream_version: 7, cursor: null, has_more: false, limit: 20, query: "appendix" },
};

const PUBLISH_RESULT = {
  document_id: "mdoc_3",
  revision_id: "mrev_3_1",
  revision_no: 1,
  stream_entry_id: "mstr_3",
  stream_position: 3,
  anchor: "sec-mdoc-3",
  title: "New doc",
  checksum: "sha256:abc",
  stream_version: 8,
  correlation_id: null,
};

const REVISE_RESULT = {
  document_id: "mdoc_2",
  revision_id: "mrev_2_4",
  revision_no: 4,
  superseded_revision_id: "mrev_2_3",
  stream_position: 2,
  anchor: "sec-mdoc-2",
  stream_version: 8,
  correlation_id: null,
};

const DELETE_RESULT = {
  document_id: "mdoc_2",
  deletion_state: "soft_deleted",
  trash_entry_id: 42,
  display_name: "Appendix",
  stream_version: 8,
  correlation_id: null,
};

// The restore route delegates to the landed Trash core — its return IS the
// Trash RestoreResult shape.
const RESTORE_RESULT = {
  trash_entry_id: "42",
  entity_id: "mdoc_2",
  entity_type: "manual_document",
  display_name: "Appendix",
  status: "restored",
  deletion_state: "active",
  current_revision_id: "mrev_2_3",
  row_version: 3,
  correlation_id: null,
};

// apiStub matches in insertion order: the specific admin fragments (:upload,
// :restore, /revisions) MUST precede the bare create fragment — the create
// path "/admin/manual/documents" is a substring of all of them.
function stubRoutes(extra: Record<string, unknown> = {}) {
  return stubApi({
    "POST :restore": RESTORE_RESULT,
    "POST :upload": PUBLISH_RESULT,
    "POST /revisions": REVISE_RESULT,
    "DELETE /admin/manual/documents": DELETE_RESULT,
    "POST /admin/manual/documents": PUBLISH_RESULT,
    "GET /manual/search": SEARCH,
    "GET /manual/stream": STREAM,
    ...extra,
  });
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/user-manual"]}>
        <Routes>
          <Route path="/user-manual" element={<UserManual />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function callFor(
  fetchMock: ReturnType<typeof stubApi>,
  method: string,
  fragment: string,
): RequestInit {
  const call = fetchMock.mock.calls.find(
    ([url, init]) =>
      String(url).includes(fragment) && ((init?.method ?? "GET") as string) === method,
  );
  expect(call).toBeTruthy();
  return call?.[1] as RequestInit;
}

function headersOf(init: RequestInit): Record<string, string> {
  return (init.headers ?? {}) as Record<string, string>;
}

describe("User Manual page", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders the published stream: baseline first, canonical blocks, one snapshot version", async () => {
    stubRoutes();
    renderPage();

    expect(await screen.findByText("Entropia Guide")).toBeTruthy();
    expect(screen.getByText("Baseline")).toBeTruthy();
    expect(screen.getByText(/Stream v7/)).toBeTruthy();
    // Canonical block types render as text nodes (doc 21 §9.2).
    expect(screen.getByText("Introduction")).toBeTruthy();
    expect(screen.getByText("Welcome to Entropia.")).toBeTruthy();
    expect(screen.getByText("Second item")).toBeTruthy();
    expect(screen.getByText("print('hi')")).toBeTruthy();
    expect(screen.getByText(/Be careful\./)).toBeTruthy();
    // Appended section with its source provenance.
    expect(screen.getByText("Appendix")).toBeTruthy();
    expect(screen.getByText("Added text document")).toBeTruthy();
  });

  it("hides replace/delete on the baseline from the server-truth is_baseline flag (UM-10)", async () => {
    stubRoutes();
    renderPage();

    await screen.findByText("Appendix");
    // Only the non-baseline section carries admin actions.
    expect(screen.getAllByRole("button", { name: "Delete…" })).toHaveLength(1);
    expect(screen.getAllByRole("button", { name: "Replace content" })).toHaveLength(1);
  });

  it("searches only on submit and renders chunk results verbatim", async () => {
    const fetchMock = stubRoutes();
    renderPage();
    await screen.findByText("Appendix");

    // A blank/untouched query never fetches (doc 21 §14 — blank searches nothing).
    expect(
      fetchMock.mock.calls.every(([url]) => !String(url).includes("/manual/search")),
    ).toBe(true);

    fireEvent.change(screen.getByLabelText("Search query"), { target: { value: "appendix" } });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    expect(await screen.findByText("…the appendix body…")).toBeTruthy();
    expect(screen.getByText("Appendix › Details")).toBeTruthy();
    const init = callFor(fetchMock, "GET", "/manual/search");
    expect(init).toBeTruthy();
    const url = String(
      fetchMock.mock.calls.find(([u]) => String(u).includes("/manual/search"))?.[0],
    );
    expect(url).toContain("q=appendix");
  });

  it("publishes an added text document guarded by the rendered stream snapshot", async () => {
    const fetchMock = stubRoutes();
    renderPage();
    await screen.findByText("Appendix");

    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "New doc" } });
    fireEvent.change(screen.getByLabelText("Content"), { target: { value: "Body text." } });
    fireEvent.click(screen.getByRole("button", { name: "Publish document" }));

    expect(await screen.findByText(/Published “New doc” rev 1/)).toBeTruthy();
    const init = callFor(fetchMock, "POST", "/admin/manual/documents");
    const body = JSON.parse(String(init.body)) as Record<string, unknown>;
    // OCC is the BODY-form expected_stream_version INT from the rendered page.
    expect(body.expected_stream_version).toBe(7);
    expect(body.title).toBe("New doc");
    expect(body.allow_duplicate).toBe(false);
    expect(headersOf(init)["Idempotency-Key"]).toBeTruthy();
    // Success invalidates ["manual"] — the reader stream refetches.
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.filter(
          ([url, i]) =>
            String(url).includes("/manual/stream") && ((i?.method ?? "GET") as string) === "GET",
        ).length,
      ).toBeGreaterThan(1),
    );
  });

  it("uploads a document omitting the blank optional title", async () => {
    const fetchMock = stubRoutes();
    renderPage();
    await screen.findByText("Appendix");

    fireEvent.change(screen.getByLabelText("Source filename"), { target: { value: "guide.md" } });
    fireEvent.change(screen.getByLabelText("File content (UTF-8 text)"), {
      target: { value: "# Uploaded" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Upload & publish" }));

    await screen.findByText(/Published “New doc” rev 1/);
    const init = callFor(fetchMock, "POST", ":upload");
    const body = JSON.parse(String(init.body)) as Record<string, unknown>;
    expect(body.source_filename).toBe("guide.md");
    expect(body.expected_stream_version).toBe(7);
    // Blank optional field is OMITTED — the server derives the title.
    expect("title" in body).toBe(false);
    expect(headersOf(init)["Idempotency-Key"]).toBeTruthy();
  });

  it("replaces a revision with the section head as the BODY-form OCC token", async () => {
    const fetchMock = stubRoutes();
    renderPage();
    await screen.findByText("Appendix");

    fireEvent.click(screen.getByRole("button", { name: "Replace content" }));
    fireEvent.change(screen.getByLabelText("Replacement content"), {
      target: { value: "Updated appendix." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Publish revision 4" }));

    expect(await screen.findByText(/Published rev 4 at position 2/)).toBeTruthy();
    const init = callFor(fetchMock, "POST", "/admin/manual/documents/mdoc_2/revisions");
    const body = JSON.parse(String(init.body)) as Record<string, unknown>;
    // expected_head_revision_id = the visible head from this page's snapshot;
    // a moved head is 409 MANUAL_REVISION_CONFLICT verbatim (body wins over If-Match).
    expect(body.expected_head_revision_id).toBe("mrev_2_3");
    expect(body.content).toBe("Updated appendix.");
    expect(headersOf(init)["Idempotency-Key"]).toBeTruthy();
  });

  it("soft deletes after a two-step confirm — DELETE carries a BODY + Idempotency-Key", async () => {
    const fetchMock = stubRoutes();
    renderPage();
    await screen.findByText("Appendix");

    fireEvent.click(screen.getByRole("button", { name: "Delete…" }));
    fireEvent.change(screen.getByLabelText("Delete reason for Appendix"), {
      target: { value: "outdated" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Confirm delete" }));

    expect(await screen.findByText(/moved to Trash \(stream v8\)/)).toBeTruthy();
    const init = callFor(fetchMock, "DELETE", "/admin/manual/documents/mdoc_2");
    const body = JSON.parse(String(init.body)) as Record<string, unknown>;
    expect(body.reason).toBe("outdated");
    expect(body.expected_stream_version).toBe(7);
    expect(headersOf(init)["Idempotency-Key"]).toBeTruthy();
  });

  it("restores by document id — no body, Idempotency-Key only (Trash-core delegate)", async () => {
    const fetchMock = stubRoutes();
    renderPage();
    await screen.findByText("Appendix");

    fireEvent.change(screen.getByLabelText("Document id to restore"), {
      target: { value: "mdoc_2" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Restore" }));

    expect(await screen.findByText(/Restored “Appendix” — mdoc_2 is active\./)).toBeTruthy();
    const init = callFor(fetchMock, "POST", ":restore");
    expect(init.body).toBeUndefined();
    expect(headersOf(init)["Idempotency-Key"]).toBeTruthy();
  });
});
