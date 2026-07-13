// Trading Signal data access (doc 04 §7–§9). Typed read models + mutations over
// routes/trading_signal.py — the source-import chain (upload immutable asset →
// durable 202 import job → import report) and the native work-object plane
// (create & attach → append revisions → read). EMPIRICAL route map (signatures
// read, PR #105/#111/#113/#115/#117 lesson):
//  - POST /trading-signals/source-assets (201) — UTF-8 TEXT content only (the
//    route contract is `content: str`; raw bytes never travel through the
//    page). Content-addressed: an identical re-upload by the same owner
//    returns the prior asset with deduplicated:true. Fresh Idempotency-Key per
//    attempt; NO OCC token (a create has no head to race).
//  - POST /trading-signals/imports (202) — durable jobs row on the `data`
//    queue (CR-09; survives browser close). Fresh Idempotency-Key; no OCC.
//  - GET  /trading-signals/imports/{job_id} — the import report. While the
//    worker runs it carries the transport JobStatus and a null
//    normalized_event_revision_id; once the parse/map/validate pass lands it
//    carries the domain status + counts + skipped-row evidence (server-capped
//    at 200 rows). Keyed under ["jobs"] so the job.updated SSE event sweeps it
//    live — poll is the loss-tolerant fallback (INF-11) and stops on a
//    terminal status.
//  - POST /trading-signals (201) — validate the §9.2 config server-side +
//    require a succeeded, non-empty, time-safe import, then create the native
//    work object (root + immutable revision 1) and, when attach (Save & Add,
//    default true), attach onto the default Mainboard in the same tx — the
//    composition_hash moves, so the prior Ready report is STALE. Fresh
//    Idempotency-Key; NO OCC.
//  - POST /trading-signals/{root_id}/revisions (201) — append immutable
//    revision N+1. OCC travels BODY-form as expected_head_revision_id STR
//    (server-side optional — this client ALWAYS sends the rendered head, the
//    manual/strategy lesson); stale → 409. NEVER auto-repins the Mainboard
//    item (doc 04 rule 9) → the composition does NOT move.
//  - GET  /trading-signals/{root_id} — work-object header + current revision.
// Pin ("Use This Revision") and delete are NOT on this router — they REUSE the
// Mainboard router (CR-01: a Trading Signal is a work object, not a package).
// No dedicated SSE event for the work object itself → every
// ["trading-signals"] key is swept by the resource.changed full refresh.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, apiRequest } from "./apiClient";

// ---------------------------------------------------------------------------
// Wire types (mirror application/{commands,queries}/trading_signal.py returns)
// ---------------------------------------------------------------------------

// POST /trading-signals/source-assets return (commands upload_source_asset).
export interface UploadSourceAssetResult {
  source_asset_id: string;
  raw_asset_hash: string;
  size_bytes: number;
  deduplicated: boolean;
}

// POST /trading-signals/imports return (commands request_trading_signal_import).
export interface RequestImportResult {
  job_id: string;
  source_asset_id: string;
  queue: string;
  status: string;
}

// GET /trading-signals/imports/{job_id} (queries get_import_report). Until the
// worker writes the normalized revision, status is the transport JobStatus and
// the revision id is null; afterwards status is the domain outcome
// (pending/succeeded/failed) and the evidence fields are present.
export interface SignalImportReport {
  job_id: string;
  status: string;
  normalized_event_revision_id: string | null;
  source_asset_id?: string;
  instrument_id?: string;
  accepted_count: number;
  skipped_count: number;
  skipped_rows: Array<Record<string, unknown>>;
  validation_summary: Record<string, unknown> | null;
  content_hash?: string;
}

// GET /trading-signals/{root_id} current_revision projection.
export interface WorkObjectRevisionView {
  revision_id: string;
  revision_no: number;
  payload: Record<string, unknown>;
  source_provenance: Record<string, unknown> | null;
  available_time: string | null;
  content_hash: string;
}

// GET /trading-signals/{root_id} (queries get_trading_signal).
export interface TradingSignalDetail {
  root_id: string;
  object_kind: string;
  owner_principal_id: string | null;
  lifecycle_state: string;
  deletion_state: string;
  current_revision_id: string | null;
  row_version: number;
  current_revision: WorkObjectRevisionView | null;
}

