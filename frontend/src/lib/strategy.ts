// Strategy Details data access (doc 02 §7–§9). Typed read models + mutations
// over routes/strategy.py — the Strategy editor draft workflow (draft → patch
// → validate → save revision) that feeds the attach → Ready Check → RUN path.
// EMPIRICAL route map (signatures read, PR #105/#111/#113/#115 lesson):
//  - POST  /strategy-drafts (201) — creates registry root + strategy head +
//    mutable editor draft in one command. display_name is command-REQUIRED
//    (non-empty) even though the route body is optional; rationale_family_id
//    and initial_payload are optional. Fresh Idempotency-Key per attempt; NO
//    OCC token (a create has no head to race). The returned draft_id is the
//    ONLY handle to the editor draft — draft ids are independent "stratdraft"
//    ULIDs and NO root→draft lookup endpoint exists, so the page keeps the
//    draft id in the URL (?draft=).
//  - PATCH /strategy-drafts/{id} — full `payload` replacement (a shallow
//    `patch` merge also exists server-side; this UI always sends the full
//    payload). OCC travels BODY-form as expected_draft_row_version INT (the
//    route prefers the body over If-Match and REQUIRES one of them — 422
//    otherwise); a stale token → 409 STRATEGY_DRAFT_CONFLICT verbatim, never
//    last-write-wins (AT-19). + fresh Idempotency-Key. Draft row_version
//    starts at 0 on create — 0 is a valid expected token.
//  - POST  /strategy-drafts/{id}/validate — reads NO body and NO headers: a
//    pure compiler pass (doc 02 §8.4) with no draft mutation, no revision and
//    NO audit row → no Idempotency-Key travels and nothing is invalidated.
//  - POST  /strategy-drafts/{id}/save (201) — OCC body + Idempotency-Key.
//    Atomic validate → immutable strategy_revision → mirror work-object
//    revision → re-pin every attached Mainboard item (composition_hash moves
//    → the prior Ready report is STALE) → mark draft saved. Success therefore
//    invalidates ["strategy"] + ["mainboard"] + ["readiness"] + ["audit"].
//    A blocked config → 422 (STRATEGY_VALIDATION_FAILED /
//    SIZING_METHOD_NOT_EXCLUSIVE / …) with the compiler issue list in
//    error.details — rendered verbatim, never re-derived.
//  - POST  /strategy-drafts/{id}/clear — OCC body + Idempotency-Key; resets
//    unsaved editor state only (never deletes the root or a saved revision,
//    never creates a Trash entry — AT-23).
//  - GET   /strategy-drafts/{id} · /strategies/{root} ·
//    /strategies/{root}/revisions?limit= (bare LIST, no page envelope) ·
//    /strategy-revisions/{id} — owner/Admin reads (private visibility).
// Strategy has NO dedicated SSE event → every ["strategy"] key is swept by
// the resource.changed full refresh (lib/sse.ts).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, apiRequest } from "./apiClient";

// ---------------------------------------------------------------------------
// Wire types (mirror backend application/{queries,commands}/strategy*.py)
// ---------------------------------------------------------------------------

// GAP-03: provenance a derived draft carries (mirrors the backend
// source_provenance dict). NULL for ordinary (non-derived) drafts.
export interface SourceProvenance {
  source_package_root_id: string;
  source_package_revision_id: string;
  source_content_hash: string;
  source_package_kind: string;
  source_display_name: string;
  inherited_dependencies: Record<string, unknown>;
}

// GET /strategy-drafts (queries list_strategy_drafts, F-18 durable/discoverable).
// The actor's own drafts, newest edit first; Admins see every owner. is_attached =
// the strategy root is on a Mainboard; has_revision = a Save produced an immutable
// revision. Drafts never leak across users (owner-scoped server-side).
export interface StrategyDraftSummary {
  draft_id: string;
  strategy_root_id: string | null;
  display_name: string;
  lifecycle_state: string;
  is_dirty: boolean;
  row_version: number;
  last_saved_revision_id: string | null;
  has_revision: boolean;
  is_attached: boolean;
  owner_principal_id: string | null;
  updated_at: string | null;
}

