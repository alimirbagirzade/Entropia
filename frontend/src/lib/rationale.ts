// Rationale Families data access (doc 10 §7, §8). The shared-editing surface: any
// authenticated actor may manage families + edit assignments (ensure_can_manage_families
// / ensure_can_edit_assignments) — Admin-only is NOT used here, a Guest is rejected
// with the 401 envelope verbatim. Two shared projections live under
// ["rationale-families"] (registry) and ["rationale-assignments"] (the package
// assignment table); neither has a dedicated SSE event, so resource.changed sweeps
// them. Mutations invalidate their own prefix + ["audit"] (each command emits an
// audit event), mirroring lib/trash.ts / lib/adminPanel.ts.
//
// Optimistic concurrency: a family Revise pins the head revision
// (expected_head_revision_id = current_revision_id, the command's token — doc 10 §5
// Save row); a Soft-delete carries the root row_version as the "rv-N" If-Match ETag
// (shared/concurrency.py row_version_from_if_match); a batch Save echoes the
// assignment meta.table_version as expected_table_version. A stale token -> 409
// verbatim.

import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";

import { api, apiRequest } from "./apiClient";

// ---------------------------------------------------------------------------
// Wire types — mirror application/queries/rationale.py _family_dict / _assignment_row
// and application/commands/rationale.py return dicts verbatim.
// ---------------------------------------------------------------------------

export interface RationaleFamilyCard {
  entity_id: string;
  current_revision_id: string;
  revision_no: number;
  display_name: string;
  normalized_name: string;
  subfamilies: string[];
  compatible_output_types: string[];
  display_color: string | null;
  created_by_actor_id: string | null;
  row_version: number;
  created_at: string | null;
}

export interface RationaleFamiliesPage {
  data: RationaleFamilyCard[];
  meta: { cursor: string | null; has_more: boolean };
}

export interface RationaleAssignmentRow {
  package_root_id: string;
  package_kind: string;
  package_name: string | null;
  current_package_revision_id: string | null;
  rationale_family_id: string | null;
  rationale_family_revision_id: string | null;
  current_family_name: string | null;
  assignment_state: string;
  family_active: boolean;
}

export interface RationaleAssignmentsPage {
  data: RationaleAssignmentRow[];
  meta: { cursor: string | null; has_more: boolean; table_version: string };
}

export interface CreateFamilyResult {
  entity_id: string;
  revision_id: string;
  revision_no: number;
  display_name: string;
  display_color: string | null;
  row_version: number;
}

export interface ReviseFamilyResult {
  entity_id: string;
  revision_id: string;
  revision_no: number;
  display_name: string;
  row_version: number;
}

export interface SoftDeleteFamilyResult {
  entity_id: string;
  deletion_state: string;
  display_name: string | null;
}

export interface AssignmentWarning {
  code: string;
  package_root_id: string;
  message: string;
}

export interface BatchAssignResult {
  created_revisions: Array<{
    package_root_id: string;
    revision_id: string;
    rationale_family_id: string | null;
  }>;
  count: number;
  warnings: AssignmentWarning[];
  table_version: string;
}

// One staged assignment change (doc 10 §7.1). rationale_family_id null = explicit
// unassign; the family pins carry the selected family's current revision so a
// concurrent rename -> 409, not a silent stale write.
export interface AssignmentChangeInput {
  package_root_id: string;
  expected_head_revision_id: string | null;
  rationale_family_id: string | null;
  expected_family_current_revision_id: string | null;
}

// ---------------------------------------------------------------------------
// Presentation helpers — server strings stay verbatim over the wire.
// ---------------------------------------------------------------------------

// doc 10 §9.2 assignment-state projection. assigned_to_deleted_family flags a pinned
// family root that was soft-deleted (down); unassigned is a valid explicit null
// (neutral); assigned points at an active family (ok).
export function assignmentStateTone(state: string): "ok" | "warn" | "down" | "neutral" {
  if (state === "assigned") return "ok";
  if (state === "assigned_to_deleted_family") return "down";
  return "neutral";
}

// ---------------------------------------------------------------------------
// Query hooks
// ---------------------------------------------------------------------------

