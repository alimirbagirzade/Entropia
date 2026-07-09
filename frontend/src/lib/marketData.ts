// Market Data data access (doc 11 §3, §6, §7). The primary price/execution layer:
// a dataset Root + immutable revisions move DRAFT -> UPLOADING -> ANALYZING ->
// NEEDS_REVIEW -> VERIFIED -> (Admin) APPROVED; only an ACTIVE+APPROVED revision
// feeds research/backtests. This slice binds the READ surface (registry list,
// detail, approved-bundle resolve), the owner INGEST chain (create dataset,
// raw-upload start/finalize, durable analysis job, schema mapping) AND the
// revision lifecycle actions: append a DRAFT revision under OCC, append a
// superseding successor, Admin-approve a VERIFIED revision and Admin-deprecate an
// APPROVED one. Revisions + approve carry the root row_version as an
// If-Match "rv-N" ETag (etag_for_row_version) + a fresh Idempotency-Key per
// attempt; successor + deprecate carry neither (their routes read no such header).
// Approve + deprecate are Admin-only SERVER-side (ensure_can_approve) — the UI
// never pre-gates, a denial renders the 403 envelope verbatim.
//
// All hooks live under ["market-data"]; there is no dedicated market-data SSE
// event (commands emit resource.changed), so the full-refresh sweep covers them.
// Mutations invalidate ["market-data"] + ["audit"] (each command audits),
// mirroring lib/rationale.ts / lib/trash.ts.

import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";

import { api, apiRequest } from "./apiClient";

// ---------------------------------------------------------------------------
// Wire types — mirror application/queries/market_data.py _revision_dict /
// get_market_dataset_detail / resolve_approved_market_data_bundle and
// application/commands/market_data.py return dicts verbatim.
// ---------------------------------------------------------------------------

export interface MarketDatasetRow {
  entity_id: string;
  revision_id: string;
  revision_no: number;
  revision_state: string;
  market_data_type: string;
  validation_status: string | null;
  title: string | null;
  instrument_id: string | null;
  content_hash: string | null;
  manifest_hash: string | null;
  owner_principal_id: string | null;
  row_version: number;
  lifecycle_state: string;
  created_at: string | null;
}

export interface MarketDatasetsPage {
  data: MarketDatasetRow[];
  meta: { cursor: string | null; has_more: boolean };
}

export interface MarketRevisionRef {
  revision_id: string;
  revision_no: number;
  revision_state: string;
}

export interface MarketDatasetDetail extends MarketDatasetRow {
  revisions: MarketRevisionRef[];
}

