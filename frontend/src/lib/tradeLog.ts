// Trade Log data access (doc 05 §8–§10). Typed read models + mutations over
// routes/trade_log.py — the near-symmetric twin of lib/tradingSignal.ts with
// two deliberate divergences mirrored VERBATIM from the backend:
//  1. The import produces a canonical_trade_record_batch — the report and the
//     §10.2 import_binding carry record_batch_revision_id (NOT
//     normalized_event_revision_id).
//  2. Trade Log is HISTORICAL data (doc 05 §10.4): the work-object revision
//     always carries available_time=null — there is no per-event
//     anti-lookahead availability contract.
// EMPIRICAL route map (signatures read): identical shape to the Trading
// Signal router — 4 POSTs all read a fresh Idempotency-Key; the ONLY OCC
// token is BODY-form expected_head_revision_id STR on /revisions (server-side
// optional — this client ALWAYS sends the rendered head); create/upload/
// import carry no OCC (no head to race). Pin ("Use This Revision") and delete
// REUSE the Mainboard router (CR-01, TL-01: a Trade Log is a work object, not
// a package). The import report is keyed under ["jobs"] (job.updated SSE
// sweep + terminal-stop poll fallback, INF-11); the work-object keys
// ["trade-logs"] have no dedicated SSE event → resource.changed sweeps them.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, apiRequest } from "./apiClient";
import { uploadFile } from "./upload";
import type {
  RequestImportResult,
  UploadSourceAssetResult,
  WorkObjectRevisionView,
} from "./tradingSignal";
import { TERMINAL_IMPORT_STATUSES } from "./tradingSignal";

// Shared column-mapping helpers (doc 05 §5.2) — re-exported so the Trade Log page
// imports them from its own lib, mirroring the twin's surface.
export { mappingHashFromSummary, parseColumnMapping } from "./tradingSignal";

// ---------------------------------------------------------------------------
// Wire types (mirror application/{commands,queries}/trade_log.py returns)
// ---------------------------------------------------------------------------

// GET /trade-logs/imports/{job_id} (queries get_import_report). The twin diff:
// the produced evidence is a record batch, not a normalized event revision.
export interface TradeLogImportReport {
  job_id: string;
  status: string;
  record_batch_revision_id: string | null;
  source_asset_id?: string;
  instrument_id?: string;
  accepted_count: number;
  skipped_count: number;
  skipped_rows: Array<Record<string, unknown>>;
  validation_summary: Record<string, unknown> | null;
  content_hash?: string;
}

// GET /trade-logs/{root_id} (queries get_trade_log). current_revision reuses
// the shared work-object projection; available_time is always null here.
export interface TradeLogDetail {
  root_id: string;
  object_kind: string;
  owner_principal_id: string | null;
  lifecycle_state: string;
  deletion_state: string;
  current_revision_id: string | null;
  row_version: number;
  current_revision: WorkObjectRevisionView | null;
}

// POST /trade-logs return (commands create_trade_log_and_attach).
export interface CreateTradeLogResult {
  root_id: string;
  revision_id: string;
  revision_no: number;
  object_kind: string;
  config_hash: string;
  row_version: number;
  attached: boolean;
  ready_state: string;
  workspace_id?: string;
  item_id?: string;
  composition_hash?: string | null;
}

// POST /trade-logs/{root_id}/revisions return (commands
// create_trade_log_revision). auto_repinned is always false (Rule 10).
export interface CreateTradeLogRevisionResult {
  root_id: string;
  revision_id: string;
  revision_no: number;
  config_hash: string;
  row_version: number;
  auto_repinned: boolean;
}

// ---------------------------------------------------------------------------
// Taxonomy mirrors (hydration only — the server re-validates every dispatch)
// ---------------------------------------------------------------------------

// commands/trade_log.py _ALLOWED_EXTENSIONS.
export const TRADE_LOG_SOURCE_EXTENSIONS = [".txt", ".csv"] as const;

const IMPORT_POLL_INTERVAL_MS = 5000;

// §10.2 payload skeleton pre-seeded with the import binding — a hydration-only
// convenience for the JSON editor. The twin diffs vs the Trading Signal
// template: time_model (not time_policy + event_model), content_profile data
// quality, ledger price source, and the record-batch import binding.
export function buildTradeLogPayloadTemplate(input: {
  sourceAssetId: string;
  recordBatchRevisionId: string;
  instrumentId: string;
  sourceTimezone: string;
  mappingRevisionId?: string;
}): Record<string, unknown> {
  const importBinding: Record<string, unknown> = {
    source_asset_id: input.sourceAssetId,
    record_batch_revision_id: input.recordBatchRevisionId,
  };
  if (input.mappingRevisionId !== undefined && input.mappingRevisionId !== "") {
    importBinding.mapping_revision_id = input.mappingRevisionId;
  }
  return {
    kind: "trade_log",
    identity: { display_name: "" },
    source: { provider_name: "", source_kind: "file" },
    instrument_scope: {
      instrument_id: input.instrumentId,
      display_symbol: input.instrumentId,
    },
    time_model: {
      resolution_kind: "event_based",
      source_timezone: input.sourceTimezone,
      normalization_timezone: "UTC",
    },
    data_quality: { content_profile: "entry_exit_records_only" },
    price_policy: { source: "trade_log_entry_exit_price" },
    ohlcv_policy: { use_mode: "ignore" },
    import_binding: importBinding,
  };
}

