import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { InstrumentPicker } from "@/components/InstrumentPicker";
import { Loading } from "@/components/Loading";
import { StatusBadge } from "@/components/StatusBadge";
import { ApiError } from "@/lib/apiClient";
import { EM_DASH, formatUtc, useDefaultMainboard } from "@/lib/backtest";
import { TradingSignalConfigEditor } from "@/components/TradingSignalConfigForm";
import { useSignalConfigEditorState } from "@/lib/tradingSignalForm";
import {
  type CreateSignalRevisionResult,
  type CreateTradingSignalResult,
  type ExportTradingSignalResult,
  type SignalImportReport,
  type TradingSignalDetail,
  buildSignalPayloadTemplate,
  mappingHashFromSummary,
  parseColumnMapping,
  useCreateSignalRevision,
  useCreateTradingSignal,
  useExportTradingSignal,
  useRequestSignalImport,
  useSignalImportReport,
  useTradingSignal,
  useUploadSignalSource,
} from "@/lib/tradingSignal";

// UI-04 — the doc 04 §3 Trading Signal is a 2-column inline panel
// (TRADING SIGNAL SOURCE / BULK TRADING SIGNAL IMPORT) closed by a sticky
// bottom toolbar (mockup .details-grid + .panel-actions), reusing the UI-02
// column/card/toolbar shell. Every hook / OCC token / Idempotency header /
// query key below is UNCHANGED from lib/tradingSignal.ts — only the visual
// grouping (identity + source config on the left, the TXT/CSV file + read-only
// format guide on the right, primary actions in a sticky toolbar) is new. The
// source-import chain (upload an immutable TXT/CSV asset → durable 202 import
// job → import report → Save & Add as a native work object) is unchanged.
//
// R2-01a — this editor body was lifted VERBATIM out of pages/TradingSignal.tsx
// so it can be mounted twice: as the /trading-signal page (mode="page", the URL
// carries ?job= / ?root=) and, from R2-01b onward, inline on a Mainboard row
// (mode="inline", the job handle lives in component state and the root arrives
// through initialRoot). No hook, query key, OCC token or Idempotency behaviour
// changed in the move.

// Failures surface the backend canonical envelope verbatim — the client never
// invents signal-domain messages (422 config blockers arrive in error.details).
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

// Read-only column guidance (mockup .trading-data-format-box). Canonical event
// set per doc 04 "Canonical Rule" — a Trading Signal revision carries at least
// these fields; the browser parser is never the authority.
const SIGNAL_FORMAT_GUIDE = `Required canonical event fields:
event_id, event_time, available_time, instrument_id, direction, signal_type, source_record_id

Optional columns:
price, symbol, size

Accepted separators:
comma, semicolon, tab or |

Example:
sig-001, 2024-01-01 10:00, 2024-01-01 10:05, BTCUSDT, long, entry, ref-1
sig-002, 2024-01-02 09:15, 2024-01-02 09:20, BTCUSDT, short, entry, ref-2`;

// Forward contract for R2-01b (Mainboard inline mount). "page" keeps the URL as
// the single source of truth for the job/root handles (CR-09 durability);
// "inline" renders no page chrome, takes its root through initialRoot, and
// reports Save & Add / close intent back to the host row.
export type TradingSignalEditorProps = {
  mode: "page" | "inline";
  initialRoot?: string;
  onSaved?: (rootId: string) => void;
  onClose?: () => void;
};

