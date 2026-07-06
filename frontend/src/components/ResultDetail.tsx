import { EM_DASH, formatMetricValue, type BacktestResultDetail } from "@/lib/backtest";

const hashStyle = { fontFamily: "monospace", fontSize: 12, wordBreak: "break-all" } as const;

// Immutable Result detail (doc 15 §9.4): hydrated ONLY from the result_id
// projection — never from the current Mainboard form. Values render verbatim;
// a non-computed metric shows its availability, never a fabricated 0 (L4).
export function ResultDetail({ result }: { result: BacktestResultDetail }) {
  const artifactEntries = Object.entries(result.artifact_counts);
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
      {result.metrics.length === 0 ? (
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
            {result.metrics.map((metric) => (
              <tr key={metric.key}>
                <td>{metric.label}</td>
                <td>{formatMetricValue(metric)}</td>
                <td>{metric.availability}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

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
