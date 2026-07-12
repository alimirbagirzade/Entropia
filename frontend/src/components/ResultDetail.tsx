import { useState } from "react";

import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { ApiError } from "@/lib/apiClient";
import {
  EM_DASH,
  EXPORT_FORMATS,
  EXPORT_TYPES,
  formatMetricValue,
  formatUtc,
  useCreateResultExport,
  useResultArtifact,
  useResultMetrics,
  type BacktestResultDetail,
  type ExportFormatValue,
  type TradeLedgerRow,
} from "@/lib/backtest";

const hashStyle = { fontFamily: "monospace", fontSize: 12, wordBreak: "break-all" } as const;

// Mutation failures surface the backend canonical envelope verbatim — the client
// never invents result-domain messages (mirrors ResultsHistory/ErrorState).
function mutationErrorText(error: unknown): string {
  if (error instanceof ApiError) return `${error.code}: ${error.message}`;
  return error instanceof Error ? error.message : "Request failed.";
}

// Immutable Result detail (doc 15 §9.4): hydrated ONLY from the result_id
// projection — never from the current Mainboard form. Values render verbatim;
// a non-computed metric shows its availability, never a fabricated 0 (L4).
// The Metrics section binds the profile-hydrated view (doc 17 §9.1): the
// resolved Arrange Metrics profile filters/orders the persisted rows. While
// that view loads — or if it fails — the raw persisted rows keep rendering.
export function ResultDetail({ result }: { result: BacktestResultDetail }) {
  const artifactEntries = Object.entries(result.artifact_counts);
  const hydrated = useResultMetrics(result.result_id);
  const profile = hydrated.data?.profile ?? null;
  const metricRows = hydrated.data?.metrics ?? result.metrics;
  return (
    <section className="card" aria-labelledby="result-detail-h" style={{ marginTop: 18 }}>
      <h3 id="result-detail-h" style={{ marginTop: 0 }}>
        Backtest Result <code>{result.result_id}</code>
      </h3>

      {result.summary ? (
        <dl className="kv">
          <dt>Symbol</dt>
          <dd>{result.summary.symbol ?? EM_DASH}</dd>
          <dt>Timeframe</dt>
          <dd>{result.summary.timeframe ?? EM_DASH}</dd>
          <dt>Period</dt>
          <dd>
            {result.summary.period_start ?? EM_DASH} → {result.summary.period_end ?? EM_DASH}
          </dd>
          <dt>Total trades</dt>
          <dd>{result.summary.total_trades ?? EM_DASH}</dd>
          {result.summary.headline ? (
            <>
              <dt>Headline</dt>
              <dd>{result.summary.headline}</dd>
            </>
          ) : null}
        </dl>
      ) : (
        <p className="page-sub">No summary artifact was persisted for this result.</p>
      )}

      <h4>Metrics</h4>
      {profile ? (
        <p className="page-sub" style={{ marginTop: 0 }}>
          Profile view · {profile.is_personal ? "personal profile" : "system default"}
          {profile.is_locked ? " · locked" : ""} · registry {profile.registry_version}
        </p>
      ) : hydrated.isError ? (
        <p className="page-sub" style={{ marginTop: 0 }}>
          Profile view unavailable — showing all persisted metrics.
        </p>
      ) : null}
      {metricRows.length === 0 ? (
        <p className="page-sub">No metric values were persisted for this result.</p>
      ) : (
        <table className="metrics-table">
          <thead>
            <tr>
              <th scope="col">Metric</th>
              <th scope="col">Value</th>
              <th scope="col">Availability</th>
            </tr>
          </thead>
          <tbody>
            {metricRows.map((metric) => (
              <tr key={metric.key}>
                <td>{metric.label}</td>
                <td>{formatMetricValue(metric)}</td>
                <td>{metric.availability}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <ChartsPlaceholder />
      <TradeListSection resultId={result.result_id} />
      <ExportSection resultId={result.result_id} />

      <h4>Manifest</h4>
      <dl className="kv">
        <dt>Engine version</dt>
        <dd>{result.engine_version}</dd>
        <dt>Manifest hash</dt>
        <dd style={hashStyle}>{result.manifest_hash}</dd>
        <dt>Composition fingerprint</dt>
        <dd style={hashStyle}>{result.composition_fingerprint}</dd>
        {result.manifest ? (
          <>
            <dt>Execution key</dt>
            <dd style={hashStyle}>{result.manifest.execution_key}</dd>
            <dt>Pinned items</dt>
            <dd>{result.manifest.pinned_item_count}</dd>
          </>
        ) : null}
      </dl>

      {artifactEntries.length > 0 ? (
        <>
          <h4>Artifacts</h4>
          <dl className="kv">
            {artifactEntries.map(([kind, count]) => (
              <div key={kind} style={{ display: "contents" }}>
                <dt>{kind}</dt>
                <dd>{count}</dd>
              </div>
            ))}
          </dl>
        </>
      ) : null}
    </section>
  );
}

const placeholderStyle = {
  border: "1px dashed var(--border)",
  borderRadius: 6,
  padding: "18px 14px",
  color: "var(--text-dim)",
  fontSize: 13,
} as const;

// V18 chart placeholders (doc 15 §3.2, §13): the renderer is a deliberate Future
// boundary — the page shows an explicit placeholder, NEVER a fabricated chart or
// price series. The equity_curve / trade_ledger exports carry the real numbers.
function ChartsPlaceholder() {
  return (
    <>
      <h4>Charts</h4>
      <div style={{ display: "grid", gap: 10 }}>
        <div style={placeholderStyle}>
          Price chart with entry / exit / stop / scaling markers is not rendered in V1
          (no chart renderer yet). No fake chart or price data is shown.
        </div>
        <div style={placeholderStyle}>
          Equity curve, drawdown and exposure are not rendered in V1. Download the
          <code> equity_curve </code>
          export below to inspect the real series.
        </div>
      </div>
    </>
  );
}

// Cursor-paginated Trade Ledger drill-down (doc 15 §3.2, §7). One row is a trade
// ROOT; the server orders and pages the immutable rows and the client only
// threads the opaque cursor back. Columns are the §3.2 set exactly.
function TradeListSection({ resultId }: { resultId: string }) {
  // Server cursors visited so far; the last entry is the current page and an
  // empty stack is the first page (mirrors ResultsHistory).
  const [cursorStack, setCursorStack] = useState<string[]>([]);
  const cursor = cursorStack.length > 0 ? cursorStack[cursorStack.length - 1] : null;
  const page = useResultArtifact<TradeLedgerRow>(resultId, "trade_ledger", cursor);
  const rows = page.data?.items ?? [];
  const nextCursor = page.data?.next_cursor ?? null;

  return (
    <>
      <h4>Trade List</h4>
      {page.isLoading ? (
        <Loading label="Loading trades…" />
      ) : page.isError ? (
        <ErrorState error={page.error} onRetry={() => void page.refetch()} />
      ) : rows.length === 0 ? (
        <p className="page-sub">No trades were recorded for this result.</p>
      ) : (
        <>
          <TradeTable rows={rows} />
          <div style={{ display: "flex", gap: 10, marginTop: 10 }}>
            <button
              type="button"
              className="btn btn-ghost"
              disabled={cursorStack.length === 0 || page.isFetching}
              onClick={() => setCursorStack((stack) => stack.slice(0, -1))}
            >
              ← Previous
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              disabled={nextCursor === null || page.isFetching}
              onClick={() => {
                if (nextCursor !== null) setCursorStack((stack) => [...stack, nextCursor]);
              }}
            >
              Next →
            </button>
          </div>
        </>
      )}
    </>
  );
}

function TradeTable({ rows }: { rows: TradeLedgerRow[] }) {
  return (
    <div style={{ overflowX: "auto" }}>
      <table className="metrics-table">
        <thead>
          <tr>
            <th scope="col">Entry Time</th>
            <th scope="col">Exit Time</th>
            <th scope="col">Direction</th>
            <th scope="col">Entry Price</th>
            <th scope="col">Exit Price</th>
            <th scope="col">PnL</th>
            <th scope="col">Exit Reason</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.seq}>
              <td>{formatUtc(row.entry_time)}</td>
              <td>{formatUtc(row.exit_time)}</td>
              <td>{row.direction || EM_DASH}</td>
              <td>{row.entry_price ?? EM_DASH}</td>
              <td>{row.exit_price ?? EM_DASH}</td>
              <td>{row.pnl ?? EM_DASH}</td>
              <td>{row.exit_reason ?? EM_DASH}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Export request buttons (doc 15 §5, §7). Each ExportType materializes a
// schema-versioned derivative in the chosen format; the request is a mutation
// (fresh Idempotency-Key). The browser rows are never the export source (§8.5).
function ExportSection({ resultId }: { resultId: string }) {
  const [format, setFormat] = useState<ExportFormatValue>("csv");
  const createExport = useCreateResultExport();
  const receipt = createExport.data;

  return (
    <>
      <h4>Data Export</h4>
      <p className="page-sub" style={{ marginTop: 0 }}>
        An export is a schema-versioned derivative of the immutable Result — the browser
        table is never the source (doc 15 §8.5).
      </p>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
        <label htmlFor="export-format" style={{ fontSize: 13, color: "var(--text-dim)" }}>
          Format
        </label>
        <select
          id="export-format"
          className="auth-input"
          style={{ width: "auto" }}
          value={format}
          onChange={(event) => setFormat(event.target.value as ExportFormatValue)}
        >
          {EXPORT_FORMATS.map((value) => (
            <option key={value} value={value}>
              {value.toUpperCase()}
            </option>
          ))}
        </select>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        {EXPORT_TYPES.map((type) => (
          <button
            key={type.value}
            type="button"
            className="btn"
            disabled={createExport.isPending}
            onClick={() =>
              createExport.mutate({ resultId, exportType: type.value, exportFormat: format })
            }
          >
            {type.label}
          </button>
        ))}
      </div>

      {createExport.isError ? (
        <p role="alert" style={{ color: "var(--down)", marginTop: 10 }}>
          {mutationErrorText(createExport.error)}
        </p>
      ) : null}

      {receipt ? (
        <div style={{ marginTop: 10 }}>
          <p role="status" className="page-sub" style={{ marginTop: 0 }}>
            Export requested. The file will be available when the export job completes.
          </p>
          <dl className="kv">
            <dt>Export</dt>
            <dd>
              {`${receipt.export_type} · ${receipt.export_format} · ${receipt.row_count} rows · ${receipt.status}`}
            </dd>
            <dt>Checksum</dt>
            <dd style={hashStyle}>{receipt.checksum}</dd>
          </dl>
        </div>
      ) : null}
    </>
  );
}
