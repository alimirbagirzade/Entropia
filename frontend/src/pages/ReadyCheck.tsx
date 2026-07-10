import { Link, useSearchParams } from "react-router-dom";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { StatusBadge } from "@/components/StatusBadge";
import { ApiError } from "@/lib/apiClient";
import { EM_DASH, useDefaultMainboard } from "@/lib/backtest";
import {
  type CurrentReadiness,
  type ReadinessIssue,
  type ReadinessReport,
  type ReadinessSummary,
  readinessStateLabel,
  readinessStateTone,
  severityTone,
  useCurrentReadiness,
  useReadinessReport,
  useRunReadinessCheck,
} from "@/lib/readiness";
import { useState } from "react";

// Run-check failures surface the backend canonical envelope verbatim — the
// client never invents readiness-domain messages (mirrors BacktestRun/Login). A
// stale composition guard mismatch arrives here as 409 CompositionStale (RC-09).
function mutationErrorText(error: unknown): string {
  if (error instanceof ApiError) return `${error.code}: ${error.message}`;
  return error instanceof Error ? error.message : "Request failed.";
}

const EMPTY_SUMMARY: ReadinessSummary = {
  blocker_count: 0,
  warning_count: 0,
  pass_count: 0,
  allocation_enabled: false,
};

// A GET .../readiness response with a non-null report_id IS the full
// get_readiness_report projection at runtime (doc 14 §9.1 — the query delegates
// to it). The ?? below are inert TS-narrowing fallbacks, never fabricated data.
function currentAsReport(current: CurrentReadiness): ReadinessReport | null {
  if (current.report_id === null) return null;
  return {
    report_id: current.report_id,
    composition_id: current.composition_id,
    snapshot_id: current.snapshot_id ?? null,
    composition_fingerprint: current.composition_fingerprint ?? "",
    current_fingerprint: current.current_fingerprint ?? "",
    stored_state: current.stored_state ?? current.state,
    state: current.state,
    is_current: current.is_current ?? true,
    summary: current.summary ?? EMPTY_SUMMARY,
    issues: current.issues ?? [],
  };
}

// Backtest Ready Check (Stage 4b, doc 14). Two modes:
//  - ?report=<id> → an immutable report deep-link (hydrated only from report_id,
//    doc 14 §9.1) — the same shape a future History "View" would land on;
//  - default      → the default-Mainboard composition context + its current
//    readiness projection + a run-check admission (optionally fingerprint-guarded).
export function ReadyCheck() {
  const [searchParams] = useSearchParams();
  const reportParam = searchParams.get("report");

  return (
    <>
      <h1 className="page-title">Backtest Ready Check</h1>
      <p className="page-sub">
        {reportParam
          ? "Immutable readiness report · hydrated from the persisted snapshot only"
          : "Validate your default Mainboard composition before admitting a backtest run"}
      </p>
      {reportParam ? <StandaloneReport reportId={reportParam} /> : <ReadyCheckWorkbench />}
    </>
  );
}

function StandaloneReport({ reportId }: { reportId: string }) {
  const report = useReadinessReport(reportId);
  return (
    <>
      <div style={{ display: "flex", gap: 10 }}>
        <Link className="btn btn-ghost" to="/backtest/ready-check">
          ← Ready Check
        </Link>
        <Link className="btn btn-ghost" to="/backtest/run">
          Go to RUN
        </Link>
      </div>
      {report.isLoading ? (
        <Loading label="Loading report…" />
      ) : report.isError ? (
        <ErrorState error={report.error} onRetry={() => void report.refetch()} />
      ) : report.data ? (
        <ReadinessReportCard report={report.data} />
      ) : null}
    </>
  );
}

