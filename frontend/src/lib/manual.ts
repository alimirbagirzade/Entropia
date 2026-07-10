// User Manual data access (Stage 7a, doc 21 §7/§8): the all-role Published
// reader stream + server-side search, and the Admin-only publish/replace/
// delete/restore mutations. Every write is Admin-gated at the ROUTE and again
// in the SERVICE (require_manual_admin / require_trash_admin) — UI
// hide/disable is never authorization (doc 21 §2); a non-Admin sees the
// server 403 envelope verbatim.
//
// EMPIRICAL route map (signatures read — PR #105/#111/#113 lesson):
// - GET /manual/stream + GET /manual/search: all-role reads, keyset cursor,
//   meta carries the stream_version the page/anchors resolve against.
// - POST /admin/manual/documents (+ :upload): OCC is the BODY-form
//   `expected_stream_version` INT (optional server-side; this client always
//   guards with the rendered stream snapshot — UM-13/UM-15) + a fresh
//   Idempotency-Key per attempt.
// - POST .../{id}/revisions: OCC is the BODY-form `expected_head_revision_id`
//   STRING (the route prefers the body over the If-Match transport).
// - DELETE .../{id}: carries an OPTIONAL BODY (reason + expected_stream_version)
//   + Idempotency-Key — api.del takes neither, so apiRequest is used directly.
// - POST .../{id}:restore: NO body, Idempotency-Key only; gated by
//   require_trash_admin (NOT manual admin) and delegates to the landed Trash
//   restore — the return shape IS lib/trash.ts RestoreResult.
//
// The manual has no dedicated SSE event: reads live under ["manual"] and are
// swept by resource.changed. GET /manual/section is NOT routed (doc 21 §12 —
// the Agent reads sections through the Tool Gateway, not HTTP).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, apiRequest } from "./apiClient";
import type { RestoreResult } from "./trash";

// ---------------------------------------------------------------------------
// Wire types (mirror application/queries/manual.py and commands/manual.py
// return dicts verbatim)
// ---------------------------------------------------------------------------

// Canonical safe-render block (doc 21 §9.2). payload shapes by block_type:
// heading {level, text} / paragraph {text} / bullet_list|ordered_list {items}
// / code {code_text, language} / callout {tone, title, text} / divider {}.
export interface ManualBlock {
  block_id: string;
  block_type: string;
  anchor: string;
  payload: Record<string, unknown>;
}

export interface ManualSection {
  document_id: string;
  is_baseline: boolean;
  title: string;
  revision_id: string;
  revision_no: number;
  source_type: string;
  source_label: string;
  stream_position: number;
  anchor: string;
  blocks: ManualBlock[];
}

export interface ManualStreamPage {
  data: ManualSection[];
  meta: {
    stream_version: number;
    cursor: string | null;
    has_more: boolean;
    limit: number;
  };
}

export interface ManualSearchResult {
  chunk_id: string;
  document_id: string;
  revision_id: string;
  revision_no: number;
  title: string;
  heading_path: string;
  excerpt: string;
  anchor: string;
  block_ids: string[];
  source_label: string;
}

export interface ManualSearchPage {
  data: ManualSearchResult[];
  meta: {
    stream_version: number;
    cursor: string | null;
    has_more: boolean;
    limit: number;
    query: string;
  };
}

// commands/manual.py _publish_new_document return (create + upload share it).
export interface PublishResult {
  document_id: string;
  revision_id: string;
  revision_no: number;
  stream_entry_id: string;
  stream_position: number;
  anchor: string;
  title: string;
  checksum: string;
  stream_version: number;
  correlation_id: string | null;
}

export interface ReviseResult {
  document_id: string;
  revision_id: string;
  revision_no: number;
  superseded_revision_id: string;
  stream_position: number;
  anchor: string;
  stream_version: number;
  correlation_id: string | null;
}

// Two server branches share this shape: the idempotent-repeat branch adds
// idempotent_repeat and omits display_name.
export interface DeleteResult {
  document_id: string;
  deletion_state: string;
  trash_entry_id: string | number | null;
  stream_version: number;
  correlation_id: string | null;
  display_name?: string;
  idempotent_repeat?: boolean;
}

// ---------------------------------------------------------------------------
// Taxonomy mirrors (hydration/presentation only — the server re-validates
// every dispatch; a rejected extension is MANUAL_FILE_TYPE_UNSUPPORTED
// verbatim, doc 21 §5 UM-06)
// ---------------------------------------------------------------------------

// domain/manual/enums.py SOURCE_TYPE_BY_EXTENSION keys, same order.
export const ACCEPTED_UPLOAD_EXTENSIONS = [".txt", ".md", ".markdown", ".html", ".htm"] as const;