// GET /strategy-drafts/{id} (queries get_strategy_draft).
export interface StrategyDraft {
  draft_id: string;
  strategy_root_id: string | null;
  payload: Record<string, unknown>;
  is_dirty: boolean;
  row_version: number;
  last_saved_revision_id: string | null;
  source_provenance: SourceProvenance | null;
  updated_at: string | null;
}

// GET /strategies/{root_id} (queries get_strategy).
export interface StrategyDetail {
  strategy_root_id: string;
  display_name: string;
  lifecycle_state: string;
  current_revision_id: string | null;
  current_row_version: number;
  rationale_family_id: string | null;
  owner_principal_id: string | null;
  deletion_state: string;
}

// GET /strategies/{root_id}/revisions row (queries list_strategy_revisions —
// newest first, bare list).
export interface StrategyRevisionRow {
  strategy_revision_id: string;
  revision_number: number;
  config_hash: string;
  validation_status: string;
  created_at: string | null;
}

// A pinned dependency edge on an immutable revision (L5 root+revision+hash).
export interface StrategyReference {
  referenced_entity_type: string;
  dependency_role: string;
  referenced_root_id: string;
  referenced_revision_id: string;
  referenced_content_hash: string;
  position_in_graph: number;
}

// GET /strategy-revisions/{id} (queries get_strategy_revision).
export interface StrategyRevisionDetail {
  strategy_revision_id: string;
  strategy_root_id: string;
  revision_number: number;
  config_hash: string;
  validation_status: string;
  lifecycle_snapshot: string | null;
  family_snapshot: string | null;
  payload: Record<string, unknown>;
  references: StrategyReference[];
  created_at: string | null;
}

// POST /strategy-drafts return (commands create_strategy_draft).
export interface CreateDraftResult {
  draft_id: string;
  strategy_root_id: string;
  display_name: string;
  row_version: number;
}

// POST /strategy-drafts with source_package_* return (commands
// derive_strategy_draft_from_package). Carries the pinned source + inherited deps.
export interface DeriveDraftResult {
  draft_id: string;
  strategy_root_id: string;
  display_name: string;
  row_version: number;
  source_provenance: SourceProvenance;
}

// PATCH /strategy-drafts/{id} return (commands patch_strategy_draft).
export interface PatchDraftResult {
  draft_id: string;
  strategy_root_id: string | null;
  row_version: number;
  is_dirty: boolean;
}

// One compiler finding (domain/strategy/compiler.py — {field, code, message}).
export interface StrategyIssue {
  field: string;
  code: string;
  message: string;
}

// POST validate return (commands validate_strategy_draft). warnings is an
// always-empty reserved list in Stage 3b.
export interface ValidateDraftResult {
  draft_id: string;
  valid: boolean;
  issues: StrategyIssue[];
  warnings: unknown[];
}

// One re-pinned Mainboard item from a save (commands _repin_attached_items).
export interface PinnedMainboardItem {
  item_id: string;
  pinned_revision_id: string;
  composition_hash: string | null;
}

// POST save return (commands save_strategy_revision). ready_state is the
// constant "STALE" — a save is never a Ready PASS (doc 02 §7.1).
export interface SaveRevisionResult {
  strategy_root_id: string;
  strategy_revision_id: string;
  revision_number: number;
  config_hash: string;
  mirror_revision_id: string;
  pinned_items: PinnedMainboardItem[];
  ready_state: string;
  warnings: unknown[];
  correlation_id: string | null;
}

// POST clear return (commands clear_strategy_draft).
export interface ClearDraftResult {
  draft_id: string;
  row_version: number;
  cleared: boolean;
}

