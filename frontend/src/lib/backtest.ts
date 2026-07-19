// Backtest data access for the Stage 5 live-data pages (docs 15/16): typed read
// models over RUN admission, durable run status, the immutable Result detail and
// the server-side Results History index, plus the default-Mainboard composition
// context the RUN page admits against. The client never computes domain state —
// every value below is rendered verbatim from a backend projection.
//
// Every backtest query key starts with the ["backtests"] prefix so the SSE
// `backtest.run.updated` invalidation (lib/sse.ts EVENT_QUERY_KEYS) sweeps them.
// The run-status poll below is only the loss-tolerant fallback (INF-11); SSE is
// the primary freshness signal.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, apiRequest } from "./apiClient";

// ---------------------------------------------------------------------------
// Wire types (mirror backend application/queries projections)
// ---------------------------------------------------------------------------

export interface MainboardItem {
  item_id: string;
  item_kind: string;
  work_object_root_id: string;
  pinned_revision_id: string | null;
  position_index: number;
  is_enabled: boolean;
  display_label_override: string | null;
  row_version: number;
}

// The most recent active succeeded Result projected onto the Mainboard
// (doc 15 §9.4). `snapshot_differs` is server-recomputed: true when the live
// composition fingerprint has moved past the result's pinned one — the row stays
// readable but is clearly labelled, never treated as a current test.
export interface LatestResultSummary {
  result_id: string;
  manifest_hash: string;
  composition_fingerprint: string;
  engine_version: string;
  created_at: string;
  snapshot_differs: boolean;
  summary: {
    symbol: string | null;
    timeframe: string | null;
    period_start: string | null;
    period_end: string | null;
    total_trades: number;
    headline: Record<string, unknown>;
  } | null;
}

export interface DefaultMainboard {
  workspace_id: string;
  workspace_kind: string;
  composition_hash: string | null;
  row_version: number;
  items: MainboardItem[];
  ready_summary: { state: string; report_id: string | null };
  latest_result_summary: LatestResultSummary | null;
}

// Canonical BacktestRun lifecycle (backend domain/backtest/enums.py). The wire
// value stays a plain string; this set only decides when to stop polling.
export const TERMINAL_RUN_STATES: ReadonlySet<string> = new Set([
  "succeeded",
  "failed",
  "cancelled",
]);

export interface BacktestRunAdmission {
  run_id: string;
  state: string;
  manifest_hash: string;
  composition_fingerprint: string;
  ready_report_id: string | null;
  retry_of_run_id: string | null;
  warning_count?: number;
  job_id: string | null;
}

