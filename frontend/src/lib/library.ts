// Package Library catalog data access (doc 08 §3, §4, §9.2): the read-only,
// authentication-gated catalog list (per-role visibility applied SERVER-side —
// the client never hides rows) and the enriched detail projection. Guests get
// the 401 envelope verbatim (doc 08 §2 "katalog döndürülmez").
//
// The catalog has no dedicated SSE event: package lifecycle changes ride
// resource.changed (full refresh). Read keys live under ["library"]. This
// surface is GET-only — every mutating package action stays out of this slice,
// so no OCC token is sent from here (the detail ETag exists for later slices).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { QueryClient } from "@tanstack/react-query";

import { api, apiRequest } from "./apiClient";

// ---------------------------------------------------------------------------
// Facet taxonomies — hydration-only mirrors of domain/package/catalog.py and
// the lifecycle/package enums. Selects are seeded from these; the SERVER
// re-validates every filter and rejects a bad value with the 422 envelope
// verbatim (CatalogFilterInvalid) — the mirror is never authorization.
// ---------------------------------------------------------------------------

export const CATALOG_PACKAGE_KINDS = [
  "strategy",
  "indicator",
  "condition",
  "embedded_system",
] as const;

export const CATALOG_LIFECYCLE_STATES = ["active", "deprecated"] as const;

export const PACKAGE_VALIDATION_STATES = [
  "pending",
  "passed",
  "warning",
  "failed",
  "stale",
] as const;

export const APPROVAL_STATES = ["draft", "approval_requested", "approved", "rejected"] as const;

export const VISIBILITY_SCOPES = ["private", "explicitly_shared", "published", "system"] as const;

// Sentinel rationale-family filter value: packages with no pinned family.
export const UNASSIGNED_FAMILY = "unassigned";

// ---------------------------------------------------------------------------
// Wire types (mirror application/queries/library.py `_package_row` / detail
// verbatim)
// ---------------------------------------------------------------------------

// The ten capability flags of doc 08 §4.2 — a UX hint, never the authority:
// the server re-validates every guard on each command.
export interface PackagePermissions {
  can_view: boolean;
  can_use: boolean;
  can_derive: boolean;
  can_create_revision: boolean;
  can_request_validation: boolean;
  can_request_approval: boolean;
  can_approve_publish: boolean;
  can_deprecate: boolean;
  can_soft_delete: boolean;
  can_export: boolean;
}

// Backend dataclass field order — rendered in this order so the grid is stable.
export const PERMISSION_FLAGS: readonly (keyof PackagePermissions)[] = [
  "can_view",
  "can_use",
  "can_derive",
  "can_create_revision",
  "can_request_validation",
  "can_request_approval",
  "can_approve_publish",
  "can_deprecate",
  "can_soft_delete",
  "can_export",
] as const;

// Catalog performance fields (doc 08 §3.2 boxed): only Strategy packages with
// linked runs could ever carry values and none are linked in this stage, so
// the server sends "not_applicable" for every field — never a fabricated zero
// (L4). The client renders whatever string arrives.
export const PERFORMANCE_FIELDS = [
  "net_profit",
  "max_drawdown",
  "romad",
  "win_rate",
  "trade_count",
  "out_of_sample",
] as const;

export interface PinnedFamilyRef {
  id: string;
  name: string | null;
}

export interface LibraryPackageRow {
  entity_id: string;
  package_kind: string;
  name: string | null;
  current_revision_id: string;
  revision_no: number;
  lifecycle_state: string;
  validation_state: string;
  approval_state: string;
  visibility_scope: string;
  rationale_family: PinnedFamilyRef | null;
  output_kinds: string[];
  derived_from_revision_id: string | null;
  owner_principal_id: string | null;
  row_version: number;
  content_hash: string;
  created_at: string | null;
  permissions: PackagePermissions;
  performance: Record<string, string>;
}

export interface LibraryPage {
  data: LibraryPackageRow[];
  meta: { cursor: string | null; has_more: boolean };
}

// Detail resolves the pinned family snapshot to its CURRENT name (rename
// without re-pin); a soft-deleted family keeps its pinned name, flagged
// inactive (doc 08 §4.3 section 6).
export interface LiveRationaleFamily {
  id: string;
  name: string | null;
  pinned_name: string | null;
  family_active: boolean;
}

export interface ProvenanceScan {
  scan_id: string;
  attempt_no: number;
  status: string;
  detected_calls: string[];
  resolved_refs: string[];
  missing_calls: string[];
  unsupported_calls: string[];
  registry_fingerprint: string | null;
  context_hash: string | null;
}

// Best-effort Stage-2e creation provenance for a package built via a request.
export interface PackageProvenance {
  request_entity_id: string;
  creation_mode: string;
  source_kind: string;
  source_language: string | null;
  target_runtime: string;
  draft_revision_id: string | null;
  scan: ProvenanceScan | null;
}

export interface RevisionSummary {
  revision_id: string;
  revision_no: number;
  validation_state: string;
  approval_state: string;
  change_note: string | null;
  created_at: string | null;
}

