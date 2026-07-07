import { useState, type FormEvent } from "react";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { StatusBadge } from "@/components/StatusBadge";
import { ApiError } from "@/lib/apiClient";
import { formatUtc } from "@/lib/backtest";
import {
  DEFAULT_TRASH_FILTERS,
  purgeStatusTone,
  useRestoreEntry,
  useTrashEntries,
  useTrashEntry,
  type TrashEntry,
  type TrashFilters,
} from "@/lib/trash";

// Wide JSON snapshots wrap + scroll inside their own box (never widen the page).
const snapshotStyle = {
  fontFamily: "monospace",
  fontSize: 12,
  whiteSpace: "pre-wrap",
  wordBreak: "break-all",
  maxHeight: 240,
  overflow: "auto",
  margin: 0,
  padding: 8,
  border: "1px solid var(--border)",
  borderRadius: 6,
} as const;

// Command failures surface the backend canonical envelope verbatim — the
// client never invents trash-domain messages (mirrors Panel / AnalysisLab).
function mutationErrorText(error: unknown): string {
  if (error instanceof ApiError) return `${error.code}: ${error.message}`;
  return error instanceof Error ? error.message : "Request failed.";
}

// Forward-only opaque keyset cursors (server contract): Prev replays the
// cursor stack, the client never re-orders or fabricates a page.
function useCursorStack() {
  const [stack, setStack] = useState<string[]>([]);
  const cursor = stack.length > 0 ? stack[stack.length - 1] : null;
  return {
    cursor,
    canPrev: stack.length > 0,
    next: (nextCursor: string) => setStack((prev) => [...prev, nextCursor]),
    prev: () => setStack((prev) => prev.slice(0, -1)),
    reset: () => setStack([]),
  };
}

// Admin Trash (doc 20 §7): the recoverable soft-deleted index + immutable
// snapshot detail + OCC restore. Admin-only server-side — a non-Admin sees the
// 403 envelope verbatim (UI visibility is never authorization, doc 20 §2).
// Purge (destructive, needs a re-auth proof) is intentionally out of scope for
// this restore-focused slice; the Restore action is the payoff here.
export function Trash() {
  return (
    <>
      <h1 className="page-title">Trash</h1>
      <p className="page-sub">
        Admin-only recoverable soft-deleted objects · restore returns the object with its
        original id and revision (no new version)
      </p>
      <TrashCard />
    </>
  );
}

function TrashCard() {
  const [filters, setFilters] = useState<TrashFilters>(DEFAULT_TRASH_FILTERS);
  const [draftQ, setDraftQ] = useState("");
  const [selectedEntryId, setSelectedEntryId] = useState<string | null>(null);
  const pager = useCursorStack();
  const entries = useTrashEntries(filters, pager.cursor);
  const restore = useRestoreEntry();

  const applyFilter = (patch: Partial<TrashFilters>) => {
    setFilters((prev) => ({ ...prev, ...patch }));
    pager.reset();
  };

  const onSearch = (event: FormEvent) => {
    event.preventDefault();
    applyFilter({ q: draftQ.trim() || null });
  };

  // The object_type filter options come from the server response, never a
  // hard-coded client list.
  const objectTypes = entries.data?.meta.object_types ?? [];

  return (
    <section className="card" aria-labelledby="trash-h">
      <h3 id="trash-h" style={{ marginTop: 0 }}>
        Recoverable entries
        {entries.data ? (
          <span className="page-sub" style={{ marginLeft: 8 }}>
            ({entries.data.meta.recoverable_total} recoverable)
          </span>
        ) : null}
      </h3>
      <form
        onSubmit={onSearch}
        style={{ display: "flex", flexWrap: "wrap", gap: 12, marginBottom: 12 }}
      >
        <label htmlFor="trash-type">
          Object type{" "}
          <select
            id="trash-type"
            value={filters.object_type ?? ""}
            onChange={(event) => applyFilter({ object_type: event.target.value || null })}
          >
            <option value="">all</option>
            {objectTypes.map((objectType) => (
              <option key={objectType} value={objectType}>
                {objectType}
              </option>
            ))}
          </select>
        </label>
        <label htmlFor="trash-q">
          Search{" "}
          <input
            id="trash-q"
            value={draftQ}
            onChange={(event) => setDraftQ(event.target.value)}
            placeholder="name / owner"
          />
        </label>
        <button type="submit" className="btn">
          Search
        </button>
      </form>

      {entries.isLoading ? (
        <Loading label="Loading trash…" />
      ) : entries.isError ? (
        <ErrorState error={entries.error} onRetry={() => void entries.refetch()} />
      ) : entries.data ? (
        <>
          {entries.data.data.length === 0 ? (
            <EmptyState title="No recoverable objects match the current filters" />
          ) : (
            <table className="metrics-table">
              <thead>
                <tr>
                  <th scope="col">Object type</th>
                  <th scope="col">Name</th>
                  <th scope="col">Deleted (UTC)</th>
                  <th scope="col">Reason</th>
                  <th scope="col">Status</th>
                  <th scope="col" aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {entries.data.data.map((entry) => (
                  <TrashRow
                    key={entry.trash_entry_id}
                    entry={entry}
                    onRestore={() =>
                      restore.mutate({
                        trash_entry_id: entry.trash_entry_id,
                        expected_head_revision_id: entry.row_version,
                      })
                    }
                    onDetail={() => setSelectedEntryId(entry.trash_entry_id)}
                    isRestoring={restore.isPending}
                  />
                ))}
              </tbody>
            </table>
          )}
          <Pager
            canPrev={pager.canPrev}
            nextCursor={entries.data.meta.cursor}
            onPrev={pager.prev}
            onNext={pager.next}
          />
        </>
      ) : null}

      {restore.isError ? (
        <p role="alert" style={{ color: "var(--down)", marginBottom: 0 }}>
          {mutationErrorText(restore.error)}
        </p>
      ) : null}
      {restore.data ? (
        <p aria-live="polite">
          Restored — {restore.data.display_name} ({restore.data.entity_type}) back to{" "}
          {restore.data.deletion_state} (v{restore.data.row_version}).
        </p>
      ) : null}

      {selectedEntryId ? (
        <TrashDetail entryId={selectedEntryId} onClose={() => setSelectedEntryId(null)} />
      ) : null}
    </section>
  );
}

