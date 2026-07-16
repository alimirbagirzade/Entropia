import { useState } from "react";
import { Link } from "react-router-dom";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { ApiError } from "@/lib/apiClient";
import {
  DEFAULT_HISTORY_SORT,
  EM_DASH,
  HISTORY_SORTS,
  KEY_METRIC_COLUMNS,
  formatMetricValue,
  formatUtc,
  useBacktestResult,
  useCompareResults,
  useResultsHistory,
  useSoftDeleteResult,
  type HistoryRow,
  type HistorySortValue,
  type ManifestItemRef,
} from "@/lib/backtest";

const COMPARE_CAPACITY = 2;

// Mutation failures surface the backend canonical envelope verbatim — the
// client never invents history-domain messages (mirrors BacktestRun/ErrorState).
function mutationErrorText(error: unknown): string {
  if (error instanceof ApiError) return `${error.code}: ${error.message}`;
  return error instanceof Error ? error.message : "Request failed.";
}

// A compare-context value is a string or a manifest sub-object — rendered
// verbatim (objects as JSON), never interpreted or ranked (doc 16 §8.3).
function contextText(value: unknown): string {
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

// Results History (Stage 5b, doc 16): the authoritative server-side index over
// immutable results — sort and keyset cursor come from the backend; the client
// never re-orders rows. "View" deep-links into the RUN page's ?result= mode.
export function ResultsHistory() {
  const [sort, setSort] = useState<HistorySortValue>(DEFAULT_HISTORY_SORT);
  // Server cursors visited so far; the last entry is the current page and an
  // empty stack is the first page. A sort change resets to the first page.
  const [cursorStack, setCursorStack] = useState<string[]>([]);
  // Compare selection in pick order (columns A/B mirror it), capped at two.
  const [selected, setSelected] = useState<string[]>([]);
  const [comparePair, setComparePair] = useState<[string, string] | null>(null);
  // Two-step delete confirm: first click arms the row, second click commits.
  const [armedDelete, setArmedDelete] = useState<string | null>(null);
  // v18 expandable cards: which rows have their metrics panel open.
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set());
  const toggleExpanded = (resultId: string) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(resultId)) next.delete(resultId);
      else next.add(resultId);
      return next;
    });
  const cursor = cursorStack.length > 0 ? cursorStack[cursorStack.length - 1] : null;
  const history = useResultsHistory(sort, cursor);
  const softDelete = useSoftDeleteResult();

  const rows = history.data?.items ?? [];
  const nextCursor = history.data?.next_cursor ?? null;

  const toggleSelect = (resultId: string) => {
    setSelected((ids) =>
      ids.includes(resultId)
        ? ids.filter((id) => id !== resultId)
        : ids.length < COMPARE_CAPACITY
          ? [...ids, resultId]
          : ids,
    );
  };

  const deleteRow = (resultId: string) => {
    if (armedDelete !== resultId) {
      setArmedDelete(resultId);
      return;
    }
    softDelete.mutate(resultId, {
      onSuccess: () => {
        setArmedDelete(null);
        setSelected((ids) => ids.filter((id) => id !== resultId));
        setComparePair((pair) => (pair !== null && pair.includes(resultId) ? null : pair));
      },
    });
  };

  return (
    <>
      <h1 className="page-title">Results History</h1>
      <p className="page-sub">Immutable backtest results · server-side sort and pagination</p>

      <div className="history-toolbar">
        <label htmlFor="history-sort" style={{ fontSize: 13, color: "var(--text-dim)" }}>
          Sort
        </label>
        <select
          id="history-sort"
          className="auth-input"
          style={{ width: "auto" }}
          value={sort}
          onChange={(event) => {
            setSort(event.target.value as HistorySortValue);
            setCursorStack([]);
          }}
        >
          {HISTORY_SORTS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <button
          type="button"
          className="btn"
          disabled={selected.length !== COMPARE_CAPACITY}
          onClick={() => setComparePair([selected[0], selected[1]])}
        >
          Compare selected ({selected.length}/{COMPARE_CAPACITY})
        </button>
      </div>

      {history.isLoading ? (
        <Loading />
      ) : history.isError ? (
        <ErrorState error={history.error} onRetry={() => void history.refetch()} />
      ) : rows.length === 0 ? (
        <div className="card">
          <EmptyState
            glyph="🗂"
            title="No backtest results yet"
            description="Only a succeeded run materializes an immutable Result. Request a run from RUN & Backtest Results."
          />
        </div>
      ) : (
        // v18 mockup: each immutable result is a blue expandable card — the row
        // carries identity + actions, the details panel holds the key metrics.
        <div>
          {rows.map((row) => {
            const isOpen = expanded.has(row.result_id);
            return (
              <div className="history-card" key={row.result_id}>
                <div className="history-row">
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                      flexWrap: "wrap",
                      minWidth: 0,
                    }}
                  >
                    {row.allowed_actions.compare ? (
                      <input
                        type="checkbox"
                        aria-label={`Select ${row.result_id} for compare`}
                        checked={selected.includes(row.result_id)}
                        disabled={
                          !selected.includes(row.result_id) &&
                          selected.length >= COMPARE_CAPACITY
                        }
                        onChange={() => toggleSelect(row.result_id)}
                      />
                    ) : null}
                    <code>{row.result_id}</code>
                    <span>{formatUtc(row.completed_at_utc)}</span>
                    <span>{row.timeframe ?? EM_DASH}</span>
                    <span>{row.market_data_revision_summary?.symbol ?? EM_DASH}</span>
                  </div>
                  <div
                    style={{ display: "flex", alignItems: "center", gap: 8, whiteSpace: "nowrap" }}
                  >
                    <Link
                      className="btn btn-ghost"
                      to={`/backtest/run?result=${encodeURIComponent(row.result_id)}`}
                    >
                      View
                    </Link>
                    {row.allowed_actions.soft_delete ? (
                      <button
                        type="button"
                        className="btn btn-ghost"
                        disabled={softDelete.isPending}
                        onClick={() => deleteRow(row.result_id)}
                      >
                        {armedDelete === row.result_id ? "Confirm delete" : "Delete"}
                      </button>
                    ) : null}
                    <button
                      type="button"
                      className="history-arrow"
                      aria-label={`Details for ${row.result_id}`}
                      aria-expanded={isOpen}
                      onClick={() => toggleExpanded(row.result_id)}
                    >
                      {isOpen ? "▲" : "▼"}
                    </button>
                  </div>
                </div>
                {/* Always rendered so the key metrics + provenance are
                    addressable; CSS collapses the panel until the row is
                    expanded. */}
                <HistoryDetails row={row} isOpen={isOpen} />
              </div>
            );
          })}
        </div>
      )}

      {softDelete.isError ? (
        <p role="alert" style={{ color: "var(--down)", marginTop: 10 }}>
          {mutationErrorText(softDelete.error)}
        </p>
      ) : null}

      <div style={{ display: "flex", gap: 10, marginTop: 14 }}>
        <button
          type="button"
          className="btn"
          disabled={cursorStack.length === 0 || history.isFetching}
          onClick={() => setCursorStack((stack) => stack.slice(0, -1))}
        >
          ← Previous
        </button>
        <button
          type="button"
          className="btn"
          disabled={nextCursor === null || history.isFetching}
          onClick={() => {
            if (nextCursor !== null) setCursorStack((stack) => [...stack, nextCursor]);
          }}
        >
          Next →
        </button>
      </div>

      {comparePair !== null ? (
        <ComparePanel pair={comparePair} onClose={() => setComparePair(null)} />
      ) : null}
    </>
  );
}

