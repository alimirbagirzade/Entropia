import { useState } from "react";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { StatusBadge } from "@/components/StatusBadge";
import { ApiError } from "@/lib/apiClient";
import { formatUtc } from "@/lib/backtest";
import {
  asRecordArray,
  requestStateTone,
  scanStatusTone,
  useDependencyScan,
  usePackageRequest,
  usePackageRequests,
  useRunPrecheck,
  type MissingCall,
  type PackageRequestDetail,
  type ResolvedRef,
  type ScanSummary,
} from "@/lib/createPackage";

// Command failures surface the backend canonical envelope verbatim — the client
// never invents Pre-Check domain messages (mirrors CreatePackage / Panel).
function mutationErrorText(error: unknown): string {
  if (error instanceof ApiError) return `${error.code}: ${error.message}`;
  return error instanceof Error ? error.message : "Request failed.";
}

// Forward-only opaque keyset cursors (server contract): Prev replays the cursor
// stack, the client never re-orders or fabricates a page.
function useCursorStack() {
  const [stack, setStack] = useState<string[]>([]);
  const top = stack.length > 0 ? stack[stack.length - 1] : null;
  return {
    cursor: top ?? null,
    canPrev: stack.length > 0,
    next: (nextCursor: string) => setStack((prev) => [...prev, nextCursor]),
    prev: () => setStack((prev) => prev.slice(0, -1)),
  };
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

// Pre-Check (doc 07): run an immutable dependency scan for one of the actor's
// own requests, read the §7.1 dependency result rows, and open the immutable
// scan artifact viewer (GET /dependency-scans/{scan_id}). The scan is evidence —
// closing/leaving this page never cancels or mutates it.
export function PreCheck() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  return (
    <>
      <h1 className="page-title">Pre-Check</h1>
      <p className="page-sub">
        Resolve a request's declared canonical TA calls against the trusted Embedded System
        Package registry. Each run writes an immutable scan artifact pinning exact revisions;
        candidate generation is gated on a fresh passed scan server-side.
      </p>
      <RequestPickerCard selectedId={selectedId} onSelect={setSelectedId} />
      {selectedId !== null ? <PreCheckCard requestId={selectedId} /> : null}
    </>
  );
}

// ---------------------------------------------------------------------------
// Request picker — the actor's own requests (Admins see all), keyset-paged.
// ---------------------------------------------------------------------------

