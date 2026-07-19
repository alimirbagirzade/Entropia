import { useState } from "react";

import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { ApiError } from "@/lib/apiClient";
import {
  diagnosticWarningLabel,
  EM_DASH,
  EXPORT_FORMATS,
  EXPORT_TYPES,
  formatMetricValue,
  formatUtc,
  useCreateResultExport,
  useResultArtifact,
  useResultMetrics,
  type BacktestResultDetail,
  CONTRIBUTION_METRIC_ROWS,
  type ContributionMarginal,
  type DiagnosticContent,
  type DiagnosticRow,
  type ExportFormatValue,
  type PerItemBreakdown,
  type ManifestItemRef,
  type ResultManifestExcerpt,
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
              <dd>
                <dl className="kv kv-compact" style={{ margin: 0 }}>
                  {Object.entries(result.summary.headline).map(([key, value]) => (
                    <div key={key} style={{ display: "flex", gap: 8 }}>
                      <dt style={{ margin: 0, minWidth: 160 }}>{key}</dt>
                      <dd style={{ margin: 0 }}>
                        {value === null || value === undefined ? EM_DASH : String(value)}
                      </dd>
                    </div>
                  ))}
                </dl>
              </dd>
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
      <PerItemBreakdownSection resultId={result.result_id} />
      <ContributionSection resultId={result.result_id} />
      <DiagnosticsSection resultId={result.result_id} />
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

      <ManifestExcerptSection excerpt={result.manifest_excerpt} />

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

const NOT_PINNED = "Not separately pinned";

function refLabel(ref: ManifestItemRef): string {
  return `${ref.root_id ?? EM_DASH} @ ${ref.revision_id ?? EM_DASH}`;
}

// Immutable ResultManifestExcerpt (doc 16 §8.2/§9.4): pinned strategy/external
// refs + allocation/execution context + artifact availability, read ONLY from the
// result manifest — never re-resolved from the current Mainboard (§15). Fields the
// V1 manifest does not separately pin (package/market-data/research-data) render an
// honest "Not separately pinned", never a fabricated ref (doc 16 §4).
function ManifestExcerptSection({ excerpt }: { excerpt: ResultManifestExcerpt }) {
  const strategyRefs = excerpt.strategy_revision_refs;
  const externalRefs = excerpt.external_work_refs;
  return (
    <>
      <h4>Manifest excerpt</h4>
      <dl className="kv">
        <dt>Composition snapshot</dt>
        <dd style={hashStyle}>{excerpt.composition_snapshot_id ?? EM_DASH}</dd>
        <dt>Engine contract</dt>
        <dd>{excerpt.engine_contract_version ?? EM_DASH}</dd>
        <dt>Strategy revisions</dt>
        <dd>
          {strategyRefs.length === 0 ? (
            NOT_PINNED
          ) : (
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {strategyRefs.map((ref) => (
                <li key={ref.item_id ?? refLabel(ref)} style={hashStyle}>
                  {refLabel(ref)}
                </li>
              ))}
            </ul>
          )}
        </dd>
        {externalRefs.length > 0 ? (
          <>
            <dt>External work</dt>
            <dd>
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {externalRefs.map((ref) => (
                  <li key={ref.item_id ?? refLabel(ref)} style={hashStyle}>
                    {`${ref.item_kind ?? EM_DASH} · ${refLabel(ref)}`}
                  </li>
                ))}
              </ul>
            </dd>
          </>
        ) : null}
        <dt>Allocation plan revision</dt>
        <dd style={hashStyle}>
          {excerpt.portfolio_allocation_plan_revision_id ?? NOT_PINNED}
        </dd>
        <dt>Market Data revision</dt>
        <dd>{excerpt.market_data_revision ?? NOT_PINNED}</dd>
        <dt>Artifacts available</dt>
        <dd>{excerpt.artifact_availability.any_available ? "Yes" : "No"}</dd>
      </dl>
      <p className="page-sub" style={{ marginTop: 0 }}>
        Read only from the immutable result manifest — package, Market Data and
        Research Data revisions are pinned inside the strategy config, surfaced
        transitively via the strategy revisions above (doc 16 §4, §8.2).
      </p>
    </>
  );
}

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

const warnBoxStyle = {
  border: "1px solid var(--warn)",
  borderRadius: 6,
  padding: "10px 12px",
  color: "var(--warn)",
  fontSize: 13,
} as const;

// Informational engine counters surfaced verbatim (real values, never a
// fabricated fallback). warnings / reproducibility_note / entry_model are handled
// separately above, so they are not repeated here.
const DIAGNOSTIC_DISPLAY_FIELDS: { key: string; label: string }[] = [
  { key: "engine_kind", label: "Engine kind" },
  { key: "bars_processed", label: "Bars processed" },
  { key: "indicator_blocks", label: "Indicator blocks" },
  { key: "condition_blocks", label: "Condition blocks" },
  { key: "decision_trace_count", label: "Decision trace events" },
];

// Per-item breakdown (v17, engine.py combine_item_runs → diagnostics.composition).
// A multi-item RUN simulates each enabled Strategy SEPARATELY and folds the
// contributions into one portfolio Result; this section attributes that composite back
// to its parts — each executing strategy's OWN isolated PnL / drawdown / trade count (on
// its own capital basis) plus its OWN equity curve. Non-executing objects (Trading
// Signal / Trade Log) are recorded but run no bar-replay (the honest V1 boundary), so
// they show a note and no curve. Absent for a lone-Strategy result (no composition block
// is emitted — the byte-identical no-compose path).
const perItemBoxStyle = {
  border: "1px solid var(--border)",
  borderRadius: "var(--radius)",
  padding: 12,
  marginTop: 10,
} as const;
const equityScrollStyle = {
  maxHeight: 220,
  overflowY: "auto",
  marginTop: 8,
} as const;

function perItemNum(value: string | null): string {
  return value ?? EM_DASH;
}

function PerItemBreakdownSection({ resultId }: { resultId: string }) {
  const page = useResultArtifact<DiagnosticRow>(resultId, "diagnostics", null);
  const composition = page.data?.items[0]?.content?.composition ?? null;
  if (page.isLoading || page.isError || composition === null) {
    // No standalone loading/error UI: the Diagnostics section below owns that surface for
    // the same artifact. A single-Strategy result legitimately has no composition block.
    return null;
  }
  const items = composition.items;
  return (
    <>
      <h4>Per-item breakdown</h4>
      <p className="page-sub" style={{ marginTop: 0 }}>
        {`${composition.strategy_count} executing ${
          composition.strategy_count === 1 ? "strategy" : "strategies"
        } · ${composition.participating_item_count} participating item${
          composition.participating_item_count === 1 ? "" : "s"
        }. Each executing strategy is simulated separately over its own bars; the figures below are its ISOLATED performance (own capital basis), not its portfolio-rebased slice.`}
      </p>
      {items.map((item) => (
        <PerItemCard key={item.item_id} item={item} />
      ))}
    </>
  );
}

function PerItemCard({ item }: { item: PerItemBreakdown }) {
  return (
    <div style={perItemBoxStyle}>
      <strong>
        {item.item_kind} <code style={hashStyle}>{item.item_id}</code>
      </strong>
      {!item.executed ? (
        <p className="page-sub" style={{ margin: "6px 0 0" }}>
          Recorded for traceability but not simulated — a {item.item_kind} affects a run only
          as a Strategy data input (V1 boundary), so it has no standalone equity curve.
        </p>
      ) : (
        <>
          <dl className="kv" style={{ marginTop: 8 }}>
            <dt>Symbol</dt>
            <dd>{item.symbol ?? EM_DASH}</dd>
            <dt>Initial capital</dt>
            <dd>{perItemNum(item.initial_capital)}</dd>
            <dt>Final equity</dt>
            <dd>{perItemNum(item.final_equity)}</dd>
            <dt>Net profit</dt>
            <dd>
              {perItemNum(item.net_profit)}
              {item.net_profit_pct !== null ? ` (${item.net_profit_pct}%)` : ""}
            </dd>
            <dt>Max drawdown</dt>
            <dd>
              {perItemNum(item.max_drawdown)}
              {item.max_drawdown_pct !== null ? ` (${item.max_drawdown_pct}%)` : ""}
            </dd>
            <dt>Trades</dt>
            <dd>
              {item.total_trades} ({item.winning_trades} winning)
              {item.trade_seq_range
                ? ` · ledger seq ${item.trade_seq_range[0]}–${item.trade_seq_range[1]}`
                : ""}
            </dd>
          </dl>
          {item.equity_curve.length > 0 ? (
            <div style={equityScrollStyle}>
              <table className="metrics-table">
                <thead>
                  <tr>
                    <th scope="col">Seq</th>
                    <th scope="col">Time</th>
                    <th scope="col">Equity</th>
                    <th scope="col">Drawdown</th>
                  </tr>
                </thead>
                <tbody>
                  {item.equity_curve.map((point) => (
                    <tr key={point.seq}>
                      <td>{point.seq}</td>
                      <td>{point.timestamp ? formatUtc(point.timestamp) : EM_DASH}</td>
                      <td>{point.equity}</td>
                      <td>{point.drawdown}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="page-sub" style={{ margin: "6px 0 0" }}>
              No equity points (the strategy opened no position over its bars).
            </p>
          )}
        </>
      )}
    </div>
  );
}

// Contribution (v17, engine.py _contribution_block — video 3:35 "what does an item add
// to the universe"). Everything below is computed ONCE server-side at run time and
// persisted into the immutable Result; this section renders it VERBATIM — the client
// performs no correlation, no fold, no arithmetic. Present only when the composition
// has 2+ executing strategies (the server omits the block otherwise).
function contributionValue(value: string | number | null): string {
  if (value === null) return EM_DASH;
  return String(value);
}

function ContributionSection({ resultId }: { resultId: string }) {
  const page = useResultArtifact<DiagnosticRow>(resultId, "diagnostics", null);
  const composition = page.data?.items[0]?.content?.composition ?? null;
  const contribution = composition?.contribution ?? null;
  if (page.isLoading || page.isError || composition === null || contribution === null) {
    // Loading/error surfaces belong to the Diagnostics section (same artifact); a
    // composition below 2 executing strategies legitimately has no contribution block.
    return null;
  }
  const corr = contribution.correlation;
  const div = contribution.diversification;
  return (
    <>
      <h4>Contribution</h4>
      <p className="page-sub" style={{ marginTop: 0 }}>
        What each item adds to the composition — computed server-side at run time from
        the per-item runs ({composition.capital_allocation === "shared_pool"
          ? "shared-pool capital"
          : "independent capital"}); rendered verbatim.
      </p>

      <div style={perItemBoxStyle}>
        <strong>Realized-PnL correlation</strong>
        <p className="page-sub" style={{ margin: "6px 0 0" }}>
          {contribution.method.correlation}
        </p>
        <div style={{ overflowX: "auto", marginTop: 8 }}>
          <table className="metrics-table">
            <thead>
              <tr>
                <th scope="col"></th>
                {corr.item_ids.map((id) => (
                  <th key={id} scope="col">
                    <code style={hashStyle}>{id}</code>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {corr.matrix.map((row, i) => (
                <tr key={corr.item_ids[i]}>
                  <th scope="row">
                    <code style={hashStyle}>{corr.item_ids[i]}</code>
                  </th>
                  {row.map((cell, j) => (
                    <td key={corr.item_ids[j]}>{cell ?? EM_DASH}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <dl className="kv" style={{ marginTop: 8 }}>
          <dt>Aligned points</dt>
          <dd>{corr.aligned_point_count}</dd>
          <dt>Average pairwise correlation</dt>
          <dd>{corr.average_pairwise ?? EM_DASH}</dd>
        </dl>
      </div>

      <div style={perItemBoxStyle}>
        <strong>Diversification</strong>
        <dl className="kv" style={{ marginTop: 8 }}>
          <dt>Sum of item max drawdowns</dt>
          <dd>{div.sum_of_item_max_drawdowns}</dd>
          <dt>Portfolio max drawdown</dt>
          <dd>{div.portfolio_max_drawdown}</dd>
          <dt>Drawdown reduction</dt>
          <dd>{div.drawdown_reduction}</dd>
          <dt>Average pairwise correlation</dt>
          <dd>{div.average_pairwise_correlation ?? EM_DASH}</dd>
        </dl>
      </div>

      <div style={perItemBoxStyle}>
        <strong>Marginal contribution</strong>
        <p className="page-sub" style={{ margin: "6px 0 0" }}>
          {contribution.method.marginal}
        </p>
        {contribution.marginal.map((entry) => (
          <MarginalCard key={entry.item_id} entry={entry} />
        ))}
      </div>
    </>
  );
}

function MarginalCard({ entry }: { entry: ContributionMarginal }) {
  return (
    <div style={perItemBoxStyle}>
      <strong>
        Without <code style={hashStyle}>{entry.item_id}</code>
      </strong>
      <p className="page-sub" style={{ margin: "6px 0 0" }}>
        {`The composition without this item would have started from ${entry.without_item.initial_capital} and ended at ${entry.without_item.final_equity}. Delta = full composition minus without-item.`}
      </p>
      <div style={{ overflowX: "auto", marginTop: 8 }}>
        <table className="metrics-table">
          <thead>
            <tr>
              <th scope="col">Metric</th>
              <th scope="col">Without this item</th>
              <th scope="col">Delta (this item&apos;s contribution)</th>
            </tr>
          </thead>
          <tbody>
            {CONTRIBUTION_METRIC_ROWS.map(({ key, label }) => (
              <tr key={key}>
                <td>{label}</td>
                <td>{contributionValue(entry.without_item[key])}</td>
                <td>{contributionValue(entry.delta[key])}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// Deterministic run diagnostics (doc 15 §13). The single `run_diagnostics`
// artifact row states — via the reproducibility note and the honest L4 warnings —
// how this result was produced: whether real indicator triggers or a breakout
// proxy fired, whether an indicator block went unresolved, or whether an
// unsupported sizing method fell back to notional. Diagnostics is the
// deterministic engine artifact, NOT a numeric truth source that overrides the
// metrics (§13). AI Review below is an explicit V1 placeholder — never fabricated.
function DiagnosticsSection({ resultId }: { resultId: string }) {
  const page = useResultArtifact<DiagnosticRow>(resultId, "diagnostics", null);
  const content = page.data?.items[0]?.content ?? null;
  const warnings = content?.warnings ?? [];

  return (
    <>
      <h4>Diagnostics</h4>
      {page.isLoading ? (
        <Loading label="Loading diagnostics…" />
      ) : page.isError ? (
        <ErrorState error={page.error} onRetry={() => void page.refetch()} />
      ) : content === null ? (
        <p className="page-sub">No diagnostics artifact was persisted for this result.</p>
      ) : (
        <>
          {content.reproducibility_note ? (
            <p className="page-sub" style={{ marginTop: 0 }}>
              {content.reproducibility_note}
            </p>
          ) : null}
          {warnings.length > 0 ? (
            <div role="alert" style={warnBoxStyle}>
              <strong>
                {`${warnings.length} diagnostic warning${warnings.length === 1 ? "" : "s"}`}
              </strong>
              <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>
                {warnings.map((code) => (
                  <li key={code}>{diagnosticWarningLabel(code)}</li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="page-sub">
              No diagnostic warnings — the run produced no honesty flags.
            </p>
          )}
          <DiagnosticCounters content={content} />
        </>
      )}

      <h4>AI Review</h4>
      <div style={placeholderStyle}>
        AI Review is not generated in V1 (no analysis capability enabled). The
        diagnostics above are the deterministic engine artifact; no AI verdict or
        fabricated diagnosis is produced (doc 15 §13).
      </div>
    </>
  );
}

function DiagnosticCounters({ content }: { content: DiagnosticContent }) {
  const rows = DIAGNOSTIC_DISPLAY_FIELDS.map((field) => ({
    ...field,
    value: content[field.key],
  })).filter((field) => field.value !== undefined && field.value !== null);
  if (rows.length === 0) return null;
  return (
    <dl className="kv" style={{ marginTop: 10 }}>
      {rows.map((field) => (
        <div key={field.key} style={{ display: "contents" }}>
          <dt>{field.label}</dt>
          <dd>{String(field.value)}</dd>
        </div>
      ))}
    </dl>
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