// ---------------------------------------------------------------------------
// Presentation taxonomy (mirror domain/strategy/enums.py — hydration only,
// the server is authoritative for every state transition)
// ---------------------------------------------------------------------------

type Tone = "ok" | "warn" | "down" | "neutral";

// StrategyLifecycleStateEnum wire tokens (schema §3.1).
export const STRATEGY_LIFECYCLE_LABELS: Record<string, string> = {
  draft: "Draft",
  validated: "Validated",
  active_candidate: "Active candidate",
  locked_for_test: "Locked for test",
  deprecated: "Deprecated",
  soft_deleted: "Soft-deleted",
};

export const STRATEGY_LIFECYCLE_TONES: Record<string, Tone> = {
  draft: "neutral",
  validated: "ok",
  active_candidate: "ok",
  locked_for_test: "warn",
  deprecated: "down",
  soft_deleted: "down",
};

// ValidationStatusEnum wire tokens (schema §3.2).
export const VALIDATION_STATUS_TONES: Record<string, Tone> = {
  validating: "neutral",
  valid: "ok",
  invalid: "down",
  stale: "warn",
};

export function lifecycleLabel(state: string): string {
  return STRATEGY_LIFECYCLE_LABELS[state] ?? state;
}

export function lifecycleTone(state: string): Tone {
  return STRATEGY_LIFECYCLE_TONES[state] ?? "neutral";
}

export function validationStatusTone(status: string): Tone {
  return VALIDATION_STATUS_TONES[status] ?? "neutral";
}

// ---------------------------------------------------------------------------
// Query hooks
// ---------------------------------------------------------------------------

// F-18: the actor's discoverable drafts (removes the ?draft= URL dependency — a
// draft is now findable after a browser restart / re-login). No dedicated SSE
// event → swept by the resource.changed full refresh with every other ["strategy"]
// key; own create/save/clear invalidate it.
export function useMyStrategyDrafts() {
  return useQuery({
    queryKey: ["strategy", "drafts", "mine"],
    queryFn: () => api.get<StrategyDraftSummary[]>("/strategy-drafts"),
  });
}

export function useStrategyDraft(draftId: string | null) {
  return useQuery({
    queryKey: ["strategy", "draft", draftId],
    queryFn: () =>
      api.get<StrategyDraft>(`/strategy-drafts/${encodeURIComponent(draftId ?? "")}`),
    enabled: draftId !== null,
  });
}

export function useStrategy(rootId: string | null) {
  return useQuery({
    queryKey: ["strategy", "root", rootId],
    queryFn: () => api.get<StrategyDetail>(`/strategies/${encodeURIComponent(rootId ?? "")}`),
    enabled: rootId !== null,
  });
}

export function useStrategyRevisions(rootId: string | null) {
  return useQuery({
    queryKey: ["strategy", "revisions", rootId],
    queryFn: () =>
      api.get<StrategyRevisionRow[]>(
        `/strategies/${encodeURIComponent(rootId ?? "")}/revisions`,
      ),
    enabled: rootId !== null,
  });
}

// An immutable revision never changes once written → long staleTime.
export function useStrategyRevision(revisionId: string | null) {
  return useQuery({
    queryKey: ["strategy", "revision", revisionId],
    queryFn: () =>
      api.get<StrategyRevisionDetail>(
        `/strategy-revisions/${encodeURIComponent(revisionId ?? "")}`,
      ),
    enabled: revisionId !== null,
    staleTime: 5 * 60 * 1000,
  });
}

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------

// Create the root + draft. No OCC (nothing exists yet); fresh Idempotency-Key.
// Writes a strategy.draft_created audit row → ["audit"] joins ["strategy"].
export function useCreateStrategyDraft() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { displayName: string; rationaleFamilyId: string | null }) =>
      apiRequest<CreateDraftResult>("/strategy-drafts", {
        method: "POST",
        body: {
          display_name: input.displayName,
          ...(input.rationaleFamilyId !== null
            ? { rationale_family_id: input.rationaleFamilyId }
            : {}),
        },
        headers: { "Idempotency-Key": crypto.randomUUID() },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["strategy"] });
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}