// The exact APPROVED revision a Run/Agent must consume (AT #15 — the manifest
// pins the precise revision + hashes, never "latest").
export interface ApprovedBundle {
  entity_id: string;
  revision_id: string;
  revision_no: number;
  revision_state: string;
  content_hash: string | null;
  manifest_hash: string | null;
  market_data_type: string;
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

// 202 admission for the durable analysis job (D4/CR-09): the jobs row is the
// source of truth and survives browser close; there is no jobs list surface, so
// the job id is informational and progress lands back on the revision state.
export interface AnalysisAccepted {
  job_id: string;
  entity_id: string;
  revision_id: string;
  queue: string;
  status: string;
}

export interface SchemaMappingResult {
  mapping_id: string;
  review_required: boolean;
  confirmed_mapping: Record<string, string | null> | null;
}

// ---------------------------------------------------------------------------
// Taxonomy hydration mirrors — domain/market_data/enums.py. Select/checklist
// hydration ONLY; the server re-validates every submitted value (CR-04).
// ---------------------------------------------------------------------------

// MarketDataType: the three accepted shapes; no other type is silently accepted.
export const MARKET_DATA_TYPES = ["ohlcv", "tick_trades", "spread_execution"] as const;

// MarketRevisionState — rendered verbatim; `verified` is distinct from `approved`
// (only an Admin moves verified -> approved).
export const MARKET_REVISION_STATES = [
  "draft",
  "uploading",
  "analyzing",
  "needs_review",
  "verified",
  "rejected",
  "approved",
  "deprecated",
] as const;

// TimezoneMode (domain/market_data/enums.py): declared source-timezone semantics
// a revision must carry. `custom` requires an IANA id — the server rejects a
// custom mode with no zone (TimezoneSpec validation); the UI only surfaces the
// IANA input for `custom` and never fabricates a default zone.
export const TIMEZONE_MODES = ["exchange", "utc", "custom"] as const;

// ---------------------------------------------------------------------------
// Presentation helpers — server strings stay verbatim over the wire.
// ---------------------------------------------------------------------------

export function revisionStateTone(state: string): "ok" | "warn" | "down" | "neutral" {
  if (state === "approved" || state === "verified") return "ok";
  if (state === "needs_review") return "warn";
  if (state === "rejected" || state === "deprecated") return "down";
  return "neutral";
}

// One textarea entry per line; blank lines are stripped (transport shaping only).
export function linesToList(value: string): string[] {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
}

// "canonical: source_column" per line -> the confirmed_mapping dict the command
// expects (dict[str, str | None]). An empty right-hand side maps the canonical
// field to null (explicitly unmapped); lines without a colon are skipped.
export function parseMappingLines(value: string): Record<string, string | null> {
  const mapping: Record<string, string | null> = {};
  for (const line of linesToList(value)) {
    const colonAt = line.indexOf(":");
    if (colonAt <= 0) continue;
    const canonical = line.slice(0, colonAt).trim();
    const source = line.slice(colonAt + 1).trim();
    if (canonical.length === 0) continue;
    mapping[canonical] = source.length > 0 ? source : null;
  }
  return mapping;
}

// ---------------------------------------------------------------------------
// Query hooks
// ---------------------------------------------------------------------------

// Registry of head revisions visible to the actor (role-aware server-side;
// soft-deleted and unauthorized roots are excluded by the query, doc 11 §3.2).
export function useMarketDatasets(cursor: string | null) {
  return useQuery({
    queryKey: ["market-data", "registry", cursor],
    queryFn: () => {
      const params = new URLSearchParams();
      if (cursor !== null) params.set("cursor", cursor);
      const qs = params.toString();
      return api.get<MarketDatasetsPage>(`/market-datasets${qs ? `?${qs}` : ""}`);
    },
    placeholderData: (previous) => previous,
  });
}

// Head detail + revision history. The response carries the root row_version —
// the ETag/If-Match OCC token of the deferred lifecycle actions.
export function useMarketDataset(entityId: string | null) {
  return useQuery({
    queryKey: ["market-data", "detail", entityId],
    queryFn: () => api.get<MarketDatasetDetail>(`/market-datasets/${encodeURIComponent(entityId ?? "")}`),
    enabled: entityId !== null,
  });
}

// Read-only resolve probe (ESP resolve-probe pattern): which exact revision would
// a Run pin right now? 404 verbatim when there is no ACTIVE+APPROVED revision —
// consumers never silently bind to an unapproved/deleted dataset.
export function useApprovedBundle(entityId: string | null, enabled: boolean) {
  return useQuery({
    queryKey: ["market-data", "approved-bundle", entityId],
    queryFn: () =>
      api.get<ApprovedBundle>(
        `/market-datasets/${encodeURIComponent(entityId ?? "")}/approved-bundle`,
      ),
    enabled: entityId !== null && enabled,
    retry: false,
  });
}

// ---------------------------------------------------------------------------
// Mutations — the owner ingest chain (doc 11 §3.1 workflow ribbon Steps 1-3).
// Draft edits are owner-or-Admin SERVER-side (ensure_can_edit_draft); the UI
// never pre-gates (visibility is never authorization) — a denial renders the
// 401/403 envelope verbatim.
// ---------------------------------------------------------------------------

function invalidateMarketData(queryClient: QueryClient) {
  void queryClient.invalidateQueries({ queryKey: ["market-data"] });
  void queryClient.invalidateQueries({ queryKey: ["audit"] });
}

export interface CreateDatasetInput {
  market_data_type: string;
  payload: Record<string, unknown>;
  title: string | null;
  instrument_id: string | null;
}

// Create the dataset Root + first DRAFT revision (owner = actor). The route
// carries NO Idempotency-Key header (mirrored verbatim — the create command is
// not idempotency-wrapped upstream).
export function useCreateDataset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateDatasetInput) =>
      api.post<CreateDatasetResult>("/market-datasets", input),
    onSuccess: () => invalidateMarketData(queryClient),
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

