import { useEffect, useRef, useState, type ChangeEvent, type FormEvent, type ReactNode } from "react";

import { AdminApprovalNote, useIsAdmin } from "@/components/AdminGate";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { StatusBadge } from "@/components/StatusBadge";
import { ApiError } from "@/lib/apiClient";
import {
  ACCEPTED_UPLOAD_EXTENSIONS,
  type DeleteResult,
  type ManualBlock,
  type ManualSection,
  type PublishResult,
  useCreateManualDocument,
  useManualSearch,
  useManualStream,
  useReplaceManualRevision,
  useRestoreManualDocument,
  useSoftDeleteManualDocument,
  useUploadManualDocument,
} from "@/lib/manual";
import { type RestoreResult, useTrashEntries } from "@/lib/trash";

// Failures surface the backend canonical envelope verbatim — the client never
// invents manual-domain messages (MANUAL_STREAM_CONFLICT / MANUAL_REVISION_
// CONFLICT / MANUAL_DUPLICATE_CONTENT / BASELINE_MANUAL_IMMUTABLE arrive
// as-is, doc 21 §10).
function mutationErrorText(error: unknown): string {
  if (error instanceof ApiError) return `${error.code}: ${error.message}`;
  return error instanceof Error ? error.message : "Request failed.";
}

// ---------------------------------------------------------------------------
// Doc 21 §6.1 — the page's final UI copy, VERBATIM. These strings are the
// spec's own wording: never translated, reworded or paraphrased. Only the
// documented “{title}” slot in the remove-confirmation body is interpolated.
// Presentation only — no route path, react-query key, OCC token or
// Idempotency-Key is derived from anything here.
//
// Honest boundary: §6.1's "Unsupported type error", "Parse error", "Duplicate
// content warning", "Unauthorized error" and "Stale conflict" rows are NOT
// mirrored here on purpose — those five are backend failures and this page
// renders the canonical envelope verbatim (see mutationErrorText above,
// doc 21 §10 / O-02). Restating them client-side would invent a second
// message for the same defect. "Upload read failure" likewise has no client
// surface since F-03 moved the upload to multipart: the server decodes the
// bytes, so the client never performs the read that could fail.
// ---------------------------------------------------------------------------
const MANUAL_COPY = {
  searchPlaceholder: "Search headings or text",
  composerTitlePlaceholder: "Manual document title",
  composerContentPlaceholder:
    "Paste or write the complete text. It will be appended below the existing manual in the same continuous reading flow.",
  nonAdminHelper:
    "Only Admin can upload or add manual documents. All roles can search, open and read the complete manual text.",
  blankSearchEmptyState: "Enter a word or phrase to search every part of the continuous manual.",
  noSearchResult: "No document text matches this search.",
  textAppendSuccess: "Text document added to the end of the continuous manual.",
  uploadSuccess: "Uploaded document added to the end of the continuous manual.",
  softDeleteSuccess: "Document moved to Trash.",
  requiredFieldsError: "A document title and full text are required.",
  removeConfirmTitle: "Remove manual document?",
  removeConfirmCancel: "Cancel",
  removeConfirmProceed: "Move to Trash",
  searchIndexNote: "Search index updating. New content may appear in search shortly.",
} as const;

function removeConfirmBody(title: string): string {
  return `“${title}” will be removed from the published manual and moved to Trash. Existing historical citations remain preserved according to retention policy.`;
}

// The §6.1 toast is the headline; this keeps the concrete publish coordinates
// (title / revision / stream position) as secondary detail so the verbatim
// sentence stays an exact text node of its own.
function publishDetailText(result: PublishResult): string {
  return `Published “${result.title}” rev ${result.revision_no} at stream position ${result.stream_position}.`;
}

interface PublishNotice {
  text: string;
  detail: string;
}

// ---------------------------------------------------------------------------
// Stale anchor recovery (doc 21 §7 / §14, acceptance UM-18). A search result
// carries the anchor of the snapshot the SEARCH INDEX saw, which can lag the
// rendered stream. Opening a result therefore resolves the anchor against the
// CURRENT stream first; a miss refetches the stream and retries once; a second
// miss shows doc 21 §7's exact wording rather than a dead jump. Presentation +
// refetch only — no route path, react-query key, or OCC token is touched.
// ---------------------------------------------------------------------------