function RequestPickerCard({
  selectedId,
  onSelect,
}: {
  selectedId: string | null;
  onSelect: (requestId: string) => void;
}) {
  const pager = useCursorStack();
  const requests = usePackageRequests(pager.cursor);

  return (
    <section className="card" aria-labelledby="pc-requests-h">
      <h3 id="pc-requests-h" style={{ marginTop: 0 }}>
        My requests
      </h3>
      {requests.isLoading ? (
        <Loading label="Loading requests…" />
      ) : requests.isError ? (
        <ErrorState error={requests.error} onRetry={() => void requests.refetch()} />
      ) : requests.data ? (
        <>
          {requests.data.data.length === 0 ? (
            <EmptyState
              title="No requests yet"
              description="Create a request on the Create Package page first."
            />
          ) : (
            <table className="metrics-table">
              <thead>
                <tr>
                  <th scope="col">Request</th>
                  <th scope="col">Type</th>
                  <th scope="col">Source</th>
                  <th scope="col">State</th>
                  <th scope="col" />
                </tr>
              </thead>
              <tbody>
                {requests.data.data.map((req) => (
                  <tr key={req.request_id}>
                    <td>
                      <code>{req.request_id}</code>
                    </td>
                    <td>{req.package_type}</td>
                    <td>{req.source_kind}</td>
                    <td>
                      <StatusBadge tone={requestStateTone(req.state)} label={req.state} />
                    </td>
                    <td>
                      <button
                        type="button"
                        className="btn btn-ghost"
                        aria-pressed={selectedId === req.request_id}
                        onClick={() => onSelect(req.request_id)}
                      >
                        Select
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <Pager
            canPrev={pager.canPrev}
            nextCursor={requests.data.meta.cursor}
            onPrev={pager.prev}
            onNext={pager.next}
          />
        </>
      ) : null}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Pre-Check runner — status pill, run command, §7.1 dependency result rows.
// ---------------------------------------------------------------------------

function PreCheckCard({ requestId }: { requestId: string }) {
  const request = usePackageRequest(requestId);
  return (
    <section className="card" aria-labelledby="pc-run-h">
      <h3 id="pc-run-h" style={{ marginTop: 0 }}>
        Dependency scan
      </h3>
      {request.isLoading ? (
        <Loading label="Loading request…" />
      ) : request.isError ? (
        <ErrorState error={request.error} onRetry={() => void request.refetch()} />
      ) : request.data ? (
        <PreCheckBody detail={request.data} />
      ) : null}
    </section>
  );
}

function PreCheckBody({ detail }: { detail: PackageRequestDetail }) {
  const precheck = useRunPrecheck();
  const [scanId, setScanId] = useState<string | null>(null);
  const scan = detail.current_scan;
  const isStale = scan !== null && scan.status === "passed" && !detail.precheck_fresh;

  return (
    <>
      <dl className="kv">
        <dt>Request</dt>
        <dd>
          <code>{detail.request_id}</code>
        </dd>
        <dt>State</dt>
        <dd>
          <StatusBadge tone={requestStateTone(detail.state)} label={detail.state} />
        </dd>
        <dt>Source</dt>
        <dd>
          {detail.source_kind}
          {detail.source_language ? ` · ${detail.source_language}` : ""} → {detail.target_runtime}
        </dd>
        <dt>TA Pre-Check</dt>
        <dd>
          {scan ? (
            <StatusBadge tone={scanStatusTone(scan.status)} label={scan.status} />
          ) : (
            <StatusBadge tone="neutral" label="not_checked" />
          )}
        </dd>
        <dt>Fresh</dt>
        <dd>{detail.precheck_fresh ? "yes" : "no"}</dd>
      </dl>

      {isStale ? (
        <p role="alert" style={{ color: "var(--warn)" }}>
          {STALE_LINE}
        </p>
      ) : null}

      <div style={{ display: "flex", gap: 12, marginTop: 10 }}>
        <button
          type="button"
          className="btn btn-primary"
          disabled={precheck.isPending}
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
        <p role="alert" style={{ color: "var(--down)", marginBottom: 0 }}>
          {mutationErrorText(precheck.error)}
        </p>
      ) : null}
      {precheck.data ? (
        <p aria-live="polite" style={{ marginBottom: 0 }}>
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
        </>
      ) : (
        <p className="cp-note" style={{ marginTop: 12, marginBottom: 0 }}>
          No Pre-Check scan yet for this request.
        </p>
      )}

      {scanId !== null ? <ScanViewer scanId={scanId} /> : null}
    </>
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
      <h4 style={{ margin: "0 0 8px" }}>Dependency results (attempt {scan.attempt_no})</h4>
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

// ---------------------------------------------------------------------------
// Immutable scan artifact viewer (GET /dependency-scans/{scan_id}).
// ---------------------------------------------------------------------------

function ScanViewer({ scanId }: { scanId: string }) {
  const scan = useDependencyScan(scanId);
  return (
    <div style={{ marginTop: 14 }}>
      <h4 style={{ margin: "0 0 8px" }}>Scan artifact</h4>
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
          <dt>Context hash</dt>
          <dd>
            <code>{scan.data.context_hash ?? "—"}</code>
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

function Pager({
  canPrev,
  nextCursor,
  onPrev,
  onNext,
}: {
  canPrev: boolean;
  nextCursor: string | null;
  onPrev: () => void;
  onNext: (cursor: string) => void;
}) {
  if (!canPrev && nextCursor === null) return null;
  return (
    <div style={{ display: "flex", gap: 12, marginTop: 12 }}>
      <button type="button" className="btn" disabled={!canPrev} onClick={onPrev}>
        Prev
      </button>
      <button
        type="button"
        className="btn"
        disabled={nextCursor === null}
        onClick={() => (nextCursor !== null ? onNext(nextCursor) : undefined)}
      >
        Next
      </button>
    </div>
  );
}
