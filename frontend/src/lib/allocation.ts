// Portfolio / Equity Allocation data access (doc 13 §3.3, §7–§11). Typed read
// models + mutations over routes/allocation.py — the editor of the allocation
// draft the Backtest Ready Check reads. EMPIRICAL route map (signatures read,
// PR #105/#111 lesson):
//  - GET  .../portfolio-allocation-draft — draft projection + candidate items;
//    the body's row_version IS the live OCC token (0 = no plan yet, and 0 is
//    the valid creation token, doc 13 §7.2). An ETag mirrors it; we use the body.
//  - PUT  .../portfolio-allocation-draft — autosave upsert. The OCC token
//    travels BODY-form as expected_row_version (the route prefers the body over
//    If-Match) + a fresh Idempotency-Key per attempt. A stale token → 409
//    ALLOCATION_DRAFT_CONFLICT, never last-write-wins (§10.1). item_type is
//    accepted but IGNORED server-side (derived from the composition item, §8.2)
//    so the client never sends it.
//  - POST .../portfolio-allocation/validate — reads NO body and NO headers; a
//    rerun is a NEW immutable validation_report_id (§11.1) + an audit row. No
//    plan revision and no draft mutation is created.
//  - POST .../portfolio-allocation/sync — PURE READ merge preview (query layer,
//    §10.2 Flow D): nothing is applied and no audit row is written, so no
//    Idempotency-Key travels and nothing is invalidated (the research-data
//    bundle-compiler pattern). A removal is applied only by an explicit
//    follow-up PUT with the merged entries (§14#9).
//  - POST .../portfolio-allocation/revisions — 201; OCC body
//    expected_row_version + fresh Idempotency-Key; only a blocker-free ENABLED
//    draft may become an immutable plan revision (§8.5) — else 422
//    ALLOCATION_HAS_BLOCKERS / ALLOCATION_VALIDATION_FAILED verbatim.
// Allocation has NO dedicated SSE event → the ["allocation"] keys are swept by
// the resource.changed full refresh (lib/sse.ts). A draft PUT returns
// readiness_invalidated: true → it also invalidates ["readiness"] and
// ["mainboard"] (the Ready Check + default-Mainboard ready_summary read this
// draft); the revision POST return carries no such flag → ["allocation"] +
// ["audit"] only.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, apiRequest } from "./apiClient";

// ---------------------------------------------------------------------------
// Wire types (mirror backend application/{queries,commands}/allocation_plan.py)
// ---------------------------------------------------------------------------

// Money travels as decimal STRINGS on the wire — never binary float (doc 13 §13).
export interface AllocationMoney {
  amount: string;
  currency: string;
}

// One persisted allocation row (queries _entry_projection). item_type is the
// server-DERIVED MainboardItemKind (strategy | trading_signal | trade_log).
export interface AllocationEntry {
  entry_id: string;
  composition_item_id: string;
  item_type: string;
  active: boolean;
  equity_share_percent: string | null;
  position_index: number;
}

// The mutable draft projection (queries _draft_projection). draft_fingerprint
// is absent on the default independent draft returned before any plan exists.
export interface AllocationDraft {
  enabled: boolean;
  initial_capital: AllocationMoney | null;
  compounding_mode: string | null;
  reserve_cash_percent: string | null;
  // Portfolio-level rules (doc 13 §8.4, cross-item): composition-wide exposure
  // ceiling (% of P0; null = no cap) + opposing same-instrument signal policy
  // (null = KEEP_SEPARATE). Both absent on pre-rules drafts.
  max_total_exposure_percent?: string | null;
  conflict_policy?: string | null;
  draft_fingerprint?: string;
  entries: AllocationEntry[];
}

// An unrepresented compatible composition item (queries _candidate — the §3.3
// item picker source). Adding one to the draft is a client-side edit; it binds
// by composition_item_id only (§8.2).
export interface AllocationCandidate {
  composition_item_id: string;
  item_type: string;
  work_object_root_id: string;
  is_enabled: boolean;
  position_index: number;
  display_label_override: string | null;
}

// GET .../portfolio-allocation-draft response. row_version 0 + null plan_id =
// no plan row yet (the default independent draft); 0 is then the valid PUT token.
export interface AllocationDraftResponse {
  composition_id: string;
  plan_id: string | null;
  current_revision_id: string | null;
  row_version: number;
  draft: AllocationDraft;
  candidate_items: AllocationCandidate[];
}

