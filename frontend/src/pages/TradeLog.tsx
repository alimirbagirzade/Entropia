import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { StatusBadge } from "@/components/StatusBadge";
import { ApiError } from "@/lib/apiClient";
import { EM_DASH, useDefaultMainboard } from "@/lib/backtest";
import {
  type CreateTradeLogResult,
  type CreateTradeLogRevisionResult,
  type ExportTradeLogResult,
  type TradeLogDetail,
  type TradeLogImportReport,
  buildTradeLogPayloadTemplate,
  mappingHashFromSummary,
  parseColumnMapping,
  useCreateTradeLog,
  useCreateTradeLogRevision,
  useExportTradeLog,
  useRequestTradeLogImport,
  useTradeLog,
  useTradeLogImportReport,
  useUploadTradeLogSource,
} from "@/lib/tradeLog";

// UI-05 — the doc 05 §3 Trade Log is the near-symmetric twin of the Trading
// Signal page (UI-04): a 2-column inline panel (TRADE LOG SOURCE / BULK TRADE
// LOG IMPORT) closed by a sticky bottom toolbar (mockup .details-grid +
// .panel-actions), reusing the UI-02 column/card/toolbar shell. Every hook /
// OCC token / Idempotency header / query key below is UNCHANGED from
// lib/tradeLog.ts — only the visual grouping (identity + source config on the
// left, the TXT/CSV file + read-only format guide on the right, primary actions
// in a sticky toolbar) is new. The source-import chain (upload an immutable
// TXT/CSV asset → durable 202 import job → import report → Save & Add as a
// native work object) is unchanged. Twin diff vs Trading Signal: the produced
// object is a record batch and a Trade Log is HISTORICAL data — its revisions
// carry no available_time (doc 05 §10.4).

// Failures surface the backend canonical envelope verbatim — the client never
// invents trade-log-domain messages (422 config blockers arrive in error.details).
function mutationErrorText(error: unknown): string {
  if (error instanceof ApiError) return `${error.code}: ${error.message}`;
  return error instanceof Error ? error.message : "Request failed.";
}

function importStatusTone(status: string): "ok" | "warn" | "down" | "neutral" {
  if (status === "succeeded") return "ok";
  if (status === "failed" || status === "failed_final" || status === "cancelled") return "down";
  if (status === "running" || status === "claimed") return "warn";
  return "neutral";
}

const preStyle = {
  whiteSpace: "pre-wrap",
  overflowX: "auto",
  background: "var(--bg-elev-2)",
  padding: 12,
  borderRadius: 8,
  fontSize: 13,
  margin: 0,
} as const;

const SKIPPED_ROWS_SHOWN = 20;

// Read-only column guidance (mockup .trading-data-format-box for the Trade Log
// panel). Canonical trade-record set per doc 05 — a Trade Log revision carries
// at least these entry/exit fields; the browser parser is never the authority.
// No available_time: a Trade Log is historical ledger data (doc 05 §10.4).
const TRADE_LOG_FORMAT_GUIDE = `Required columns:
direction, entry_time, entry_price, exit_time, exit_price

Optional columns:
size, fees, pnl, symbol, open, high, low, close, volume

Accepted separators:
comma, semicolon, tab or |

Example:
Long,2024-01-01 10:00,42100,2024-01-01 15:30,42850,1.0,2.1,750,BTCUSDT
Short,2024-01-02 09:15,43000,2024-01-02 18:00,41950,1.0,2.4,1050,BTCUSDT`;

