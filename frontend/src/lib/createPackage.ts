// Create Package data access (doc 06 §4/§5/§7/§9, doc 07 §8/§10): compose an
// immutable create-package request, list the actor's own requests, open the
// read-only request projection (flow state + current Pre-Check scan), and drive
// the request lifecycle ACTIONS — run Pre-Check, generate candidate, create
// draft, approve & publish — plus the immutable dependency-scan artifact viewer.
//
// Concurrency contract: pre-check / generate-candidate carry the request
// row_version as an X-Request-Version OCC header (stale tab -> 409 verbatim);
// draft carries the expected_candidate_hash body token; approve carries the
// draft head as expected_head_revision_id. Every action sends a FRESH
// Idempotency-Key per attempt (a retry after a rejection is a new decision,
// not a replay). Approve is Admin-only server-side (CR-02) — the UI never
// role-gates the button; a non-Admin sees the 403 envelope verbatim.
//
// Create Package has no dedicated SSE event: a new request / state move changes
// an entity's lifecycle, swept by resource.changed (full refresh). Read keys live
// under ["package-requests"]; mutations invalidate that prefix (+ ["audit"] —
// every action writes audit rows the Panel Logs page binds). The Rationale
// Family selector reads the shared ["rationale-families"] list.

import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";

import { api, apiRequest } from "./apiClient";

// ---------------------------------------------------------------------------
// Enums mirrored from backend domain/create_package/enums.py (CR-04: the wire
// values are lowercase snake_case, returned verbatim).
// ---------------------------------------------------------------------------

export type CreatePackageKind = "indicator" | "condition" | "embedded_system";

export type CreationMode =
  | "translate_existing_code"
  | "generate_from_description"
  | "repair_existing_code"
  | "review_existing_code";

export type SourceKind = "code" | "description";

export type SourceLanguage = "pinescript" | "python" | "cpp" | "other";

// V1 fixes the target runtime to the registered Python adapter
// (value_objects.SUPPORTED_TARGET_RUNTIMES); pine_v5 exists in the enum but the
// backend rejects it with RuntimeUnavailable, so the form only offers python.
export const SUPPORTED_TARGET_RUNTIME = "python";

export const CREATE_PACKAGE_KINDS: CreatePackageKind[] = [
  "indicator",
  "condition",
  "embedded_system",
];

export const CREATION_MODES: CreationMode[] = [
  "translate_existing_code",
  "generate_from_description",
  "repair_existing_code",
  "review_existing_code",
];

export const SOURCE_LANGUAGES: SourceLanguage[] = ["pinescript", "python", "cpp", "other"];

// Code modes carry supplied code (source_language required); Generate From
// Description carries a description (source_language forbidden). Mirrors
// value_objects.source_kind_for_mode / _CODE_MODES.
const CODE_MODES: ReadonlySet<CreationMode> = new Set<CreationMode>([
  "translate_existing_code",
  "repair_existing_code",
  "review_existing_code",
]);

export function sourceKindForMode(mode: CreationMode): SourceKind {
  return CODE_MODES.has(mode) ? "code" : "description";
}

// Output-contract `kind` values allowed per package type (doc 06 §4.3; mirrors
// value_objects._OUTPUT_KINDS_BY_KIND). The server re-validates on submit.
export const OUTPUT_KINDS_BY_KIND: Record<CreatePackageKind, string[]> = {
  indicator: ["directional_signal", "numeric_series", "state_series", "boolean_event"],
  condition: ["boolean_condition"],
  embedded_system: [
    "directional_signal",
    "numeric_series",
    "state_series",
    "boolean_event",
    "resolver_output",
  ],
};

export function outputKindsFor(kind: CreatePackageKind): string[] {
  return OUTPUT_KINDS_BY_KIND[kind] ?? [];
}

// Presentation-only badge tone for the read-only flow state (the wire state
// stays a plain string). Blocked/failed/rejected are down; the passed/ready/
// approved milestones are ok; stale warns; the rest are neutral in-flight.
const DOWN_STATES: ReadonlySet<string> = new Set([
  "precheck_blocked",
  "precheck_failed",
  "candidate_failed",
  "rejected",
  "revision_required",
]);
const OK_STATES: ReadonlySet<string> = new Set([
  "precheck_passed",
  "precheck_not_applicable",
  "candidate_ready",
  "eligible_for_approval",
  "approved",
]);

export function requestStateTone(state: string): "ok" | "warn" | "down" | "neutral" {
  if (DOWN_STATES.has(state)) return "down";
  if (state === "precheck_stale") return "warn";
  if (OK_STATES.has(state)) return "ok";
  return "neutral";
}

// Presentation-only badge tone for the Pre-Check scan status (PrecheckScanStatus
// wire values verbatim; stale is computed on read server-side).
export function scanStatusTone(status: string): "ok" | "warn" | "down" | "neutral" {
  if (status === "passed" || status === "not_applicable") return "ok";
  if (status === "blocked" || status === "failed") return "down";
  if (status === "stale") return "warn";
  return "neutral";
}

