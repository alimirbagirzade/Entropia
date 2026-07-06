import { Link, useSearchParams } from "react-router-dom";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { ResultDetail } from "@/components/ResultDetail";
import { StatusBadge } from "@/components/StatusBadge";
import { ApiError } from "@/lib/apiClient";
import {
  EM_DASH,
  TERMINAL_RUN_STATES,
  formatUtc,
  useBacktestResult,
  useBacktestRun,
  useDefaultMainboard,
  useRequestBacktestRun,
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

// Admission/retry failures surface the backend canonical envelope verbatim —
// the client never invents run-domain messages (mirrors ErrorState/Login).
function mutationErrorText(error: unknown): string {
  if (error instanceof ApiError) return `${error.code}: ${error.message}`;
  return error instanceof Error ? error.message : "Request failed.";
}

// RUN & Backtest Results (Stage 5a, doc 15). Two modes:
//  - ?result=<id>  → immutable Result deep-link (hydrated ONLY from result_id,
//    doc 15 §8.5 — this is where Results History "View" lands);
//  - default       → composition context + 202 run admission + durable run
//    status. The run id lives in ?run= so a page refresh keeps tracking the
//    durable row (reconnect-safe, doc 15 §4).
export function BacktestRun() {
  const [searchParams, setSearchParams] = useSearchParams();
  const resultParam = searchParams.get("result");
  const runParam = searchParams.get("run");

  return (
    <>
      <h1 className="page-title">RUN &amp; Backtest Results</h1>
      <p className="page-sub">
        {resultParam
          ? "Immutable result detail · hydrated from persisted artifacts only"
          : "Admit a backtest run for your default Mainboard composition and follow it live"}
      </p>
      {resultParam ? (
        <StandaloneResult resultId={resultParam} />
      ) : (
        <RunWorkbench runId={runParam} onRunAdmitted={(id) => setSearchParams({ run: id })} />
      )}
    </>
  );
}

function StandaloneResult({ resultId }: { resultId: string }) {
  const result = useBacktestResult(resultId);
  return (
    <>
      <div style={{ display: "flex", gap: 10 }}>
        <Link className="btn btn-ghost" to="/backtest/history">
          ← Results History
        </Link>
        <Link className="btn btn-ghost" to="/backtest/run">
          Go to RUN
        </Link>
      </div>
      {result.isLoading ? (
        <Loading label="Loading result…" />
      ) : result.isError ? (
        <ErrorState error={result.error} onRetry={() => void result.refetch()} />
      ) : result.data ? (
        <ResultDetail result={result.data} />
      ) : null}
    </>
  );
}

function RunWorkbench({
  runId,
  onRunAdmitted,
}: {
  runId: string | null;
  onRunAdmitted: (runId: string) => void;
}) {
  const mainboard = useDefaultMainboard();
  const requestRun = useRequestBacktestRun();
  const composition = mainboard.data;
  const enabledCount = composition?.items.filter((item) => item.is_enabled).length ?? 0;
  const warningCount = requestRun.data?.warning_count ?? 0;

  return (
    <>
      <section className="card" aria-labelledby="composition-h">
        <h3 id="composition-h" style={{ marginTop: 0 }}>
          Composition
        </h3>
        {mainboard.isLoading ? (
          <Loading />
        ) : mainboard.isError ? (
          <ErrorState error={mainboard.error} onRetry={() => void mainboard.refetch()} />
        ) : composition ? (
          <>
            <dl className="kv">
              <dt>Workspace</dt>
              <dd>
                <code>{composition.workspace_id}</code>
              </dd>
              <dt>Items</dt>
              <dd>
                {composition.items.length} ({enabledCount} enabled)
              </dd>
              <dt>Composition hash</dt>
              <dd>{composition.composition_hash ?? EM_DASH}</dd>
            </dl>
            <div style={{ marginTop: 14, display: "flex", alignItems: "center", gap: 12 }}>
              <button
                type="button"
                className="btn btn-primary"
                disabled={requestRun.isPending}
                onClick={() =>
                  requestRun.mutate(composition.workspace_id, {
                    onSuccess: (admission) => onRunAdmitted(admission.run_id),
                  })
                }
              >
                {requestRun.isPending ? "Requesting…" : "Request Backtest Run"}
              </button>
              {warningCount > 0 ? (
                <StatusBadge tone="warn" label={`${warningCount} readiness warning(s)`} />
              ) : null}
            </div>
            {requestRun.isError ? (
              <p role="alert" style={{ color: "var(--down)", marginBottom: 0 }}>
                {mutationErrorText(requestRun.error)}
              </p>
            ) : null}
          </>
        ) : null}
      </section>

      {runId ? (
        <RunStatus runId={runId} onRunAdmitted={onRunAdmitted} />
      ) : (
        <div className="card" style={{ marginTop: 18 }}>
          <EmptyState
            glyph="▶"
            title="No active run"
            description="Request a run above, or open an immutable result from Results History."
          />
        </div>
      )}
    </>
  );
}

function RunStatus({
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
