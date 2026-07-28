// Admin Trash data access (Stage 6c doc 20 §7): the recoverable soft-deleted
// entry index, the immutable per-entry snapshot detail, and the OCC-guarded
// restore. Every surface is Admin-only at the ROUTE and again in the service
// (require_trash_admin) — a hidden nav item is never authorization (doc 20 §2);
// a non-Admin sees the server 403 envelope verbatim.
//
// Trash has no dedicated SSE event: a restore changes an entity's lifecycle
// (resource.changed → full refresh) and emits an audit event
// (audit.event.created → ["audit"]). Read keys live under ["trash"]; the
// restore mutation invalidates ["trash"] + ["audit"] the same way
// lib/adminPanel.ts useAssignRole does.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, api, apiRequest } from "./apiClient";

// ---------------------------------------------------------------------------
// Wire types (mirror backend application/queries/trash.py `_row`/detail and
// application/commands/deletion.py restore return verbatim)
// ---------------------------------------------------------------------------

export interface TrashEntry {
  trash_entry_id: string;
  entity_id: string;
  object_type: string;
  display_name: string;
  original_location: string | null;
  original_owner: string | null;
  deleted_by: string | null;
  deleted_at: string | null;
  delete_reason: string | null;
  status: string;
  purge_status: string | null;
  purge_job_id: string | null;
  restore_eligible: boolean;
  row_version: number;
  correlation_id: string | null;
}

export interface TrashEntriesPage {
  data: TrashEntry[];
  meta: {
    cursor: string | null;
    has_more: boolean;
    limit: number;
    recoverable_total: number;
    object_types: string[];
  };
}

export interface TrashTombstone {
  purged_at: string | null;
  purged_by: string | null;
}

export interface TrashEntryDetail extends TrashEntry {
  deletion_snapshot: Record<string, unknown>;
  dependency_snapshot: Record<string, unknown>;
  purge_error: string | null;
  purge_requested_by: string | null;
  restored_at: string | null;
  restored_by: string | null;
  current_deletion_state: string | null;
  tombstone: TrashTombstone | null;
}

export interface RestoreResult {
  trash_entry_id: string;
  entity_id: string;
  entity_type: string;
  display_name: string;
  status: string;
  deletion_state: string;
  current_revision_id: string | number | null;
  // O-17: the typed resolution that actually unlocked this restore, or null when
  // it restored cleanly and nothing needed resolving.
  applied_resolution: string | null;
  row_version: number;
  correlation_id: string | null;
}

// ---------------------------------------------------------------------------
// Restore preflight + typed conflict resolutions (O-17, doc 20 §5, §6, §8.2)
// ---------------------------------------------------------------------------

// One option the DOMAIN adapter offers. The client never invents, renames or
// filters these — an empty option set means nothing can unblock the conflict
// and the object stays in Trash (doc 20 §8.2).
export interface RestoreResolutionOption {
  conflict_kind: string;
  resolution: string;
  label: string;
  description: string;
}

export interface RestorePreflight {
  trash_entry_id: string;
  entity_id: string;
  object_type: string;
  display_name: string;
  expected_head_revision_id: number;
  outcome: "allow" | "conflict" | "blocked";
  blocked_reason: string | null;
  conflict_kind: string | null;
  conflict_summary: string | null;
  resolutions: RestoreResolutionOption[];
}

export const RESTORE_CONFLICT_CODE = "RESTORE_CONFLICT";

// The 409 envelope carries the same catalog the preflight read returns: message
// is the {conflict_summary} doc 20 §6 interpolates, details is one row per typed
// resolution. Parsed defensively — a row without a resolution token is dropped
// rather than rendered as a nameless choice.
export function restoreConflictOptions(error: unknown): RestoreResolutionOption[] {
  if (!(error instanceof ApiError) || error.code !== RESTORE_CONFLICT_CODE) return [];
  return error.details.flatMap((row) => {
    const resolution = typeof row.resolution === "string" ? row.resolution : null;
    if (resolution === null) return [];
    return [
      {
        conflict_kind: typeof row.conflict_kind === "string" ? row.conflict_kind : "",
        resolution,
        label: typeof row.label === "string" ? row.label : resolution,
        description: typeof row.description === "string" ? row.description : "",
      },
    ];
  });
}

// Purge request 202 return (mirrors commands/deletion.py request_purge dict
// verbatim): the target moved to purge_pending and a durable maintenance job
// is enqueued (doc 20 §8.3). The purge itself runs in the worker — the request
// only accepts the job.
export interface PurgeResult {
  purge_job_id: string;
  trash_entry_id: string;
  entity_id: string;
  entity_type: string;
  deletion_state: string;
  purge_status: string;
  row_version: number;
  correlation_id: string | null;
}

// ---------------------------------------------------------------------------
// Filters — the object_type option list is hydrated from the server response
// (`meta.object_types`), never a hard-coded client list.
// ---------------------------------------------------------------------------

export interface TrashFilters {
  q: string | null;
  object_type: string | null;
}

export const DEFAULT_TRASH_FILTERS: TrashFilters = { q: null, object_type: null };

// Badge tone for the live purge/restore control state (presentation only — the
// wire status/purge_status stay plain strings).
export function purgeStatusTone(purgeStatus: string | null): "warn" | "down" | "neutral" {
  if (purgeStatus === "pending") return "warn";
  if (purgeStatus === "failed" || purgeStatus === "purged") return "down";
  return "neutral";
}

