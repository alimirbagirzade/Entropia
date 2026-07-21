import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { UserManual } from "@/pages/UserManual";
import { apiErrorRoute, stubApi } from "./helpers/apiStub";
import { stubUpload } from "./helpers/xhrStub";

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

// Real document chooser (F-03): the Restore drawer sources its options from
// actual recoverable Trash entries, never a manually-typed document id.
const TRASH_ENTRIES = {
  data: [
    {
      trash_entry_id: "42",
      entity_id: "mdoc_2",
      object_type: "manual_document",
      display_name: "Appendix",
      original_location: "Help / User Manual",
      original_owner: "User",
      deleted_by: "User",
      deleted_at: "2026-07-15T00:00:00Z",
      delete_reason: null,
      status: "soft_deleted",
      purge_status: null,
      purge_job_id: null,
      restore_eligible: true,
      row_version: 3,
      correlation_id: null,
    },
  ],
  meta: { cursor: null, has_more: false, limit: 20, recoverable_total: 1, object_types: ["manual_document"] },
};

// apiStub matches in insertion order: the specific admin fragments (:upload,
// :restore, /revisions) MUST precede the bare create fragment — the create
// path "/admin/manual/documents" is a substring of all of them.
// R2-09: the maintenance actions render only for a server-confirmed Admin
// (/me projection, fail-closed) — the shared baseline runs under ME_ADMIN;
// the visibility tests below override the projection.
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
  role: "user",
  is_admin: false,
  is_authenticated: true,
};