// Step 1: record the immutable raw-asset evidence row (D5/D6). The bytes live in
// object storage; this page registers the object key + digest metadata only —
// there is no browser byte-upload endpoint on this surface.
export function useStartUpload() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ entity_id, ...body }: StartUploadInput) =>
      api.post<StartUploadResult>(
        `/market-datasets/${encodeURIComponent(entity_id)}/raw-uploads`,
        body,
      ),
    onSuccess: () => invalidateMarketData(queryClient),
  });
}

// Mark the upload complete: DRAFT -> UPLOADING. Idempotent server-side — a fresh
// Idempotency-Key per attempt makes a retry a new decision, not a replay.
export function useFinalizeUpload() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { entity_id: string; asset_id: string }) =>
      apiRequest<FinalizeUploadResult>(
        `/market-datasets/${encodeURIComponent(input.entity_id)}/raw-uploads/finalize`,
        {
          method: "POST",
          headers: { "Idempotency-Key": crypto.randomUUID() },
          body: { asset_id: input.asset_id },
        },
      ),
    onSuccess: () => invalidateMarketData(queryClient),
  });
}

// Step 2: enqueue the durable profile/mapping analysis job (202; -> ANALYZING).
export function useRequestAnalysis() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { entity_id: string }) =>
      apiRequest<AnalysisAccepted>(
        `/market-datasets/${encodeURIComponent(input.entity_id)}/analysis`,
        {
          method: "POST",
          headers: { "Idempotency-Key": crypto.randomUUID() },
        },
      ),
    onSuccess: () => invalidateMarketData(queryClient),
  });
}

export interface ConfirmMappingInput {
  entity_id: string;
  market_data_type: string;
  source_columns: string[];
  // undefined = let the server auto-confirm an unambiguous proposal; an
  // ambiguous/unmapped essential field then rejects with MAPPING_REVIEW_REQUIRED
  // verbatim (D7) and the user supplies the explicit mapping.
  confirmed_mapping: Record<string, string | null> | undefined;
}

export function useConfirmMapping() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ entity_id, confirmed_mapping, ...rest }: ConfirmMappingInput) =>
      api.post<SchemaMappingResult>(
        `/market-datasets/${encodeURIComponent(entity_id)}/schema-mapping`,
        confirmed_mapping === undefined ? rest : { ...rest, confirmed_mapping },
      ),
    onSuccess: () => invalidateMarketData(queryClient),
  });
}

// ---------------------------------------------------------------------------
// Revision lifecycle mutations (doc 11 §5) — the four actions that move a
// dataset through its revision chain. Draft edits are owner-or-Admin, approve +
// deprecate are Admin-only; ALL gates live server-side, the UI never pre-gates.
// ---------------------------------------------------------------------------

// create_market_dataset_revision -> {entity_id, revision_id, revision_no,
// row_version}. row_version is the root's post-append token — a subsequent OCC
// action must re-read the detail rather than reuse this stale value.
export interface CreateRevisionResult {
  entity_id: string;
  revision_id: string;
  revision_no: number;
  row_version: number;
}

// create_successor_revision (route dict) -> {entity_id, revision_id,
// revision_no, revision_state}.
export interface SuccessorResult {
  entity_id: string;
  revision_id: string;
  revision_no: number;
  revision_state: string;
}

// approve_market_dataset_revision / deprecate_market_dataset_revision share the
// {entity_id, revision_id, revision_state} return shape.
export interface ApprovalResult {
  entity_id: string;
  revision_id: string;
  revision_state: string;
}

