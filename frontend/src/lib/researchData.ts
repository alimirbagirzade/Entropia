// Research Data access (doc 12 §3, §5, §7). The secondary/context layer above the
// primary Market Data price surface: a dataset Root + immutable revisions move
// DRAFT -> ANALYZING -> NEEDS_REVIEW -> VERIFIED -> (Admin) APPROVED; only an
// ACTIVE+APPROVED revision feeds research/backtest evidence bundles. Every
// endpoint is gated server-side to Admin/Supervisor/Agent page access (doc 12 §2)
// — Users and Guests see the 403 envelope verbatim; the UI never pre-gates.
//
// This slice binds the READ surface (role-aware registry list, head detail) and
// the owner INGEST chain: create a dataset Root pinned to an Approved Market Data
// dataset (DR3 — a create with no ACTIVE+APPROVED market link answers 409
// DEPENDENCY_BLOCKED verbatim), register + finalize the immutable raw asset, and
// enqueue the durable analysis job. The revision lifecycle (append DRAFT/successor
// revision, set time policy, declare field/feature definitions, Admin
// approve/revoke, evidence bundles) is a deferred follow-up — the detail
// row_version is already surfaced as its future If-Match OCC token.
//
// All hooks live under ["research-data"]; there is no dedicated research-data SSE
// event (commands emit resource.changed), so the full-refresh sweep covers them.
// Mutations invalidate ["research-data"] + ["audit"] (each command audits),
// mirroring lib/marketData.ts / lib/rationale.ts.

import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";

import { api, apiRequest } from "./apiClient";

// ---------------------------------------------------------------------------
// Wire types — mirror application/queries/research_data.py _revision_dict /
// get_research_dataset_detail and application/commands/research_data.py return
// dicts verbatim. Nullable columns stay nullable; server strings are rendered
// as-is (no client-side domain state).
// ---------------------------------------------------------------------------

export interface ResearchDatasetRow {
  entity_id: string;
  revision_id: string;
  revision_no: number;
  revision_state: string;
  validation_status: string | null;
  display_name: string | null;
  category_key: string | null;
  custom_category: string | null;
  provider_name: string | null;
  usage_scope: string | null;
  linked_market_dataset_revision_id: string | null;
  event_time_semantics: string | null;
  available_time_policy: string | null;
  available_delay_seconds: number | null;
  frequency_policy: string | null;
  source_timezone_mode: string | null;
  source_timezone_iana: string | null;
  content_hash: string | null;
  manifest_hash: string | null;
  owner_principal_id: string | null;
  row_version: number;
  lifecycle_state: string;
  created_at: string | null;
}

export interface ResearchDatasetsPage {
  data: ResearchDatasetRow[];
  meta: { cursor: string | null; has_more: boolean };
}

export interface ResearchRevisionRef {
  revision_id: string;
  revision_no: number;
  revision_state: string;
}

export interface ResearchDatasetDetail extends ResearchDatasetRow {
  revisions: ResearchRevisionRef[];
}

export interface CreateDatasetResult {
  entity_id: string;
  revision_id: string;
  revision_state: string;
}

export interface StartUploadResult {
  asset_id: string;
  entity_id: string;
}

export interface FinalizeUploadResult {
  entity_id: string;
  asset_id: string;
  revision_id: string;
  revision_state: string;
}

// 202 admission for the durable analysis job (DR8): the jobs row is the source of
// truth and survives browser close; there is no jobs list surface, so the job id
// is informational and progress lands back on the revision state.
export interface AnalysisAccepted {
  job_id: string;
  entity_id: string;
  revision_id: string;
  queue: string;
  status: string;
}

// ---------------------------------------------------------------------------
// Taxonomy hydration mirrors — domain/research_data/enums.py. Select hydration
// ONLY; the server re-validates every submitted value (CR-04).
// ---------------------------------------------------------------------------

// ResearchCategory — the eight built-in categories. `other_custom` is extensible:
// it carries a non-empty custom_category and every other category must NOT (the
// server's CategorySpec enforces both directions — CustomCategoryRequired /
// ValidationError verbatim).
export const RESEARCH_CATEGORIES = [
  "open_interest",
  "funding_rate",
  "liquidations",
  "order_book",
  "liquidity_heatmap",
  "onchain_flows",
  "macro_calendar",
  "other_custom",
] as const;