function ReadyCheckWorkbench() {
  const mainboard = useDefaultMainboard();
  const composition = mainboard.data;
  const compositionId = composition?.workspace_id ?? null;
  const currentFingerprint = composition?.composition_hash ?? null;

  const readiness = useCurrentReadiness(compositionId);
  const runCheck = useRunReadinessCheck();
  const [guard, setGuard] = useState(false);

  const report = readiness.data ? currentAsReport(readiness.data) : null;
  const enabledCount = composition?.items.filter((item) => item.is_enabled).length ?? 0;

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
              <dd>
                {currentFingerprint ? <code>{currentFingerprint}</code> : EM_DASH}
              </dd>
            </dl>
            <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 10 }}>
              <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14 }}>
                <input
                  type="checkbox"
                  checked={guard}
                  disabled={currentFingerprint === null}
                  onChange={(event) => setGuard(event.target.checked)}
                />
                Guard: fail if the composition changed since this page loaded
              </label>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={runCheck.isPending || compositionId === null}
                  onClick={() =>
                    runCheck.mutate({
                      compositionId: compositionId ?? "",
                      ...(guard && currentFingerprint !== null
                        ? { expectedFingerprint: currentFingerprint }
                        : {}),
                    })
                  }
                >
                  {runCheck.isPending ? "Running check…" : "Run Ready Check"}
                </button>
              </div>
              {runCheck.isError ? (
                <p role="alert" style={{ color: "var(--down)", marginBottom: 0 }}>
                  {mutationErrorText(runCheck.error)}
                </p>
              ) : null}
            </div>
          </>
        ) : null}
      </section>

      <div style={{ marginTop: 18 }}>
        {readiness.isLoading ? (
          <div className="card">
            <Loading label="Loading readiness…" />
          </div>
        ) : readiness.isError ? (
          <div className="card">
            <ErrorState error={readiness.error} onRetry={() => void readiness.refetch()} />
          </div>
        ) : report ? (
          <ReadinessReportCard report={report} />
        ) : (
          <div className="card">
            <EmptyState
              glyph="✓"
              title="Not checked yet"
              description="Run a Ready Check above to validate the composition and surface any blockers or warnings."
            />
          </div>
        )}
      </div>
    </>
  );
}

function ReadinessReportCard({ report }: { report: ReadinessReport }) {
  // When is_current is false the effective state is "stale" (composition changed
  // since the check) or "superseded" (a newer report exists) — the server picks
  // which (doc 14 §4, query _effective_state); the client never re-derives it.
  const stale = report.state === "stale";
  return (
    <section className="card" aria-labelledby="report-h">
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          marginBottom: 12,
          flexWrap: "wrap",
        }}
      >
        <h3 id="report-h" style={{ margin: 0 }}>
          Readiness report
        </h3>
        <StatusBadge tone={readinessStateTone(report.state)} label={readinessStateLabel(report.state)} />
        {!report.is_current ? (
          <span className="badge" style={{ color: "var(--warn)" }}>
            {stale ? "stale · re-run to refresh" : "superseded · a newer report exists"}
          </span>
        ) : null}
      </div>

      <dl className="kv">
        <dt>Report</dt>
        <dd>
          <code>{report.report_id}</code>
        </dd>
        <dt>Blockers</dt>
        <dd style={{ color: report.summary.blocker_count > 0 ? "var(--down)" : undefined }}>
          {report.summary.blocker_count}
        </dd>
        <dt>Warnings</dt>
        <dd style={{ color: report.summary.warning_count > 0 ? "var(--warn)" : undefined }}>
          {report.summary.warning_count}
        </dd>
        <dt>Passed</dt>
        <dd>{report.summary.pass_count}</dd>
        <dt>Allocation</dt>
        <dd>{report.summary.allocation_enabled ? "enabled" : "independent (off)"}</dd>
        <dt>Fingerprint</dt>
        <dd>{report.composition_fingerprint ? <code>{report.composition_fingerprint}</code> : EM_DASH}</dd>
      </dl>

      <div style={{ marginTop: 16 }}>
        <IssuesTable issues={report.issues} />
      </div>
    </section>
  );
}

function IssuesTable({ issues }: { issues: ReadinessIssue[] }) {
  if (issues.length === 0) {
    return (
      <EmptyState
        glyph="✓"
        title="No blockers or warnings"
        description="Every enabled composition item passed. The composition is ready to admit a run."
      />
    );
  }
  return (
    <table className="metrics-table">
      <thead>
        <tr>
          <th>Severity</th>
          <th>Code</th>
          <th>Scope</th>
          <th>Detail</th>
        </tr>
      </thead>
      <tbody>
        {issues.map((issue, index) => (
          <tr key={`${issue.code}-${issue.scope_id ?? index}`}>
            <td>
              <StatusBadge tone={severityTone(issue.severity)} label={issue.severity} />
            </td>
            <td>
              <code>{issue.code}</code>
            </td>
            <td>
              {issue.scope}
              {issue.scope_id ? (
                <div style={{ fontSize: 12, color: "var(--text-dim)" }}>
                  <code>{issue.scope_id}</code>
                </div>
              ) : null}
              {issue.field_path ? (
                <div style={{ fontSize: 12, color: "var(--text-dim)" }}>{issue.field_path}</div>
              ) : null}
            </td>
            <td>
              <div>{issue.message}</div>
              {issue.remediation ? (
                <div style={{ fontSize: 12, color: "var(--text-dim)", marginTop: 4 }}>
                  {issue.remediation}
                </div>
              ) : null}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