// A single validation finding (domain rules AllocationIssue.as_dict).
export interface AllocationIssue {
  code: string;
  severity: string;
  message: string;
  field: string | null;
  composition_item_id: string | null;
}

export interface SleeveAmount {
  composition_item_id: string;
  equity_share_percent: string;
  initial_sleeve_capital: string;
}

// Server-canonical preview amounts (domain rules DerivedAmounts.as_dict) — the
// client renders these verbatim and never recomputes capital math (doc 13 §8.3).
export interface DerivedAmounts {
  currency: string | null;
  portfolio_initial_capital: string;
  reserved_cash: string;
  capital_available: string;
  total_allocated: string;
  unallocated: string;
  active_share_total: string;
  sleeves: SleeveAmount[];
}

// PUT draft return (commands upsert_allocation_draft).
export interface SaveDraftResult {
  composition_id: string;
  plan_id: string;
  enabled: boolean;
  row_version: number;
  draft_fingerprint: string;
  inline_issues: AllocationIssue[];
  derived: DerivedAmounts | null;
  readiness_invalidated: boolean;
}

// POST validate return (commands validate_allocation_draft). state is the
// UPPERCASE allocation readiness token (NOT_SELECTED | NOT_READY |
// READY_WITH_WARNINGS | READY) — distinct from the lowercase doc-14 readiness
// states. warnings is the warning-severity subset of issues.
export interface AllocationValidationReport {
  validation_report_id: string;
  composition_id: string;
  enabled: boolean;
  state: string;
  valid: boolean;
  issues: AllocationIssue[];
  warnings: AllocationIssue[];
  derived: DerivedAmounts | null;
  config_hash: string | null;
}

// POST sync return (queries sync_preview — non-destructive Flow D preview).
export interface SyncPreview {
  composition_id: string;
  retained: AllocationEntry[];
  missing: AllocationEntry[];
  new_candidates: AllocationCandidate[];
  requires_confirmation: boolean;
}

// POST revisions return (commands create_allocation_revision).
export interface RevisionResult {
  composition_id: string;
  plan_id: string;
  plan_revision_id: string;
  revision_no: number;
  config_hash: string;
  current_revision_id: string;
  row_version: number;
  derived: DerivedAmounts | null;
}

// ---------------------------------------------------------------------------
// PUT input shape (mirrors routes PutDraftBody minus the ignored item_type)
// ---------------------------------------------------------------------------

export interface AllocationEntryInput {
  composition_item_id: string;
  active: boolean;
  equity_share_percent: string | null;
}

export interface AllocationDraftInput {
  enabled: boolean;
  initial_capital: AllocationMoney | null;
  compounding_mode: string | null;
  reserve_cash_percent: string | null;
  max_total_exposure_percent: string | null;
  conflict_policy: string | null;
  entries: AllocationEntryInput[];
}

// ---------------------------------------------------------------------------
// Presentation taxonomy (mirror domain/allocation/enums.py — hydration only,
// the server re-validates every submitted token and is authoritative)
// ---------------------------------------------------------------------------

// AllocationCurrency wire tokens (doc 13 §5.1).
export const ALLOCATION_CURRENCIES = ["USD", "USDT", "EUR", "TRY"] as const;

// CrossItemConflictPolicy wire tokens (doc 13 §8.4 — hydration only; the V1
// engine executes NET conservatively as BLOCK_OPPOSITE and the server
// pre-discloses that as the CONFLICT_POLICY_NET_V1 warning, rendered verbatim).
export const CONFLICT_POLICIES = ["KEEP_SEPARATE", "BLOCK_OPPOSITE", "NET"] as const;

export const CONFLICT_POLICY_LABELS: Record<string, string> = {
  KEEP_SEPARATE: "Keep separate (independent items)",
  BLOCK_OPPOSITE: "Block opposite (earlier-pinned item wins)",
  NET: "Net (V1: executed as Block opposite)",
};

// CompoundingMode wire tokens (doc 13 §5.1, §8.3; Fixed Item Notional is NOT
// a V1 option, §6). Labels are presentation-only.
export const COMPOUNDING_MODES = [
  "COMPOUND_PORTFOLIO_EQUITY",
  "FIXED_INITIAL_PORTFOLIO_CAPITAL",
] as const;