export const OTHER_CUSTOM_CATEGORY = "other_custom";

// UsageScope — what system behavior a revision may feed (doc 12 §5.3, §9.3):
// research_backtest is evidence-bundle eligible after approval; agent_research_only
// is investigation/context only; feature_input_only needs an approved feature
// definition before Strategy consumption.
export const USAGE_SCOPES = [
  "research_backtest",
  "agent_research_only",
  "feature_input_only",
] as const;

// ResearchRevisionState — rendered verbatim; `verified` is distinct from
// `approved` (only an Admin moves verified -> approved) and `approval_revoked`
// stops new use without mutating pinned manifests.
export const RESEARCH_REVISION_STATES = [
  "draft",
  "analyzing",
  "needs_review",
  "verified",
  "approved",
  "deprecated",
  "approval_revoked",
] as const;

// ---------------------------------------------------------------------------
// Presentation helpers — server strings stay verbatim over the wire.
// ---------------------------------------------------------------------------

export function researchStateTone(state: string): "ok" | "warn" | "down" | "neutral" {
  if (state === "approved" || state === "verified") return "ok";
  if (state === "needs_review") return "warn";
  if (state === "deprecated" || state === "approval_revoked") return "down";
  return "neutral";
}

// ---------------------------------------------------------------------------
// Query hooks
// ---------------------------------------------------------------------------

// Registry of head revisions visible to the actor (role-aware server-side;
// soft-deleted and unauthorized roots are excluded by the query, doc 12 §3).
export function useResearchDatasets(cursor: string | null) {
  return useQuery({
    queryKey: ["research-data", "registry", cursor],
    queryFn: () => {
      const params = new URLSearchParams();
      if (cursor !== null) params.set("cursor", cursor);
      const qs = params.toString();
      return api.get<ResearchDatasetsPage>(`/research-datasets${qs ? `?${qs}` : ""}`);
    },
    placeholderData: (previous) => previous,
  });
}

// Head detail + revision history. The response carries the root row_version — the
// ETag/If-Match OCC token of the deferred revision-lifecycle actions.
export function useResearchDataset(entityId: string | null) {
  return useQuery({
    queryKey: ["research-data", "detail", entityId],
    queryFn: () =>
      api.get<ResearchDatasetDetail>(`/research-datasets/${encodeURIComponent(entityId ?? "")}`),
    enabled: entityId !== null,
  });
}

// ---------------------------------------------------------------------------
// Mutations — the owner ingest chain (doc 12 §3 workflow strip Steps 1-4). Draft
// edits are owner-or-Admin SERVER-side (ensure_can_edit_draft); the UI never
// pre-gates — a denial renders the 401/403 envelope verbatim.
// ---------------------------------------------------------------------------

function invalidateResearchData(queryClient: QueryClient) {
  void queryClient.invalidateQueries({ queryKey: ["research-data"] });
  void queryClient.invalidateQueries({ queryKey: ["audit"] });
}

export interface CreateDatasetInput {
  // DR3: the exact Market Data dataset whose ACTIVE+APPROVED revision this
  // research dataset pins. No approved market link -> 409 DEPENDENCY_BLOCKED.
  market_entity_id: string;
  payload: Record<string, unknown>;
  category: string;
  usage_scope: string;
  // Only `other_custom` carries a custom_category; other categories send null and
  // the server rejects a stray value (CategorySpec ValidationError verbatim).
  custom_category: string | null;
  display_name: string | null;
  provider_name: string | null;
}

// Create the dataset Root + first DRAFT revision (owner = actor). The route
// carries NO Idempotency-Key header (mirrored verbatim — the create command is
// not idempotency-wrapped upstream).
export function useCreateDataset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateDatasetInput) =>
      api.post<CreateDatasetResult>("/research-datasets", input),
    onSuccess: () => invalidateResearchData(queryClient),
  });
}

export interface StartUploadInput {
  entity_id: string;
  object_key: string;
  content_digest: string;
  size_bytes: number;
  content_type: string | null;
  original_filename: string | null;
}