// Trading Signal editor (Stage 3c, doc 04 §7–§9). URL modes in page mode:
// ?job= (durable import handle — the jobs row survives browser close, CR-09)
// and ?root= (work-object detail + revision composer). Pin ("Use This
// Revision") and delete are Mainboard operations — not here (CR-01).
export function TradingSignalEditor({
  mode,
  initialRoot,
  onSaved,
  onClose,
}: TradingSignalEditorProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [inlineJobId, setInlineJobId] = useState<string | null>(null);

  const isPage = mode === "page";
  const rootId = isPage ? searchParams.get("root") : (initialRoot ?? null);
  const jobId = isPage ? searchParams.get("job") : inlineJobId;

  const handleJobAccepted = (id: string) => {
    if (isPage) setSearchParams({ job: id });
    else setInlineJobId(id);
  };

  // R2-04: Close panel moved INTO the sticky toolbar (GAP item 3 fix #4 — the
  // toolbar carries Validate / Save / Cancel / Close panel together).
  return rootId !== null ? (
    <DetailView rootId={rootId} onClose={isPage ? undefined : onClose} />
  ) : (
    <Workbench
      jobId={jobId}
      onJobAccepted={handleJobAccepted}
      onSaved={onSaved}
      onClose={isPage ? undefined : onClose}
    />
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
  onSaved,
  onClose,
}: {
  jobId: string | null;
  onJobAccepted: (jobId: string) => void;
  onSaved?: (rootId: string) => void;
  onClose?: () => void;
}) {
  const [sourceAssetId, setSourceAssetId] = useState("");
  const [instrumentId, setInstrumentId] = useState("");
  const [sourceTimezone, setSourceTimezone] = useState("UTC");

  const upload = useUploadSignalSource();
  const requestImport = useRequestSignalImport();
  const create = useCreateTradingSignal();
  const report = useSignalImportReport(jobId);

  const reportData = report.data ?? null;
  const succeededReport =
    reportData !== null &&
    reportData.status === "succeeded" &&
    reportData.normalized_event_revision_id !== null
      ? reportData
      : null;
  const importReady = succeededReport !== null;

  // Seed the payload editor from the succeeded import; blank binding otherwise
  // (the server compiler rejects it verbatim — the editor stays usable).
  const template = buildSignalPayloadTemplate({
    sourceAssetId: succeededReport?.source_asset_id ?? sourceAssetId,
    normalizedEventRevisionId: succeededReport?.normalized_event_revision_id ?? "",
    instrumentId: succeededReport?.instrument_id ?? instrumentId,
    sourceTimezone,
    mappingRevisionId: mappingHashFromSummary(succeededReport?.validation_summary ?? null),
  });

  return (
    <>
      {/* v18 two-column inline panel: TRADING SIGNAL SOURCE | BULK IMPORT. */}
      <div className="details-grid two-col">
        <div className="details-column">
          <div className="column-title">Trading Signal Source</div>
          <ImportIdentityCard
            sourceAssetId={sourceAssetId}
            instrumentId={instrumentId}
            sourceTimezone={sourceTimezone}
            requesting={requestImport.isPending}
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
          <div className="column-title">Bulk Trading Signal Import</div>
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
        key={succeededReport?.normalized_event_revision_id ?? "blank"}
        template={template}
        importReady={importReady}
        pending={create.isPending}
        onClose={onClose}
        onCreate={(payload, attach) =>
          create.mutate(
            { payload, attach },
            { onSuccess: (result) => onSaved?.(result.root_id) },
          )
        }
      />
      {create.isError ? <MutationErrorCard error={create.error} /> : null}
      {create.data ? <CreateResultCard result={create.data} /> : null}

      <AttachedSignalsCard />
    </>
  );
}

