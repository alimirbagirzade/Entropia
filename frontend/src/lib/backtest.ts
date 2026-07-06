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

import { api } from "./apiClient";

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

export interface DefaultMainboard {
  workspace_id: string;
  workspace_kind: string;
  composition_hash: string | null;
  row_version: number;
  items: MainboardItem[];
  ready_summary: { state: string; report_id: string | null };
  latest_result_summary: unknown;
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
  headline: string | null;
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
  artifact_counts: Record<string, number>;
}

export type MetricCell = Omit<MetricValue, "formula_version">;

export interface HistoryRow {
  result_id: string;
  display_title: string;
  composition_context: { composition_id: string; composition_fingerprint: string };
  key_metrics: Record<string, MetricCell | null>;
  market_data_revision_summary: unknown;
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
      api.post<BacktestRunAdmission>(
        `/mainboard-compositions/${encodeURIComponent(compositionId)}/backtest-runs`,
        {},
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
      api.post<BacktestRunAdmission>(`/backtest-runs/${encodeURIComponent(runId)}/retries`),
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
      api.post<{ result_id: string; deletion_state: string }>(
        `/backtest-results/${encodeURIComponent(resultId)}/delete`,
        {},
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["backtests"] });
    },
  });
}