// Narrow an unknown scan payload member (detected/resolved/missing/unsupported
// are JSONB lists on the wire) to a safe record array for row rendering.
export function asRecordArray(value: unknown): Array<Record<string, unknown>> {
  if (!Array.isArray(value)) return [];
  return value.filter(
    (item): item is Record<string, unknown> => typeof item === "object" && item !== null,
  );
}

// ---------------------------------------------------------------------------
// Wire types (mirror queries/create_package.py projections verbatim)
// ---------------------------------------------------------------------------

export interface ScanSummary {
  scan_id: string;
  attempt_no: number;
  status: string;
  detected: unknown;
  resolved: unknown;
  missing: unknown;
  scanner_version: string | null;
  registry_fingerprint: string | null;
  context_hash: string | null;
}

export interface PackageRequestSummary {
  request_id: string;
  package_type: string;
  state: string;
  source_kind: string;
  package_root_id: string | null;
}

export interface PackageRequestsPage {
  data: PackageRequestSummary[];
  meta: { cursor: string | null; has_more: boolean };
}

export interface PackageRequestDetail {
  request_id: string;
  package_type: string;
  creation_mode: string;
  source_kind: string;
  source_language: string | null;
  target_runtime: string;
  output_contract: Record<string, unknown>;
  rationale_family_id: string | null;
  compatible_rationale_family_ids: string[];
  declared_dependencies: Array<Record<string, unknown>>;
  state: string;
  context_hash: string;
  request_version: number;
  owner_principal_id: string | null;
  current_scan: ScanSummary | null;
  precheck_fresh: boolean;
  package_root_id: string | null;
  draft_revision_id: string | null;
  can_generate_candidate: boolean;
  created_at: string | null;
}

export interface CreateRequestResult {
  request_id: string;
  package_type: string;
  source_kind: string;
  state: string;
  context_hash: string;
  request_version: number;
}

export interface CreateRequestInput {
  package_type: CreatePackageKind;
  creation_mode: CreationMode;
  target_runtime: string;
  request_body: string;
  output_contract: Record<string, unknown>;
  source_language: SourceLanguage | null;
  other_language_label: string | null;
  rationale_family_id: string | null;
  declared_dependencies: Array<{ key: string }>;
}

// Resolved/missing row shapes (commands/create_package.py::_resolve_declared):
// each resolved ref pins the exact ESP revision (never name-only/latest, P4/L5);
// a typed resolver error becomes a missing call with its precise code.
export interface ResolvedRef {
  call?: string;
  canonical_key?: string;
  embedded_entity_id?: string;
  embedded_revision_id?: string;
  content_hash?: string;
  runtime_adapter?: string;
  registry_version?: number;
}

export interface MissingCall {
  call?: string;
  code?: string;
  message?: string;
}

// Immutable scan artifact detail (queries/create_package.py::get_dependency_scan).
export interface DependencyScanDetail extends ScanSummary {
  request_id: string;
  unsupported: unknown;
  source_hash: string | null;
  language: string | null;
  job_id: string | null;
  completed_at: string | null;
}

// Action results (mirror commands/create_package.py return dicts verbatim).
export interface PrecheckActionResult {
  request_id: string;
  scan_id: string;
  attempt_no: number;
  status: string;
  state: string;
  resolved: number;
  missing: Array<Record<string, unknown>>;
  registry_fingerprint: string;
  job_id: string;
}

export interface CandidateActionResult {
  request_id: string;
  state: string;
  candidate_hash: string;
  job_id: string;
}

export interface DraftActionResult {
  request_id: string;
  package_root_id: string | null;
  draft_revision_id: string | null;
  state: string;
}

export interface ApproveActionResult {
  request_id: string;
  package_root_id: string | null;
  revision_id: string | null;
  approval_state: string;
  visibility_scope: string;
  state: string;
}

export interface RationaleFamily {
  entity_id: string;
  display_name: string;
  normalized_name?: string;
  display_color?: string | null;
}

export interface RationaleFamiliesPage {
  data: RationaleFamily[];
  meta: { cursor: string | null; has_more: boolean };
}

// ---------------------------------------------------------------------------
// Query hooks
// ---------------------------------------------------------------------------

// The Rationale Family selector for the create form (indicator/condition require
// an ACTIVE family). Shared read under ["rationale-families"]; first page only.
export function useRationaleFamilies(cursor: string | null) {
  return useQuery({
    queryKey: ["rationale-families", cursor],
    queryFn: () => {
      const params = new URLSearchParams();
      if (cursor !== null) params.set("cursor", cursor);
      const qs = params.toString();
      return api.get<RationaleFamiliesPage>(`/rationale-families${qs ? `?${qs}` : ""}`);
    },
    staleTime: 5 * 60 * 1000,
  });
}