// Step 1: record the immutable raw-asset evidence row (doc 12 §7 Browse File). The
// bytes live in object storage; this page registers the object key + digest
// metadata only — there is no browser byte-upload endpoint on this surface.
export function useStartUpload() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ entity_id, ...body }: StartUploadInput) =>
      api.post<StartUploadResult>(
        `/research-datasets/${encodeURIComponent(entity_id)}/upload-session`,
        body,
      ),
    onSuccess: () => invalidateResearchData(queryClient),
  });
}

// Mark the upload complete. Idempotent server-side — a fresh Idempotency-Key per
// attempt makes a retry a new decision, not a replay.
export function useFinalizeUpload() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { entity_id: string; asset_id: string }) =>
      apiRequest<FinalizeUploadResult>(
        `/research-datasets/${encodeURIComponent(input.entity_id)}/upload-session/finalize`,
        {
          method: "POST",
          headers: { "Idempotency-Key": crypto.randomUUID() },
          body: { asset_id: input.asset_id },
        },
      ),
    onSuccess: () => invalidateResearchData(queryClient),
  });
}

// Step 2: enqueue the durable analysis job on the data queue (202; DRAFT ->
// ANALYZING). Idempotent — same key returns the same job id.
export function useRequestAnalysis() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { entity_id: string }) =>
      apiRequest<AnalysisAccepted>(
        `/research-datasets/${encodeURIComponent(input.entity_id)}/analysis`,
        {
          method: "POST",
          headers: { "Idempotency-Key": crypto.randomUUID() },
        },
      ),
    onSuccess: () => invalidateResearchData(queryClient),
  });
}

// ===========================================================================
// Revision lifecycle (doc 12 §5, §7, §8, §9) — the eight actions that carry a
// dataset past ingest. Draft edits (revise / time-policy / field / feature) are
// owner-or-Admin; approve + revoke are Admin-only; ALL gates live server-side and
// the UI never pre-gates (a denial renders the 401/403 envelope verbatim). Revise
// + approve + revoke carry the root row_version as an If-Match "rv-N" ETag
// (etag_for_row_version) + a fresh Idempotency-Key per attempt; time-policy +
// field/feature + the two bundle compilers read NO such header (mirrored verbatim
// — their routes take none, AMPIRICALLY read). The bundle compilers are PURE READS
// (no durable row, no audit/outbox) — content-addressed probes, no invalidation.
// ===========================================================================

// Taxonomy hydration mirrors — domain/research_data/enums.py. Select hydration
// ONLY; the server re-validates every submitted value (CR-04).

// EventTimeSemantics — how a record's event timestamp is interpreted (doc 12 §5.2).
export const EVENT_TIME_SEMANTICS = [
  "provider_event_timestamp",
  "provider_snapshot_timestamp",
  "bar_close_end_time",
  "custom_documented_event_time",
] as const;

// AvailableTimePolicy — how the first real availability time is derived. Only
// `fixed_delay` carries a positive delay; every other rule MUST send delay=null so
// a stale prior delay never reaches the engine (the server's AvailableTimeSpec
// rejects a mismatch — TIME_POLICY_INVALID verbatim).
export const AVAILABLE_TIME_POLICIES = [
  "same_as_event_time",
  "fixed_delay",
  "provider_publish_timestamp",
  "custom_documented_rule",
] as const;

export const FIXED_DELAY_POLICY = "fixed_delay";

// ResearchTimezoneMode — declared source timezone. `custom` requires an IANA id;
// `utc`/`exchange` must NOT carry one (the server re-validates both directions).
export const RESEARCH_TIMEZONE_MODES = ["utc", "exchange", "custom"] as const;

export const CUSTOM_TIMEZONE_MODE = "custom";

// ---------------------------------------------------------------------------
// Lifecycle wire types — mirror the command / route / bundle-compiler return
// dicts verbatim (application/commands/research_data.py, apps/api/routes/
// research_data.py, application/jobs/research_data.py::_seal_bundle).
// ---------------------------------------------------------------------------

// create_research_dataset_revision -> {entity_id, revision_id, revision_no,
// row_version}. row_version is the root's post-append token — a subsequent OCC
// action must re-read the detail rather than reuse this stale value.
export interface CreateRevisionResult {
  entity_id: string;
  revision_id: string;
  revision_no: number;
  row_version: number;
}

// set_time_policy (route dict) -> {time_policy_id, entity_id, available_time_policy}.
export interface TimePolicyResult {
  time_policy_id: string;
  entity_id: string;
  available_time_policy: string;
}

