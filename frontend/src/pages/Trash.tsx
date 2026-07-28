import { useState, type FormEvent } from "react";

import { useIsAdmin } from "@/components/AdminGate";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { StatusBadge } from "@/components/StatusBadge";
import { ApiError } from "@/lib/apiClient";
import { useReauth } from "@/lib/auth";
import { formatUtc } from "@/lib/backtest";
import {
  DEFAULT_TRASH_FILTERS,
  RESTORE_CONFLICT_CODE,
  purgeStatusTone,
  restoreConflictOptions,
  useRequestPurge,
  useRestoreEntry,
  useRestorePreflight,
  useTrashEntries,
  useTrashEntry,
  type RestoreResolutionOption,
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

// UI-20 / Admin Trash (doc 20 §7): "Panel / Trash" title + recoverable
// soft-deleted index + an UPPER JSON snapshot panel (opened per row, above the
// table — the v18 mockup shape, not a generic bottom-of-page detail view) +
// OCC restore + OCC-guarded Permanent Delete. Every surface is Admin-only
// server-side — a non-Admin sees the 403 envelope verbatim (UI visibility is
// never authorization, doc 20 §2). Permanent Delete is a destructive two-phase
// 202 that requires a second confirmation phrase (the exact object name) AND a
// REAL re-authentication proof (F-21): the operator's password is re-verified
// through `POST /auth/reauth` and the short-lived, single-use, purpose-scoped
// token it mints is what actually authorizes the purge — no arbitrary text
// ever reaches the server as a proof.
export function Trash() {
  return (
    <>
      <h1 className="page-title">Panel / Trash</h1>
      <p className="page-sub">
        Admin-only recoverable soft-deleted objects · restore returns the object with its
        original id and revision (no new version) · Permanent Delete starts an irreversible,
        retention-checked purge
      </p>
      <TrashCard />
    </>
  );
}

function TrashCard() {
  // R2-09 (GAP item 10): restore / permanent delete are Admin-only — the row
  // actions render only for a server-confirmed Admin (/me projection,
  // fail-closed). Presentation only: the server re-checks require_trash_admin
  // on every call and a stale-cache denial renders the 403 envelope verbatim.
  const isAdmin = useIsAdmin();
  const [filters, setFilters] = useState<TrashFilters>(DEFAULT_TRASH_FILTERS);
  const [draftQ, setDraftQ] = useState("");
  const [snapshotEntryId, setSnapshotEntryId] = useState<string | null>(null);
  const [purgeTarget, setPurgeTarget] = useState<TrashEntry | null>(null);
  // The purge 202 return omits display_name (only entity_id/type); capture the
  // human name at accept time so the toast can echo the object name (doc 20 §9).
  const [purgedName, setPurgedName] = useState<string | null>(null);
  // O-17: the entry whose restore came back RESTORE_CONFLICT. Holding the entry
  // (not just a flag) keeps the retry on the SAME expected deletion version the
  // Admin reviewed, per doc 20 §8.2.
  const [conflictTarget, setConflictTarget] = useState<TrashEntry | null>(null);
  const pager = useCursorStack();
  const entries = useTrashEntries(filters, pager.cursor);
  const restore = useRestoreEntry();

  // A restore attempt, optionally carrying the typed resolution the Admin chose
  // from the server's option set. Only a RESTORE_CONFLICT opens the "Restore
  // needs attention" panel; every other failure keeps rendering the canonical
  // envelope verbatim, exactly as before.
  const runRestore = (entry: TrashEntry, resolution?: string) => {
    setConflictTarget(null);
    restore.mutate(
      {
        trash_entry_id: entry.trash_entry_id,
        expected_head_revision_id: entry.row_version,
        ...(resolution !== undefined ? { resolution } : {}),
      },
      {
        onError: (error) => {
          if (error instanceof ApiError && error.code === RESTORE_CONFLICT_CODE) {
            setConflictTarget(entry);
          }
        },
      },
    );
  };
  // Purge mutation state lives in the card (not the composer) so the accepted
  // result survives the composer closing after a successful request.
  const purge = useRequestPurge();

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
    <section className="card panel-card" aria-labelledby="trash-h">
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

      {/* Snapshot content renders in this UPPER panel, above the table — the
          same position it holds in the v18 mockup — rather than only inside a
          generic bottom-of-page entry-detail view. */}
      {snapshotEntryId ? (
        <SnapshotPanel entryId={snapshotEntryId} onClose={() => setSnapshotEntryId(null)} />
      ) : null}

      {entries.isLoading ? (
        <Loading label="Loading trash…" />
      ) : entries.isError ? (
        <ErrorState error={entries.error} onRetry={() => void entries.refetch()} />
      ) : entries.data ? (
        <>
          {entries.data.data.length === 0 ? (
            <EmptyState title="No recoverable objects match the current filters" />
          ) : (
            <table className="database-table">
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
                    isAdmin={isAdmin}
                    onRestore={() => runRestore(entry)}
                    onPurge={() => {
                      purge.reset();
                      setPurgeTarget(entry);
                    }}
                    onOpenSnapshot={() => setSnapshotEntryId(entry.trash_entry_id)}
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

      {/* A restore conflict gets the doc 20 §6 panel instead of a bare error
          line — it is the only failure with alternatives to choose from. */}
      {restore.isError && conflictTarget === null ? (
        <p role="alert" style={{ color: "var(--down)", marginBottom: 0 }}>
          {mutationErrorText(restore.error)}
        </p>
      ) : null}
      {conflictTarget ? (
        <RestoreConflictPanel
          entry={conflictTarget}
          errorSummary={
            restore.error instanceof ApiError ? restore.error.message : "the restore preflight failed"
          }
          errorOptions={restoreConflictOptions(restore.error)}
          isRestoring={restore.isPending}
          onRetry={(resolution) => runRestore(conflictTarget, resolution)}
          onDismiss={() => {
            restore.reset();
            setConflictTarget(null);
          }}
        />
      ) : null}
      {restore.data ? (
        <p aria-live="polite">
          Restored — {restore.data.display_name} ({restore.data.entity_type}) back to{" "}
          {restore.data.deletion_state} (v{restore.data.row_version}).
          {restore.data.applied_resolution
            ? ` Applied resolution: ${restore.data.applied_resolution}.`
            : ""}
        </p>
      ) : null}

      {purgeTarget ? (
        <PurgeComposer
          entry={purgeTarget}
          isPurging={purge.isPending}
          error={purge.isError ? purge.error : null}
          onCancel={() => {
            purge.reset();
            setPurgeTarget(null);
          }}
          onConfirm={(confirmationPhrase, reauthProof) =>
            purge.mutate(
              {
                trash_entry_id: purgeTarget.trash_entry_id,
                confirmation_phrase: confirmationPhrase,
                reauth_proof: reauthProof,
                expected_head_revision_id: purgeTarget.row_version,
              },
              // The request was accepted (202) — close the composer; the card
              // keeps `purge.data` so the accepted toast renders below.
              {
                onSuccess: () => {
                  setPurgedName(purgeTarget.display_name);
                  setPurgeTarget(null);
                },
              },
            )
          }
        />
      ) : null}

      {/* doc 20 §9 Purge accepted toast — verbatim, only after the 202. */}
      {purge.data ? (
        <p aria-live="polite" style={{ color: "var(--warn)" }}>
          Permanent deletion was requested for “{purgedName ?? purge.data.entity_id}”. Track the
          purge status before leaving this page. (job {purge.data.purge_job_id})
        </p>
      ) : null}
    </section>
  );
}

function TrashRow({
  entry,
  isAdmin,
  onRestore,
  onPurge,
  onOpenSnapshot,
  isRestoring,
}: {
  entry: TrashEntry;
  isAdmin: boolean;
  onRestore: () => void;
  onPurge: () => void;
  onOpenSnapshot: () => void;
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
          isAdmin ? (
            <>
              <button type="button" className="btn" disabled={isRestoring} onClick={onRestore}>
                Restore
              </button>{" "}
              {/* Permanent Delete is eligible on the same recoverable statuses as
                  Restore (the purge command shares _assert_entry_recoverable); it
                  opens the confirmation composer, it never purges on click. */}
              <button type="button" className="btn btn-danger" onClick={onPurge}>
                Permanent Delete
              </button>{" "}
            </>
          ) : (
            // R2-09: no primary control for an unauthorized user — the entry
            // state stays read-only with the reason spelled out.
            <span className="page-sub" role="note">
              Admin approval required
            </span>
          )
        ) : (
          <span className="page-sub">not restorable</span>
        )}{" "}
        <button type="button" className="btn" onClick={onOpenSnapshot}>
          Open Snapshot
        </button>
      </td>
    </tr>
  );
}

// doc 20 §6 "Restore needs attention" (O-17). The restore command refused and
// returned a TYPED conflict; this panel renders the §6 copy verbatim and lets
// the Admin pick ONLY from the resolutions the domain adapter offered.
//
// Three honest outcomes, none of them invented client-side:
//   - options present  -> choose one, retry on the SAME expected deletion version
//   - options empty    -> nothing can unblock it; the object stays in Trash
//   - preflight allow  -> the record changed and the conflict cleared; plain retry
//
// "Re-check" re-reads the canonical preflight — doc 20 §8.2's "Admin refreshes
// canonical detail" after the record moved. The client never repairs anything.
function RestoreConflictPanel({
  entry,
  errorSummary,
  errorOptions,
  isRestoring,
  onRetry,
  onDismiss,
}: {
  entry: TrashEntry;
  errorSummary: string;
  errorOptions: RestoreResolutionOption[];
  isRestoring: boolean;
  onRetry: (resolution?: string) => void;
  onDismiss: () => void;
}) {
  const [chosen, setChosen] = useState<string | null>(null);
  const preflight = useRestorePreflight(entry.trash_entry_id);

  // The live preflight is canonical once it lands; until then the 409 envelope
  // (same catalog, captured a moment earlier) drives the panel.
  const live = preflight.data;
  const cleared = live?.outcome === "allow";
  const summary = live?.conflict_summary ?? errorSummary;
  const options = live ? live.resolutions : errorOptions;
  const chosenIsOffered = chosen !== null && options.some((o) => o.resolution === chosen);

  return (
    <section
      aria-labelledby="restore-conflict-h"
      style={{
        marginTop: 16,
        padding: 12,
        border: "1px solid var(--warn)",
        borderRadius: 6,
      }}
    >
      <h4 id="restore-conflict-h" style={{ marginTop: 0 }}>
        Restore needs attention
      </h4>
      {/* doc 20 §6 conflict copy — verbatim, with {conflict_summary} filled in. */}
      <p className="page-sub" style={{ marginTop: 0 }} role="alert">
        This object cannot be restored automatically because: {summary}. Review the available
        domain-specific resolution options. No change has been applied; the object remains in
        Trash.
      </p>

      {cleared ? (
        <p aria-live="polite">
          The conflict no longer applies — the record changed since the failed attempt. Restore
          can be retried as-is.
        </p>
      ) : options.length === 0 ? (
        // An empty option set is the server's real answer, not a loading state.
        <p aria-live="polite">
          No resolution options are available for this conflict. “{entry.display_name}” stays in
          Trash until the underlying record is repaired.
        </p>
      ) : (
        <fieldset style={{ border: "1px solid var(--border)", borderRadius: 6, marginBottom: 12 }}>
          <legend>Resolution options</legend>
          {options.map((option) => (
            <label
              key={option.resolution}
              htmlFor={`restore-resolution-${option.resolution}`}
              style={{ display: "block", marginBottom: 8 }}
            >
              <input
                id={`restore-resolution-${option.resolution}`}
                type="radio"
                name="restore-resolution"
                value={option.resolution}
                checked={chosen === option.resolution}
                onChange={() => setChosen(option.resolution)}
              />{" "}
              {option.label}
              {option.description ? (
                <span className="page-sub" style={{ display: "block", marginLeft: 24 }}>
                  {option.description}
                </span>
              ) : null}
            </label>
          ))}
        </fieldset>
      )}

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        {cleared || options.length > 0 ? (
          <button
            type="button"
            className="btn"
            // doc 20 §8.2: with a conflict outstanding the command cannot be
            // started without a resolution the server itself offered.
            disabled={isRestoring || (!cleared && !chosenIsOffered)}
            onClick={() => onRetry(cleared ? undefined : (chosen ?? undefined))}
          >
            {isRestoring ? "Restoring…" : "Retry restore"}
          </button>
        ) : null}
        <button
          type="button"
          className="btn"
          disabled={preflight.isFetching}
          onClick={() => void preflight.refetch()}
        >
          {preflight.isFetching ? "Re-checking…" : "Re-check"}
        </button>
        <button type="button" className="btn" onClick={onDismiss} disabled={isRestoring}>
          Close
        </button>
      </div>
    </section>
  );
}

function SnapshotPanel({ entryId, onClose }: { entryId: string; onClose: () => void }) {
  const detail = useTrashEntry(entryId);
  return (
    <div
      style={{
        marginBottom: 16,
        padding: 12,
        border: "1px solid var(--border)",
        borderRadius: 6,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <h4 style={{ margin: 0 }}>Snapshot{detail.data ? `: ${detail.data.display_name}` : ""}</h4>
        <button type="button" className="btn" onClick={onClose}>
          Close
        </button>
      </div>
      {detail.isLoading ? (
        <Loading label="Loading snapshot…" />
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

// Permanent Delete confirmation (doc 20 §8.3, §9; F-21): a two-step gate that
// must collect BOTH the exact object name AND the Admin's current password
// before any purge command is sent. The password is never sent as the proof
// itself — Confirm first calls `POST /auth/reauth` to re-verify it and mint a
// short-lived, single-use, purpose-scoped proof, and ONLY that server-issued
// token is forwarded to the purge command. A wrong password fails at the
// re-auth step and never reaches purge at all.
function PurgeComposer({
  entry,
  isPurging,
  error,
  onCancel,
  onConfirm,
}: {
  entry: TrashEntry;
  isPurging: boolean;
  error: unknown;
  onCancel: () => void;
  onConfirm: (confirmationPhrase: string, reauthProof: string) => void;
}) {
  const [confirmationPhrase, setConfirmationPhrase] = useState("");
  const [password, setPassword] = useState("");
  const reauth = useReauth();
  // The server checks confirmation_phrase against display_name || entity_id;
  // the list projection already resolves display_name to that same fallback.
  const phraseMatches = confirmationPhrase.trim() === entry.display_name;
  const busy = isPurging || reauth.isPending;
  const canConfirm = phraseMatches && password.length > 0 && !busy;

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (!canConfirm) return;
    reauth.mutate(
      { password, purpose: "trash_purge" },
      { onSuccess: (result) => onConfirm(confirmationPhrase.trim(), result.reauth_proof) },
    );
  };

  return (
    <form
      onSubmit={onSubmit}
      aria-labelledby="purge-h"
      style={{
        marginTop: 16,
        padding: 12,
        border: "1px solid var(--down)",
        borderRadius: 6,
      }}
    >
      <h4 id="purge-h" style={{ marginTop: 0, color: "var(--down)" }}>
        Permanent Delete
      </h4>
      {/* doc 20 §9 permanent delete confirmation copy — verbatim. */}
      <p className="page-sub" style={{ marginTop: 0 }}>
        Permanently delete “{entry.display_name}” ({entry.object_type})? This starts an
        irreversible purge of eligible recoverable payloads. The object cannot be restored after
        purge. Audit evidence and a minimal tombstone remain. Enter the object name and complete
        Admin re-authentication to continue.
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 10, maxWidth: 420 }}>
        <label htmlFor="purge-phrase">
          Type the object name to confirm{" "}
          <input
            id="purge-phrase"
            value={confirmationPhrase}
            onChange={(event) => setConfirmationPhrase(event.target.value)}
            placeholder={entry.display_name}
            autoComplete="off"
          />
        </label>
        <label htmlFor="purge-reauth">
          Admin password (re-authentication){" "}
          <input
            id="purge-reauth"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
          />
        </label>
        {confirmationPhrase.trim().length > 0 && !phraseMatches ? (
          <span className="page-sub" style={{ color: "var(--down)" }}>
            The confirmation phrase must match the object name exactly.
          </span>
        ) : null}
        <div style={{ display: "flex", gap: 12 }}>
          <button type="submit" className="btn btn-danger" disabled={!canConfirm}>
            {reauth.isPending
              ? "Re-authenticating…"
              : isPurging
                ? "Requesting…"
                : "Confirm permanent delete"}
          </button>
          <button type="button" className="btn" onClick={onCancel} disabled={busy}>
            Cancel
          </button>
        </div>
        {reauth.isError ? (
          <p role="alert" style={{ color: "var(--down)", margin: 0 }}>
            {mutationErrorText(reauth.error)}
          </p>
        ) : error ? (
          <p role="alert" style={{ color: "var(--down)", margin: 0 }}>
            {mutationErrorText(error)}
          </p>
        ) : null}
      </div>
    </form>
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