export function usePackageRequests(cursor: string | null) {
  return useQuery({
    queryKey: ["package-requests", "list", cursor],
    queryFn: () => {
      const params = new URLSearchParams();
      if (cursor !== null) params.set("cursor", cursor);
      const qs = params.toString();
      return api.get<PackageRequestsPage>(`/create-package/requests${qs ? `?${qs}` : ""}`);
    },
    // Keep the current table mounted while a page flip is in flight.
    placeholderData: (previous) => previous,
  });
}

export function usePackageRequest(requestId: string | null) {
  return useQuery({
    queryKey: ["package-requests", "detail", requestId],
    queryFn: () =>
      api.get<PackageRequestDetail>(
        `/create-package/requests/${encodeURIComponent(requestId ?? "")}`,
      ),
    enabled: requestId !== null,
  });
}

// The immutable dependency-scan artifact (doc 07 §10): evidence never mutates
// once written, so a long staleTime is safe; the key stays under
// ["package-requests"] so the resource.changed sweep is harmless.
export function useDependencyScan(scanId: string | null) {
  return useQuery({
    queryKey: ["package-requests", "scan", scanId],
    queryFn: () =>
      api.get<DependencyScanDetail>(`/dependency-scans/${encodeURIComponent(scanId ?? "")}`),
    enabled: scanId !== null,
    staleTime: 5 * 60 * 1000,
  });
}

// ---------------------------------------------------------------------------
// Mutation — create a request (POST /create-package/requests)
// ---------------------------------------------------------------------------

// A fresh Idempotency-Key per submit keeps a retry after a rejection a new
// decision, not a replay; the submit button stays disabled while pending so a
// double-click never creates two requests. On success the ["package-requests"]
// list is invalidated. The server re-validates every field and returns the
// canonical error envelope verbatim (the client never invents CP messages).
export function useCreatePackageRequest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateRequestInput) =>
      apiRequest<CreateRequestResult>("/create-package/requests", {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: input,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["package-requests"] });
    },
  });
}

// ---------------------------------------------------------------------------
// Mutations — request lifecycle actions (doc 06 §7, doc 07 §8)
// ---------------------------------------------------------------------------

// Every action moves the request projection and writes audit rows; refetch both.
function invalidateActions(queryClient: QueryClient) {
  void queryClient.invalidateQueries({ queryKey: ["package-requests"] });
  void queryClient.invalidateQueries({ queryKey: ["audit"] });
}

// Pre-check / generate-candidate carry the request row_version as an
// X-Request-Version OCC header so a stale tab gets the 409 verbatim instead of
// silently racing a concurrent edit (mirrors agentLab postWithIfMatch), plus a
// fresh Idempotency-Key per attempt (doc 07 §8.1).
function postWithRequestVersion<T>(path: string, requestVersion: number): Promise<T> {
  return apiRequest<T>(path, {
    method: "POST",
    headers: {
      "X-Request-Version": String(requestVersion),
      "Idempotency-Key": crypto.randomUUID(),
    },
  });
}

export function useRunPrecheck() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { request_id: string; request_version: number }) =>
      postWithRequestVersion<PrecheckActionResult>(
        `/create-package/requests/${encodeURIComponent(input.request_id)}/pre-check`,
        input.request_version,
      ),
    onSuccess: () => invalidateActions(queryClient),
  });
}

export function useGenerateCandidate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { request_id: string; request_version: number }) =>
      postWithRequestVersion<CandidateActionResult>(
        `/create-package/requests/${encodeURIComponent(input.request_id)}/generate-candidate`,
        input.request_version,
      ),
    onSuccess: () => invalidateActions(queryClient),
  });
}

// Draft races the CANDIDATE, not the request head: the expected_candidate_hash
// body token (from the accepted generate result) rejects a stale candidate with
// the typed error verbatim. Idempotent server-side: an existing draft replays
// the SAME root + revision.
export function useCreateDraft() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { request_id: string; expected_candidate_hash: string | null }) =>
      apiRequest<DraftActionResult>(
        `/create-package/requests/${encodeURIComponent(input.request_id)}/draft`,
        {
          method: "POST",
          headers: { "Idempotency-Key": crypto.randomUUID() },
          body: { expected_candidate_hash: input.expected_candidate_hash },
        },
      ),
    onSuccess: () => invalidateActions(queryClient),
  });
}

// Admin-only server-side (CR-02); expected_head_revision_id pins the draft head
// so a concurrent revision move gets the conflict verbatim. UI visibility is
// never authorization — a non-Admin click surfaces the 403 envelope verbatim.
export function useApproveRequest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      request_id: string;
      expected_head_revision_id: string | null;
      note: string | null;
    }) =>
      apiRequest<ApproveActionResult>(
        `/create-package/requests/${encodeURIComponent(input.request_id)}/approve`,
        {
          method: "POST",
          headers: { "Idempotency-Key": crypto.randomUUID() },
          body: {
            expected_head_revision_id: input.expected_head_revision_id,
            note: input.note,
          },
        },
      ),
    onSuccess: () => invalidateActions(queryClient),
  });
}