export interface LibraryPackageDetail extends Omit<LibraryPackageRow, "rationale_family"> {
  input_contract: Record<string, unknown>;
  output_contract: Record<string, unknown>;
  dependency_snapshot: Record<string, unknown> | null;
  validation_summary: Record<string, unknown> | null;
  change_note: string | null;
  rationale_family: LiveRationaleFamily | null;
  provenance: PackageProvenance | null;
  revisions: RevisionSummary[];
}

// ---------------------------------------------------------------------------
// Filters — every facet optional (doc 08 §5); an empty facet param is NEVER
// sent. The wire param for the kind facet is `type` (route alias).
// ---------------------------------------------------------------------------

export interface LibraryFilters {
  type: string | null;
  lifecycle_state: string | null;
  validation_state: string | null;
  approval_state: string | null;
  visibility_scope: string | null;
  rationale_family_id: string | null;
  q: string | null;
}

export const DEFAULT_LIBRARY_FILTERS: LibraryFilters = {
  type: null,
  lifecycle_state: null,
  validation_state: null,
  approval_state: null,
  visibility_scope: null,
  rationale_family_id: null,
  q: null,
};

// Badge tones (presentation only — the wire states stay plain strings).
export function validationTone(state: string): "ok" | "warn" | "down" | "neutral" {
  if (state === "passed") return "ok";
  if (state === "warning" || state === "stale") return "warn";
  if (state === "failed") return "down";
  return "neutral";
}

export function approvalTone(state: string): "ok" | "warn" | "down" | "neutral" {
  if (state === "approved") return "ok";
  if (state === "approval_requested") return "warn";
  if (state === "rejected") return "down";
  return "neutral";
}

export function lifecycleTone(state: string): "ok" | "warn" | "neutral" {
  if (state === "active") return "ok";
  if (state === "deprecated") return "warn";
  return "neutral";
}

// ---------------------------------------------------------------------------
// Query hooks — all under the ["library"] prefix (swept by resource.changed)
// ---------------------------------------------------------------------------

export function useLibraryPackages(filters: LibraryFilters, cursor: string | null) {
  return useQuery({
    queryKey: ["library", "list", filters, cursor],
    queryFn: () => {
      const params = new URLSearchParams();
      for (const [key, value] of Object.entries(filters)) {
        if (value) params.set(key, value);
      }
      if (cursor !== null) params.set("cursor", cursor);
      const qs = params.toString();
      return api.get<LibraryPage>(`/library${qs ? `?${qs}` : ""}`);
    },
    // Keep the current table mounted while a page flip is in flight.
    placeholderData: (previous) => previous,
  });
}

export function useLibraryPackage(entityId: string | null) {
  return useQuery({
    queryKey: ["library", "detail", entityId],
    queryFn: () =>
      api.get<LibraryPackageDetail>(`/library/${encodeURIComponent(entityId ?? "")}`),
    enabled: entityId !== null,
  });
}

// ---------------------------------------------------------------------------
// Lifecycle mutations — GAP-06 epic slice 1 (doc 08 §7): Deprecate + Move to
// Trash. A lifecycle change moves the catalog projection AND writes an audit
// event, so both sweep ["library"] + ["audit"]; a delete additionally lands a
// Trash entry, so it sweeps ["trash"]. The client never pre-gates on the
// permission flags — the server re-validates and renders 403/409 verbatim.
// ---------------------------------------------------------------------------

export interface DeprecatePackageResult {
  entity_id: string;
  lifecycle_state: string;
}

function invalidateLibrary(queryClient: QueryClient, options: { trash?: boolean } = {}) {
  void queryClient.invalidateQueries({ queryKey: ["library"] });
  void queryClient.invalidateQueries({ queryKey: ["audit"] });
  if (options.trash) void queryClient.invalidateQueries({ queryKey: ["trash"] });
}

// Deprecate carries NO OCC token or Idempotency-Key — it appends no revision, so
// it cannot race the head (mirrors the sibling market_data deprecate). A
// non-active / soft-deleted root -> 409 LIFECYCLE_BLOCKED (rendered verbatim).
export function useDeprecatePackage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { entityId: string; note?: string }) =>
      api.post<DeprecatePackageResult>(
        `/library/${encodeURIComponent(input.entityId)}/deprecate`,
        input.note ? { note: input.note } : {},
      ),
    onSuccess: () => invalidateLibrary(queryClient),
  });
}

// Move to Trash is a soft delete under OCC: the root row_version travels as the
// If-Match "rv-N" ETag (etag_for_row_version) + a fresh Idempotency-Key per
// attempt; a stale head -> 409 STALE_REVISION, a repeat delete is a no-op. The
// route returns 204 (no body). Restore stays the Admin-only Trash surface.
export function useSoftDeletePackage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { entityId: string; rowVersion: number; reason?: string }) =>
      apiRequest<void>(`/library/${encodeURIComponent(input.entityId)}`, {
        method: "DELETE",
        headers: {
          "If-Match": `"rv-${input.rowVersion}"`,
          "Idempotency-Key": crypto.randomUUID(),
        },
        body: input.reason ? { reason: input.reason } : {},
      }),
    onSuccess: () => invalidateLibrary(queryClient, { trash: true }),
  });
}