// GAP-03: derive a NEW strategy draft from a usable Strategy Package (doc 01 §8.2,
// doc 08 §4.3). The source is pinned (root + optional exact revision, else head) and
// provenance is recorded; the source package is never modified. No OCC (a create has
// no head to race); fresh Idempotency-Key. The UI never pre-authorizes — the server
// re-validates usability/kind/visibility and renders the canonical error verbatim
// (403 foreign-private / 422 PACKAGE_NOT_DERIVABLE). Invalidates ["strategy"] +
// ["audit"] (the derive writes a strategy.derived_from_package audit row).
export function useDeriveStrategyDraftFromPackage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      sourcePackageRootId: string;
      sourcePackageRevisionId?: string | null;
      displayName?: string | null;
    }) =>
      apiRequest<DeriveDraftResult>("/strategy-drafts", {
        method: "POST",
        body: {
          source_package_root_id: input.sourcePackageRootId,
          ...(input.sourcePackageRevisionId != null
            ? { source_package_revision_id: input.sourcePackageRevisionId }
            : {}),
          ...(input.displayName != null ? { display_name: input.displayName } : {}),
        },
        headers: { "Idempotency-Key": crypto.randomUUID() },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["strategy"] });
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}

// Full-payload replacement edit. expectedRowVersion is the rendered draft's
// row_version (0 is valid — a fresh draft); stale → 409 STRATEGY_DRAFT_CONFLICT.
export function usePatchStrategyDraft() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      draftId: string;
      expectedRowVersion: number;
      payload: Record<string, unknown>;
    }) =>
      apiRequest<PatchDraftResult>(
        `/strategy-drafts/${encodeURIComponent(input.draftId)}`,
        {
          method: "PATCH",
          body: {
            payload: input.payload,
            expected_draft_row_version: input.expectedRowVersion,
          },
          headers: { "Idempotency-Key": crypto.randomUUID() },
        },
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["strategy"] });
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}

// Pure compiler pass over the SERVER draft (not unsaved editor text). The
// route reads no body/headers and writes no audit row → nothing invalidated.
export function useValidateStrategyDraft() {
  return useMutation({
    mutationFn: (input: { draftId: string }) =>
      api.post<ValidateDraftResult>(
        `/strategy-drafts/${encodeURIComponent(input.draftId)}/validate`,
      ),
  });
}

// Freeze the draft into an immutable revision. Re-pins attached Mainboard
// items in the same tx (composition_hash moves → prior Ready report STALE) →
// ["mainboard"] + ["readiness"] invalidate alongside ["strategy"] + ["audit"].
export function useSaveStrategyRevision() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { draftId: string; expectedRowVersion: number }) =>
      apiRequest<SaveRevisionResult>(
        `/strategy-drafts/${encodeURIComponent(input.draftId)}/save`,
        {
          method: "POST",
          body: { expected_draft_row_version: input.expectedRowVersion },
          headers: { "Idempotency-Key": crypto.randomUUID() },
        },
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["strategy"] });
      void queryClient.invalidateQueries({ queryKey: ["mainboard"] });
      void queryClient.invalidateQueries({ queryKey: ["readiness"] });
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}

// Reset unsaved editor state to blank (root + saved revisions untouched).
export function useClearStrategyDraft() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { draftId: string; expectedRowVersion: number }) =>
      apiRequest<ClearDraftResult>(
        `/strategy-drafts/${encodeURIComponent(input.draftId)}/clear`,
        {
          method: "POST",
          body: { expected_draft_row_version: input.expectedRowVersion },
          headers: { "Idempotency-Key": crypto.randomUUID() },
        },
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["strategy"] });
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}