// Card 1 (SOURCE column) — signal identity + source configuration. The source
// asset id is SYSTEM-CARRIED from the file upload on the right (R2-04 / GAP
// item 3 fix #3 — never a user-editable technical field); instrument and
// timezone are the canonical mapping inputs. The optional column mapping and
// the "Request import" action close the card (mockup §1 IDENTITY + §2 SOURCE).
function ImportIdentityCard({
  sourceAssetId,
  instrumentId,
  sourceTimezone,
  requesting,
  onInstrumentId,
  onSourceTimezone,
  onRequest,
}: {
  sourceAssetId: string;
  instrumentId: string;
  sourceTimezone: string;
  requesting: boolean;
  onInstrumentId: (value: string) => void;
  onSourceTimezone: (value: string) => void;
  onRequest: (importMapping: Record<string, string>) => void;
}) {
  const [mappingText, setMappingText] = useState("");
  return (
    <form
      className="detail-card"
      aria-labelledby="ts-identity-h"
      onSubmit={(event) => {
        event.preventDefault();
        onRequest(parseColumnMapping(mappingText));
      }}
    >
      <h3 id="ts-identity-h" className="detail-card-title">
        1. Trading Signal Identity
      </h3>
      <p className="cp-note" style={{ marginTop: 0 }}>
        Enqueues a durable normalization job on the data queue (202) — the report below stays
        reachable through its job URL even after the browser closes.
      </p>
      <div className="strategy-form-grid">
        <div className="cp-field">
          <span>Source asset</span>
          <div>
            {sourceAssetId !== "" ? (
              <code>{sourceAssetId}</code>
            ) : (
              <small className="cp-note">
                Upload the TXT/CSV file on the right — the asset id is carried automatically.
              </small>
            )}
          </div>
        </div>
        <InstrumentPicker
          label="Instrument"
          required
          value={instrumentId}
          onChange={onInstrumentId}
        />
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
          placeholder={"event_time = signal_time\navailable_time = known_at\nsource_record_id = ref"}
        />
        <small className="cp-note">
          Leave blank when the file uses canonical (or aliased) signal headers. An explicit
          mapping is what lets a legacy entry/exit ledger import as a Trading Signal; the server
          never infers an ambiguous mapping.
        </small>
      </label>
      <div style={{ marginTop: 10 }}>
        <button
          className="btn btn-primary"
          type="submit"
          disabled={requesting || sourceAssetId === ""}
        >
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
    <div className="detail-card" aria-labelledby="ts-upload-h">
      <h3 id="ts-upload-h" className="detail-card-title">
        3. Trading Signal TXT / CSV File
      </h3>
      <p className="cp-note" style={{ marginTop: 0 }}>
        Select a UTF-8 TXT/CSV signal-event file — the browser transfers the file itself. The
        asset is immutable and content-addressed (an identical re-upload reuses the prior asset);
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
          <span>Signal-event file (.txt / .csv)</span>
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

      <div className="format-guide">{SIGNAL_FORMAT_GUIDE}</div>
      <p className="format-note">
        The content format above is read-only guidance — the system does not use a paste box here;
        the required data must be supplied through the TXT / CSV file selector.{" "}
        <code>available_time</code> is the mandatory lookahead guard: it need not equal{" "}
        <code>event_time</code> and cannot be blank.
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
  report: SignalImportReport | null;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  onRetry: () => void;
}) {
  return (
    <section className="card" style={{ marginTop: 18 }} aria-labelledby="ts-report-h">
      <h3 id="ts-report-h" style={{ marginTop: 0 }}>
        Import report
      </h3>
      {isLoading ? (
        <Loading label="Loading import report…" />
      ) : isError ? (
        <ErrorState error={error} onRetry={onRetry} />
      ) : report !== null ? (
        <>
          {/* v18 mockup: the import report reads as a bordered wireframe table. */}
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
                <th scope="row">Normalized revision</th>
                <td>
                  {report.normalized_event_revision_id !== null ? (
                    <code>{report.normalized_event_revision_id}</code>
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

// Typed config editor (R2-04, GAP item 3): the documented §9.2 fields render
// as typed controls and PRODUCE the payload; validation blockers (the compiler
// rules mirrored client-side) show next to their fields. Raw JSON survives
// only in the admin-gated Advanced disclosure. The primary actions live in the
// sticky bottom toolbar (Validate / Save / Cancel / Close panel).
function CreatePanel({
  template,
  importReady,
  pending,
  onCreate,
  onClose,
}: {
  template: Record<string, unknown>;
  importReady: boolean;
  pending: boolean;
  onCreate: (payload: Record<string, unknown>, attach: boolean) => void;
  onClose?: () => void;
}) {
  const editor = useSignalConfigEditorState(template);
  const [attach, setAttach] = useState(true);

  const submit = () => {
    const payload = editor.buildPayload();
    if (payload !== null) onCreate(payload, attach);
  };

  return (
    <>
      <section className="card" style={{ marginTop: 18 }} aria-labelledby="ts-create-h">
        <h3 id="ts-create-h" style={{ marginTop: 0 }}>
          Create Trading Signal
        </h3>
        <p className="cp-note">
          Requires a succeeded, non-empty, time-safe import — the source binding is carried from
          the report automatically. Save is never a Ready PASS; with “attach” on (Save &amp; Add)
          the object joins the default Mainboard and the prior Ready report goes STALE.
          {importReady ? "" : " Complete an import above to seed the binding."}
        </p>
        <TradingSignalConfigEditor
          state={editor.state}
          errors={editor.errors}
          onChange={editor.setState}
          rawMode={editor.rawMode}
          rawText={editor.rawText}
          rawError={editor.rawError}
          onRawModeChange={editor.enterRawMode}
          onRawTextChange={editor.setRawText}
        />
        <label style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 10 }}>
          <input
            type="checkbox"
            checked={attach}
            onChange={(event) => setAttach(event.target.checked)}
          />
          <span>Attach to the default Mainboard (Save &amp; Add)</span>
        </label>
        {editor.validNote !== null ? (
          <p role="status" className="cp-note" style={{ marginBottom: 0 }}>
            {editor.validNote}
          </p>
        ) : null}
      </section>

      {/* Sticky bottom toolbar — Validate / Save / Cancel / Close panel
          (mockup .panel-actions; GAP item 3 fix #4 full toolbar). */}
      <div className="panel-actions">
        <div className="panel-actions-title">Save / Package Actions</div>
        <button type="button" className="panel-action-button" onClick={editor.validate}>
          Validate
        </button>
        <button
          type="button"
          className="panel-action-button primary"
          disabled={pending}
          onClick={submit}
        >
          {pending ? "Saving…" : "Save Trading Signal"}
        </button>
        <button
          type="button"
          className="panel-action-button"
          onClick={() => editor.reset(template)}
        >
          Cancel
        </button>
        {onClose ? (
          <button type="button" className="panel-action-button" onClick={onClose}>
            Close panel
          </button>
        ) : null}
      </div>
    </>
  );
}

function CreateResultCard({ result }: { result: CreateTradingSignalResult }) {
  return (
    <section className="card" style={{ marginTop: 18 }} aria-labelledby="ts-created-h">
      <h3 id="ts-created-h" style={{ marginTop: 0 }}>
        Trading Signal saved
      </h3>
      <dl className="kv">
        <dt>Root</dt>
        <dd>
          <Link to={`/trading-signal?root=${encodeURIComponent(result.root_id)}`}>
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
// Discovery: trading-signal items attached to the default Mainboard (the
// Strategy page pattern). A saved but never-attached object stays reachable
// through its create-result ?root= link.
// ---------------------------------------------------------------------------

function AttachedSignalsCard() {
  const mainboard = useDefaultMainboard();
  const signalItems = (mainboard.data?.items ?? []).filter(
    (item) => item.item_kind === "trading_signal",
  );

  return (
    <section className="card" style={{ marginTop: 18 }} aria-labelledby="ts-attached-h">
      <h3 id="ts-attached-h" style={{ marginTop: 0 }}>
        Attached trading signals
      </h3>
      {mainboard.isLoading ? (
        <Loading />
      ) : mainboard.isError ? (
        <ErrorState error={mainboard.error} onRetry={() => void mainboard.refetch()} />
      ) : signalItems.length === 0 ? (
        <EmptyState
          title="No trading-signal items on the default Mainboard"
          description="Saved signals appear here once attached to the composition."
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
            {signalItems.map((item) => (
              <tr key={item.item_id}>
                <td>{item.display_label_override ?? EM_DASH}</td>
                <td>
                  <code>{item.work_object_root_id}</code>
                </td>
                <td>{item.pinned_revision_id ? <code>{item.pinned_revision_id}</code> : EM_DASH}</td>
                <td>{item.is_enabled ? "yes" : "no"}</td>
                <td>
                  <Link
                    to={`/trading-signal?root=${encodeURIComponent(item.work_object_root_id)}`}
                  >
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

function DetailView({ rootId, onClose }: { rootId: string; onClose?: () => void }) {
  const detail = useTradingSignal(rootId);
  const revise = useCreateSignalRevision();
  const exportSignal = useExportTradingSignal();

  if (detail.isLoading) {
    return (
      <div className="card">
        <Loading label="Loading trading signal…" />
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
          exportPending={exportSignal.isPending}
          onClose={onClose}
          onSave={(payload) =>
            revise.mutate({
              rootId,
              payload,
              expectedHeadRevisionId: data.current_revision_id ?? "",
            })
          }
          onExport={() => exportSignal.mutate({ rootId })}
        />
      ) : null}
      {revise.isError ? <MutationErrorCard error={revise.error} /> : null}
      {revise.data ? <RevisionResultCard result={revise.data} /> : null}
      {exportSignal.isError ? <MutationErrorCard error={exportSignal.error} /> : null}
      {exportSignal.data ? <ExportResultCard result={exportSignal.data} /> : null}
    </>
  );
}

function DetailHeaderCard({ data }: { data: TradingSignalDetail }) {
  return (
    <section className="card" aria-labelledby="ts-detail-h">
      <h3 id="ts-detail-h" style={{ marginTop: 0 }}>
        Trading Signal
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
        Pin (“Use This Revision”) and delete are Mainboard operations — a Trading Signal is a work
        object, not a package.
      </p>
    </section>
  );
}

function CurrentRevisionCard({ data }: { data: TradingSignalDetail }) {
  const revision = data.current_revision;
  if (revision === null) return null;
  return (
    <section className="card" style={{ marginTop: 18 }} aria-labelledby="ts-revision-h">
      <h3 id="ts-revision-h" style={{ marginTop: 0 }}>
        Current revision #{revision.revision_no}
      </h3>
      <dl className="kv">
        <dt>Revision</dt>
        <dd>
          <code>{revision.revision_id}</code>
        </dd>
        <dt>Available time</dt>
        <dd>{formatUtc(revision.available_time)}</dd>
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
// Package). Export As Package (doc 04 §7, Rule 17) produces the immutable
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
  onClose,
}: {
  headRevisionId: string;
  seedPayload: Record<string, unknown>;
  savePending: boolean;
  canExport: boolean;
  exportPending: boolean;
  onSave: (payload: Record<string, unknown>) => void;
  onExport: () => void;
  onClose?: () => void;
}) {
  // R2-04: the revision composer uses the SAME typed form, seeded from the
  // rendered head revision payload.
  const editor = useSignalConfigEditorState(seedPayload);

  const submit = () => {
    const payload = editor.buildPayload();
    if (payload !== null) onSave(payload);
  };

  return (
    <>
      <section className="card" style={{ marginTop: 18 }} aria-labelledby="ts-revise-h">
        <h3 id="ts-revise-h" style={{ marginTop: 0 }}>
          Save new revision
        </h3>
        <p className="cp-note">
          Appends immutable revision N+1 guarded by the rendered head (<code>{headRevisionId}</code>
          ) — a stale tab gets a 409, never last-write-wins. The Mainboard item is NEVER
          auto-repinned: use “Use This Revision” on the Mainboard to change the active composition.
          Export As Package produces the immutable source-mapping/provenance manifest for the pinned
          head — it never mutates the source (repeated clicks return the same manifest hash).
        </p>
        <TradingSignalConfigEditor
          state={editor.state}
          errors={editor.errors}
          onChange={editor.setState}
          rawMode={editor.rawMode}
          rawText={editor.rawText}
          rawError={editor.rawError}
          onRawModeChange={editor.enterRawMode}
          onRawTextChange={editor.setRawText}
        />
        {editor.validNote !== null ? (
          <p role="status" className="cp-note" style={{ marginBottom: 0 }}>
            {editor.validNote}
          </p>
        ) : null}
      </section>

      <div className="panel-actions">
        <div className="panel-actions-title">Save / Package Actions</div>
        <button type="button" className="panel-action-button" onClick={editor.validate}>
          Validate
        </button>
        <button
          type="button"
          className="panel-action-button primary"
          disabled={savePending}
          onClick={submit}
        >
          {savePending ? "Saving…" : "Save new revision"}
        </button>
        <button
          type="button"
          className="panel-action-button"
          onClick={() => editor.reset(seedPayload)}
        >
          Cancel
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
        {onClose ? (
          <button type="button" className="panel-action-button" onClick={onClose}>
            Close panel
          </button>
        ) : null}
      </div>
    </>
  );
}

function ExportResultCard({ result }: { result: ExportTradingSignalResult }) {
  return (
    <section className="card" style={{ marginTop: 18 }} aria-labelledby="ts-export-h">
      <h3 id="ts-export-h" style={{ marginTop: 0 }}>
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

function RevisionResultCard({ result }: { result: CreateSignalRevisionResult }) {
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