const NOT_PINNED = "Not separately pinned";

// A pinned manifest ref as a stable "root @ revision" identity line — mirrors
// ResultDetail so the inline panel and the full View page read identically.
function refLabel(ref: ManifestItemRef): string {
  return `${ref.root_id ?? EM_DASH} @ ${ref.revision_id ?? EM_DASH}`;
}

// A pinned-ref list (or the honest "Not separately pinned" when the V1 manifest
// carries none of that class), rendered verbatim — never re-resolved from the
// current Mainboard (doc 16 §15).
function RefList({ refs, prefixKind = false }: { refs: ManifestItemRef[]; prefixKind?: boolean }) {
  if (refs.length === 0) return <span>{NOT_PINNED}</span>;
  return (
    <ul className="history-ref-list">
      {refs.map((ref) => (
        <li key={ref.item_id ?? refLabel(ref)}>
          <code>{prefixKind ? `${ref.item_kind ?? EM_DASH} · ${refLabel(ref)}` : refLabel(ref)}</code>
        </li>
      ))}
    </ul>
  );
}

// UI-16: the inline expanded panel lets a user verify result IDENTITY and
// PRODUCTION INPUTS without leaving for the separate View page (spec §UI-16).
// Key metrics, Data, Date and the immutable manifest summary read straight from
// the immutable history row; the pinned Strategies/Parameters (the manifest
// excerpt) are lazily read from the immutable Result detail ONLY once the row is
// expanded — a presentation reuse of the existing detail hook, never a new
// route / react-query key / API call. The panel is always in the DOM (CSS
// collapses it) so its content stays addressable.
function HistoryDetails({ row, isOpen }: { row: HistoryRow; isOpen: boolean }) {
  const detail = useBacktestResult(isOpen ? row.result_id : null);
  const excerpt = detail.data?.manifest_excerpt ?? null;

  const symbol = row.market_data_revision_summary?.symbol ?? EM_DASH;
  const timeframe = row.timeframe ?? EM_DASH;
  const rangeStart = row.backtest_range.start ?? EM_DASH;
  const rangeEnd = row.backtest_range.end ?? EM_DASH;

  // Pinned Strategies/Parameters need the manifest excerpt (a per-row detail
  // read). Until it resolves, the row-level provenance already stands on its own.
  const provenance = () => {
    if (detail.isLoading) return <span className="page-sub">Loading pinned inputs…</span>;
    if (detail.isError)
      return (
        <span className="page-sub">
          Pinned inputs are unavailable right now — open View for the full manifest.
        </span>
      );
    return null;
  };

  return (
    <div className={`history-details${isOpen ? " open" : ""}`}>
      <dl className="kv history-provenance">
        <dt>Strategies</dt>
        <dd>{excerpt ? <RefList refs={excerpt.strategy_revision_refs} /> : provenance()}</dd>

        {excerpt && excerpt.external_work_refs.length > 0 ? (
          <>
            <dt>External work</dt>
            <dd>
              <RefList refs={excerpt.external_work_refs} prefixKind />
            </dd>
          </>
        ) : null}

        <dt>Parameters</dt>
        <dd>
          {excerpt ? (
            <>
              <div className="history-detail-note">
                Pinned inside each immutable strategy/package revision above. The pinned
                parameter-carrying inputs are:
              </div>
              <div className="history-detail-label">Packages</div>
              <RefList refs={excerpt.package_revision_refs} />
              <div className="history-detail-label">Allocation plan revision</div>
              <code>{excerpt.portfolio_allocation_plan_revision_id ?? NOT_PINNED}</code>
              <div className="history-detail-label">Execution key</div>
              <code className="history-hash">{excerpt.execution_context.execution_key ?? EM_DASH}</code>
            </>
          ) : (
            provenance()
          )}
        </dd>

        <dt>Data</dt>
        <dd>
          {symbol} · {timeframe} · {excerpt?.market_data_revision ?? "stored Market Data source"}
        </dd>

        <dt>Date</dt>
        <dd>
          Completed {formatUtc(row.completed_at_utc)} · Range {rangeStart} → {rangeEnd}
        </dd>
      </dl>

      <div className="history-detail-label">Key metrics</div>
      <table className="metrics-table">
        <tbody>
          {KEY_METRIC_COLUMNS.map((column) => (
            <tr key={column.key}>
              <th scope="row">{column.label}</th>
              <td>{formatMetricValue(row.key_metrics[column.key])}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="history-detail-label">Immutable manifest summary</div>
      <dl className="kv kv-compact history-manifest">
        <dt>Manifest hash</dt>
        <dd>
          <code className="history-hash">{row.manifest_hash}</code>
        </dd>
        <dt>Engine version</dt>
        <dd>
          <code>{row.engine_version}</code>
        </dd>
        <dt>Composition fingerprint</dt>
        <dd>
          <code className="history-hash">
            {row.composition_context.composition_fingerprint}
          </code>
        </dd>
        <dt>Materialization</dt>
        <dd>{row.materialization_status}</dd>
        {excerpt ? (
          <>
            <dt>Pinned items</dt>
            <dd>
              {excerpt.strategy_revision_refs.length +
                excerpt.external_work_refs.length +
                excerpt.package_revision_refs.length}
            </dd>
          </>
        ) : null}
      </dl>
      <p className="page-sub history-detail-foot">
        This panel shows which strategies, parameters and data produced this result, plus
        the immutable manifest identity — no need to open the separate View page.
      </p>
    </div>
  );
}

// Side-by-side read of two immutable results (doc 16 §8.3). The server flags
// each differing context field; the panel makes the difference VISIBLE and
// nothing more — no winner, no ranking (RH-09).
function ComparePanel({ pair, onClose }: { pair: [string, string]; onClose: () => void }) {
  const compare = useCompareResults(pair);
  const data = compare.data;
  const [a, b] = data?.results ?? [null, null];
  const contextFields = data ? Object.entries(data.context.fields) : [];

  return (
    <section className="card" aria-labelledby="compare-h" style={{ marginTop: 18 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <h3 id="compare-h" style={{ margin: 0 }}>
          Compare results
        </h3>
        <button type="button" className="btn btn-ghost" onClick={onClose}>
          Close
        </button>
      </div>

      {compare.isLoading ? (
        <Loading label="Loading comparison…" />
      ) : compare.isError ? (
        <ErrorState error={compare.error} onRetry={() => void compare.refetch()} />
      ) : data && a !== null && b !== null ? (
        <>
          {data.context_differs ? (
            <p role="alert" style={{ color: "var(--warn)" }}>
              Context differs — the comparison is informational only; neither result is ranked.
            </p>
          ) : (
            <p className="page-sub">Contexts match.</p>
          )}

          <table className="metrics-table">
            <thead>
              <tr>
                <th scope="col" aria-label="Field" />
                <th scope="col">
                  <code>{a.result_id}</code>
                </th>
                <th scope="col">
                  <code>{b.result_id}</code>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Symbol</td>
                <td>{a.summary?.symbol ?? EM_DASH}</td>
                <td>{b.summary?.symbol ?? EM_DASH}</td>
              </tr>
              <tr>
                <td>Timeframe</td>
                <td>{a.summary?.timeframe ?? EM_DASH}</td>
                <td>{b.summary?.timeframe ?? EM_DASH}</td>
              </tr>
              <tr>
                <td>Period</td>
                <td>
                  {a.summary?.period_start ?? EM_DASH} → {a.summary?.period_end ?? EM_DASH}
                </td>
                <td>
                  {b.summary?.period_start ?? EM_DASH} → {b.summary?.period_end ?? EM_DASH}
                </td>
              </tr>
              {KEY_METRIC_COLUMNS.map((column) => (
                <tr key={column.key}>
                  <td>{column.label}</td>
                  <td>{formatMetricValue(a.key_metrics[column.key])}</td>
                  <td>{formatMetricValue(b.key_metrics[column.key])}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <h4>Run context</h4>
          <table className="metrics-table">
            <thead>
              <tr>
                <th scope="col">Field</th>
                <th scope="col">A</th>
                <th scope="col">B</th>
                <th scope="col" aria-label="Differs" />
              </tr>
            </thead>
            <tbody>
              {contextFields.map(([name, field]) => (
                <tr key={name}>
                  <td>{name}</td>
                  <td style={{ wordBreak: "break-all" }}>{contextText(field.a)}</td>
                  <td style={{ wordBreak: "break-all" }}>{contextText(field.b)}</td>
                  <td>{field.differs ? <span className="badge">differs</span> : null}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : null}
    </section>
  );
}
