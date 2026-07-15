import { useEffect, useRef, useState, type ChangeEvent, type FormEvent, type ReactNode } from "react";

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

function publishNoticeText(result: PublishResult): string {
  return `Published “${result.title}” rev ${result.revision_no} — added to the end of the continuous manual.`;
}

function readFileAsText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.onerror = () => reject(new Error("manual_file_unreadable"));
    reader.readAsText(file);
  });
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
// Composers are never client-gated (doc 21 §2 — UI visibility is never
// authorization); a non-Admin sees the server 403 envelope verbatim. Baseline
// actions ARE hidden, but from the server-truth is_baseline flag on the wire,
// not a client guess (UM-10).
export function UserManual() {
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

  const [notice, setNotice] = useState<string | null>(null);
  const [openDrawer, setOpenDrawer] = useState<"add" | "upload" | "restore" | null>(null);

  return (
    <>
      <h2 className="page-title">User Manual</h2>
      <p className="page-sub">
        Published guide stream (doc 21) — baseline first, appended sections in stream order.
      </p>

      <div className="user-manual-shell">
        <aside className="user-manual-sidebar">
          <div className="manual-side-title">MANUAL DOCUMENTS</div>

          <ManualSearchNav streamVersion={streamVersion} />

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
            <button type="button" className="btn btn-ghost" onClick={() => setOpenDrawer("add")}>
              + Add / Paste Text
            </button>
            <button type="button" className="btn btn-ghost" onClick={() => setOpenDrawer("upload")}>
              Upload Document
            </button>
            <button type="button" className="btn btn-ghost" onClick={() => setOpenDrawer("restore")}>
              Restore a Document
            </button>
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

          {notice ? <div className="manual-notice">{notice}</div> : null}
          {lastDelete ? (
            <div className="manual-notice">
              <strong>Deleted:</strong> {lastDelete.display_name ?? lastDelete.document_id} — document{" "}
              <code>{lastDelete.document_id}</code> moved to Trash (stream v{lastDelete.stream_version}).
              Restore it from the sidebar or the Admin Trash page.
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
              setNotice(publishNoticeText(result));
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
              setNotice(publishNoticeText(result));
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
              setNotice(`Restored “${result.display_name}” — ${result.entity_id} is ${result.deletion_state}.`);
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

function ManualSearchNav({ streamVersion }: { streamVersion: number | null }) {
  const [input, setInput] = useState("");
  const [query, setQuery] = useState("");
  const [cursorStack, setCursorStack] = useState<string[]>([]);
  const cursor = cursorStack.length > 0 ? (cursorStack[cursorStack.length - 1] ?? null) : null;
  const search = useManualSearch(query, cursor);
  const results = search.data ?? null;

  return (
    <>
      <div className="manual-search-label">Search all manual text</div>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          setCursorStack([]);
          setQuery(input);
        }}
      >
        <input
          className="manual-search-input"
          type="search"
          placeholder="Search headings or text"
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
        {search.isLoading && query.trim().length > 0 ? <Loading label="Searching…" /> : null}
        {search.isError ? <ErrorState error={search.error} onRetry={() => void search.refetch()} /> : null}
        {results && query.trim().length > 0 ? (
          <>
            {streamVersion !== null && streamVersion !== results.meta.stream_version ? (
              <p className="cp-note">
                The reader shows a different snapshot; the index may lag (re-run the search).
              </p>
            ) : null}
            {results.data.length === 0 ? (
              <div className="manual-empty-state">Nothing matched “{results.meta.query}”.</div>
            ) : (
              results.data.map((row) => (
                <a key={row.chunk_id} className="manual-search-result" href={`#${row.anchor}`}>
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
          <div className="manual-empty-state">
            Enter a word or phrase to search every part of the continuous manual.
          </div>
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
  deletePending: boolean;
  deleteError: string | null;
  onDelete: (documentId: string, reason: string) => void;
}

function SectionView({ section, deletePending, deleteError, onDelete }: SectionViewProps) {
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
          restore_eligible. Non-baseline actions still re-check Admin
          server-side. */}
      {section.is_baseline ? null : (
        <div className="manual-document-actions">
          <button type="button" className="btn btn-ghost" onClick={() => setShowReplace((v) => !v)}>
            {showReplace ? "Close replace" : "Replace content"}
          </button>
          {confirmingDelete ? (
            <>
              <input
                className="auth-input"
                placeholder="Reason (optional)"
                value={deleteReason}
                onChange={(event) => setDeleteReason(event.target.value)}
                aria-label={`Delete reason for ${section.title}`}
              />
              <button
                type="button"
                className="btn"
                disabled={deletePending}
                onClick={() => onDelete(section.document_id, deleteReason)}
              >
                Confirm delete
              </button>
              <button type="button" className="btn btn-ghost" onClick={() => setConfirmingDelete(false)}>
                Cancel
              </button>
            </>
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

  return (
    <form
      className="manual-compose"
      onSubmit={(event) => {
        event.preventDefault();
        if (expectedStreamVersion === null) return;
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
        <span>Title</span>
        <input className="auth-input" value={title} onChange={(event) => setTitle(event.target.value)} />
      </label>
      <label className="auth-field">
        <span>Content</span>
        <textarea
          className="auth-input"
          rows={8}
          value={content}
          onChange={(event) => setContent(event.target.value)}
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
      <button
        type="submit"
        className="btn btn-primary"
        disabled={
          create.isPending ||
          expectedStreamVersion === null ||
          title.trim().length === 0 ||
          content.trim().length === 0
        }
      >
        Publish document
      </button>
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
  const [readError, setReadError] = useState<string | null>(null);

  const onFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    setFile(event.target.files?.[0] ?? null);
    setReadError(null);
    upload.reset();
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (file === null || expectedStreamVersion === null) return;
    let content: string;
    try {
      content = await readFileAsText(file);
    } catch {
      setReadError("The selected document could not be read. Use a UTF-8 TXT, MD or HTML text file.");
      return;
    }
    upload.mutate(
      {
        source_filename: file.name,
        content,
        ...(title.trim() ? { title: title.trim() } : {}),
        allow_duplicate: allowDuplicate,
        expected_stream_version: expectedStreamVersion,
      },
      { onSuccess: onPublished },
    );
  };

  return (
    <form className="manual-compose" onSubmit={(event) => void submit(event)}>
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
      {readError ? <p className="auth-hint">{readError}</p> : null}
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