export interface BacktestRun {
  run_id: string;
  composition_id: string;
  state: string;
  manifest_hash: string;
  composition_fingerprint: string;
  composition_snapshot_id: string | null;
  ready_report_id: string | null;
  retry_of_run_id: string | null;
  result_id: string | null;
  failure_code: string | null;
  failure_message: string | null;
  job_id: string | null;
  created_at: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface ResultSummary {
  symbol: string | null;
  timeframe: string | null;
  period_start: string | null;
  period_end: string | null;
  total_trades: number | null;
  // The engine emits headline metrics as a structured object (mirrors
  // LatestResultSummary.headline), not a scalar string.
  headline: Record<string, unknown> | null;
}

export interface MetricValue {
  key: string;
  label: string;
  unit: string;
  value_format: string;
  value: string | null;
  availability: string;
  formula_version?: string | null;
}

export interface ManifestExcerpt {
  manifest_hash: string;
  execution_key: string;
  engine_version: string;
  pinned_item_count: number;
}

// One pinned Mainboard item ref (doc 16 §9.4). The exact (kind, root, revision)
// tuple the run pinned — never re-resolved from the current Mainboard (§15).
export interface ManifestItemRef {
  item_id: string | null;
  item_kind: string | null;
  root_id: string | null;
  revision_id: string | null;
  position: number | null;
  enabled: boolean | null;
}

// Immutable ResultManifestExcerptDTO (doc 16 §8.2/§9.4): pinned strategy/external
// refs, allocation + execution context and artifact availability, read ONLY from
// the result manifest. Fields the V1 manifest does not separately pin
// (package_revision_refs, market_data_revision, research_data_revision_refs) are
// honestly empty/null — carried transitively by strategy_revision_refs.
export interface ResultManifestExcerpt {
  result_id: string;
  composition_snapshot_id: string | null;
  strategy_revision_refs: ManifestItemRef[];
  external_work_refs: ManifestItemRef[];
  package_revision_refs: ManifestItemRef[];
  market_data_revision: string | null;
  research_data_revision_refs: ManifestItemRef[];
  portfolio_allocation_plan_revision_id: string | null;
  execution_context: {
    execution_key: string | null;
    composition_fingerprint: string | null;
    capital_execution: unknown;
  };
  engine_contract_version: string | null;
  artifact_context: unknown;
  completed_at_utc: string | null;
  artifact_availability: { counts: Record<string, number>; any_available: boolean };
}

export interface BacktestResultDetail {
  result_id: string;
  run_id: string;
  composition_id: string;
  composition_fingerprint: string;
  manifest_hash: string;
  engine_version: string;
  summary: ResultSummary | null;
  metrics: MetricValue[];
  manifest: ManifestExcerpt | null;
  manifest_excerpt: ResultManifestExcerpt;
  artifact_counts: Record<string, number>;
}

export type MetricCell = Omit<MetricValue, "formula_version">;

export interface HistoryRow {
  result_id: string;
  display_title: string;
  composition_context: { composition_id: string; composition_fingerprint: string };
  key_metrics: Record<string, MetricCell | null>;
  // The pinned instrument the result ran on (doc 16 §9.4) — honest null when the
  // summary pinned no symbol; a dedicated MD revision is not separately pinned.
  market_data_revision_summary: { symbol: string } | null;
  timeframe: string | null;
  backtest_range: { start: string | null; end: string | null };
  manifest_hash: string;
  engine_version: string;
  completed_at_utc: string | null;
  materialization_status: string;
  allowed_actions: { view: boolean; compare: boolean; export: boolean; soft_delete: boolean };
}

export interface HistoryPage {
  items: HistoryRow[];
  next_cursor: string | null;
  query_fingerprint: string;
  sort: string;
}

// Read-only two-result comparison (doc 16 §8.3). The server flags per-field
// context differences; it never auto-ranks a "winner" (RH-09) and neither does
// the client. Field values may be strings or manifest sub-objects — rendered
// verbatim (objects as JSON), never interpreted.
export interface CompareEntry {
  result_id: string;
  engine_version: string;
  manifest_hash: string;
  summary: ResultSummary | null;
  key_metrics: Record<string, MetricCell | null>;
}

export interface CompareField {
  a: unknown;
  b: unknown;
  differs: boolean;
}

export interface CompareResponse {
  results: CompareEntry[];
  context: { fields: Record<string, CompareField>; context_differs: boolean };
  context_differs: boolean;
}

// Profile-hydrated Result metrics (doc 17 §9.1): the caller's resolved Arrange
// Metrics profile filters/orders the immutable persisted rows. Presentation
// only (CR-07) — a selected-but-absent metric arrives as not_computed with a
// null value, never a fabricated 0 (L4).
export interface ResultMetricsProfile {
  profile_id: string;
  scope: string;
  is_personal: boolean;
  is_locked: boolean;
  registry_version: string;
}

export interface ResultMetricsView {
  result_id: string;
  profile: ResultMetricsProfile;
  metrics: MetricCell[];
}

// ---------------------------------------------------------------------------
// Result artifact drill-down + export (doc 15 §3.2, §5, §7)
// ---------------------------------------------------------------------------

// Queryable immutable result artifacts (backend domain/backtest/artifacts.py
// ArtifactType). The drill-down is server-paginated with an opaque keyset cursor
// — the client never offsets or re-orders (doc 15 §7).
export const RESULT_ARTIFACT_KINDS = [
  "trade_ledger",
  "equity_curve",
  "signal_events",
  "diagnostics",
] as const;

export type ResultArtifactKind = (typeof RESULT_ARTIFACT_KINDS)[number];

// One Trade Ledger row is a trade ROOT (backend project_row): fills/scaling legs
// never become separate rows, so a page never double-counts (doc 15 §3.2, §14).
// Prices/PnL arrive as decimal strings (or null) — rendered verbatim, never
// re-computed; a null cell shows an em dash, never a fabricated 0 (L4).
export interface TradeLedgerRow {
  seq: number;
  entry_time: string;
  exit_time: string | null;
  direction: string;
  entry_price: string | null;
  exit_price: string | null;
  pnl: string | null;
  exit_reason: string | null;
}

export interface ResultArtifactPage<T> {
  result_id: string;
  artifact_type: string;
  items: T[];
  next_cursor: string | null;
}

// Diagnostics artifact row (backend project_row: {diagnostic_id, kind, content,
// created_at}). The single deterministic `run_diagnostics` row carries the honest
// L4 warnings (proxy fallback / unresolved indicator blocks / unsupported sizing)
// and the reproducibility note that states whether real indicator triggers or a
// breakout proxy produced this result (doc 15 §13). `content` is an open dict; the
// UI reads the keys it knows and never fabricates a missing one.
export interface DiagnosticContent {
  entry_model?: string;
  reproducibility_note?: string;
  warnings?: string[];
  [key: string]: unknown;
}

export interface DiagnosticRow {
  diagnostic_id: string;
  kind: string;
  content: DiagnosticContent;
  created_at: string | null;
}

// Engine diagnostics warning codes (domain/backtest/engine.py) → an honest,
// human-readable line. Prefix-coded warnings keep their tail so the specific
// cause shows; an unknown code (e.g. an unresolved indicator-plan reason) is
// surfaced verbatim rather than dropped or invented (L4).
const _SIZING_UNSUPPORTED_PREFIX = "position_sizing_method_unsupported:";

export function diagnosticWarningLabel(code: string): string {
  if (code === "no_bars_in_source")
    return "No bars were available in the pinned market source for this run.";
  if (code === "indicator_plan_empty_fallback_proxy")
    return "The indicator layer produced no computable trigger — this result used a breakout entry proxy, not real indicator signals.";
  if (code.startsWith(_SIZING_UNSUPPORTED_PREFIX))
    return `Position sizing method "${code.slice(_SIZING_UNSUPPORTED_PREFIX.length)}" is not modelled — the run fell back to notional sizing.`;
  return code;
}

// Export contract (backend domain/backtest/export.py). The label is V18 wording;
// the value is the authoritative wire enum. `summary` has no drill-down list but
// is exportable (doc 15 §3.2 Data Export).
export const EXPORT_TYPES = [
  { value: "trade_ledger", label: "Trade Ledger" },
  { value: "equity_curve", label: "Equity Curve" },
  { value: "signal_events", label: "Signal Events" },
  { value: "diagnostics", label: "Diagnostics" },
  { value: "summary", label: "Summary" },
] as const;

export const EXPORT_FORMATS = ["csv", "json", "parquet"] as const;

export type ExportFormatValue = (typeof EXPORT_FORMATS)[number];

// A schema-versioned DERIVATIVE of one immutable Result (doc 15 §9.1). The bytes
// live in object storage; this metadata row carries the checksum + provenance
// (source manifest hash) + row_count the UI surfaces after a request.
export interface ResultExport {
  export_id: string;
  result_id: string;
  export_type: string;
  export_format: string;
  source_manifest_hash: string;
  object_key: string;
  checksum: string;
  schema_version: string;
  row_count: number;
  status: string;
}

// Canonical server sort keys (backend domain/backtest/history.py::HistorySort)
// paired with their V18 dropdown labels. The wire enum is authoritative.
export const HISTORY_SORTS = [
  { value: "newest_current", label: "Newest" },
  { value: "net_profit_percent_desc", label: "Highest Return" },
  { value: "romad_desc", label: "Highest RoMaD" },
  { value: "max_drawdown_asc", label: "Lowest Drawdown" },
  { value: "win_rate_desc", label: "Highest Winrate" },
  { value: "total_trades_desc", label: "Most Trades" },
] as const;

export type HistorySortValue = (typeof HISTORY_SORTS)[number]["value"];

export const DEFAULT_HISTORY_SORT: HistorySortValue = "newest_current";

// Key-metric digest columns in canonical order (backend KEY_METRIC_KEYS).
export const KEY_METRIC_COLUMNS = [
  { key: "net_profit", label: "Net Profit" },
  { key: "romad", label: "ROMAD" },
  { key: "max_drawdown", label: "Max Drawdown" },
  { key: "win_rate", label: "Win Rate" },
  { key: "total_trades", label: "Trades" },
] as const;

// ---------------------------------------------------------------------------
// Formatting (presentation only — a missing metric is NEVER rendered as 0, L4)
// ---------------------------------------------------------------------------

export const EM_DASH = "—";

const AVAILABILITY_LABELS: Record<string, string> = {
  not_computed: "Not computed",
  not_available: "Not available",
  no_qualifying_trades: "No qualifying trades",
};

export function formatMetricValue(
  cell: Pick<MetricCell, "value" | "value_format" | "availability"> | null | undefined,
): string {
  if (!cell) return EM_DASH;
  if (cell.value === null) return AVAILABILITY_LABELS[cell.availability] ?? EM_DASH;
  const numeric = Number(cell.value);
  if (!Number.isFinite(numeric)) return cell.value;
  switch (cell.value_format) {
    case "signed_percent":
      return `${numeric > 0 ? "+" : ""}${numeric.toFixed(2)}%`;
    case "percent":
      return `${numeric.toFixed(2)}%`;
    case "decimal2":
      return numeric.toFixed(2);
    case "integer":
      return String(Math.trunc(numeric));
    default:
      return cell.value;
  }
}

// Deterministic, locale-free "YYYY-MM-DD HH:MM UTC" for wire ISO timestamps.
export function formatUtc(iso: string | null | undefined): string {
  if (!iso) return EM_DASH;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return `${date.toISOString().slice(0, 16).replace("T", " ")} UTC`;
}

// ---------------------------------------------------------------------------
// Query hooks
// ---------------------------------------------------------------------------

const RUN_POLL_INTERVAL_MS = 5_000;
const RESULT_STALE_TIME_MS = 5 * 60_000;

// Composition context the RUN page admits against. Lives here (not lib/hooks.ts)
// because the backtest RUN flow is its only consumer today; the Stage 3 real
// Mainboard page can lift it app-level when it lands.
export function useDefaultMainboard() {
  return useQuery({
    queryKey: ["mainboard", "default"],
    queryFn: () => api.get<DefaultMainboard>("/mainboards/default"),
  });
}

export function useBacktestRun(runId: string | null) {
  return useQuery({
    queryKey: ["backtests", "run", runId],
    queryFn: () => api.get<BacktestRun>(`/backtest-runs/${encodeURIComponent(runId ?? "")}`),
    enabled: runId !== null,
    // SSE is the primary freshness signal; this poll is the loss-tolerant
    // fallback and stops once the durable run row is terminal.
    refetchInterval: (query) => {
      const state = query.state.data?.state;
      return state !== undefined && TERMINAL_RUN_STATES.has(state)
        ? false
        : RUN_POLL_INTERVAL_MS;
    },
  });
}

export function useBacktestResult(resultId: string | null) {
  return useQuery({
    queryKey: ["backtests", "result", resultId],
    queryFn: () => api.get<BacktestResultDetail>(`/backtest-results/${encodeURIComponent(resultId ?? "")}`),
    enabled: resultId !== null,
    // A Result is immutable (doc 15 §9.4); the ["backtests"] invalidation sweep
    // may still refetch it after run events, which is harmless.
    staleTime: RESULT_STALE_TIME_MS,
  });
}

export function useResultsHistory(sort: HistorySortValue, cursor: string | null) {
  return useQuery({
    queryKey: ["backtests", "history", sort, cursor],
    queryFn: () => {
      const params = new URLSearchParams({ sort });
      if (cursor !== null) params.set("cursor", cursor);
      return api.get<HistoryPage>(`/backtest-results?${params.toString()}`);
    },
    // Keep the current table mounted while a sort/cursor flip is in flight.
    placeholderData: (previous) => previous,
  });
}

// Profile-hydrated metrics live under the ["metric-profile"] prefix, NOT
// ["backtests"]: the Result rows are immutable — the caller's resolved profile
// is the only mutable input, so an Arrange Metrics Apply (which invalidates
// ["metric-profile"]) must sweep this view. Cross-tab profile changes ride the
// SSE resource.changed full refresh (no dedicated metric-profile event).
export function useResultMetrics(resultId: string | null) {
  return useQuery({
    queryKey: ["metric-profile", "result-metrics", resultId],
    queryFn: () =>
      api.get<ResultMetricsView>(
        `/backtest-results/${encodeURIComponent(resultId ?? "")}/metrics`,
      ),
    enabled: resultId !== null,
  });
}

// One keyset page of a result's immutable artifact (doc 15 §7). Lives under the
// ["backtests"] prefix so the SSE sweep covers it; a Result is immutable, so the
// page is long-lived (staleTime) and `placeholderData` keeps the current page
// mounted across a cursor flip. The opaque cursor is server-issued — the client
// only threads it back, never forges an offset.
export function useResultArtifact<T>(
  resultId: string | null,
  kind: ResultArtifactKind,
  cursor: string | null,
) {
  return useQuery({
    queryKey: ["backtests", "artifact", resultId, kind, cursor],
    queryFn: () => {
      const params = new URLSearchParams();
      if (cursor !== null) params.set("cursor", cursor);
      const query = params.toString();
      return api.get<ResultArtifactPage<T>>(
        `/backtest-results/${encodeURIComponent(resultId ?? "")}/artifacts/${kind}${
          query ? `?${query}` : ""
        }`,
      );
    },
    enabled: resultId !== null,
    staleTime: RESULT_STALE_TIME_MS,
    placeholderData: (previous) => previous,
  });
}

// Compare is a READ over two immutable results — POST is only the transport
// for the id pair (doc 16 §8.3). Selection order is preserved: columns A/B
// mirror the order the user picked, and the client never re-ranks.
export function useCompareResults(pair: [string, string] | null) {
  return useQuery({
    queryKey: ["backtests", "compare", pair?.[0] ?? null, pair?.[1] ?? null],
    queryFn: () =>
      api.post<CompareResponse>("/backtest-results/compare", { result_ids: pair }),
    enabled: pair !== null,
    // Both inputs are immutable results; the ["backtests"] SSE sweep may still
    // refetch after run events, which is harmless.
    staleTime: RESULT_STALE_TIME_MS,
  });
}

// ---------------------------------------------------------------------------
// Mutations (202 admissions — the client never waits on the engine, doc 15 §8.2)
// ---------------------------------------------------------------------------

export function useRequestBacktestRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (compositionId: string) =>
      // 202 admission — a fresh Idempotency-Key per attempt lets the server dedup
      // a network retry to the same run instead of admitting a duplicate one
      // (the route reads the header, INF-04/INF-05).
      apiRequest<BacktestRunAdmission>(
        `/mainboard-compositions/${encodeURIComponent(compositionId)}/backtest-runs`,
        { method: "POST", headers: { "Idempotency-Key": crypto.randomUUID() }, body: {} },
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["backtests"] });
    },
  });
}

