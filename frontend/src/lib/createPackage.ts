// Create Package data access (doc 06 §4/§5/§9): compose an immutable
// create-package request, list the actor's own requests, and open the read-only
// request projection (flow state + current Pre-Check scan). This slice binds the
// request LIFECYCLE ENTRY only — Pre-Check run, candidate generation, draft and
// approve are a follow-up slice; the detail surfaces their read-only hints
// (current_scan, precheck_fresh, can_generate_candidate) that those actions use.
//
// Create Package has no dedicated SSE event: a new request / state move changes
// an entity's lifecycle, swept by resource.changed (full refresh). Read keys live
// under ["package-requests"]; the create mutation invalidates that prefix. The
// Rationale Family selector reads the shared ["rationale-families"] list.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

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
