import { useState } from "react";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { Modal } from "@/components/Modal";
import { StatusBadge } from "@/components/StatusBadge";
import { ApiError } from "@/lib/apiClient";
import {
  type CurrentReadiness,
  type ReadinessIssue,
  type ReadinessReport,
  type ReadinessSummary,
  readinessStateLabel,
  readinessStateTone,
  useCurrentReadiness,
  useRunReadinessCheck,
} from "@/lib/readiness";

// UI-14 — Backtest Ready Check as a modal opened from the Mainboard's fixed
// lower-right Ready Check/RUN shell (the v18 prototype's runBacktestReadyCheck /
// showBacktestReadyReport overlay), NOT a separate route. The `/backtest/ready-check`
// route survives as the immutable ?report= deep-link fallback (ReadyCheck.tsx);
// this modal is the primary in-context workflow.
//
// Readiness stays SERVER-authoritative (doc 14 §3.2/§12.2) — unlike the prototype
// which computed passed/failed/warnings in the browser. The three columns are
// derived from the immutable report projection only: Passed = summary.pass_count
// (a count; the server emits no per-pass strings, so the client never fabricates
// them, L4), Failed = the blocker issues, Warnings = the warning issues. Every
// issue string is authored server-side and rendered verbatim.

// The canonical error envelope is surfaced verbatim (mirrors ReadyCheck.tsx /
// BacktestRun) — the client never invents a readiness-domain message. A stale
// composition guard mismatch arrives as 409 CompositionStale (RC-09).
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
// get_readiness_report projection at runtime (doc 14 §9.1). The ?? are inert
// TS-narrowing fallbacks, never fabricated data.
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

export function ReadyCheckModal({
  compositionId,
  currentFingerprint,
  onClose,
}: {
  compositionId: string | null;
  currentFingerprint: string | null;
  onClose: () => void;
}) {
  const readiness = useCurrentReadiness(compositionId);
  const runCheck = useRunReadinessCheck();
  // Guard: pass the loaded fingerprint as the OCC token so a run refuses (409
  // CompositionStale) if the composition changed since this modal opened.
  const [guard, setGuard] = useState(false);

  const report = readiness.data ? currentAsReport(readiness.data) : null;

  // Running the check is an explicit user action, not an on-open side effect: each
  // run mints a NEW immutable report + audit row (RC-18), so the modal shows the
  // latest current readiness and lets the user re-run deliberately.
  function runReadyCheck() {
    if (compositionId === null) return;
    runCheck.mutate({
      compositionId,
      ...(guard && currentFingerprint !== null ? { expectedFingerprint: currentFingerprint } : {}),
    });
  }

  return (
    <Modal open onClose={onClose} titleId="ready-check-modal-title" wide>
      <div className="ready-check-modal">
        <div className="ready-check-modal-head">
          <h2 id="ready-check-modal-title" className="modal-title">
            Backtest Ready Check
          </h2>
          {report ? (
            <StatusBadge
              tone={readinessStateTone(report.state)}
              label={readinessStateLabel(report.state)}
            />
          ) : null}
        </div>

        <div className="ready-check-run-row">
          <label className="ready-check-guard">
            <input
              type="checkbox"
              checked={guard}
              disabled={currentFingerprint === null}
              onChange={(event) => setGuard(event.target.checked)}
            />
            Guard: fail if the composition changed since this check opened
          </label>
          <button
            type="button"
            className="btn btn-primary"
            disabled={runCheck.isPending || compositionId === null}
            onClick={runReadyCheck}
          >
            {runCheck.isPending ? "Running check…" : "Run Ready Check"}
          </button>
        </div>
        {runCheck.isError ? (
          <p role="alert" style={{ color: "var(--down)", margin: "0 0 10px" }}>
            {mutationErrorText(runCheck.error)}
          </p>
        ) : null}

        {readiness.isLoading ? (
          <Loading label="Loading readiness…" />
        ) : readiness.isError ? (
          <ErrorState error={readiness.error} onRetry={() => void readiness.refetch()} />
        ) : (
          <ReadyReportGrid report={report} />
        )}

        <div className="ready-check-actions">
          <button type="button" className="page-button" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </Modal>
  );
}

// The documented three-column Passed / Failed / Warnings layout (v18
// showBacktestReadyReport). Failed/Warnings render the real issue rows split by
// severity (doc 14 §9.1: severity is only blocker | warning); Passed shows the
// server pass_count — there is no per-pass string to invent (L4).
function ReadyReportGrid({ report }: { report: ReadinessReport | null }) {
  const blockers = report?.issues.filter((issue) => issue.severity === "blocker") ?? [];
  const warnings = report?.issues.filter((issue) => issue.severity === "warning") ?? [];
  const passCount = report?.summary.pass_count ?? 0;

  if (report === null) {
    return (
      <EmptyState
        glyph="✓"
        title="Not checked yet"
        description="Run a Ready Check to validate the composition and surface any blockers or warnings."
      />
    );
  }

  return (
    <div className="ready-report-grid" role="group" aria-label="Ready Check report">
      <section className="ready-report-card" aria-label="Passed">
        <h3>Passed</h3>
        {passCount > 0 ? (
          <p className="ready-pass">
            ✓ {passCount} check{passCount === 1 ? "" : "s"} passed.
          </p>
        ) : (
          <p className="ready-report-empty">No passed check yet.</p>
        )}
      </section>

      <section className="ready-report-card" aria-label="Failed">
        <h3>Failed</h3>
        {blockers.length === 0 ? (
          <p className="ready-pass">✓ No blocking issue detected.</p>
        ) : (
          blockers.map((issue, index) => (
            <IssueLine key={issueKey(issue, index)} issue={issue} kind="fail" />
          ))
        )}
      </section>

      <section className="ready-report-card" aria-label="Warnings">
        <h3>Warnings</h3>
        {warnings.length === 0 ? (
          <p className="ready-report-empty">No warnings.</p>
        ) : (
          warnings.map((issue, index) => (
            <IssueLine key={issueKey(issue, index)} issue={issue} kind="warn" />
          ))
        )}
      </section>
    </div>
  );
}

function issueKey(issue: ReadinessIssue, index: number): string {
  return `${issue.code}-${issue.scope_id ?? index}`;
}

function IssueLine({ issue, kind }: { issue: ReadinessIssue; kind: "fail" | "warn" }) {
  return (
    <div className={kind === "fail" ? "ready-fail" : "ready-warn"}>
      <span className="ready-issue-message">
        {kind === "fail" ? "✗ " : "! "}
        {issue.message}
      </span>
      <span className="ready-issue-meta">
        <code>{issue.code}</code>
        {issue.scope ? ` · ${issue.scope}` : ""}
      </span>
      {issue.remediation ? (
        <span className="ready-issue-remediation">{issue.remediation}</span>
      ) : null}
    </div>
  );
}
