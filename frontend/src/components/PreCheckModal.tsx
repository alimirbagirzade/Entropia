import { useState } from "react";

import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { Modal } from "@/components/Modal";
import { StatusBadge } from "@/components/StatusBadge";
import { ApiError } from "@/lib/apiClient";
import { formatUtc } from "@/lib/backtest";
import {
  asRecordArray,
  packageActionAvailability,
  scanStatusTone,
  useDependencyScan,
  useRunPrecheck,
  type MissingCall,
  type PackageRequestDetail,
  type ResolvedRef,
  type ScanSummary,
} from "@/lib/createPackage";

// UI-07 — Pre-Check as a keyboard-accessible overlay opened from the Create
// Package workspace (the v18 prototype's cpRunPreCheck "TA PRE-CHECK RESULT"
// overlay), NOT a separate route. The `/packages/pre-check` route survives as the
// standalone request-picker fallback (PreCheck.tsx); this modal is the primary
// in-context workflow — the request is already selected in the workspace, so the
// user never has to walk a request table and re-select the package.
//
// The scan stays SERVER-authoritative (doc 07): unlike the prototype, which
// detected TA calls with a browser regex, this runs the real dependency scan and
// renders only the immutable projection — every resolved/missing row and its
// passed/blocked/failed/warning status is authored server-side. Running Pre-Check
// carries the request row_version as the X-Request-Version OCC token and a fresh
// Idempotency-Key (the useRunPrecheck hook is reused unchanged).

// The canonical error envelope surfaces verbatim (mirrors CreatePackage /
// PreCheck) — the client never invents a Pre-Check domain message.
function mutationErrorText(error: unknown): string {
  if (error instanceof ApiError) return `${error.code}: ${error.message}`;
  return error instanceof Error ? error.message : "Request failed.";
}

// Canonical doc 07 §7.2 status-line text per terminal scan status; any other
// status falls back to the wire value rendered verbatim.
const STATUS_LINES: Record<string, string> = {
  passed: "Pre-Check passed. Dependency manifest is ready for candidate generation.",
  blocked:
    "Pre-Check blocked. Resolve the listed Embedded System Package dependencies and run it again.",
  not_applicable: "Pre-Check not applicable — Generate From Description carries no code.",
};

const STALE_LINE = "Pre-Check is stale because the source changed. Run it again before sending.";

