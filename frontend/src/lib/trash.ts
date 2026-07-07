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

import { api, apiRequest } from "./apiClient";

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

// ---------------------------------------------------------------------------
// Mutation — restore (POST /trash-entries/{id}/restore)
// ---------------------------------------------------------------------------

// OCC: expected_head_revision_id carries the entry's row_version so a stale tab
// gets the 409 envelope verbatim instead of restoring against a moved target.
// A fresh Idempotency-Key per attempt keeps a retry after a rejection a new
// decision, not a replay (the body token wins over If-Match, doc 20 §14).
export function useRestoreEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { trash_entry_id: string; expected_head_revision_id: number }) =>
      apiRequest<RestoreResult>(
        `/trash-entries/${encodeURIComponent(input.trash_entry_id)}/restore`,
        {
          method: "POST",
          headers: { "Idempotency-Key": crypto.randomUUID() },
          body: { expected_head_revision_id: input.expected_head_revision_id },
        },
      ),
    onSuccess: () => {
      // The root lifecycle changed AND the command emitted an audit event.
      void queryClient.invalidateQueries({ queryKey: ["trash"] });
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}