// define_field / define_feature (route dicts).
export interface FieldDefinitionResult {
  field_definition_id: string;
  field_name: string;
}

export interface FeatureDefinitionResult {
  feature_definition_id: string;
  feature_name: string;
}

// approve_research_dataset_revision / revoke_research_dataset_approval share the
// {entity_id, revision_id, revision_state} return shape.
export interface ApprovalResult {
  entity_id: string;
  revision_id: string;
  revision_state: string;
}

// One pinned member of a compiled bundle. The exact research revision id + content
// hash AND the linked market revision id + content hash — never "latest".
export interface BundleMember {
  research_revision_id: string;
  research_content_hash: string | null;
  usage_scope: string | null;
  market_dataset_revision_id: string | null;
  market_content_hash: string | null;
}

// _seal_bundle -> a content-addressed immutable bundle. task_id / run_request_id
// appear only when the request supplied them (the server drops None from the body).
export interface BundleResult {
  bundle_kind: string;
  members: BundleMember[];
  compiler_version: string;
  resolved_at: string;
  bundle_hash: string;
  task_id?: string;
  run_request_id?: string;
}

// If-Match "rv-N" OCC token + a fresh Idempotency-Key per attempt — the exact
// header pair etag_for_row_version + the idempotent commands expect (revise,
// approve, revoke). Mirrors lib/marketData.ts::postWithOcc.
function postWithOcc<T>(path: string, rowVersion: number, body: unknown): Promise<T> {
  return apiRequest<T>(path, {
    method: "POST",
    headers: { "If-Match": `"rv-${rowVersion}"`, "Idempotency-Key": crypto.randomUUID() },
    body,
  });
}

// ---------------------------------------------------------------------------
// Revise (OCC) — append a new DRAFT revision (doc 12 §5).
// ---------------------------------------------------------------------------

// The revision body (CreateRevisionRequest). category + usage_scope +
// timezone_mode are REQUIRED by the schema; custom_category is non-null only for
// `other_custom`; timezone_iana is non-null only for `custom`; market_entity_id
// re-links a fresh Approved market bundle (DR3) when supplied. The server
// re-validates every field.
export interface RevisionBody {
  payload: Record<string, unknown>;
  category: string;
  usage_scope: string;
  timezone_mode: string;
  custom_category: string | null;
  timezone_iana: string | null;
  market_entity_id: string | null;
  display_name: string | null;
  provider_name: string | null;
  base_revision_id: string | null;
}

export interface CreateRevisionInput extends RevisionBody {
  entity_id: string;
  // The root row_version read from the detail — the If-Match OCC token. A stale
  // value -> 409 verbatim.
  row_version: number;
}

// Append a new DRAFT revision under OCC. A stale row_version -> 409; a custom
// category/timezone that violates the requiredness rule -> the server's
// CUSTOM_CATEGORY_REQUIRED / TIME_POLICY_INVALID envelope verbatim.
export function useCreateRevision() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ entity_id, row_version, ...body }: CreateRevisionInput) =>
      postWithOcc<CreateRevisionResult>(
        `/research-datasets/${encodeURIComponent(entity_id)}/revisions`,
        row_version,
        body,
      ),
    onSuccess: () => invalidateResearchData(queryClient),
  });
}

// ---------------------------------------------------------------------------
// Time policy (no OCC) — set the event/available time rules (doc 12 §5.2, §8.4).
// ---------------------------------------------------------------------------

export interface TimePolicyInput {
  entity_id: string;
  event_time_semantics: string;
  available_time_policy: string;
  timezone_mode: string;
  // Non-null ONLY for fixed_delay (positive); every other policy sends null.
  delay_seconds: number | null;
  // Non-null ONLY for the custom timezone mode.
  timezone_iana: string | null;
}

// The route reads no If-Match/Idempotency-Key — none is sent (mirrored verbatim).
export function useSetTimePolicy() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ entity_id, ...body }: TimePolicyInput) =>
      api.post<TimePolicyResult>(
        `/research-datasets/${encodeURIComponent(entity_id)}/time-policy`,
        body,
      ),
    onSuccess: () => invalidateResearchData(queryClient),
  });
}

