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
  useCompareResults,
  useResultsHistory,
  useSoftDeleteResult,
  type HistorySortValue,
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
                      aria-label={`Metrics for ${row.result_id}`}
                      aria-expanded={isOpen}
                      onClick={() => toggleExpanded(row.result_id)}
                    >
                      {isOpen ? "▲" : "▼"}
                    </button>
                  </div>
                </div>
                {/* Always rendered so the key metrics are addressable; CSS
                    collapses the panel until the row is expanded. */}
                <div className={`history-details${isOpen ? " open" : ""}`}>
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
                </div>
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