export function useRetryBacktestRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (runId: string) =>
      // A retry is deliberately a distinct decision, but a fresh Idempotency-Key
      // still collapses an accidental double-submit / network retry to one
      // admission (the route reads the header).
      apiRequest<BacktestRunAdmission>(`/backtest-runs/${encodeURIComponent(runId)}/retries`, {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["backtests"] });
    },
  });
}

// Doc-16 soft-delete affordance (reuses the 5a command server-side). The
// history row carries no row_version, so no OCC token is sent — the server
// accepts an optional expected_row_version and the command is idempotent and
// owner/Admin-gated regardless. The history list filters deleted rows, so the
// ["backtests"] invalidation makes the row disappear.
export function useSoftDeleteResult() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (resultId: string) =>
      // The command is idempotent server-side, but a fresh Idempotency-Key still
      // lets the server dedup a retry to the same delete (the route reads it).
      apiRequest<{ result_id: string; deletion_state: string }>(
        `/backtest-results/${encodeURIComponent(resultId)}/delete`,
        { method: "POST", headers: { "Idempotency-Key": crypto.randomUUID() }, body: {} },
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["backtests"] });
    },
  });
}

// Materialize a schema-versioned export from an immutable Result (doc 15 §5, §7).
// The export is a derivative — it never mutates the Result or its artifact_counts
// — so only ["audit"] is swept (the command emits export_requested/completed). A
// fresh Idempotency-Key per attempt keeps a retry a distinct decision; the server
// dedups an in-flight retry of the SAME key to the same export (doc 15 §11).
export function useCreateResultExport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      resultId: string;
      exportType: string;
      exportFormat: ExportFormatValue;
    }) =>
      apiRequest<ResultExport>(
        `/backtest-results/${encodeURIComponent(input.resultId)}/exports`,
        {
          method: "POST",
          body: { export_type: input.exportType, export_format: input.exportFormat },
          headers: { "Idempotency-Key": crypto.randomUUID() },
        },
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}
