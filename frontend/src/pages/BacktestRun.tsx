import { Link, useSearchParams } from "react-router-dom";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { ResultDetail } from "@/components/ResultDetail";
import { RunProgress } from "@/components/RunProgress";
import { StatusBadge } from "@/components/StatusBadge";
import { ApiError } from "@/lib/apiClient";
import {
  EM_DASH,
  useBacktestResult,
  useDefaultMainboard,
  useRequestBacktestRun,
} from "@/lib/backtest";
import { isReadyForRun, readyStatusText, readyStatusTone } from "@/lib/mainboard";

// Admission failures surface the backend canonical envelope verbatim — the
// client never invents run-domain messages (mirrors ErrorState/Login).
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
  // F-16: admission is gated on the SAME readiness projection the backend authz
  // enforces (request_backtest_run refuses to queue — 422 READINESS_BLOCKED —
  // when blocker_count > 0). Disabling the button when the composition is not
  // RUN-runnable keeps the visual + keyboard gate consistent with that authz
  // rather than relying only on the server rejecting the click.
  const readyState = composition?.ready_summary.state ?? "not_ready";
  const runnable = composition !== undefined && isReadyForRun(readyState);

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
              <dt>Backtest readiness</dt>
              <dd>
                <StatusBadge tone={readyStatusTone(readyState)} label={readyStatusText(readyState)} />
              </dd>
            </dl>
            <div style={{ marginTop: 14, display: "flex", alignItems: "center", gap: 12 }}>
              <button
                type="button"
                className="btn btn-primary"
                disabled={requestRun.isPending || !runnable}
                aria-describedby={runnable ? undefined : "run-admit-locked-note"}
                title={
                  runnable
                    ? undefined
                    : "RUN is available only after a current Backtest Ready Check passes."
                }
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
            {!runnable ? (
              // Locked: the composition has not passed a current Ready Check, so
              // admission is refused up front (matching the backend authz) instead
              // of round-tripping to a 422. The Ready Check page is the way out.
              <p id="run-admit-locked-note" style={{ color: "var(--text-dim)", fontSize: 13, margin: "10px 0 0" }}>
                RUN is available only after a current Backtest Ready Check passes.{" "}
                <Link to="/backtest/ready-check">Open Backtest Ready Check</Link>
              </p>
            ) : null}
            {requestRun.isError ? (
              <p role="alert" style={{ color: "var(--down)", marginBottom: 0 }}>
                {mutationErrorText(requestRun.error)}
              </p>
            ) : null}
          </>
        ) : null}
      </section>

      {runId ? (
        <RunProgress runId={runId} onRunAdmitted={onRunAdmitted} />
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