// The revision body shared by the create-revision and successor routes
// (CreateRevisionRequest). timezone_mode is REQUIRED by the request schema even
// for successor (whose command ignores it); timezone_iana is null unless mode is
// `custom` (the server re-validates the IANA requirement).
export interface RevisionBody {
  market_data_type: string;
  payload: Record<string, unknown>;
  title: string | null;
  instrument_id: string | null;
  timezone_mode: string;
  timezone_iana: string | null;
}

export interface CreateRevisionInput extends RevisionBody {
  entity_id: string;
  // The root row_version read from the detail — the If-Match OCC token. A stale
  // value -> 409 STALE_REVISION verbatim.
  row_version: number;
}

export type CreateSuccessorInput = RevisionBody & { entity_id: string };

export interface ApprovalInput {
  entity_id: string;
  revision_id: string;
  note: string | null;
  // Only revisions + approve carry OCC; deprecate reads no If-Match, so its hook
  // omits row_version entirely (see useDeprecateRevision).
  row_version: number;
}

// If-Match "rv-N" OCC token + a fresh Idempotency-Key per attempt — the exact
// header pair etag_for_row_version + the idempotent commands expect (revisions,
// approve). Mirrors lib/rationale.ts useSoftDeleteFamily / lib/createPackage.ts.
function postWithOcc<T>(path: string, rowVersion: number, body: unknown): Promise<T> {
  return apiRequest<T>(path, {
    method: "POST",
    headers: { "If-Match": `"rv-${rowVersion}"`, "Idempotency-Key": crypto.randomUUID() },
    body,
  });
}

function revisionBody(input: RevisionBody): RevisionBody {
  return {
    market_data_type: input.market_data_type,
    payload: input.payload,
    title: input.title,
    instrument_id: input.instrument_id,
    timezone_mode: input.timezone_mode,
    timezone_iana: input.timezone_iana,
  };
}

// Append a new DRAFT revision under OCC. A stale row_version -> 409; a missing/
// invalid timezone -> the server's TIMEZONE_REQUIRED / validation envelope.
export function useCreateRevision() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ entity_id, row_version, ...rest }: CreateRevisionInput) =>
      postWithOcc<CreateRevisionResult>(
        `/market-datasets/${encodeURIComponent(entity_id)}/revisions`,
        row_version,
        revisionBody(rest),
      ),
    onSuccess: () => invalidateMarketData(queryClient),
  });
}

// Append a superseding successor DRAFT (prior revision stays immutable,
// recorded as supersedes_revision_id). The route reads no If-Match/Idempotency-
// Key — none is sent (mirrored verbatim).
export function useCreateSuccessor() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ entity_id, ...rest }: CreateSuccessorInput) =>
      api.post<SuccessorResult>(
        `/market-datasets/${encodeURIComponent(entity_id)}/successor`,
        revisionBody(rest),
      ),
    onSuccess: () => invalidateMarketData(queryClient),
  });
}

// Admin-only: move a VERIFIED revision -> APPROVED under OCC (If-Match +
// Idempotency-Key). A non-Admin -> 403 APPROVAL_REQUIRES_ADMIN verbatim; a
// non-verified revision -> 409 illegal-transition verbatim.
export function useApproveRevision() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ entity_id, row_version, revision_id, note }: ApprovalInput) =>
      postWithOcc<ApprovalResult>(
        `/market-datasets/${encodeURIComponent(entity_id)}/approve`,
        row_version,
        { revision_id, note },
      ),
    onSuccess: () => invalidateMarketData(queryClient),
  });
}

// Admin-only: move an APPROVED revision -> DEPRECATED. The route reads no
// If-Match/Idempotency-Key — none is sent. A non-Admin -> 403 verbatim.
export function useDeprecateRevision() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { entity_id: string; revision_id: string; note: string | null }) =>
      api.post<ApprovalResult>(
        `/market-datasets/${encodeURIComponent(input.entity_id)}/deprecate`,
        { revision_id: input.revision_id, note: input.note },
      ),
    onSuccess: () => invalidateMarketData(queryClient),
  });
}