// Trade Log (Stage 3d, doc 05 §8–§10). URL modes: ?job= (durable import handle,
// CR-09) and ?root= (work-object detail + revision composer). Pin ("Use This
// Revision") and delete are Mainboard operations (CR-01, TL-01).
export function TradeLog() {
  const [searchParams, setSearchParams] = useSearchParams();
  const rootParam = searchParams.get("root");
  const jobParam = searchParams.get("job");

  return (
    <>
      <h1 className="page-title">Trade Log</h1>
      <p className="page-sub">
        Import a historical trade ledger from a TXT/CSV file, review the canonical record batch,
        and save the Trade Log as a native work object on the Mainboard
      </p>

      {rootParam !== null ? (
        <DetailView rootId={rootParam} />
      ) : (
        <Workbench jobId={jobParam} onJobAccepted={(id) => setSearchParams({ job: id })} />
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Workbench: the 2-column source/import panel. Mutations and the shared
// instrument/timezone state live HERE so results survive child remounts and
// the report can seed the create editor.
// ---------------------------------------------------------------------------

function Workbench({
  jobId,
  onJobAccepted,
}: {
  jobId: string | null;
  onJobAccepted: (jobId: string) => void;
}) {
  const [sourceAssetId, setSourceAssetId] = useState("");
  const [instrumentId, setInstrumentId] = useState("");
  const [sourceTimezone, setSourceTimezone] = useState("UTC");

  const upload = useUploadTradeLogSource();
  const requestImport = useRequestTradeLogImport();
  const create = useCreateTradeLog();
  const report = useTradeLogImportReport(jobId);

  const reportData = report.data ?? null;
  const succeededReport =
    reportData !== null &&
    reportData.status === "succeeded" &&
    reportData.record_batch_revision_id !== null
      ? reportData
      : null;
  const importReady = succeededReport !== null;

  // Seed the payload editor from the succeeded import; blank binding otherwise
  // (the server compiler rejects it verbatim — the editor stays usable).
  const template = buildTradeLogPayloadTemplate({
    sourceAssetId: succeededReport?.source_asset_id ?? sourceAssetId,
    recordBatchRevisionId: succeededReport?.record_batch_revision_id ?? "",
    instrumentId: succeededReport?.instrument_id ?? instrumentId,
    sourceTimezone,
    mappingRevisionId: mappingHashFromSummary(succeededReport?.validation_summary ?? null),
  });

  return (
    <>
      {/* v18 two-column inline panel: TRADE LOG SOURCE | BULK IMPORT. */}
      <div className="details-grid two-col">
        <div className="details-column">
          <div className="column-title">Trade Log Source</div>
          <ImportIdentityCard
            sourceAssetId={sourceAssetId}
            instrumentId={instrumentId}
            sourceTimezone={sourceTimezone}
            requesting={requestImport.isPending}
            onSourceAssetId={setSourceAssetId}
            onInstrumentId={setInstrumentId}
            onSourceTimezone={setSourceTimezone}
            onRequest={(importMapping) =>
              requestImport.mutate(
                { sourceAssetId, instrumentId, sourceTimezone, importMapping },
                { onSuccess: (result) => onJobAccepted(result.job_id) },
              )
            }
          />
          {requestImport.isError ? <MutationErrorCard error={requestImport.error} /> : null}
        </div>

        <div className="details-column">
          <div className="column-title">Bulk Trade Log Import</div>
          <FileUploadCard
            pending={upload.isPending}
            result={upload.data ?? null}
            error={upload.isError ? upload.error : null}
            onUpload={(file) =>
              upload.mutate(
                { file },
                { onSuccess: (result) => setSourceAssetId(result.source_asset_id) },
              )
            }
          />
        </div>
      </div>

      {jobId !== null ? (
        <ImportReportCard
          jobId={jobId}
          report={reportData}
          isLoading={report.isLoading}
          isError={report.isError}
          error={report.error}
          onRetry={() => void report.refetch()}
        />
      ) : null}

      <CreatePanel
        key={succeededReport?.record_batch_revision_id ?? "blank"}
        template={template}
        importReady={importReady}
        pending={create.isPending}
        onCreate={(payload, attach) => create.mutate({ payload, attach })}
      />
      {create.isError ? <MutationErrorCard error={create.error} /> : null}
      {create.data ? <CreateResultCard result={create.data} /> : null}

      <AttachedTradeLogsCard />
    </>
  );
}

// Card 1 (SOURCE column) — trade-log identity + source configuration. The
// source asset id is auto-filled by the file upload on the right; instrument
// and timezone are the canonical mapping inputs. The optional column mapping
// and the "Request import" action close the card (mockup §1 IDENTITY + §2 SOURCE).
function ImportIdentityCard({
  sourceAssetId,
  instrumentId,
  sourceTimezone,
  requesting,
  onSourceAssetId,
  onInstrumentId,
  onSourceTimezone,
  onRequest,
}: {
  sourceAssetId: string;
  instrumentId: string;
  sourceTimezone: string;
  requesting: boolean;
  onSourceAssetId: (value: string) => void;
  onInstrumentId: (value: string) => void;
  onSourceTimezone: (value: string) => void;
  onRequest: (importMapping: Record<string, string>) => void;
}) {
  const [mappingText, setMappingText] = useState("");
  return (
    <form
      className="detail-card"
      aria-labelledby="tl-identity-h"
      onSubmit={(event) => {
        event.preventDefault();
        onRequest(parseColumnMapping(mappingText));
      }}
    >
      <h3 id="tl-identity-h" className="detail-card-title">
        1. Trade Log Identity
      </h3>
      <p className="cp-note" style={{ marginTop: 0 }}>
        Enqueues a durable normalization job on the data queue (202) — the report below stays
        reachable through its job URL even after the browser closes (TL-14).
      </p>
      <div className="strategy-form-grid">
        <label className="cp-field">
          <span>Source asset id</span>
          <input
            value={sourceAssetId}
            onChange={(event) => onSourceAssetId(event.target.value)}
            placeholder="srcasset_…"
            required
          />
        </label>
        <label className="cp-field">
          <span>Instrument id</span>
          <input
            value={instrumentId}
            onChange={(event) => onInstrumentId(event.target.value)}
            placeholder="BTCUSDT"
            required
          />
        </label>
        <label className="cp-field">
          <span>Source timezone</span>
          <input
            value={sourceTimezone}
            onChange={(event) => onSourceTimezone(event.target.value)}
            required
          />
        </label>
      </div>

      <h4 className="detail-card-title" style={{ marginTop: 14, marginBottom: 6 }}>
        2. Source Data Mapping
      </h4>
      <label className="cp-field cp-wide">
        <span>Column mapping (optional) — one “canonical_field = source_header” per line</span>
        <textarea
          rows={4}
          value={mappingText}
          onChange={(event) => setMappingText(event.target.value)}
          spellCheck={false}
          placeholder={"entry_time = Open Time\nexit_time = Close Time"}
        />
        <small className="cp-note">
          Leave blank when the file uses the canonical headers (or a known alias). The server never
          infers an ambiguous mapping — map each canonical field explicitly to resolve it.
        </small>
      </label>
      <div style={{ marginTop: 10 }}>
        <button className="btn btn-primary" type="submit" disabled={requesting}>
          {requesting ? "Requesting…" : "Request import"}
        </button>
      </div>
    </form>
  );
}

// Card 3 (BULK IMPORT column) — the real TXT/CSV file chooser (F-03) + a
// read-only monospace format guide. The system never accepts a paste box; only
// this file selector supplies data (mockup §3 TXT / CSV FILE).
function FileUploadCard({
  pending,
  result,
  error,
  onUpload,
}: {
  pending: boolean;
  result: {
    source_asset_id: string;
    raw_asset_hash: string;
    size_bytes: number;
    deduplicated: boolean;
  } | null;
  error: unknown;
  onUpload: (file: File) => void;
}) {
  const [file, setFile] = useState<File | null>(null);

  return (
    <div className="detail-card" aria-labelledby="tl-upload-h">
      <h3 id="tl-upload-h" className="detail-card-title">
        3. Trade Log TXT / CSV File
      </h3>
      <p className="cp-note" style={{ marginTop: 0 }}>
        Select a UTF-8 TXT/CSV trade-record file — the browser transfers the file itself. The asset
        is immutable and content-addressed (an identical re-upload reuses the prior asset, TL-15);
        size, encoding, and schema are validated on the server.
      </p>
      <form
        className="cp-form"
        onSubmit={(event) => {
          event.preventDefault();
          if (file) onUpload(file);
        }}
      >
        <label className="cp-field cp-wide">
          <span>Trade-record file (.txt / .csv)</span>
          <input
            type="file"
            accept=".txt,.csv,text/plain,text/csv"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
        </label>
        {file ? (
          <p className="cp-note" style={{ marginTop: 0 }}>
            Selected <code>{file.name}</code> ({file.size} bytes)
          </p>
        ) : null}
        <div className="cp-field cp-wide">
          <button className="btn btn-primary" type="submit" disabled={pending || !file}>
            {pending ? "Uploading…" : "Upload source asset"}
          </button>
        </div>
      </form>

      {error ? <MutationErrorCard error={error} /> : null}
      {result ? (
        <p className="cp-note" style={{ marginTop: 12 }}>
          {result.deduplicated
            ? "Identical content already uploaded — reusing the prior source asset "
            : "Source asset stored "}
          <code>{result.source_asset_id}</code> ({result.size_bytes} bytes,{" "}
          <code>{result.raw_asset_hash}</code>)
        </p>
      ) : null}

      <div className="format-guide">{TRADE_LOG_FORMAT_GUIDE}</div>
      <p className="format-note">
        The content format above is read-only guidance — the system does not use a paste box here;
        the required data must be supplied through the TXT / CSV file selector. A Trade Log is
        historical ledger data — its revisions carry no <code>available_time</code> lookahead guard
        (doc 05 §10.4).
      </p>
    </div>
  );
}

function ImportReportCard({
  jobId,
  report,
  isLoading,
  isError,
  error,
  onRetry,
}: {
  jobId: string;
  report: TradeLogImportReport | null;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  onRetry: () => void;
}) {
  return (
    <section className="card" style={{ marginTop: 18 }} aria-labelledby="tl-report-h">
      <h3 id="tl-report-h" style={{ marginTop: 0 }}>
        Import report
      </h3>
      {isLoading ? (
        <Loading label="Loading import report…" />
      ) : isError ? (
        <ErrorState error={error} onRetry={onRetry} />
      ) : report !== null ? (
        <>
          {/* v18 mockup: the import report reads as a bordered wireframe table.
              Twin diff vs Trading Signal — the produced object is a record batch. */}
          <table className="metrics-table">
            <tbody>
              <tr>
                <th scope="row">Job</th>
                <td>
                  <code>{jobId}</code>
                </td>
              </tr>
              <tr>
                <th scope="row">Status</th>
                <td>
                  <StatusBadge label={report.status} tone={importStatusTone(report.status)} />
                </td>
              </tr>
              <tr>
                <th scope="row">Record batch</th>
                <td>
                  {report.record_batch_revision_id !== null ? (
                    <code>{report.record_batch_revision_id}</code>
                  ) : (
                    "not produced yet"
                  )}
                </td>
              </tr>
              <tr>
                <th scope="row">Accepted / skipped</th>
                <td>
                  {report.accepted_count} / {report.skipped_count}
                </td>
              </tr>
              <tr>
                <th scope="row">Content hash</th>
                <td>{report.content_hash ? <code>{report.content_hash}</code> : EM_DASH}</td>
              </tr>
            </tbody>
          </table>
          {report.validation_summary !== null ? (
            <pre style={{ ...preStyle, marginTop: 12 }}>
              {JSON.stringify(report.validation_summary, null, 2)}
            </pre>
          ) : null}
          <SkippedRows rows={report.skipped_rows} skippedCount={report.skipped_count} />
        </>
      ) : null}
    </section>
  );
}

function SkippedRows({
  rows,
  skippedCount,
}: {
  rows: Array<Record<string, unknown>>;
  skippedCount: number;
}) {
  if (rows.length === 0) return null;
  const shown = rows.slice(0, SKIPPED_ROWS_SHOWN);
  return (
    <>
      <h4 style={{ marginBottom: 6 }}>Skipped rows</h4>
      <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13 }}>
        {shown.map((row, index) => (
          <li key={index}>
            <code>{JSON.stringify(row)}</code>
          </li>
        ))}
      </ul>
      {skippedCount > shown.length ? (
        <p className="cp-note" style={{ marginTop: 8 }}>
          Showing {shown.length} of {skippedCount} skipped rows (the report itself carries at most
          200).
        </p>
      ) : null}
    </>
  );
}

// Raw JSON payload editor (Strategy precedent): parse failures stay
// client-side; the server compiler is the sole authority on config semantics.
// The primary Save action lives in a sticky bottom toolbar (mockup
// .panel-actions "Save As Trade Log Package").
function CreatePanel({
  template,
  importReady,
  pending,
  onCreate,
}: {
  template: Record<string, unknown>;
  importReady: boolean;
  pending: boolean;
  onCreate: (payload: Record<string, unknown>, attach: boolean) => void;
}) {
  const [text, setText] = useState(() => JSON.stringify(template, null, 2));
  const [attach, setAttach] = useState(true);
  const [parseError, setParseError] = useState<string | null>(null);

  const submit = () => {
    try {
      const parsed: unknown = JSON.parse(text);
      if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
        setParseError("The payload must be a JSON object.");
        return;
      }
      setParseError(null);
      onCreate(parsed as Record<string, unknown>, attach);
    } catch (error) {
      setParseError(error instanceof Error ? error.message : "Invalid JSON.");
    }
  };

  return (
    <>
      <section className="card" style={{ marginTop: 18 }} aria-labelledby="tl-create-h">
        <h3 id="tl-create-h" style={{ marginTop: 0 }}>
          Create Trade Log
        </h3>
        <p className="cp-note">
          Requires a succeeded, non-empty record batch — the payload below is seeded from the report
          once available. Save is never a Ready PASS; with “attach” on (Save &amp; Add) the object
          joins the default Mainboard and the prior Ready report goes STALE.
          {importReady ? "" : " Complete an import above to seed the binding."}
        </p>
        <label className="cp-field cp-wide">
          <span>TradeLogConfig payload</span>
          <textarea
            rows={16}
            value={text}
            onChange={(event) => setText(event.target.value)}
            spellCheck={false}
          />
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 10 }}>
          <input
            type="checkbox"
            checked={attach}
            onChange={(event) => setAttach(event.target.checked)}
          />
          <span>Attach to the default Mainboard (Save &amp; Add)</span>
        </label>
        {parseError !== null ? (
          <p role="alert" style={{ color: "var(--down)", marginBottom: 0 }}>
            Not sent — invalid JSON: {parseError}
          </p>
        ) : null}
      </section>

      {/* Sticky bottom toolbar — primary Save action (mockup .panel-actions). */}
      <div className="panel-actions">
        <div className="panel-actions-title">Save / Package Actions</div>
        <button
          type="button"
          className="panel-action-button primary"
          disabled={pending}
          onClick={submit}
        >
          {pending ? "Saving…" : "Save Trade Log"}
        </button>
      </div>
    </>
  );
}

