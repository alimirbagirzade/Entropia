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