// ---------------------------------------------------------------------------
// Query hooks — all under the ["trash"] prefix (swept by resource.changed)
// ---------------------------------------------------------------------------

export function useTrashEntries(filters: TrashFilters, cursor: string | null) {
  return useQuery({
    queryKey: ["trash", "entries", filters.q, filters.object_type, cursor],
    queryFn: () => {
      const params = new URLSearchParams();
      if (filters.q) params.set("q", filters.q);
      if (filters.object_type) params.set("object_type", filters.object_type);
      if (cursor !== null) params.set("cursor", cursor);
      const qs = params.toString();
      return api.get<TrashEntriesPage>(`/trash-entries${qs ? `?${qs}` : ""}`);
    },
    // Keep the current table mounted while a page flip is in flight.
    placeholderData: (previous) => previous,
  });
}

export function useTrashEntry(trashEntryId: string | null) {
  return useQuery({
    queryKey: ["trash", "entry", trashEntryId],
    queryFn: () =>
      api.get<TrashEntryDetail>(`/trash-entries/${encodeURIComponent(trashEntryId ?? "")}`),
    enabled: trashEntryId !== null,
  });
}

// Restore preflight (O-17, doc 20 §5, §8.2) — a READ, so no OCC token and no
// Idempotency-Key. Disabled until an entry is actually being adjudicated; the
// Admin uses it to re-read the canonical conflict after the record changed
// ("Admin refreshes canonical detail", doc 20 §8.2). Advisory only: the restore
// command re-runs every check itself, so this is never treated as permission.
export function useRestorePreflight(trashEntryId: string | null) {
  return useQuery({
    queryKey: ["trash", "restore-preflight", trashEntryId],
    queryFn: () =>
      api.get<RestorePreflight>(
        `/trash-entries/${encodeURIComponent(trashEntryId ?? "")}/restore-preflight`,
      ),
    enabled: trashEntryId !== null,
    // Always re-read on demand: a cached preflight would defeat its purpose.
    staleTime: 0,
    gcTime: 0,
  });
}

// ---------------------------------------------------------------------------
// Mutation — restore (POST /trash-entries/{id}/restore)
// ---------------------------------------------------------------------------

// OCC: expected_head_revision_id carries the entry's row_version so a stale tab
// gets the 409 envelope verbatim instead of restoring against a moved target.
// A fresh Idempotency-Key per attempt keeps a retry after a rejection a new
// decision, not a replay (the body token wins over If-Match, doc 20 §14).
//
// O-17: `resolution` is the typed choice the Admin picked from the conflict's
// option set — sent ONLY when one was chosen, and only ever a token the server
// itself offered. The retry reuses the SAME expected_head_revision_id, so a
// record that moved in the meantime fails OCC instead of restoring blind
// (doc 20 §8.2). An unknown token is rejected 422 server-side; the client never
// substitutes, defaults or drops it.
export function useRestoreEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      trash_entry_id: string;
      expected_head_revision_id: number;
      resolution?: string;
    }) =>
      apiRequest<RestoreResult>(
        `/trash-entries/${encodeURIComponent(input.trash_entry_id)}/restore`,
        {
          method: "POST",
          headers: { "Idempotency-Key": crypto.randomUUID() },
          body: {
            expected_head_revision_id: input.expected_head_revision_id,
            ...(input.resolution !== undefined ? { resolution: input.resolution } : {}),
          },
        },
      ),
    onSuccess: () => {
      // The root lifecycle changed AND the command emitted an audit event.
      void queryClient.invalidateQueries({ queryKey: ["trash"] });
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}

// ---------------------------------------------------------------------------
// Mutation — request permanent delete / purge (POST /trash-entries/{id}/purge)
// ---------------------------------------------------------------------------

// Permanent Delete is a two-phase 202 (doc 20 §8.3): the request only moves the
// target to purge_pending and enqueues a durable maintenance job — the worker
// re-checks eligibility and tombstones (or returns it to soft_deleted on
// failure). The command requires BOTH a second confirmation and a re-auth
// proof:
//   - confirmation_phrase must equal the object's display identity
//     (display_name || entity_id) or the server rejects with
//     PURGE_CONFIRMATION_INVALID — never started.
//   - reauth_proof must be a non-empty token from a completed Admin
//     re-authentication step (V1 contract: presence only; full MFA is out of
//     scope, doc 20 §0) or the server rejects with REAUTH_REQUIRED.
// OCC: expected_head_revision_id carries the entry's row_version (body token
// wins over If-Match, doc 20 §14) so a stale tab gets STALE_REVISION verbatim
// instead of purging a moved target. A fresh Idempotency-Key per attempt keeps
// a retry after a rejection a new decision, not a replay (a duplicate submit
// with the SAME key returns the same job, doc 20 §9.3).
export function useRequestPurge() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      trash_entry_id: string;
      confirmation_phrase: string;
      reauth_proof: string;
      expected_head_revision_id: number;
    }) =>
      apiRequest<PurgeResult>(
        `/trash-entries/${encodeURIComponent(input.trash_entry_id)}/purge`,
        {
          method: "POST",
          headers: { "Idempotency-Key": crypto.randomUUID() },
          body: {
            confirmation_phrase: input.confirmation_phrase,
            reauth_proof: input.reauth_proof,
            expected_head_revision_id: input.expected_head_revision_id,
          },
        },
      ),
    onSuccess: () => {
      // The target moved to purge_pending AND the command emitted an audit event.
      void queryClient.invalidateQueries({ queryKey: ["trash"] });
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}
