import { useState } from "react";

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
  useCreateManualDocument,
  useManualSearch,
  useManualStream,
  useReplaceManualRevision,
  useRestoreManualDocument,
  useSoftDeleteManualDocument,
  useUploadManualDocument,
} from "@/lib/manual";

// Failures surface the backend canonical envelope verbatim — the client never
// invents manual-domain messages (MANUAL_STREAM_CONFLICT / MANUAL_REVISION_
// CONFLICT / MANUAL_DUPLICATE_CONTENT / BASELINE_MANUAL_IMMUTABLE arrive
// as-is, doc 21 §10).
function mutationErrorText(error: unknown): string {
  if (error instanceof ApiError) return `${error.code}: ${error.message}`;
  return error instanceof Error ? error.message : "Request failed.";
}

// User Manual (Stage 7a, doc 21). One continuous Published reader stream —
// baseline guide first, appended sections in stream_position order — plus
// server-side search over title/heading/content chunks, and the Admin
// publish/replace/delete/restore surface. Composers are never client-gated
// (doc 21 §2 — UI visibility is never authorization); a non-Admin sees the
// server 403 envelope verbatim. Baseline actions ARE hidden, but from the
// server-truth is_baseline flag on the wire, not a client guess (UM-10).
export function UserManual() {
  // Forward-only cursor stack (Trash pager pattern): push on next, pop on prev.
  const [cursorStack, setCursorStack] = useState<string[]>([]);
  const cursor = cursorStack.length > 0 ? (cursorStack[cursorStack.length - 1] ?? null) : null;
  const stream = useManualStream(cursor);
  // Const-rooted page reference: narrowing survives into the pager closures.
  const page = stream.data ?? null;
  const streamVersion = page?.meta.stream_version ?? null;

  // Delete state lives in the PARENT: a successful soft delete removes its
  // section from the refetched stream, so a result kept inside the section
  // component would vanish with it (Portfolio lesson).
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
      { onSuccess: (result) => setLastDelete(result) },
    );
  };

  return (
    <>
      <h2 className="page-title">User Manual</h2>
      <p className="page-sub">
        Published guide stream (doc 21) — baseline first, appended sections in stream order.
      </p>

      <SearchCard readerStreamVersion={streamVersion} />

      <div className="card">
        <h3>Reader</h3>
        {streamVersion !== null ? (
          <p className="cp-note">
            Stream v{streamVersion} — one snapshot per page; anchors resolve against this version.
          </p>
        ) : null}
        {stream.isLoading ? <Loading label="Loading manual stream…" /> : null}
        {stream.isError ? <ErrorState error={stream.error} onRetry={() => void stream.refetch()} /> : null}
        {page ? (
          <>
            {page.data.length === 0 ? (
              <EmptyState title="No published sections" description="The manual stream is empty." />
            ) : (
              page.data.map((section) => (
                <SectionView
                  key={section.document_id}
                  section={section}
                  deletePending={softDelete.isPending}
                  deleteError={softDelete.isError ? mutationErrorText(softDelete.error) : null}
                  onDelete={requestDelete}
                />
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
                disabled={!page.meta.has_more || page.meta.cursor === null}
                onClick={() => {
                  const next = page.meta.cursor;
                  if (next !== null) setCursorStack((stack) => [...stack, next]);
                }}
              >
                Next
              </button>
            </div>
          </>
        ) : null}
        {lastDelete ? (
          <div className="manual-callout">
            <strong>Deleted:</strong> {lastDelete.display_name ?? lastDelete.document_id} —{" "}
            document <code>{lastDelete.document_id}</code> moved to Trash (stream v
            {lastDelete.stream_version}). Restore it below or from the Admin Trash page.
          </div>
        ) : null}
      </div>

      <PublishCard expectedStreamVersion={streamVersion} />
      <RestoreCard />
    </>
  );
}

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------

function SearchCard({ readerStreamVersion }: { readerStreamVersion: number | null }) {
  const [input, setInput] = useState("");
  const [query, setQuery] = useState("");
  const [cursorStack, setCursorStack] = useState<string[]>([]);
  const cursor = cursorStack.length > 0 ? (cursorStack[cursorStack.length - 1] ?? null) : null;
  const search = useManualSearch(query, cursor);
  // Const-rooted results reference: narrowing survives into the pager closures.
  const results = search.data ?? null;

  return (
    <div className="card">
      <h3>Search the manual</h3>
      <form
        className="manual-search-form"
        onSubmit={(event) => {
          event.preventDefault();
          setCursorStack([]);
          setQuery(input);
        }}
      >
        <input
          className="auth-input"
          type="search"
          placeholder="Search titles, headings and content…"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          aria-label="Search query"
        />
        <button type="submit" className="btn btn-primary" disabled={input.trim().length === 0}>
          Search
        </button>
      </form>
      {search.isLoading && query.trim().length > 0 ? <Loading label="Searching…" /> : null}
      {search.isError ? <ErrorState error={search.error} onRetry={() => void search.refetch()} /> : null}
      {results && query.trim().length > 0 ? (
        <>
          <p className="cp-note">
            Results resolve against stream v{results.meta.stream_version}
            {readerStreamVersion !== null && readerStreamVersion !== results.meta.stream_version
              ? " — the reader shows a different snapshot; the index may lag (re-run the search)."
              : ""}
          </p>
          {results.data.length === 0 ? (
            <EmptyState title="No matches" description={`Nothing matched “${results.meta.query}”.`} />
          ) : (
            <table className="metrics-table">
              <thead>
                <tr>
                  <th>Document</th>
                  <th>Heading</th>
                  <th>Excerpt</th>
                  <th>Source</th>
                  <th>Anchor</th>
                </tr>
              </thead>
              <tbody>
                {results.data.map((row) => (
                  <tr key={row.chunk_id}>
                    <td>
                      {row.title} <span className="cp-note">rev {row.revision_no}</span>
                    </td>
                    <td>{row.heading_path}</td>
                    <td>{row.excerpt}</td>
                    <td>{row.source_label}</td>
                    <td>
                      <a href={`#${row.anchor}`}>#{row.anchor}</a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
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
      ) : null}
    </div>
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
      if (level <= 1) return <h4 id={block.anchor}>{text}</h4>;
      if (level === 2) return <h5 id={block.anchor}>{text}</h5>;
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
    <section className="manual-section" id={section.anchor}>
      <h3>{section.title}</h3>
      <div className="manual-section-meta">
        {section.is_baseline ? <StatusBadge label="Baseline" tone="ok" /> : null}
        <span>rev {section.revision_no}</span>
        <span>{section.source_label}</span>
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
        <div className="manual-actions">
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
// Admin publish composers (Add/Paste + Upload share one pipeline, doc 21 §14)
// ---------------------------------------------------------------------------

function PublishCard({ expectedStreamVersion }: { expectedStreamVersion: number | null }) {
  return (
    <div className="card">
      <h3>Publish (Admin)</h3>
      <p className="cp-note">
        Appends are guarded by the rendered stream snapshot (v
        {expectedStreamVersion ?? "…"}) — a concurrent publish is a 409 MANUAL_STREAM_CONFLICT to
        re-read, never a silent overwrite.
      </p>
      <div className="manual-publish-grid">
        <AddComposer expectedStreamVersion={expectedStreamVersion} />
        <UploadComposer expectedStreamVersion={expectedStreamVersion} />
      </div>
    </div>
  );
}

function PublishResultNote({ result }: { result: { anchor: string; revision_no: number; stream_version: number; title: string } }) {
  return (
    <p className="cp-note">
      Published “{result.title}” rev {result.revision_no} — anchor{" "}
      <a href={`#${result.anchor}`}>#{result.anchor}</a>, stream v{result.stream_version}.
    </p>
  );
}

function AddComposer({ expectedStreamVersion }: { expectedStreamVersion: number | null }) {
  const create = useCreateManualDocument();
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [allowDuplicate, setAllowDuplicate] = useState(false);

  return (
    <form
      className="manual-composer"
      onSubmit={(event) => {
        event.preventDefault();
        if (expectedStreamVersion === null) return;
        create.mutate({
          title: title.trim(),
          content,
          allow_duplicate: allowDuplicate,
          expected_stream_version: expectedStreamVersion,
        });
      }}
    >
      <h4>Add text document</h4>
      <label className="auth-field">
        <span>Title</span>
        <input className="auth-input" value={title} onChange={(event) => setTitle(event.target.value)} />
      </label>
      <label className="auth-field">
        <span>Content</span>
        <textarea
          className="auth-input"
          rows={6}
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
      {create.data ? <PublishResultNote result={create.data} /> : null}
    </form>
  );
}

function UploadComposer({ expectedStreamVersion }: { expectedStreamVersion: number | null }) {
  const upload = useUploadManualDocument();
  const [filename, setFilename] = useState("");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [allowDuplicate, setAllowDuplicate] = useState(false);

  return (
    <form
      className="manual-composer"
      onSubmit={(event) => {
        event.preventDefault();
        if (expectedStreamVersion === null) return;
        upload.mutate({
          source_filename: filename.trim(),
          content,
          ...(title.trim() ? { title: title.trim() } : {}),
          allow_duplicate: allowDuplicate,
          expected_stream_version: expectedStreamVersion,
        });
      }}
    >
      <h4>Upload document</h4>
      <p className="cp-note">
        UTF-8 text only ({ACCEPTED_UPLOAD_EXTENSIONS.join(", ")}) — the server re-validates the
        extension (MANUAL_FILE_TYPE_UNSUPPORTED verbatim, UM-06).
      </p>
      <label className="auth-field">
        <span>Source filename</span>
        <input
          className="auth-input"
          placeholder="guide.md"
          value={filename}
          onChange={(event) => setFilename(event.target.value)}
        />
      </label>
      <label className="auth-field">
        <span>
          Title <span className="auth-optional">(optional — derived from the filename)</span>
        </span>
        <input className="auth-input" value={title} onChange={(event) => setTitle(event.target.value)} />
      </label>
      <label className="auth-field">
        <span>File content (UTF-8 text)</span>
        <textarea
          className="auth-input"
          rows={6}
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
          upload.isPending ||
          expectedStreamVersion === null ||
          filename.trim().length === 0 ||
          content.trim().length === 0
        }
      >
        Upload &amp; publish
      </button>
      {upload.isError ? <p className="auth-hint">{mutationErrorText(upload.error)}</p> : null}
      {upload.data ? <PublishResultNote result={upload.data} /> : null}
    </form>
  );
}

// ---------------------------------------------------------------------------
// Restore (doc 21 §8.4 UM-09 — Trash-core delegate addressed by document id)
// ---------------------------------------------------------------------------

function RestoreCard() {
  const restore = useRestoreManualDocument();
  const [documentId, setDocumentId] = useState("");

  return (
    <div className="card">
      <h3>Restore a deleted document (Admin)</h3>
      <p className="cp-note">
        Delegates to the Admin Trash restore — the section returns to its original stream position
        (UM-09). Also available from the Trash page.
      </p>
      <form
        className="manual-search-form"
        onSubmit={(event) => {
          event.preventDefault();
          restore.mutate({ document_id: documentId.trim() });
        }}
      >
        <input
          className="auth-input"
          placeholder="mdoc_…"
          value={documentId}
          onChange={(event) => setDocumentId(event.target.value)}
          aria-label="Document id to restore"
        />
        <button type="submit" className="btn" disabled={restore.isPending || documentId.trim().length === 0}>
          Restore
        </button>
      </form>
      {restore.isError ? <p className="auth-hint">{mutationErrorText(restore.error)}</p> : null}
      {restore.data ? (
        <p className="cp-note">
          Restored “{restore.data.display_name}” — {restore.data.entity_id} is{" "}
          {restore.data.deletion_state}.
        </p>
      ) : null}
    </div>
  );
}
