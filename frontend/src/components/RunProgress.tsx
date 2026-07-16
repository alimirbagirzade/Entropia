import { ResultDetail } from "@/components/ResultDetail";
import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { StatusBadge } from "@/components/StatusBadge";
import { ApiError } from "@/lib/apiClient";
import {
  TERMINAL_RUN_STATES,
  formatUtc,
  useBacktestResult,
  useBacktestRun,
  useRetryBacktestRun,
} from "@/lib/backtest";

const RUN_STATE_TONES: Record<string, "ok" | "warn" | "down" | "neutral"> = {
  queued: "neutral",
  provisioning: "warn",
  running: "warn",
  succeeded: "ok",
  failed: "down",
  cancelled: "down",
};

// Admission/retry failures surface the backend canonical envelope verbatim — the
// client never invents run-domain messages (mirrors ErrorState/Login).
function mutationErrorText(error: unknown): string {
  if (error instanceof ApiError) return `${error.code}: ${error.message}`;
  return error instanceof Error ? error.message : "Request failed.";
}

// Durable run progress + the immutable Result it produces (doc 15 §4 / §9.4).
// Shared by the standalone RUN & Results page and the Mainboard inline results
// pane (UI-15) so the progress/result rendering is byte-identical in both. The
// run id is tracked by the caller; a retry swaps tracking onto the fresh run id.
export function RunProgress({
  runId,
  onRunAdmitted,
}: {
  runId: string;
  onRunAdmitted: (runId: string) => void;
}) {
  const run = useBacktestRun(runId);
  const retryRun = useRetryBacktestRun();
  const data = run.data;
  const tone = data ? (RUN_STATE_TONES[data.state] ?? "neutral") : "neutral";
  const retryable = data?.state === "failed" || data?.state === "cancelled";

  return (
    <>
      <section className="card" aria-labelledby="run-status-h" style={{ marginTop: 18 }}>
        <h3 id="run-status-h" style={{ marginTop: 0 }}>
          Run status
        </h3>
        {run.isLoading ? (
          <Loading label="Loading run…" />
        ) : run.isError ? (
          <ErrorState error={run.error} onRetry={() => void run.refetch()} />
        ) : data ? (
          <>
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
              <StatusBadge tone={tone} label={data.state} />
              {!TERMINAL_RUN_STATES.has(data.state) ? (
                <span className="badge">live · SSE + poll fallback</span>
              ) : null}
            </div>
            <dl className="kv">
              <dt>Run</dt>
              <dd>
                <code>{data.run_id}</code>
              </dd>
              <dt>Created</dt>
              <dd>{formatUtc(data.created_at)}</dd>
              <dt>Started</dt>
              <dd>{formatUtc(data.started_at)}</dd>
              <dt>Finished</dt>
              <dd>{formatUtc(data.finished_at)}</dd>
              {data.retry_of_run_id ? (
                <>
                  <dt>Retry of</dt>
                  <dd>
                    <code>{data.retry_of_run_id}</code>
                  </dd>
                </>
              ) : null}
              {data.failure_code ? (
                <>
                  <dt>Failure</dt>
                  <dd style={{ color: "var(--down)" }}>
                    {data.failure_code}
                    {data.failure_message ? ` — ${data.failure_message}` : ""}
                  </dd>
                </>
              ) : null}
            </dl>
            {retryable ? (
              <div style={{ marginTop: 14 }}>
                <button
                  type="button"
                  className="btn"
                  disabled={retryRun.isPending}
                  onClick={() =>
                    retryRun.mutate(data.run_id, {
                      onSuccess: (admission) => onRunAdmitted(admission.run_id),
                    })
                  }
                >
                  {retryRun.isPending ? "Retrying…" : "Retry run"}
                </button>
                {retryRun.isError ? (
                  <p role="alert" style={{ color: "var(--down)", marginBottom: 0 }}>
                    {mutationErrorText(retryRun.error)}
                  </p>
                ) : null}
              </div>
            ) : null}
          </>
        ) : null}
      </section>
      {data?.result_id ? <InlineResult resultId={data.result_id} /> : null}
    </>
  );
}

function InlineResult({ resultId }: { resultId: string }) {
  const result = useBacktestResult(resultId);
  if (result.isLoading) return <Loading label="Loading result…" />;
  if (result.isError) return <ErrorState error={result.error} onRetry={() => void result.refetch()} />;
  return result.data ? <ResultDetail result={result.data} /> : null;
}