// Active Family registry, cursor-paginated (doc 10 §3, §7). Shares the
// ["rationale-families"] prefix with createPackage's selector so any mutation (or
// resource.changed) sweeps both. Only the active projection is exposed; soft-deleted
// families live in the Admin-only Trash surface.
export function useFamilies(state: string, cursor: string | null) {
  return useQuery({
    queryKey: ["rationale-families", "registry", state, cursor],
    queryFn: () => {
      const params = new URLSearchParams();
      if (state) params.set("state", state);
      if (cursor !== null) params.set("cursor", cursor);
      const qs = params.toString();
      return api.get<RationaleFamiliesPage>(`/rationale-families${qs ? `?${qs}` : ""}`);
    },
    placeholderData: (previous) => previous,
  });
}

// The Package Rationale Assignment table (doc 10 §3.2, §7). meta.table_version is the
// optimistic-concurrency token a batch Save must echo back. Only Indicator + Condition
// packages render (RATIONALE_ASSIGNABLE_PACKAGE_KINDS, V1 UI scope).
export function useAssignments(cursor: string | null) {
  return useQuery({
    queryKey: ["rationale-assignments", cursor],
    queryFn: () => {
      const params = new URLSearchParams();
      if (cursor !== null) params.set("cursor", cursor);
      const qs = params.toString();
      return api.get<RationaleAssignmentsPage>(
        `/package-rationale-assignments${qs ? `?${qs}` : ""}`,
      );
    },
    placeholderData: (previous) => previous,
  });
}

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------

// A family change ripples into the assignment projection (current_family_name /
// assigned_to_deleted_family); both plus the audit trail are swept.
function invalidateRationale(queryClient: QueryClient) {
  void queryClient.invalidateQueries({ queryKey: ["rationale-families"] });
  void queryClient.invalidateQueries({ queryKey: ["rationale-assignments"] });
  void queryClient.invalidateQueries({ queryKey: ["audit"] });
}

export interface CreateFamilyInput {
  display_name: string;
  subfamilies: string[];
  compatible_output_types: string[];
  change_note: string | null;
}

// Create a Family (born active, doc 10 §8.1). No OCC token — a create has no head to
// race; a fresh Idempotency-Key makes a retry a new decision, not a replay.
export function useCreateFamily() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateFamilyInput) =>
      apiRequest<CreateFamilyResult>("/rationale-families", {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: input,
      }),
    onSuccess: () => invalidateRationale(queryClient),
  });
}

export interface ReviseFamilyInput {
  entity_id: string;
  display_name: string;
  subfamilies: string[];
  compatible_output_types: string[];
  change_note: string | null;
  // The command's concurrency token (doc 10 §5 Save): the family's current head.
  expected_head_revision_id: string;
}

// Append a new immutable Family revision (rename/enrich, doc 10 §8.3). OCC:
// expected_head_revision_id pins the current head; a stale token -> 409
// RATIONALE_FAMILY_CONFLICT verbatim.
export function useReviseFamily() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ entity_id, ...rest }: ReviseFamilyInput) =>
      apiRequest<ReviseFamilyResult>(
        `/rationale-families/${encodeURIComponent(entity_id)}/revisions`,
        {
          method: "POST",
          headers: { "Idempotency-Key": crypto.randomUUID() },
          body: rest,
        },
      ),
    onSuccess: () => invalidateRationale(queryClient),
  });
}

// Soft-delete a shared Family (doc 10 §8.5). OCC: the root row_version travels as the
// "rv-N" If-Match ETag (row_version_from_if_match). An actively-assigned family -> 409
// RATIONALE_FAMILY_IN_USE verbatim (repair the assignments first).
export function useSoftDeleteFamily() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { entity_id: string; row_version: number }) =>
      apiRequest<SoftDeleteFamilyResult>(
        `/rationale-families/${encodeURIComponent(input.entity_id)}`,
        {
          method: "DELETE",
          headers: { "If-Match": `"rv-${input.row_version}"` },
        },
      ),
    onSuccess: () => invalidateRationale(queryClient),
  });
}

// Atomically reclassify a set of packages (doc 10 §8.4, §10.2). All-or-nothing: any
// stale/invalid row rolls back the whole batch server-side. expected_table_version
// echoes the assignment table fingerprint; a moved table -> 409 verbatim. An
// OUTPUT_TYPE_NOT_LISTED warning is non-blocking (the assignment still saved).
export function useBatchAssign() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { changes: AssignmentChangeInput[]; expected_table_version: string }) =>
      apiRequest<BatchAssignResult>("/package-rationale-assignments:batch", {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: input,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["rationale-assignments"] });
      void queryClient.invalidateQueries({ queryKey: ["rationale-families"] });
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}