// ---------------------------------------------------------------------------
// Query hooks
// ---------------------------------------------------------------------------

export function useTradeLog(rootId: string | null) {
  return useQuery({
    queryKey: ["trade-logs", "root", rootId],
    queryFn: () => api.get<TradeLogDetail>(`/trade-logs/${encodeURIComponent(rootId ?? "")}`),
    enabled: rootId !== null,
  });
}

// ["jobs"]-keyed like the Trading Signal report: job.updated sweeps it live;
// the poll fallback stops on a terminal status (INF-11).
export function useTradeLogImportReport(jobId: string | null) {
  return useQuery({
    queryKey: ["jobs", "trade-log-import", jobId],
    queryFn: () =>
      api.get<TradeLogImportReport>(`/trade-logs/imports/${encodeURIComponent(jobId ?? "")}`),
    enabled: jobId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status !== undefined && TERMINAL_IMPORT_STATUSES.has(status)
        ? false
        : IMPORT_POLL_INTERVAL_MS;
    },
  });
}

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------

// Upload the immutable raw TXT/CSV source asset (content-addressed dedup,
// TL-15). Return shape is shared with the Trading Signal twin.
export function useUploadTradeLogSource() {
  const queryClient = useQueryClient();
  return useMutation({
    // F-03: real native file transfer (multipart) — the browser sends the
    // selected TXT/CSV trade-record file itself; the server derives content type
    // + digest and validates size/encoding/schema. No pasted-textarea content.
    mutationFn: (input: { file: File }) =>
      uploadFile<UploadSourceAssetResult>("/trade-logs/source-assets", input.file, {
        idempotencyKey: crypto.randomUUID(),
      }).promise,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}

// 202 durable import job on the data queue (TL-14/TL-15 idempotent; the job id
// is the durable handle — keep it in the URL, CR-09).
export function useRequestTradeLogImport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      sourceAssetId: string;
      instrumentId: string;
      sourceTimezone: string;
      importMapping?: Record<string, string> | null;
    }) =>
      apiRequest<RequestImportResult>("/trade-logs/imports", {
        method: "POST",
        body: {
          source_asset_id: input.sourceAssetId,
          instrument_id: input.instrumentId,
          source_timezone: input.sourceTimezone,
          ...(input.importMapping && Object.keys(input.importMapping).length > 0
            ? { import_mapping: input.importMapping }
            : {}),
        },
        headers: { "Idempotency-Key": crypto.randomUUID() },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}

// Save (& Add): create the native work object + revision 1 (Save != Ready
// PASS != Run, Implementation Rule 15). Attached → composition_hash moved →
// ["mainboard"] + ["readiness"] join the sweep.
export function useCreateTradeLog() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { payload: Record<string, unknown>; attach: boolean }) =>
      apiRequest<CreateTradeLogResult>("/trade-logs", {
        method: "POST",
        body: { payload: input.payload, attach: input.attach },
        headers: { "Idempotency-Key": crypto.randomUUID() },
      }),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ["trade-logs"] });
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
      if (result.attached) {
        void queryClient.invalidateQueries({ queryKey: ["mainboard"] });
        void queryClient.invalidateQueries({ queryKey: ["readiness"] });
      }
    },
  });
}

// Append immutable revision N+1 (Rule 10: NEVER auto-repins). The rendered
// head always travels as the BODY-form OCC token.
export function useCreateTradeLogRevision() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      rootId: string;
      payload: Record<string, unknown>;
      expectedHeadRevisionId: string;
    }) =>
      apiRequest<CreateTradeLogRevisionResult>(
        `/trade-logs/${encodeURIComponent(input.rootId)}/revisions`,
        {
          method: "POST",
          body: {
            payload: input.payload,
            expected_head_revision_id: input.expectedHeadRevisionId,
          },
          headers: { "Idempotency-Key": crypto.randomUUID() },
        },
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["trade-logs"] });
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}

// Export (S6, doc 05 §8 "Export As Package", §11, §13.2) — the immutable
// source-mapping/provenance MANIFEST for a Trade Log revision. Twin of
// useExportTradingSignal / the R2c package export: synchronous, owner/Admin-gated
// server-side, read-only provenance (writes only a trade_log.exported audit; the
// work object is unchanged) → invalidates only ["audit"]. A fresh Idempotency-Key
// makes repeated clicks return the same manifest_hash; NO OCC token (revisionId
// omitted → the server exports the pinned head).
export interface ExportTradeLogResult {
  root_id: string;
  revision_id: string;
  manifest_hash: string;
  manifest: Record<string, unknown>;
}

export function useExportTradeLog() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { rootId: string; revisionId?: string }) =>
      apiRequest<ExportTradeLogResult>(
        `/trade-logs/${encodeURIComponent(input.rootId)}/export`,
        {
          method: "POST",
          headers: { "Idempotency-Key": crypto.randomUUID() },
          body:
            input.revisionId !== undefined
              ? { revision_id: input.revisionId }
              : {},
        },
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}