function stubRoutes(extra: Record<string, unknown> = {}) {
  return stubApi({
    "POST :restore": RESTORE_RESULT,
    "POST /revisions": REVISE_RESULT,
    "DELETE /admin/manual/documents": DELETE_RESULT,
    "POST /admin/manual/documents": PUBLISH_RESULT,
    "GET /trash-entries": TRASH_ENTRIES,
    "GET /manual/search": SEARCH,
    "GET /manual/stream": STREAM,
    "GET /me": ME_ADMIN,
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

    // The sidebar's section nav mirrors title/source_label alongside the
    // reader, so those two specifically are scoped to the reader article.
    const article = screen.getByRole("article");
    expect(await within(article).findByText("Entropia Guide")).toBeTruthy();
    expect(within(article).getByText("Baseline")).toBeTruthy();
    expect(screen.getByText(/Stream v7/)).toBeTruthy();
    // Canonical block types render as text nodes (doc 21 §9.2).
    expect(within(article).getByText("Introduction")).toBeTruthy();
    expect(within(article).getByText("Welcome to Entropia.")).toBeTruthy();
    expect(within(article).getByText("Second item")).toBeTruthy();
    expect(within(article).getByText("print('hi')")).toBeTruthy();
    expect(within(article).getByText(/Be careful\./)).toBeTruthy();
    // Appended section with its source provenance.
    expect(within(article).getByText("Appendix")).toBeTruthy();
    expect(within(article).getByText("Added text document")).toBeTruthy();
  });

  it("hides replace/delete on the baseline from the server-truth is_baseline flag (UM-10)", async () => {
    stubRoutes();
    renderPage();

    await screen.findByText("Appendix body.");
    // Only the non-baseline section carries admin actions.
    expect(await screen.findAllByRole("button", { name: "Delete…" })).toHaveLength(1);
    expect(screen.getAllByRole("button", { name: "Replace content" })).toHaveLength(1);
  });

  it("searches only on submit and renders chunk results verbatim", async () => {
    const fetchMock = stubRoutes();
    renderPage();
    await screen.findByText("Appendix body.");

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

  it("publishes an added text document from the Add / Paste Text drawer", async () => {
    const fetchMock = stubRoutes();
    renderPage();
    await screen.findByText("Appendix body.");

    fireEvent.click(await screen.findByRole("button", { name: "+ Add / Paste Text" }));
    fireEvent.change(await screen.findByLabelText("Title"), { target: { value: "New doc" } });
    fireEvent.change(screen.getByLabelText("Content"), { target: { value: "Body text." } });
    fireEvent.click(screen.getByRole("button", { name: "Publish document" }));

    // The drawer closes and the reader shows the publish notice.
    expect(await screen.findByText(/Published “New doc” rev 1/)).toBeTruthy();
    expect(screen.queryByLabelText("Content")).toBeNull();

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

  it("uploads a real chosen file (F-03) omitting the blank optional title", async () => {
    stubRoutes();
    const { calls: uploadCalls } = stubUpload({ "POST :upload": PUBLISH_RESULT });
    renderPage();
    await screen.findByText("Appendix body.");

    fireEvent.click(await screen.findByRole("button", { name: "Upload Document" }));
    const fileInput = await screen.findByLabelText("File");
    const file = new File(["# Uploaded"], "guide.md", { type: "text/markdown" });
    fireEvent.change(fileInput, { target: { files: [file] } });
    fireEvent.click(await screen.findByRole("button", { name: "Upload & publish" }));

    expect(await screen.findByText(/Published “New doc” rev 1/)).toBeTruthy();
    // F-03: the real file bytes travel via multipart; the OCC stream version and
    // the (omitted) optional title ride form fields, not a JSON body.
    expect(uploadCalls).toHaveLength(1);
    expect(uploadCalls[0]?.url).toContain(":upload");
    expect(uploadCalls[0]?.file?.name).toBe("guide.md");
    expect(uploadCalls[0]?.fields.expected_stream_version).toBe("7");
    // Blank optional field is OMITTED — the server derives the title.
    expect("title" in uploadCalls[0]!.fields).toBe(false);
    expect(uploadCalls[0]?.headers["Idempotency-Key"]).toBeTruthy();
  });

  it("replaces a revision with the section head as the BODY-form OCC token", async () => {
    const fetchMock = stubRoutes();
    renderPage();
    await screen.findByText("Appendix body.");

    fireEvent.click(await screen.findByRole("button", { name: "Replace content" }));
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
    await screen.findByText("Appendix body.");

    fireEvent.click(await screen.findByRole("button", { name: "Delete…" }));
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

  it("restores via a real document chooser sourced from recoverable Trash entries (F-03)", async () => {
    const fetchMock = stubRoutes();
    renderPage();
    await screen.findByText("Appendix body.");

    fireEvent.click(await screen.findByRole("button", { name: "Restore a Document" }));
    const picker = await screen.findByLabelText("Document to restore");
    expect(screen.getByText("Appendix (mdoc_2)")).toBeTruthy();
    fireEvent.change(picker, { target: { value: "mdoc_2" } });
    fireEvent.click(screen.getByRole("button", { name: "Restore" }));

    expect(await screen.findByText(/Restored “Appendix” — mdoc_2 is active\./)).toBeTruthy();
    const entriesInit = callFor(fetchMock, "GET", "/trash-entries");
    expect(entriesInit).toBeTruthy();
    const entriesUrl = String(
      fetchMock.mock.calls.find(([u]) => String(u).includes("/trash-entries"))?.[0],
    );
    expect(entriesUrl).toContain("object_type=manual_document");
    const init = callFor(fetchMock, "POST", ":restore");
    expect(init.body).toBeUndefined();
    expect(headersOf(init)["Idempotency-Key"]).toBeTruthy();
  });

  // R2-09 (GAP item 10): a non-admin keeps the full read-only reader but no
  // maintenance controls — the "Admin approval required" note replaces the
  // sidebar actions and the per-section replace/delete row.
  it("hides manual maintenance from a non-admin and shows the Admin approval note", async () => {
    stubRoutes({ "GET /me": ME_USER });
    renderPage();
    await screen.findByText("Appendix body.");

    expect(screen.queryByRole("button", { name: "+ Add / Paste Text" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Upload Document" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Restore a Document" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Replace content" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Delete…" })).toBeNull();
    expect(screen.getByText(/Admin approval required/)).toBeInTheDocument();
  });

  // Fail-closed: an unknown identity projection (/me unavailable) keeps every
  // maintenance control hidden — unknown never opens the gate.
  it("fail-closed: hides manual maintenance while /me is unavailable", async () => {
    stubRoutes({
      "GET /me": apiErrorRoute(503, "SERVICE_UNAVAILABLE", "identity projection unavailable"),
    });
    renderPage();
    await screen.findByText("Appendix body.");

    expect(screen.queryByRole("button", { name: "+ Add / Paste Text" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Replace content" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Delete…" })).toBeNull();
  });
});