// Doc 21 §7, verbatim — never reworded.
const ANCHOR_UNAVAILABLE_MESSAGE = "The section is no longer available in the current manual.";

const ANCHOR_RETRY_ATTEMPTS = 10;
const ANCHOR_RETRY_POLL_MS = 16;

function scrollToAnchor(element: HTMLElement): void {
  // Smooth scroll, no mutation (doc 21 §7). Optional call: environments
  // without a layout engine simply have nothing to scroll.
  element.scrollIntoView?.({ behavior: "smooth", block: "start" });
}

// After the refetch a recovered section needs a render pass before its element
// exists, so the retry polls a bounded number of short frames instead of
// reading the DOM once and declaring the section gone.
async function waitForAnchorElement(anchor: string): Promise<HTMLElement | null> {
  for (let attempt = 0; attempt < ANCHOR_RETRY_ATTEMPTS; attempt += 1) {
    const element = document.getElementById(anchor);
    if (element) return element;
    await new Promise((resolve) => setTimeout(resolve, ANCHOR_RETRY_POLL_MS));
  }
  return null;
}

// User Manual (Stage 7a, doc 21; UI-21). One continuous Published reader
// flow — sticky MANUAL DOCUMENTS sidebar (search + section nav primary) next
// to a continuous reader pane: baseline guide first, appended sections in
// stream_position order. Pagination is real (server keyset), so "continuous"
// means accumulate-on-load-more rather than a client-side full array like the
// v18 mockup's in-memory doc list. Publish (Add Text / Upload) and Restore
// live behind an on-demand drawer (F-03: Upload reads a real chosen file via
// FileReader, never a manually-typed filename/content pair; Restore picks
// from real recoverable Trash entries, never a manually-typed document id).
// R2-09 (GAP item 10): the maintenance actions (add / upload / restore /
// replace / delete) render only for a server-confirmed Admin (/me projection,
// fail-closed) — presentation only; the server re-checks require_manual_admin
// on every dispatch and a stale-cache denial renders the 403 envelope
// verbatim. Baseline actions are additionally hidden from the server-truth
// is_baseline flag on the wire, not a client guess (UM-10).
export function UserManual() {
  const isAdmin = useIsAdmin();
  // Accumulate-on-load-more: `frontier` is the cursor for the next page to
  // fetch. Any successful mutation resets it to null (page 1), so a stale
  // accumulated tail never survives a stream_version change.
  const [frontier, setFrontier] = useState<string | null>(null);
  const stream = useManualStream(frontier);
  const [sections, setSections] = useState<ManualSection[]>([]);
  const meta = stream.data?.meta ?? null;
  const streamVersion = meta?.stream_version ?? null;

  useEffect(() => {
    if (!stream.data) return;
    const page = stream.data;
    setSections((previous) => {
      if (frontier === null) return page.data;
      const seen = new Set(previous.map((section) => section.document_id));
      return [...previous, ...page.data.filter((section) => !seen.has(section.document_id))];
    });
  }, [stream.data, frontier]);

  const resetToFirstPage = () => setFrontier(null);

  const softDelete = useSoftDeleteManualDocument();
  const [lastDelete, setLastDelete] = useState<DeleteResult | null>(null);

  const requestDelete = (documentId: string, reason: string) => {
    if (streamVersion === null) return;
    softDelete.mutate(
      {
        document_id: documentId,
        ...(reason.trim() ? { reason: reason.trim() } : {}),
        expected_stream_version: streamVersion,
      },
      {
        onSuccess: (result) => {
          setLastDelete(result);
          resetToFirstPage();
        },
      },
    );
  };

  const [notice, setNotice] = useState<PublishNotice | null>(null);
  const [openDrawer, setOpenDrawer] = useState<"add" | "upload" | "restore" | null>(null);

  return (
    <>
      {/* K-4: was <h2> — the only route of 23 that did not name itself with an
          <h1>. `.page-title` carries every visual property (global.css), so the
          level change is semantic only. It does move this page INTO K-5's set:
          the outline is now h1 -> h3 (the reader title below), a skip it did not
          have as h2 -> h3. Recorded, not hidden. */}
      <h1 className="page-title">User Manual</h1>
      <p className="page-sub">
        Published guide stream (doc 21) — baseline first, appended sections in stream order.
      </p>

      <div className="user-manual-shell">
        <aside className="user-manual-sidebar">
          <div className="manual-side-title">MANUAL DOCUMENTS</div>

          {/* UM-18: the search index can point at a snapshot the reader no
              longer shows, so the nav can ask the stream to rehydrate before
              it decides an anchor is gone. Refetching the CURRENT stream query
              keeps the accumulated tail intact (resetting to page 1 would drop
              later sections and could itself remove the anchor). */}
          <ManualSearchNav
            streamVersion={streamVersion}
            onRefetchStream={async () => {
              await stream.refetch();
            }}
          />

          <div className="manual-document-list">
            <div className="manual-section-label">CONTINUOUS MANUAL SECTIONS</div>
            {sections.length === 0 ? (
              <div className="manual-empty-state">No sections loaded yet.</div>
            ) : (
              sections.map((section) => (
                <a key={section.document_id} className="manual-document-item" href={`#${section.anchor}`}>
                  <b>{section.title}</b>
                  <span className="manual-document-meta">{section.source_label}</span>
                </a>
              ))
            )}
            {meta?.has_more ? (
              <button
                type="button"
                className="btn btn-ghost"
                style={{ width: "100%" }}
                disabled={stream.isFetching}
                onClick={() => {
                  if (meta.cursor !== null) setFrontier(meta.cursor);
                }}
              >
                {stream.isFetching ? "Loading…" : "Load more sections"}
              </button>
            ) : null}
          </div>

          <div className="manual-side-actions">
            {isAdmin ? (
              <>
                <button type="button" className="btn btn-ghost" onClick={() => setOpenDrawer("add")}>
                  + Add / Paste Text
                </button>
                <button type="button" className="btn btn-ghost" onClick={() => setOpenDrawer("upload")}>
                  Upload Document
                </button>
                <button type="button" className="btn btn-ghost" onClick={() => setOpenDrawer("restore")}>
                  Restore a Document
                </button>
              </>
            ) : (
              <>
                <AdminApprovalNote />
                {/* Doc 21 §6.1 "Non-Admin helper", verbatim and standing on its
                    own so the spec sentence is a text node of its own rather
                    than a suffix concatenated into the shared note. */}
                <p className="page-sub" role="note">
                  {MANUAL_COPY.nonAdminHelper}
                </p>
              </>
            )}
          </div>
        </aside>

        <section className="user-manual-reader">
          <div className="manual-reader-toolbar">
            <div>
              <h3 className="manual-reader-title">ENTROPIA USER MANUAL</h3>
              <div className="manual-reader-meta">
                Built-in guidance and added documents, shown as one continuous reading flow.
                {streamVersion !== null ? ` Stream v${streamVersion}.` : ""}
              </div>
            </div>
          </div>

          {notice ? (
            <div className="manual-notice">
              <strong>{notice.text}</strong> <span>{notice.detail}</span>
            </div>
          ) : null}
          {lastDelete ? (
            <div className="manual-notice">
              <strong>{MANUAL_COPY.softDeleteSuccess}</strong>{" "}
              <span>
                “{lastDelete.display_name ?? lastDelete.document_id}” — document{" "}
                <code>{lastDelete.document_id}</code> (stream v{lastDelete.stream_version}). Restore it
                from the sidebar or the Admin Trash page.
              </span>
            </div>
          ) : null}

          {stream.isLoading && sections.length === 0 ? <Loading label="Loading manual stream…" /> : null}
          {stream.isError ? <ErrorState error={stream.error} onRetry={() => void stream.refetch()} /> : null}

          <article className="manual-document-content">
            {sections.length === 0 && !stream.isLoading ? (
              <EmptyState title="No published sections" description="The manual stream is empty." />
            ) : (
              sections.map((section) => (
                <SectionView
                  key={section.document_id}
                  section={section}
                  isAdmin={isAdmin}
                  deletePending={softDelete.isPending}
                  deleteError={softDelete.isError ? mutationErrorText(softDelete.error) : null}
                  onDelete={requestDelete}
                />
              ))
            )}
          </article>
        </section>
      </div>

      {openDrawer === "add" ? (
        <Drawer title="Add / Paste Text" onClose={() => setOpenDrawer(null)}>
          <AddComposer
            expectedStreamVersion={streamVersion}
            onPublished={(result) => {
              resetToFirstPage();
              // Doc 21 §6.1 "Text append success".
              setNotice({ text: MANUAL_COPY.textAppendSuccess, detail: publishDetailText(result) });
              setOpenDrawer(null);
            }}
          />
        </Drawer>
      ) : null}
      {openDrawer === "upload" ? (
        <Drawer title="Upload Document" onClose={() => setOpenDrawer(null)}>
          <UploadComposer
            expectedStreamVersion={streamVersion}
            onPublished={(result) => {
              resetToFirstPage();
              // Doc 21 §6.1 "Upload success" — a distinct sentence from the
              // paste flow's, so the toast names how the document arrived.
              setNotice({ text: MANUAL_COPY.uploadSuccess, detail: publishDetailText(result) });
              setOpenDrawer(null);
            }}
          />
        </Drawer>
      ) : null}
      {openDrawer === "restore" ? (
        <Drawer title="Restore a Document" onClose={() => setOpenDrawer(null)}>
          <RestoreChooser
            onRestored={(result) => {
              resetToFirstPage();
              // Doc 21 §6.1 has no restore toast row; this stays the page's own
              // wording rather than borrowing a sentence that means something
              // else.
              setNotice({
                text: "Document restored to the continuous manual.",
                detail: `Restored “${result.display_name}” — ${result.entity_id} is ${result.deletion_state}.`,
              });
              setOpenDrawer(null);
            }}
          />
        </Drawer>
      ) : null}
    </>
  );
}