function TrashRow({
  entry,
  onRestore,
  onDetail,
  isRestoring,
}: {
  entry: TrashEntry;
  onRestore: () => void;
  onDetail: () => void;
  isRestoring: boolean;
}) {
  return (
    <tr>
      <td>
        <code>{entry.object_type}</code>
      </td>
      <td>{entry.display_name}</td>
      <td>
        {formatUtc(entry.deleted_at)}
        {entry.deleted_by ? ` by ${entry.deleted_by}` : ""}
      </td>
      <td>{entry.delete_reason ?? "—"}</td>
      <td>
        <StatusBadge
          tone={purgeStatusTone(entry.purge_status)}
          label={entry.purge_status ?? entry.status}
        />
      </td>
      <td>
        {entry.restore_eligible ? (
          <button type="button" className="btn" disabled={isRestoring} onClick={onRestore}>
            Restore
          </button>
        ) : (
          <span className="page-sub">not restorable</span>
        )}{" "}
        <button type="button" className="btn" onClick={onDetail}>
          Detail
        </button>
      </td>
    </tr>
  );
}

function TrashDetail({ entryId, onClose }: { entryId: string; onClose: () => void }) {
  const detail = useTrashEntry(entryId);
  return (
    <div style={{ marginTop: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <h4 style={{ margin: 0 }}>Entry detail</h4>
        <button type="button" className="btn" onClick={onClose}>
          Close
        </button>
      </div>
      {detail.isLoading ? (
        <Loading label="Loading entry…" />
      ) : detail.isError ? (
        <ErrorState error={detail.error} onRetry={() => void detail.refetch()} />
      ) : detail.data ? (
        <>
          <dl className="kv">
            <dt>Object</dt>
            <dd>
              <code>{detail.data.object_type}</code> · {detail.data.display_name} (
              {detail.data.entity_id})
            </dd>
            <dt>Original location</dt>
            <dd>
              {detail.data.original_location ?? "—"}
              {detail.data.original_owner ? ` · owner ${detail.data.original_owner}` : ""}
            </dd>
            <dt>Deleted</dt>
            <dd>
              {formatUtc(detail.data.deleted_at)}
              {detail.data.deleted_by ? ` by ${detail.data.deleted_by}` : ""}
              {detail.data.delete_reason ? ` — ${detail.data.delete_reason}` : ""}
            </dd>
            <dt>Deletion state</dt>
            <dd>{detail.data.current_deletion_state ?? "—"}</dd>
            <dt>Restore</dt>
            <dd>
              {detail.data.restore_eligible ? "eligible" : "not eligible"}
              {detail.data.restored_at
                ? ` · restored ${formatUtc(detail.data.restored_at)}${
                    detail.data.restored_by ? ` by ${detail.data.restored_by}` : ""
                  }`
                : ""}
            </dd>
            {detail.data.purge_error ? (
              <>
                <dt>Purge error</dt>
                <dd style={{ color: "var(--down)" }}>{detail.data.purge_error}</dd>
              </>
            ) : null}
            {detail.data.tombstone ? (
              <>
                <dt>Tombstone</dt>
                <dd>
                  purged {formatUtc(detail.data.tombstone.purged_at)}
                  {detail.data.tombstone.purged_by ? ` by ${detail.data.tombstone.purged_by}` : ""}
                </dd>
              </>
            ) : null}
          </dl>
          <h5 style={{ marginBottom: 4 }}>Deletion snapshot</h5>
          <pre style={snapshotStyle}>{JSON.stringify(detail.data.deletion_snapshot, null, 2)}</pre>
          <h5 style={{ marginBottom: 4 }}>Dependency snapshot</h5>
          <pre style={snapshotStyle}>
            {JSON.stringify(detail.data.dependency_snapshot, null, 2)}
          </pre>
        </>
      ) : null}
    </div>
  );
}

function Pager({
  canPrev,
  nextCursor,
  onPrev,
  onNext,
}: {
  canPrev: boolean;
  nextCursor: string | null;
  onPrev: () => void;
  onNext: (cursor: string) => void;
}) {
  if (!canPrev && nextCursor === null) return null;
  return (
    <div style={{ display: "flex", gap: 12, marginTop: 12 }}>
      <button type="button" className="btn" disabled={!canPrev} onClick={onPrev}>
        Prev
      </button>
      <button
        type="button"
        className="btn"
        disabled={nextCursor === null}
        onClick={() => (nextCursor !== null ? onNext(nextCursor) : undefined)}
      >
        Next
      </button>
    </div>
  );
}
