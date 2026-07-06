import { useMetrics } from "@/lib/hooks";
import { Loading } from "@/components/Loading";
import { ErrorState } from "@/components/ErrorState";
import { StatusBadge } from "@/components/StatusBadge";
import type { MetricsSummary } from "@/lib/metrics";

// Operational metrics dashboard over GET /v1/metrics (Prometheus text exposition,
// delivered in Stage 8b). Read-only: the backend computes every number at scrape
// time; this page parses and presents the four golden signals plus the DB-backed
// operational gauges (jobs depth, outbox lag, oldest RUNNING lease age), and
// refetches on an interval so the view tracks the live process.
export function Metrics() {
  const metrics = useMetrics();

  return (
    <>
      <h1 className="page-title">System Metrics</h1>
      <p className="page-sub">
        Golden signals &amp; operational gauges · <code>/v1/metrics</code> · refreshes every 5s
      </p>

      {metrics.isLoading ? (
        <Loading label="Scraping /v1/metrics…" />
      ) : metrics.isError ? (
        <ErrorState error={metrics.error} onRetry={() => metrics.refetch()} />
      ) : metrics.data ? (
        <MetricsPanels summary={metrics.data} fetching={metrics.isFetching} />
      ) : null}
    </>
  );
}

function MetricsPanels({ summary, fetching }: { summary: MetricsSummary; fetching: boolean }) {
  const { golden } = summary;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
        <StatusBadge label={fetching ? "updating…" : "live"} tone={fetching ? "warn" : "ok"} />
        <StatusBadge label={`${summary.familyCount} metric families`} tone="neutral" />
        {summary.degraded ? (
          <StatusBadge label="operational gauges degraded (DB unreachable)" tone="down" />
        ) : null}
      </div>

      <div style={{ display: "grid", gap: 18, gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))" }}>
        <section className="card" aria-labelledby="golden-h">
          <h3 id="golden-h" style={{ marginTop: 0 }}>Golden signals</h3>
          <div style={{ display: "grid", gap: 16, gridTemplateColumns: "1fr 1fr" }}>
            <Stat label="Traffic (requests)" value={formatCount(golden.requestsTotal)} />
            <Stat label="In flight (saturation)" value={formatCount(golden.inFlight)} />
            <Stat
              label="Errors (5xx)"
              value={formatCount(golden.serverErrors)}
              tone={golden.serverErrors > 0 ? "down" : "ok"}
            />
            <Stat
              label="Client errors (4xx)"
              value={formatCount(golden.clientErrors)}
              tone={golden.clientErrors > 0 ? "warn" : "ok"}
            />
            <Stat label="Avg latency" value={formatMs(golden.avgLatencyMs)} />
          </div>
          {Object.keys(golden.statusClasses).length > 0 ? (
            <div style={{ marginTop: 16 }}>
              <div style={{ fontSize: 12, color: "var(--text-dim)", marginBottom: 6 }}>By status class</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {Object.entries(golden.statusClasses)
                  .sort(([a], [b]) => a.localeCompare(b))
                  .map(([cls, count]) => (
                    <StatusBadge key={cls} label={`${cls}: ${formatCount(count)}`} tone={toneForClass(cls)} />
                  ))}
              </div>
            </div>
          ) : null}
        </section>

        <section className="card" aria-labelledby="ops-h">
          <h3 id="ops-h" style={{ marginTop: 0 }}>Operational gauges</h3>
          <dl className="kv">
            <dt>Outbox lag</dt>
            <dd>{formatSeconds(summary.outboxLagSeconds)}</dd>
            <dt>Oldest lease age</dt>
            <dd>{formatSeconds(summary.leaseAgeSeconds)}</dd>
            <dt>Jobs (total)</dt>
            <dd>{formatCount(summary.jobsDepthTotal)}</dd>
          </dl>
        </section>
      </div>

      <section className="card" aria-labelledby="jobs-h">
        <h3 id="jobs-h" style={{ marginTop: 0 }}>Jobs depth</h3>
        {summary.jobsDepth.length === 0 ? (
          <p style={{ color: "var(--text-dim)", margin: 0 }}>
            {summary.degraded ? "Unavailable — database unreachable at scrape time." : "No jobs on any queue."}
          </p>
        ) : (
          <table className="metrics-table">
            <thead>
              <tr>
                <th scope="col">Queue</th>
                <th scope="col">Status</th>
                <th scope="col" style={{ textAlign: "right" }}>Count</th>
              </tr>
            </thead>
            <tbody>
              {summary.jobsDepth.map((row) => (
                <tr key={`${row.queue}:${row.status}`}>
                  <td>{row.queue}</td>
                  <td>{row.status}</td>
                  <td style={{ textAlign: "right" }}>{formatCount(row.count)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: "ok" | "warn" | "down" }) {
  const color = tone === "down" ? "var(--down)" : tone === "warn" ? "var(--warn)" : "var(--text)";
  return (
    <div>
      <div style={{ fontSize: 12, color: "var(--text-dim)" }}>{label}</div>
      <div style={{ fontSize: 24, fontWeight: 600, color, lineHeight: 1.3 }}>{value}</div>
    </div>
  );
}

function toneForClass(cls: string): "ok" | "warn" | "down" | "neutral" {
  if (cls === "5xx") return "down";
  if (cls === "4xx") return "warn";
  if (cls === "2xx") return "ok";
  return "neutral";
}

function formatCount(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "—";
  return Math.round(value).toLocaleString();
}

function formatMs(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "—";
  return `${value.toFixed(1)} ms`;
}

function formatSeconds(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "—";
  return `${value.toFixed(2)} s`;
}