// ---------------------------------------------------------------------------
// Drawer — accessible dialog shell shared by Add / Upload / Restore (WCAG
// 2.2: role=dialog + aria-modal, Escape closes, focus trap, focus restored
// to the trigger on close, backdrop click closes).
// ---------------------------------------------------------------------------

function Drawer({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  const panelRef = useRef<HTMLDivElement | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);

  useEffect(() => {
    previouslyFocused.current = document.activeElement as HTMLElement | null;
    closeButtonRef.current?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
        return;
      }
      if (event.key !== "Tab") return;
      const focusables = panelRef.current?.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );
      if (!focusables || focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      previouslyFocused.current?.focus();
    };
  }, [onClose]);

  return (
    <div
      className="manual-drawer-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="manual-drawer" role="dialog" aria-modal="true" aria-label={title} ref={panelRef}>
        <div className="manual-drawer-header">
          <h3>{title}</h3>
          <button
            type="button"
            className="manual-drawer-close"
            onClick={onClose}
            ref={closeButtonRef}
            aria-label="Close"
          >
            ×
          </button>
        </div>
        <div className="manual-drawer-body">{children}</div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Search — server-side, search-on-submit only (a live-per-keystroke search
// would flood the backend); primary sidebar navigation alongside the section
// list. A blank query never fetches (doc 21 §14).
// ---------------------------------------------------------------------------

function ManualSearchNav({
  streamVersion,
  onRefetchStream,
}: {
  streamVersion: number | null;
  onRefetchStream: () => Promise<unknown>;
}) {
  const [input, setInput] = useState("");
  const [query, setQuery] = useState("");
  const [cursorStack, setCursorStack] = useState<string[]>([]);
  const cursor = cursorStack.length > 0 ? (cursorStack[cursorStack.length - 1] ?? null) : null;
  const search = useManualSearch(query, cursor);
  const results = search.data ?? null;

  const [recoveringAnchor, setRecoveringAnchor] = useState<string | null>(null);
  const [unavailableAnchor, setUnavailableAnchor] = useState<string | null>(null);

  // Doc 21 §7: "Anchor must exist in current stream version; if stale, refetch
  // then resolve." Honest boundary: the retry can only find what the stream
  // query returns — a section still behind an unloaded "Load more" page reads
  // as unavailable.
  const openResult = async (anchor: string): Promise<void> => {
    setUnavailableAnchor(null);
    const present = document.getElementById(anchor);
    if (present) {
      scrollToAnchor(present);
      return;
    }

    setRecoveringAnchor(anchor);
    try {
      await onRefetchStream();
    } catch {
      // A failed refetch is not a verdict — the retry below still decides from
      // what is actually rendered.
    }
    const recovered = await waitForAnchorElement(anchor);
    setRecoveringAnchor(null);
    if (recovered) {
      scrollToAnchor(recovered);
      return;
    }
    setUnavailableAnchor(anchor);
  };

  return (
    <>
      <div className="manual-search-label">Search all manual text</div>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          setCursorStack([]);
          setQuery(input);
          setUnavailableAnchor(null);
        }}
      >
        <input
          className="manual-search-input"
          type="search"
          placeholder={MANUAL_COPY.searchPlaceholder}
          value={input}
          onChange={(event) => setInput(event.target.value)}
          aria-label="Search query"
        />
        <button
          type="submit"
          className="btn btn-ghost"
          style={{ marginTop: 6, width: "100%" }}
          disabled={input.trim().length === 0}
        >
          Search
        </button>
      </form>
      <div className="manual-search-results">
        <div className="manual-section-label">SEARCH RESULTS</div>
        {/* Live region stays mounted so the recovery outcome is announced when
            it appears rather than arriving as a silent DOM insertion. */}
        <div role="status" aria-live="polite">
          {recoveringAnchor !== null ? (
            <p className="cp-note">Refreshing the manual to locate that section…</p>
          ) : null}
          {unavailableAnchor !== null ? <p className="cp-note">{ANCHOR_UNAVAILABLE_MESSAGE}</p> : null}
        </div>
        {search.isLoading && query.trim().length > 0 ? <Loading label="Searching…" /> : null}
        {search.isError ? <ErrorState error={search.error} onRetry={() => void search.refetch()} /> : null}
        {results && query.trim().length > 0 ? (
          <>
            {/* Doc 21 §6.1 "Search index note" — the reader and the index are
                on different snapshots, which the spec words as an indexing
                lag rather than a reader problem. */}
            {streamVersion !== null && streamVersion !== results.meta.stream_version ? (
              <p className="cp-note">{MANUAL_COPY.searchIndexNote}</p>
            ) : null}
            {results.data.length === 0 ? (
              // Doc 21 §6.1 "No search result".
              <div className="manual-empty-state">{MANUAL_COPY.noSearchResult}</div>
            ) : (
              results.data.map((row) => (
                // The href stays real (copyable / middle-clickable), but the
                // click is intercepted so a stale anchor recovers instead of
                // jumping nowhere (UM-18).
                <a
                  key={row.chunk_id}
                  className="manual-search-result"
                  href={`#${row.anchor}`}
                  onClick={(event) => {
                    event.preventDefault();
                    void openResult(row.anchor);
                  }}
                >
                  <b>{row.title}</b>
                  <span className="manual-result-excerpt">{row.heading_path}</span>
                  <span className="manual-result-excerpt">{row.excerpt}</span>
                  <span className="manual-document-meta">{row.source_label}</span>
                </a>
              ))
            )}
            <div className="manual-pager">
              <button
                type="button"
                className="btn btn-ghost"
                disabled={cursorStack.length === 0}
                onClick={() => setCursorStack((stack) => stack.slice(0, -1))}
              >
                Previous
              </button>
              <button
                type="button"
                className="btn btn-ghost"
                disabled={!results.meta.has_more || results.meta.cursor === null}
                onClick={() => {
                  const next = results.meta.cursor;
                  if (next !== null) setCursorStack((stack) => [...stack, next]);
                }}
              >
                Next
              </button>
            </div>
          </>
        ) : (
          /* Doc 21 §6.1 "Blank search empty-state". */
          <div className="manual-empty-state">{MANUAL_COPY.blankSearchEmptyState}</div>
        )}
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Reader section + canonical block renderer (doc 21 §9.2 — text nodes only,
// never markup injection; an unknown block type renders nothing, fail-closed)
// ---------------------------------------------------------------------------

function BlockView({ block }: { block: ManualBlock }) {
  const payload = block.payload;
  switch (block.block_type) {
    case "heading": {
      const level = typeof payload.level === "number" ? payload.level : 1;
      const text = String(payload.text ?? "");
      if (level <= 1) return <h5 id={block.anchor}>{text}</h5>;
      if (level === 2) return <h6 id={block.anchor}>{text}</h6>;
      return <h6 id={block.anchor}>{text}</h6>;
    }
    case "paragraph":
      return <p>{String(payload.text ?? "")}</p>;
    case "bullet_list":
    case "ordered_list": {
      const items = Array.isArray(payload.items) ? payload.items.map(String) : [];
      const rows = items.map((item, index) => <li key={index}>{item}</li>);
      return block.block_type === "bullet_list" ? <ul>{rows}</ul> : <ol>{rows}</ol>;
    }
    case "code": {
      const language = typeof payload.language === "string" ? payload.language : null;
      return (
        <pre className="manual-code">
          {language ? <span className="cp-note">{language}</span> : null}
          <code>{String(payload.code_text ?? "")}</code>
        </pre>
      );
    }
    case "callout": {
      const title = typeof payload.title === "string" ? payload.title : null;
      return (
        <div className="manual-callout">
          {title ? <strong>{title} — </strong> : null}
          {String(payload.text ?? "")}
        </div>
      );
    }
    case "divider":
      return <hr />;
    default:
      return null;
  }
}

interface SectionViewProps {
  section: ManualSection;
  isAdmin: boolean;
  deletePending: boolean;
  deleteError: string | null;
  onDelete: (documentId: string, reason: string) => void;
}

function SectionView({ section, isAdmin, deletePending, deleteError, onDelete }: SectionViewProps) {
  const [showReplace, setShowReplace] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deleteReason, setDeleteReason] = useState("");

  return (
    <section className="manual-appended-document" id={section.anchor}>
      <h4 className="manual-appended-document-title">{section.title}</h4>
      <div className="manual-appended-document-meta">
        {section.is_baseline ? <StatusBadge label="Baseline" tone="ok" /> : null}
        <span> rev {section.revision_no}</span> · <span>{section.source_label}</span> ·{" "}
        <span>position {section.stream_position}</span>
      </div>
      <div className="manual-blocks">
        {section.blocks.map((block) => (
          <BlockView key={block.block_id} block={block} />
        ))}
      </div>
      {/* Baseline is immutable through this flow (UM-10): the server-truth
          is_baseline flag hides replace/delete the way Trash gates Restore on
          restore_eligible. R2-09: replace/delete additionally render only for
          a server-confirmed Admin (fail-closed) — the reader itself stays the
          read-only surface for everyone else, and the server still re-checks
          Admin on every dispatch. */}
      {section.is_baseline || !isAdmin ? null : (
        <div className="manual-document-actions">
          <button type="button" className="btn btn-ghost" onClick={() => setShowReplace((v) => !v)}>
            {showReplace ? "Close replace" : "Replace content"}
          </button>
          {confirmingDelete ? (
            // Doc 21 §6.1 remove-confirmation trio: title, body ("{title}"
            // interpolated per the spec's own slot) and the Cancel |
            // Move to Trash action pair. Presentation only — the dispatch
            // below still sends the same body + expected_stream_version OCC
            // token and the same Idempotency-Key it did before.
            <div
              className="manual-remove-confirm"
              role="group"
              aria-label={MANUAL_COPY.removeConfirmTitle}
            >
              <strong>{MANUAL_COPY.removeConfirmTitle}</strong>
              <p className="cp-note">{removeConfirmBody(section.title)}</p>
              <input
                className="auth-input"
                placeholder="Reason (optional)"
                value={deleteReason}
                onChange={(event) => setDeleteReason(event.target.value)}
                aria-label={`Delete reason for ${section.title}`}
              />
              <button type="button" className="btn btn-ghost" onClick={() => setConfirmingDelete(false)}>
                {MANUAL_COPY.removeConfirmCancel}
              </button>
              <button
                type="button"
                className="btn"
                disabled={deletePending}
                onClick={() => onDelete(section.document_id, deleteReason)}
              >
                {MANUAL_COPY.removeConfirmProceed}
              </button>
            </div>
          ) : (
            <button type="button" className="btn btn-ghost" onClick={() => setConfirmingDelete(true)}>
              Delete…
            </button>
          )}
        </div>
      )}
      {confirmingDelete && deleteError ? <p className="auth-hint">{deleteError}</p> : null}
      {showReplace ? <ReplaceComposer section={section} /> : null}
    </section>
  );
}

// Publishes revision N+1 at the SAME stream position (doc 21 §7 UM-11). OCC:
// expected_head_revision_id = the section's visible head from this page's
// snapshot — a moved head is 409 MANUAL_REVISION_CONFLICT verbatim.
function ReplaceComposer({ section }: { section: ManualSection }) {
  const replace = useReplaceManualRevision();
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");

  return (
    <form
      className="manual-composer"
      onSubmit={(event) => {
        event.preventDefault();
        replace.mutate({
          document_id: section.document_id,
          content,
          ...(title.trim() ? { title: title.trim() } : {}),
          expected_head_revision_id: section.revision_id,
        });
      }}
    >
      <label className="auth-field">
        <span>
          New title <span className="auth-optional">(optional — keeps the current title)</span>
        </span>
        <input className="auth-input" value={title} onChange={(event) => setTitle(event.target.value)} />
      </label>
      <label className="auth-field">
        <span>Replacement content</span>
        <textarea
          className="auth-input"
          rows={6}
          value={content}
          onChange={(event) => setContent(event.target.value)}
        />
      </label>
      <button type="submit" className="btn btn-primary" disabled={replace.isPending || content.trim().length === 0}>
        Publish revision {section.revision_no + 1}
      </button>
      {replace.isError ? <p className="auth-hint">{mutationErrorText(replace.error)}</p> : null}
      {replace.data ? (
        <p className="cp-note">
          Published rev {replace.data.revision_no} at position {replace.data.stream_position} — stream v
          {replace.data.stream_version} (superseded {replace.data.superseded_revision_id}).
        </p>
      ) : null}
    </form>
  );
}

// ---------------------------------------------------------------------------
// Publish composers — Add / Paste Text and Upload share one pipeline (doc 21
// §14). Upload reads a real chosen file (F-03): no manual filename/content
// entry — FileReader derives the content client-side, then the SAME wire
// fields (source_filename/content/title/allow_duplicate) go to the server,
// which re-validates the extension (MANUAL_FILE_TYPE_UNSUPPORTED, UM-06).
// ---------------------------------------------------------------------------

function AddComposer({
  expectedStreamVersion,
  onPublished,
}: {
  expectedStreamVersion: number | null;
  onPublished: (result: PublishResult) => void;
}) {
  const create = useCreateManualDocument();
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [allowDuplicate, setAllowDuplicate] = useState(false);
  // Doc 21 §5: Document Title * and Full Text * are "always required" while the
  // composer is open, and the `*` is a real request-validation requirement, not
  // decoration. The client states the missing-field reason in the spec's own
  // words (§6.1) instead of leaving a silently dead button; the server still
  // re-validates the same two fields.
  const [requiredError, setRequiredError] = useState(false);

  return (
    <form
      className="manual-compose"
      onSubmit={(event) => {
        event.preventDefault();
        if (expectedStreamVersion === null) return;
        if (title.trim().length === 0 || content.trim().length === 0) {
          setRequiredError(true);
          return;
        }
        setRequiredError(false);
        create.mutate(
          {
            title: title.trim(),
            content,
            allow_duplicate: allowDuplicate,
            expected_stream_version: expectedStreamVersion,
          },
          { onSuccess: onPublished },
        );
      }}
    >
      <p className="cp-note">
        Appends are guarded by the rendered stream snapshot (v
        {expectedStreamVersion ?? "…"}) — a concurrent publish is a 409 MANUAL_STREAM_CONFLICT to
        re-read, never a silent overwrite.
      </p>
      <label className="auth-field">
        <span>
          Document Title <span className="auth-required">*</span>
        </span>
        <input
          className="auth-input"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder={MANUAL_COPY.composerTitlePlaceholder}
          aria-required="true"
        />
      </label>
      <label className="auth-field">
        <span>
          Full Text <span className="auth-required">*</span>
        </span>
        <textarea
          className="auth-input"
          rows={8}
          value={content}
          onChange={(event) => setContent(event.target.value)}
          placeholder={MANUAL_COPY.composerContentPlaceholder}
          aria-required="true"
        />
      </label>
      <label className="manual-check">
        <input
          type="checkbox"
          checked={allowDuplicate}
          onChange={(event) => setAllowDuplicate(event.target.checked)}
        />
        <span>Allow duplicate content (audited override)</span>
      </label>
      {/* Doc 21 §5: "openken enabled unless submission in progress" — the
          button stays reachable so a blank submit can name the missing fields
          in §6.1's wording instead of dead-ending on a disabled control. */}
      <button
        type="submit"
        className="btn btn-primary"
        disabled={create.isPending || expectedStreamVersion === null}
      >
        Publish document
      </button>
      {requiredError ? (
        <p className="auth-hint" role="alert">
          {MANUAL_COPY.requiredFieldsError}
        </p>
      ) : null}
      {create.isError ? <p className="auth-hint">{mutationErrorText(create.error)}</p> : null}
    </form>
  );
}

function UploadComposer({
  expectedStreamVersion,
  onPublished,
}: {
  expectedStreamVersion: number | null;
  onPublished: (result: PublishResult) => void;
}) {
  const upload = useUploadManualDocument();
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [allowDuplicate, setAllowDuplicate] = useState(false);

  const onFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    setFile(event.target.files?.[0] ?? null);
    upload.reset();
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (file === null || expectedStreamVersion === null) return;
    // F-03: transfer the chosen file itself (multipart). The server decodes the
    // bytes and re-validates size/encoding (UPLOAD_ENCODING_INVALID) + extension
    // (MANUAL_FILE_TYPE_UNSUPPORTED) — no client-side FileReader step.
    upload.mutate(
      {
        file,
        ...(title.trim() ? { title: title.trim() } : {}),
        allow_duplicate: allowDuplicate,
        expected_stream_version: expectedStreamVersion,
      },
      { onSuccess: onPublished },
    );
  };

  return (
    <form className="manual-compose" onSubmit={submit}>
      <p className="cp-note">
        UTF-8 text only ({ACCEPTED_UPLOAD_EXTENSIONS.join(", ")}) — the server re-validates the
        extension (MANUAL_FILE_TYPE_UNSUPPORTED verbatim, UM-06).
      </p>
      <label className="auth-field">
        <span>File</span>
        <input
          className="auth-input"
          type="file"
          accept={ACCEPTED_UPLOAD_EXTENSIONS.join(",")}
          onChange={onFileChange}
        />
      </label>
      {file ? <p className="cp-note">Selected: {file.name}</p> : null}
      <label className="auth-field">
        <span>
          Title <span className="auth-optional">(optional — derived from the filename)</span>
        </span>
        <input className="auth-input" value={title} onChange={(event) => setTitle(event.target.value)} />
      </label>
      <label className="manual-check">
        <input
          type="checkbox"
          checked={allowDuplicate}
          onChange={(event) => setAllowDuplicate(event.target.checked)}
        />
        <span>Allow duplicate content (audited override)</span>
      </label>
      <button
        type="submit"
        className="btn btn-primary"
        disabled={upload.isPending || expectedStreamVersion === null || file === null}
      >
        Upload &amp; publish
      </button>
      {upload.isError ? <p className="auth-hint">{mutationErrorText(upload.error)}</p> : null}
    </form>
  );
}

// ---------------------------------------------------------------------------
// Restore — real document chooser (F-03): picks from actually recoverable
// Trash entries (object_type=manual_document, restore_eligible) rather than
// a manually-typed document id. Delegates to the landed Trash core (doc 21
// §8.4 UM-09); the section returns to its original stream position.
// ---------------------------------------------------------------------------

function RestoreChooser({ onRestored }: { onRestored: (result: RestoreResult) => void }) {
  const entries = useTrashEntries({ q: null, object_type: "manual_document" }, null);
  const restore = useRestoreManualDocument();
  const [documentId, setDocumentId] = useState("");

  const recoverable = (entries.data?.data ?? []).filter((entry) => entry.restore_eligible);

  return (
    <div>
      <p className="cp-note">
        Delegates to the Admin Trash restore — the section returns to its original stream position
        (UM-09). Also available from the Trash page.
      </p>
      {entries.isLoading ? <Loading label="Loading deleted documents…" /> : null}
      {entries.isError ? <ErrorState error={entries.error} onRetry={() => void entries.refetch()} /> : null}
      {entries.data && recoverable.length === 0 ? (
        <div className="manual-empty-state">No deleted manual documents are available to restore.</div>
      ) : null}
      {recoverable.length > 0 ? (
        <form
          className="manual-compose"
          onSubmit={(event) => {
            event.preventDefault();
            if (!documentId) return;
            restore.mutate({ document_id: documentId }, { onSuccess: onRestored });
          }}
        >
          <label className="auth-field">
            <span>Document</span>
            <select
              className="auth-input"
              value={documentId}
              onChange={(event) => setDocumentId(event.target.value)}
              aria-label="Document to restore"
            >
              <option value="">Select a deleted document…</option>
              {recoverable.map((entry) => (
                <option key={entry.entity_id} value={entry.entity_id}>
                  {entry.display_name} ({entry.entity_id})
                </option>
              ))}
            </select>
          </label>
          <button type="submit" className="btn" disabled={restore.isPending || !documentId}>
            Restore
          </button>
          {restore.isError ? <p className="auth-hint">{mutationErrorText(restore.error)}</p> : null}
        </form>
      ) : null}
    </div>
  );
}