// POST /trading-signals return (commands create_trading_signal_and_attach).
// workspace_id/item_id/composition_hash are present only when attached.
export interface CreateTradingSignalResult {
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

// POST /trading-signals/{root_id}/revisions return
// (commands create_trading_signal_revision). auto_repinned is always false.
export interface CreateSignalRevisionResult {
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

// commands/trading_signal.py _ALLOWED_EXTENSIONS.
export const SIGNAL_SOURCE_EXTENSIONS = [".txt", ".csv"] as const;

// Import-report statuses after which polling stops: the domain outcomes
// (NormalizedRevisionStatus succeeded/failed) plus the terminal transport
// JobStatus values a crashed job can surface without a normalized row.
export const TERMINAL_IMPORT_STATUSES: ReadonlySet<string> = new Set([
  "succeeded",
  "failed",
  "cancelled",
  "failed_final",
  "superseded",
]);

const IMPORT_POLL_INTERVAL_MS = 5000;

// §9.2 payload skeleton pre-seeded with the import binding — a hydration-only
// convenience for the JSON editor. The server compiler is the sole authority
// on config semantics; every enum default here is a valid canonical token.
// Parse a "canonical_field = source_header" per-line column mapping into the
// {canonical: source} object the import route accepts (doc 04 §5.1 / doc 05 §5.2).
// Blank lines and lines without "=" are ignored; the server re-validates and NEVER
// infers an ambiguous mapping. Shared by both import twins.
export function parseColumnMapping(text: string): Record<string, string> {
  const mapping: Record<string, string> = {};
  for (const line of text.split("\n")) {
    const eq = line.indexOf("=");
    if (eq < 0) continue;
    const canonical = line.slice(0, eq).trim();
    const source = line.slice(eq + 1).trim();
    if (canonical !== "" && source !== "") mapping[canonical] = source;
  }
  return mapping;
}

// Read the server-computed column-mapping evidence hash from an import report's
// validation summary (present only when a mapping/alias was actually applied). It
// becomes the saved revision's import_binding.mapping_revision_id.
export function mappingHashFromSummary(
  summary: Record<string, unknown> | null | undefined,
): string | undefined {
  const value = summary?.mapping_hash;
  return typeof value === "string" ? value : undefined;
}

export function buildSignalPayloadTemplate(input: {
  sourceAssetId: string;
  normalizedEventRevisionId: string;
  instrumentId: string;
  sourceTimezone: string;
  mappingRevisionId?: string;
}): Record<string, unknown> {
  const importBinding: Record<string, unknown> = {
    source_asset_id: input.sourceAssetId,
    normalized_event_revision_id: input.normalizedEventRevisionId,
  };
  if (input.mappingRevisionId !== undefined && input.mappingRevisionId !== "") {
    importBinding.mapping_revision_id = input.mappingRevisionId;
  }
  return {
    kind: "trading_signal",
    identity: { display_name: "" },
    source: { provider_name: "", source_kind: "file" },
    instrument_scope: {
      instrument_id: input.instrumentId,
      display_symbol: input.instrumentId,
    },
    event_model: { resolution_kind: "event_based" },
    data_quality: { mode: "signal_events_only" },
    time_policy: {
      source_timezone: input.sourceTimezone,
      normalization_timezone: "UTC",
      availability_rule: "row_available_time",
    },
    price_policy: { source: "suggested_signal_price" },
    ohlcv_policy: { use_mode: "ignore" },
    import_binding: importBinding,
  };
}

// ---------------------------------------------------------------------------
// Query hooks
// ---------------------------------------------------------------------------

export function useTradingSignal(rootId: string | null) {
  return useQuery({
    queryKey: ["trading-signals", "root", rootId],
    queryFn: () =>
      api.get<TradingSignalDetail>(`/trading-signals/${encodeURIComponent(rootId ?? "")}`),
    enabled: rootId !== null,
  });
}

// The FIRST page binding of the ["jobs"] SSE key: job.updated sweeps this
// query live; the poll is the loss-tolerant fallback (INF-11) and stops once
// the report reaches a terminal status.
export function useSignalImportReport(jobId: string | null) {
  return useQuery({
    queryKey: ["jobs", "trading-signal-import", jobId],
    queryFn: () =>
      api.get<SignalImportReport>(
        `/trading-signals/imports/${encodeURIComponent(jobId ?? "")}`,
      ),
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

// Upload the immutable raw TXT/CSV source asset. No OCC; fresh Idempotency-Key.
// Source assets have no list/read surface — the result in the command return +
// the trading_signal.source_uploaded audit row are the evidence → ["audit"].
export function useUploadSignalSource() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { content: string; originalFilename: string | null }) =>
      apiRequest<UploadSourceAssetResult>("/trading-signals/source-assets", {
        method: "POST",
        body: {
          content: input.content,
          content_type: "text/csv",
          ...(input.originalFilename !== null && input.originalFilename !== ""
            ? { original_filename: input.originalFilename }
            : {}),
        },
        headers: { "Idempotency-Key": crypto.randomUUID() },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}

// 202 durable import job on the data queue. The job id is the durable handle
// (keep it in the URL — it survives browser close, CR-09).
export function useRequestSignalImport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      sourceAssetId: string;
      instrumentId: string;
      sourceTimezone: string;
      importMapping?: Record<string, string> | null;
    }) =>
      apiRequest<RequestImportResult>("/trading-signals/imports", {
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

// Save (& Add): create the native work object + revision 1. workspace_id is
// never sent — the server resolves the default Mainboard (doc 04 §8.1). When
// the result reports attached, the composition_hash moved in the same tx →
// the prior Ready report is STALE → ["mainboard"] + ["readiness"] join.
export function useCreateTradingSignal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { payload: Record<string, unknown>; attach: boolean }) =>
      apiRequest<CreateTradingSignalResult>("/trading-signals", {
        method: "POST",
        body: { payload: input.payload, attach: input.attach },
        headers: { "Idempotency-Key": crypto.randomUUID() },
      }),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ["trading-signals"] });
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
      if (result.attached) {
        void queryClient.invalidateQueries({ queryKey: ["mainboard"] });
        void queryClient.invalidateQueries({ queryKey: ["readiness"] });
      }
    },
  });
}

// Append immutable revision N+1. expectedHeadRevisionId is the rendered head —
// always sent (the server treats it as optional; a stale tab must 409, never
// last-write-wins). NEVER auto-repins → the composition does not move.
export function useCreateSignalRevision() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      rootId: string;
      payload: Record<string, unknown>;
      expectedHeadRevisionId: string;
    }) =>
      apiRequest<CreateSignalRevisionResult>(
        `/trading-signals/${encodeURIComponent(input.rootId)}/revisions`,
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
      void queryClient.invalidateQueries({ queryKey: ["trading-signals"] });
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}