// ---------------------------------------------------------------------------
// Field / feature definitions (no OCC) — doc 12 §8.3, §9.3.
// ---------------------------------------------------------------------------

export interface FieldDefinitionInput {
  entity_id: string;
  field_name: string;
  semantic_type: string;
  measurement_method: string;
  null_semantics: string;
  event_time_source: string;
  availability_rule: string;
  allowed_usage: string;
  // The only optional field (doc 12 §8.3); everything else is required or the
  // server answers FIELD_MEANING_INSUFFICIENT verbatim.
  unit_or_scale: string | null;
}

export function useDefineField() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ entity_id, ...body }: FieldDefinitionInput) =>
      api.post<FieldDefinitionResult>(
        `/research-datasets/${encodeURIComponent(entity_id)}/field-definitions`,
        body,
      ),
    onSuccess: () => invalidateResearchData(queryClient),
  });
}

export interface FeatureDefinitionInput {
  entity_id: string;
  feature_name: string;
  definition: Record<string, unknown>;
  feature_version: number;
  approval_state: string | null;
}

export function useDefineFeature() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ entity_id, ...body }: FeatureDefinitionInput) =>
      api.post<FeatureDefinitionResult>(
        `/research-datasets/${encodeURIComponent(entity_id)}/feature-definitions`,
        body,
      ),
    onSuccess: () => invalidateResearchData(queryClient),
  });
}

// ---------------------------------------------------------------------------
// Approve / revoke (Admin, OCC) — doc 12 §2, §7.
// ---------------------------------------------------------------------------

export interface ApprovalInput {
  entity_id: string;
  revision_id: string;
  note: string | null;
  row_version: number;
}

// Admin-only: move a VERIFIED revision -> APPROVED under OCC. A non-Admin -> 403
// APPROVAL_REQUIRES_ADMIN verbatim; a revision whose time policy/market link is no
// longer valid -> 409 TIME_POLICY_INVALID / DEPENDENCY_BLOCKED (DR3/DR4).
export function useApproveRevision() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ entity_id, row_version, revision_id, note }: ApprovalInput) =>
      postWithOcc<ApprovalResult>(
        `/research-datasets/${encodeURIComponent(entity_id)}/approve`,
        row_version,
        { revision_id, note },
      ),
    onSuccess: () => invalidateResearchData(queryClient),
  });
}

// Admin-only: move an APPROVED revision -> APPROVAL_REVOKED (stops new use; pinned
// manifests stay immutable). Same OCC + Idempotency-Key header pair as approve.
export function useRevokeApproval() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ entity_id, row_version, revision_id, note }: ApprovalInput) =>
      postWithOcc<ApprovalResult>(
        `/research-datasets/${encodeURIComponent(entity_id)}/revoke`,
        row_version,
        { revision_id, note },
      ),
    onSuccess: () => invalidateResearchData(queryClient),
  });
}

// ---------------------------------------------------------------------------
// Bundle compilers (pure read) — doc 12 §9.1, §9.2. No durable row, no audit —
// content-addressed probes, no Idempotency-Key, no invalidation (mirrors the ESP
// resolve probe / Market Data approved-bundle).
// ---------------------------------------------------------------------------

export interface AgentBundleInput {
  research_revision_ids: string[];
  task_id: string | null;
}

export interface EvidenceBundleInput {
  research_revision_ids: string[];
  run_request_id: string | null;
}

// Compile an immutable Agent research bundle (doc 12 §9.1). A non-consumable member
// -> the canonical NOT_FOUND envelope verbatim.
export function useCompileAgentBundle() {
  return useMutation({
    mutationFn: (input: AgentBundleInput) =>
      api.post<BundleResult>("/research-datasets/bundles/agent", input),
  });
}

// Compile an immutable Backtest evidence bundle (doc 12 §9.2). Each member must be
// ACTIVE+APPROVED, usage-scope-eligible and time-policy-valid or the server answers
// USAGE_SCOPE_FORBIDDEN / FIELD_MEANING_INSUFFICIENT / TIME_POLICY_INVALID /
// NOT_FOUND verbatim.
export function useCompileEvidenceBundle() {
  return useMutation({
    mutationFn: (input: EvidenceBundleInput) =>
      api.post<BundleResult>("/research-datasets/bundles/backtest-evidence", input),
  });
}