export const COMPOUNDING_MODE_LABELS: Record<string, string> = {
  COMPOUND_PORTFOLIO_EQUITY: "Compound portfolio equity",
  FIXED_INITIAL_PORTFOLIO_CAPITAL: "Fixed initial portfolio capital",
};

// Validation-report state labels/tones (commands _readiness_state — UPPERCASE).
export const ALLOCATION_STATE_LABELS: Record<string, string> = {
  NOT_SELECTED: "Not selected (independent)",
  NOT_READY: "Not ready",
  READY_WITH_WARNINGS: "Ready with warnings",
  READY: "Ready",
};

export const ALLOCATION_STATE_TONES: Record<string, "ok" | "warn" | "down" | "neutral"> = {
  NOT_SELECTED: "neutral",
  NOT_READY: "down",
  READY_WITH_WARNINGS: "warn",
  READY: "ok",
};

export function allocationStateLabel(state: string): string {
  return ALLOCATION_STATE_LABELS[state] ?? state;
}

export function allocationStateTone(state: string): "ok" | "warn" | "down" | "neutral" {
  return ALLOCATION_STATE_TONES[state] ?? "neutral";
}

// ---------------------------------------------------------------------------
// Query hooks
// ---------------------------------------------------------------------------

// The composition's draft projection + candidate item picker. Keyed under
// ["allocation", "draft", id] so every allocation mutation refetches it.
export function useAllocationDraft(compositionId: string | null) {
  return useQuery({
    queryKey: ["allocation", "draft", compositionId],
    queryFn: () =>
      api.get<AllocationDraftResponse>(
        `/mainboard-compositions/${encodeURIComponent(compositionId ?? "")}/portfolio-allocation-draft`,
      ),
    enabled: compositionId !== null,
  });
}

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------

// Autosave-upsert the draft. expectedRowVersion is the GET's row_version (0
// creates the plan row). Success invalidates ["allocation"] + ["readiness"] +
// ["mainboard"] (the command returns readiness_invalidated: true — the Ready
// Check and the default-Mainboard ready_summary read this draft) + ["audit"].
export function useSaveAllocationDraft() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      compositionId: string;
      expectedRowVersion: number;
      draft: AllocationDraftInput;
    }) =>
      apiRequest<SaveDraftResult>(
        `/mainboard-compositions/${encodeURIComponent(input.compositionId)}/portfolio-allocation-draft`,
        {
          method: "PUT",
          body: { expected_row_version: input.expectedRowVersion, ...input.draft },
          headers: { "Idempotency-Key": crypto.randomUUID() },
        },
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["allocation"] });
      void queryClient.invalidateQueries({ queryKey: ["readiness"] });
      void queryClient.invalidateQueries({ queryKey: ["mainboard"] });
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}

// Validate the CURRENT server draft (not the local editor state). The route
// reads no body/headers; each run mints a new immutable report id + an audit
// row, so only ["audit"] is invalidated — the draft itself never moves.
export function useValidateAllocation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { compositionId: string }) =>
      api.post<AllocationValidationReport>(
        `/mainboard-compositions/${encodeURIComponent(input.compositionId)}/portfolio-allocation/validate`,
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}

// Non-destructive Sync-From-Mainboard merge preview (§10.2 Flow D). A PURE
// READ served by the query layer: no Idempotency-Key, no audit, nothing to
// invalidate. Applying the merge is an explicit Save (PUT) of the merged
// entries — never automatic (§14#9).
export function useSyncPreview() {
  return useMutation({
    mutationFn: (input: { compositionId: string }) =>
      api.post<SyncPreview>(
        `/mainboard-compositions/${encodeURIComponent(input.compositionId)}/portfolio-allocation/sync`,
      ),
  });
}

// Freeze the validated, blocker-free ENABLED draft into an immutable plan
// revision (§8.5). OCC body token + fresh Idempotency-Key per attempt; the
// return has no readiness_invalidated flag → ["allocation"] + ["audit"] only.
export function useCreateAllocationRevision() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { compositionId: string; expectedRowVersion: number }) =>
      apiRequest<RevisionResult>(
        `/mainboard-compositions/${encodeURIComponent(input.compositionId)}/portfolio-allocation/revisions`,
        {
          method: "POST",
          body: { expected_row_version: input.expectedRowVersion },
          headers: { "Idempotency-Key": crypto.randomUUID() },
        },
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["allocation"] });
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}