// ---------------------------------------------------------------------------
// Query hooks — all under the ["manual"] prefix (swept by resource.changed)
// ---------------------------------------------------------------------------

export function useManualStream(cursor: string | null) {
  return useQuery({
    queryKey: ["manual", "stream", cursor],
    queryFn: () => {
      const params = new URLSearchParams();
      if (cursor !== null) params.set("cursor", cursor);
      const qs = params.toString();
      return api.get<ManualStreamPage>(`/manual/stream${qs ? `?${qs}` : ""}`);
    },
    // Keep the current stream mounted while a page flip is in flight.
    placeholderData: (previous) => previous,
  });
}

// A blank query searches nothing server-side (doc 21 §14) — the hook stays
// disabled until there is a needle, so no useless round-trip is made.
export function useManualSearch(q: string, cursor: string | null) {
  const needle = q.trim();
  return useQuery({
    queryKey: ["manual", "search", needle, cursor],
    queryFn: () => {
      const params = new URLSearchParams();
      params.set("q", needle);
      if (cursor !== null) params.set("cursor", cursor);
      return api.get<ManualSearchPage>(`/manual/search?${params.toString()}`);
    },
    enabled: needle.length > 0,
    placeholderData: (previous) => previous,
  });
}

// ---------------------------------------------------------------------------
// Mutations — Admin-only server-side; fresh Idempotency-Key per attempt so a
// retry after a rejection is a new decision, not a replay
// ---------------------------------------------------------------------------

export interface CreateDocumentInput {
  title: string;
  content: string;
  allow_duplicate: boolean;
  expected_stream_version: number;
}

export function useCreateManualDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateDocumentInput) =>
      apiRequest<PublishResult>("/admin/manual/documents", {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: input,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["manual"] });
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}

export interface UploadDocumentInput {
  source_filename: string;
  content: string;
  // Omitted when blank: the server derives the title from the filename stem.
  title?: string;
  allow_duplicate: boolean;
  expected_stream_version: number;
}

export function useUploadManualDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: UploadDocumentInput) =>
      apiRequest<PublishResult>("/admin/manual/documents:upload", {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: input,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["manual"] });
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}

// NOTE (doc 21 §7): revision replacement is a landed backend capability the
// V18 reader spec does not surface; this client binds it as an explicit Admin
// maintenance affordance so the full route surface is frontend-bound (the
// PR #95 gated-POST precedent). The server still gates it end-to-end.
export interface ReplaceRevisionInput {
  document_id: string;
  content: string;
  // Omitted when blank: the server keeps the current head title.
  title?: string;
  // The section's visible head revision id — a moved head is a 409
  // MANUAL_REVISION_CONFLICT verbatim (doc 21 §7/§10; body wins over If-Match).
  expected_head_revision_id: string;
}

export function useReplaceManualRevision() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ document_id, ...body }: ReplaceRevisionInput) =>
      apiRequest<ReviseResult>(
        `/admin/manual/documents/${encodeURIComponent(document_id)}/revisions`,
        {
          method: "POST",
          headers: { "Idempotency-Key": crypto.randomUUID() },
          body,
        },
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["manual"] });
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}

export interface DeleteDocumentInput {
  document_id: string;
  // Omitted when blank — the wire field is nullable.
  reason?: string;
  // Stale snapshot -> 409 MANUAL_STREAM_CONFLICT verbatim (UM-15).
  expected_stream_version: number;
}

// Soft delete writes a page-contract Trash entry in the same tx (doc 21 §8.4)
// — the Admin Trash index moves, so ["trash"] is invalidated alongside.
export function useSoftDeleteManualDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ document_id, ...body }: DeleteDocumentInput) =>
      apiRequest<DeleteResult>(`/admin/manual/documents/${encodeURIComponent(document_id)}`, {
        method: "DELETE",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["manual"] });
      void queryClient.invalidateQueries({ queryKey: ["trash"] });
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}

// Restore is addressed by DOCUMENT id and delegates to the landed Trash core
// (doc 21 §8.4 UM-09): no body, no OCC token — the recoverable Trash entry is
// resolved server-side; the return shape is the Trash RestoreResult.
export function useRestoreManualDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { document_id: string }) =>
      apiRequest<RestoreResult>(
        `/admin/manual/documents/${encodeURIComponent(input.document_id)}:restore`,
        {
          method: "POST",
          headers: { "Idempotency-Key": crypto.randomUUID() },
        },
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["manual"] });
      void queryClient.invalidateQueries({ queryKey: ["trash"] });
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}