function CreateResultCard({ result }: { result: CreateTradeLogResult }) {
  return (
    <section className="card" style={{ marginTop: 18 }} aria-labelledby="tl-created-h">
      <h3 id="tl-created-h" style={{ marginTop: 0 }}>
        Trade Log saved
      </h3>
      <dl className="kv">
        <dt>Root</dt>
        <dd>
          <Link to={`/trade-log?root=${encodeURIComponent(result.root_id)}`}>
            <code>{result.root_id}</code>
          </Link>
        </dd>
        <dt>Revision</dt>
        <dd>
          <code>{result.revision_id}</code> (#{result.revision_no})
        </dd>
        <dt>Config hash</dt>
        <dd>
          <code>{result.config_hash}</code>
        </dd>
        <dt>Attached</dt>
        <dd>
          {result.attached
            ? `yes — item ${result.item_id ?? EM_DASH} on workspace ${result.workspace_id ?? EM_DASH}`
            : "no (Save only)"}
        </dd>
        <dt>Ready state</dt>
        <dd>
          <StatusBadge label={result.ready_state} tone="warn" />
        </dd>
      </dl>
      <p className="cp-note" style={{ marginTop: 10 }}>
        Save is never a Ready PASS — re-run the Backtest Ready Check before RUN.
      </p>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Discovery: trade-log items attached to the default Mainboard (the Strategy
// page pattern). A saved but never-attached object stays reachable through
// its create-result ?root= link.
// ---------------------------------------------------------------------------

function AttachedTradeLogsCard() {
  const mainboard = useDefaultMainboard();
  const tradeLogItems = (mainboard.data?.items ?? []).filter(
    (item) => item.item_kind === "trade_log",
  );

  return (
    <section className="card" style={{ marginTop: 18 }} aria-labelledby="tl-attached-h">
      <h3 id="tl-attached-h" style={{ marginTop: 0 }}>
        Attached trade logs
      </h3>
      {mainboard.isLoading ? (
        <Loading />
      ) : mainboard.isError ? (
        <ErrorState error={mainboard.error} onRetry={() => void mainboard.refetch()} />
      ) : tradeLogItems.length === 0 ? (
        <EmptyState
          title="No trade-log items on the default Mainboard"
          description="Saved trade logs appear here once attached to the composition."
        />
      ) : (
        <table className="metrics-table">
          <thead>
            <tr>
              <th>Label</th>
              <th>Work object root</th>
              <th>Pinned revision</th>
              <th>Enabled</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {tradeLogItems.map((item) => (
              <tr key={item.item_id}>
                <td>{item.display_label_override ?? EM_DASH}</td>
                <td>
                  <code>{item.work_object_root_id}</code>
                </td>
                <td>{item.pinned_revision_id ? <code>{item.pinned_revision_id}</code> : EM_DASH}</td>
                <td>{item.is_enabled ? "yes" : "no"}</td>
                <td>
                  <Link to={`/trade-log?root=${encodeURIComponent(item.work_object_root_id)}`}>
                    View
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Detail (?root=): work-object header + current revision + revision composer.
// The primary Save/Export actions sit in a sticky bottom toolbar; mutation
// state lives HERE so results survive the composer remount when the head moves
// (the Strategy/Portfolio lesson).
// ---------------------------------------------------------------------------

function DetailView({ rootId }: { rootId: string }) {
  const detail = useTradeLog(rootId);
  const revise = useCreateTradeLogRevision();
  const exportLog = useExportTradeLog();

  if (detail.isLoading) {
    return (
      <div className="card">
        <Loading label="Loading trade log…" />
      </div>
    );
  }
  if (detail.isError) {
    return (
      <div className="card">
        <ErrorState error={detail.error} onRetry={() => void detail.refetch()} />
      </div>
    );
  }
  const data = detail.data;
  if (!data) return null;

  const canExport = data.current_revision_id !== null;

  return (
    <>
      <DetailHeaderCard data={data} />
      {data.current_revision !== null ? <CurrentRevisionCard data={data} /> : null}
      {data.current_revision_id !== null && data.current_revision !== null ? (
        <RevisionEditor
          key={data.current_revision_id}
          headRevisionId={data.current_revision_id}
          seedPayload={data.current_revision.payload}
          savePending={revise.isPending}
          canExport={canExport}
          exportPending={exportLog.isPending}
          onSave={(payload) =>
            revise.mutate({
              rootId,
              payload,
              expectedHeadRevisionId: data.current_revision_id ?? "",
            })
          }
          onExport={() => exportLog.mutate({ rootId })}
        />
      ) : null}
      {revise.isError ? <MutationErrorCard error={revise.error} /> : null}
      {revise.data ? <RevisionResultCard result={revise.data} /> : null}
      {exportLog.isError ? <MutationErrorCard error={exportLog.error} /> : null}
      {exportLog.data ? <ExportResultCard result={exportLog.data} /> : null}
    </>
  );
}

function DetailHeaderCard({ data }: { data: TradeLogDetail }) {
  return (
    <section className="card" aria-labelledby="tl-detail-h">
      <h3 id="tl-detail-h" style={{ marginTop: 0 }}>
        Trade Log
      </h3>
      <dl className="kv">
        <dt>Root</dt>
        <dd>
          <code>{data.root_id}</code>
        </dd>
        <dt>Object kind</dt>
        <dd>
          <code>{data.object_kind}</code>
        </dd>
        <dt>Lifecycle</dt>
        <dd>{data.lifecycle_state}</dd>
        <dt>Deletion state</dt>
        <dd>{data.deletion_state}</dd>
        <dt>Current revision</dt>
        <dd>{data.current_revision_id !== null ? <code>{data.current_revision_id}</code> : EM_DASH}</dd>
        <dt>Row version</dt>
        <dd>{data.row_version}</dd>
      </dl>
      <p className="cp-note" style={{ marginTop: 10 }}>
        Pin (“Use This Revision”) and delete are Mainboard operations — a Trade Log is a work
        object, not a package.
      </p>
    </section>
  );
}

function CurrentRevisionCard({ data }: { data: TradeLogDetail }) {
  const revision = data.current_revision;
  if (revision === null) return null;
  return (
    <section className="card" style={{ marginTop: 18 }} aria-labelledby="tl-revision-h">
      <h3 id="tl-revision-h" style={{ marginTop: 0 }}>
        Current revision #{revision.revision_no}
      </h3>
      <dl className="kv">
        <dt>Revision</dt>
        <dd>
          <code>{revision.revision_id}</code>
        </dd>
        <dt>Available time</dt>
        <dd>none — historical ledger data (no anti-lookahead availability contract)</dd>
        <dt>Content hash</dt>
        <dd>
          <code>{revision.content_hash}</code>
        </dd>
      </dl>
      {revision.source_provenance !== null ? (
        <>
          <h4 style={{ marginBottom: 6 }}>Source provenance</h4>
          <pre style={preStyle}>{JSON.stringify(revision.source_provenance, null, 2)}</pre>
        </>
      ) : null}
      <h4 style={{ marginBottom: 6 }}>Canonical payload</h4>
      <pre style={preStyle}>{JSON.stringify(revision.payload, null, 2)}</pre>
    </section>
  );
}

// Revision composer + sticky bottom toolbar (Save new revision + Export As
// Package). Export As Package (doc 05 §8, §11, §13.2) produces the immutable
// source-mapping/provenance manifest for the pinned head revision — read-only,
// the button stays enabled; owner/Admin is enforced server-side (403 verbatim).
function RevisionEditor({
  headRevisionId,
  seedPayload,
  savePending,
  canExport,
  exportPending,
  onSave,
  onExport,
}: {
  headRevisionId: string;
  seedPayload: Record<string, unknown>;
  savePending: boolean;
  canExport: boolean;
  exportPending: boolean;
  onSave: (payload: Record<string, unknown>) => void;
  onExport: () => void;
}) {
  const [text, setText] = useState(() => JSON.stringify(seedPayload, null, 2));
  const [parseError, setParseError] = useState<string | null>(null);

  const submit = () => {
    try {
      const parsed: unknown = JSON.parse(text);
      if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
        setParseError("The payload must be a JSON object.");
        return;
      }
      setParseError(null);
      onSave(parsed as Record<string, unknown>);
    } catch (error) {
      setParseError(error instanceof Error ? error.message : "Invalid JSON.");
    }
  };

  return (
    <>
      <section className="card" style={{ marginTop: 18 }} aria-labelledby="tl-revise-h">
        <h3 id="tl-revise-h" style={{ marginTop: 0 }}>
          Save new revision
        </h3>
        <p className="cp-note">
          Appends immutable revision N+1 guarded by the rendered head (<code>{headRevisionId}</code>
          ) — a stale tab gets a 409, never last-write-wins. The Mainboard item is NEVER
          auto-repinned (Rule 10): use “Use This Revision” on the Mainboard to change the active
          composition. Export As Package produces the immutable source-mapping/provenance manifest
          for the pinned head — it never mutates the source (repeated clicks return the same manifest
          hash).
        </p>
        <label className="cp-field cp-wide">
          <span>Revision payload</span>
          <textarea
            rows={14}
            value={text}
            onChange={(event) => setText(event.target.value)}
            spellCheck={false}
          />
        </label>
        {parseError !== null ? (
          <p role="alert" style={{ color: "var(--down)", marginBottom: 0 }}>
            Not sent — invalid JSON: {parseError}
          </p>
        ) : null}
      </section>

      <div className="panel-actions">
        <div className="panel-actions-title">Save / Package Actions</div>
        <button
          type="button"
          className="panel-action-button primary"
          disabled={savePending}
          onClick={submit}
        >
          {savePending ? "Saving…" : "Save new revision"}
        </button>
        {canExport ? (
          <button
            type="button"
            className="panel-action-button"
            disabled={exportPending}
            onClick={onExport}
          >
            {exportPending ? "Exporting…" : "Export manifest"}
          </button>
        ) : null}
      </div>
    </>
  );
}

function ExportResultCard({ result }: { result: ExportTradeLogResult }) {
  return (
    <section className="card" style={{ marginTop: 18 }} aria-labelledby="tl-export-h">
      <h3 id="tl-export-h" style={{ marginTop: 0 }}>
        Export As Package
      </h3>
      <dl className="kv">
        <dt>Revision</dt>
        <dd>
          <code>{result.revision_id}</code>
        </dd>
        <dt>Manifest hash</dt>
        <dd>
          <code>{result.manifest_hash}</code>
        </dd>
      </dl>
    </section>
  );
}

function RevisionResultCard({ result }: { result: CreateTradeLogRevisionResult }) {
  return (
    <section className="card" style={{ marginTop: 18 }}>
      <p style={{ margin: 0 }}>
        Revision #{result.revision_no} saved — <code>{result.revision_id}</code> (config hash{" "}
        <code>{result.config_hash}</code>). Not auto-repinned: the Mainboard item still points at
        the prior revision.
      </p>
    </section>
  );
}

// Renders the canonical envelope verbatim; a 422 config failure additionally
// carries the validation issue list in error.details — shown as-is.
function MutationErrorCard({ error }: { error: unknown }) {
  const details = error instanceof ApiError ? error.details : [];
  return (
    <div className="card" style={{ marginTop: 18 }}>
      <p role="alert" style={{ color: "var(--down)", margin: 0 }}>
        {mutationErrorText(error)}
      </p>
      {details.length > 0 ? (
        <ul style={{ margin: "8px 0 0", paddingLeft: 18, fontSize: 13 }}>
          {details.map((detail, index) => (
            <li key={index}>
              <code>{JSON.stringify(detail)}</code>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