export function PreCheckModal({
  detail,
  onClose,
}: {
  detail: PackageRequestDetail;
  onClose: () => void;
}) {
  const precheck = useRunPrecheck();
  const [scanId, setScanId] = useState<string | null>(null);
  const scan = detail.current_scan;
  const actions = packageActionAvailability(detail);
  // A passed scan that no longer certifies the current source (server-truth flag).
  const isStale = scan !== null && scan.status === "passed" && !detail.precheck_fresh;

  return (
    <Modal open onClose={onClose} titleId="precheck-modal-title" wide>
      <div className="ready-check-modal">
        <div className="ready-check-modal-head">
          <h2 id="precheck-modal-title" className="modal-title">
            TA Pre-Check Result
          </h2>
          {/* The status pill is the direct visual link to the Package Status TA
              Pre-Check row (passed / blocked / failed / warning / not_checked). */}
          {scan ? (
            <StatusBadge
              tone={scanStatusTone(scan.status)}
              label={`${scan.status}${detail.precheck_fresh ? "" : " · stale"}`}
            />
          ) : (
            <StatusBadge tone="neutral" label="not_checked" />
          )}
        </div>

        <p className="cp-note" style={{ marginTop: 0 }}>
          Resolve <code>{detail.request_id}</code>'s declared canonical TA calls against the trusted
          Embedded System Package registry. Each run writes an immutable scan artifact pinning exact
          revisions; candidate generation is gated on a fresh passed scan server-side.
        </p>

        {isStale ? (
          <p role="alert" style={{ color: "var(--warn)", margin: "0 0 10px" }}>
            {STALE_LINE}
          </p>
        ) : null}

        <div className="ready-check-run-row">
          <span className="cp-note" style={{ margin: 0 }}>
            {actions.precheck
              ? "Re-scan this request's dependencies."
              : "Pre-Check is frozen for this flow state — the current scan is read-only."}
          </span>
          <button
            type="button"
            className="btn btn-primary"
            disabled={!actions.precheck || precheck.isPending}
            onClick={() =>
              precheck.mutate({
                request_id: detail.request_id,
                request_version: detail.request_version,
              })
            }
          >
            {precheck.isPending ? "Checking dependencies…" : "Run Pre-Check"}
          </button>
        </div>

        {precheck.isError ? (
          <p role="alert" style={{ color: "var(--down)", margin: "0 0 10px" }}>
            {mutationErrorText(precheck.error)}
          </p>
        ) : null}
        {precheck.data ? (
          <p aria-live="polite" style={{ margin: "0 0 10px" }}>
            {STATUS_LINES[precheck.data.status] ?? `Pre-Check ${precheck.data.status}.`} (scan{" "}
            <code>{precheck.data.scan_id}</code>, attempt {precheck.data.attempt_no})
          </p>
        ) : null}

        {scan ? (
          <>
            <ScanResultRows scan={scan} />
            <div style={{ display: "flex", gap: 12, marginTop: 12 }}>
              <button
                type="button"
                className="btn"
                aria-pressed={scanId === scan.scan_id}
                onClick={() => setScanId(scan.scan_id)}
              >
                View scan artifact
              </button>
            </div>
            {scanId !== null ? <ScanViewer scanId={scanId} /> : null}
          </>
        ) : (
          <p className="cp-note" style={{ marginTop: 12 }}>
            No Pre-Check scan yet for this request. Run Pre-Check to resolve its code TA calls.
          </p>
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

// Dependency result rows (doc 07 §7.1): each row carries the literal Resolved /
// Missing text — never color/checkmark alone — and every value is rendered as a
// text node (untrusted source can never inject markup).
function ScanResultRows({ scan }: { scan: ScanSummary }) {
  const resolved = asRecordArray(scan.resolved) as ResolvedRef[];
  const missing = asRecordArray(scan.missing) as MissingCall[];
  if (resolved.length === 0 && missing.length === 0) return null;
  return (
    <div style={{ marginTop: 12 }}>
      <h3 style={{ margin: "0 0 8px", fontSize: 14 }}>
        Dependency results (attempt {scan.attempt_no})
      </h3>
      <table className="metrics-table">
        <thead>
          <tr>
            <th scope="col">Result</th>
            <th scope="col">Call</th>
            <th scope="col">Detail</th>
          </tr>
        </thead>
        <tbody>
          {resolved.map((ref, index) => (
            <tr key={`resolved-${ref.canonical_key ?? index}`}>
              <td>✓ Resolved</td>
              <td>
                <code>{ref.call ?? ref.canonical_key ?? "—"}</code>
              </td>
              <td>
                Embedded System Package found: <code>{ref.embedded_entity_id ?? "—"}</code>{" "}
                (revision <code>{ref.embedded_revision_id ?? "—"}</code>)
              </td>
            </tr>
          ))}
          {missing.map((call, index) => (
            <tr key={`missing-${call.call ?? index}`}>
              <td>✕ Missing</td>
              <td>
                <code>{call.call ?? "—"}</code>
              </td>
              <td>
                {call.code ? `${call.code}: ` : ""}
                {call.message ?? "Missing canonical Embedded System Package."}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Immutable scan artifact viewer (GET /dependency-scans/{scan_id}).
function ScanViewer({ scanId }: { scanId: string }) {
  const scan = useDependencyScan(scanId);
  return (
    <div style={{ marginTop: 14 }}>
      <h3 style={{ margin: "0 0 8px", fontSize: 14 }}>Scan artifact</h3>
      {scan.isLoading ? (
        <Loading label="Loading scan…" />
      ) : scan.isError ? (
        <ErrorState error={scan.error} onRetry={() => void scan.refetch()} />
      ) : scan.data ? (
        <dl className="kv">
          <dt>Scan</dt>
          <dd>
            <code>{scan.data.scan_id}</code> (attempt {scan.data.attempt_no})
          </dd>
          <dt>Status</dt>
          <dd>
            <StatusBadge tone={scanStatusTone(scan.data.status)} label={scan.data.status} />
          </dd>
          <dt>Request</dt>
          <dd>
            <code>{scan.data.request_id}</code>
          </dd>
          <dt>Language</dt>
          <dd>{scan.data.language ?? "—"}</dd>
          <dt>Scanner</dt>
          <dd>{scan.data.scanner_version ?? "—"}</dd>
          <dt>Registry fingerprint</dt>
          <dd>
            <code>{scan.data.registry_fingerprint ?? "—"}</code>
          </dd>
          <dt>Source hash</dt>
          <dd>
            <code>{scan.data.source_hash ?? "—"}</code>
          </dd>
          <dt>Unsupported calls</dt>
          <dd>{asRecordArray(scan.data.unsupported).length}</dd>
          <dt>Job</dt>
          <dd>
            <code>{scan.data.job_id ?? "—"}</code>
          </dd>
          <dt>Completed</dt>
          <dd>{formatUtc(scan.data.completed_at)}</dd>
        </dl>
      ) : null}
    </div>
  );
}
