import { useState } from "react";
import { Link } from "react-router-dom";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import {
  DEFAULT_HISTORY_SORT,
  EM_DASH,
  HISTORY_SORTS,
  KEY_METRIC_COLUMNS,
  formatMetricValue,
  formatUtc,
  useResultsHistory,
  type HistorySortValue,
} from "@/lib/backtest";

// Results History (Stage 5b, doc 16): the authoritative server-side index over
// immutable results — sort and keyset cursor come from the backend; the client
// never re-orders rows. "View" deep-links into the RUN page's ?result= mode.
export function ResultsHistory() {
  const [sort, setSort] = useState<HistorySortValue>(DEFAULT_HISTORY_SORT);
  // Server cursors visited so far; the last entry is the current page and an
  // empty stack is the first page. A sort change resets to the first page.
  const [cursorStack, setCursorStack] = useState<string[]>([]);
  const cursor = cursorStack.length > 0 ? cursorStack[cursorStack.length - 1] : null;
  const history = useResultsHistory(sort, cursor);

  const rows = history.data?.items ?? [];
  const nextCursor = history.data?.next_cursor ?? null;

  return (
    <>
      <h1 className="page-title">Results History</h1>
      <p className="page-sub">Immutable backtest results · server-side sort and pagination</p>

      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
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
        <div className="card" style={{ overflowX: "auto", padding: 0 }}>
          <table className="metrics-table">
            <thead>
              <tr>
                <th scope="col">Result</th>
                <th scope="col">Completed</th>
                <th scope="col">Timeframe</th>
                {KEY_METRIC_COLUMNS.map((column) => (
                  <th key={column.key} scope="col">
                    {column.label}
                  </th>
                ))}
                <th scope="col" aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.result_id}>
                  <td>
                    <code>{row.result_id}</code>
                  </td>
                  <td>{formatUtc(row.completed_at_utc)}</td>
                  <td>{row.timeframe ?? EM_DASH}</td>
                  {KEY_METRIC_COLUMNS.map((column) => (
                    <td key={column.key}>{formatMetricValue(row.key_metrics[column.key])}</td>
                  ))}
                  <td>
                    <Link className="btn btn-ghost" to={`/backtest/run?result=${encodeURIComponent(row.result_id)}`}>
                      View
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

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
    </>
  );
}
