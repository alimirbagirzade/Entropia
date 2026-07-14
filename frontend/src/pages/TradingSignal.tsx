import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { StatusBadge } from "@/components/StatusBadge";
import { ApiError } from "@/lib/apiClient";
import { EM_DASH, formatUtc, useDefaultMainboard } from "@/lib/backtest";
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

// Trading Signal (Stage 3c, doc 04 §7–§9). The source-import chain (upload an
// immutable TXT/CSV asset → durable 202 import job → import report) feeding
// the native work-object plane (Save & Add → append revisions → read). URL
// modes: ?job= (durable import handle — the jobs row survives browser close,
// CR-09) and ?root= (work-object detail + revision composer). Pin ("Use This
// Revision") and delete are Mainboard operations — not on this page (CR-01).
export function TradingSignal() {
  const [searchParams, setSearchParams] = useSearchParams();
  const rootParam = searchParams.get("root");
  const jobParam = searchParams.get("job");

  return (
    <>
      <h1 className="page-title">Trading Signal</h1>
      <p className="page-sub">
        Import external signal events from a TXT/CSV file, review the normalization report, and
        save the Trading Signal as a native work object on the Mainboard
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
// Workbench: upload → import → report → create. Mutations and the shared
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
      <UploadCard
        pending={upload.isPending}
        onUpload={(content, filename) =>
          upload.mutate(
            { content, originalFilename: filename },
            { onSuccess: (result) => setSourceAssetId(result.source_asset_id) },
          )
        }
      />
      {upload.isError ? <MutationErrorCard error={upload.error} /> : null}
      {upload.data ? (
        <section className="card" style={{ marginTop: 18 }}>
          <p style={{ margin: 0 }}>
            {upload.data.deduplicated
              ? "Identical content already uploaded — reusing the prior source asset "
              : "Source asset stored "}
            <code>{upload.data.source_asset_id}</code> ({upload.data.size_bytes} bytes,{" "}
            <code>{upload.data.raw_asset_hash}</code>)
          </p>
        </section>
      ) : null}

      <ImportRequestCard
        sourceAssetId={sourceAssetId}
        instrumentId={instrumentId}
        sourceTimezone={sourceTimezone}
        pending={requestImport.isPending}
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

      <CreateCard
        key={succeededReport?.normalized_event_revision_id ?? "blank"}
        template={template}
        importReady={importReady}
        pending={create.isPending}
        onCreate={(payload, attach) => create.mutate({ payload, attach })}
      />
      {create.isError ? <MutationErrorCard error={create.error} /> : null}
      {create.data ? <CreateResultCard result={create.data} /> : null}

      <AttachedSignalsCard />
    </>
  );
}

function UploadCard({
  pending,
  onUpload,
}: {
  pending: boolean;
  onUpload: (content: string, filename: string | null) => void;
}) {
  const [content, setContent] = useState("");
  const [filename, setFilename] = useState("");

  return (
    <section className="card" aria-labelledby="ts-upload-h">
      <h3 id="ts-upload-h" style={{ marginTop: 0 }}>
        Upload source file
      </h3>
      <p className="cp-note">
        UTF-8 TXT/CSV text only — the asset is immutable and content-addressed (an identical
        re-upload reuses the prior asset). Raw bytes never travel through this page.
      </p>
      <form
        className="cp-form"
        onSubmit={(event) => {
          event.preventDefault();
          onUpload(content, filename === "" ? null : filename);
        }}
      >
        <label className="cp-field cp-wide">
          <span>File content</span>
          <textarea
            rows={6}
            value={content}
            onChange={(event) => setContent(event.target.value)}
            spellCheck={false}
            required
          />
        </label>
        <label className="cp-field">
          <span>Original filename (optional, .txt/.csv)</span>
          <input
            value={filename}
            onChange={(event) => setFilename(event.target.value)}
            placeholder="signals.csv"
          />
        </label>
        <div className="cp-field cp-wide">
          <button className="btn btn-primary" type="submit" disabled={pending}>
            {pending ? "Uploading…" : "Upload source asset"}
          </button>
        </div>
      </form>
    </section>
  );
}

function ImportRequestCard({
  sourceAssetId,
  instrumentId,
  sourceTimezone,
  pending,
  onSourceAssetId,
  onInstrumentId,
  onSourceTimezone,
  onRequest,
}: {
  sourceAssetId: string;
  instrumentId: string;
  sourceTimezone: string;
  pending: boolean;
  onSourceAssetId: (value: string) => void;
  onInstrumentId: (value: string) => void;
  onSourceTimezone: (value: string) => void;
  onRequest: (importMapping: Record<string, string>) => void;
}) {
  const [mappingText, setMappingText] = useState("");
  return (
    <section className="card" style={{ marginTop: 18 }} aria-labelledby="ts-import-h">
      <h3 id="ts-import-h" style={{ marginTop: 0 }}>
        Request import
      </h3>
      <p className="cp-note">
        Enqueues a durable normalization job on the data queue (202) — the report below stays
        reachable through its job URL even after the browser closes.
      </p>
      <form
        className="cp-form"
        onSubmit={(event) => {
          event.preventDefault();
          onRequest(parseColumnMapping(mappingText));
        }}
      >
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
        <div className="cp-field cp-wide">
          <button className="btn btn-primary" type="submit" disabled={pending}>
            {pending ? "Requesting…" : "Request import"}
          </button>
        </div>
      </form>
    </section>
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

// Raw JSON payload editor (Strategy precedent): parse failures stay
// client-side; the server compiler is the sole authority on config semantics.
function CreateCard({
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

  return (
    <section className="card" style={{ marginTop: 18 }} aria-labelledby="ts-create-h">
      <h3 id="ts-create-h" style={{ marginTop: 0 }}>
        Create Trading Signal
      </h3>
      <p className="cp-note">
        Requires a succeeded, non-empty, time-safe import — the payload below is seeded from the
        report once available. Save is never a Ready PASS; with “attach” on (Save &amp; Add) the
        object joins the default Mainboard and the prior Ready report goes STALE.
        {importReady ? "" : " Complete an import above to seed the binding."}
      </p>
      <label className="cp-field cp-wide">
        <span>TradingSignalConfig payload</span>
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
      <div style={{ marginTop: 10 }}>
        <button
          type="button"
          className="btn btn-primary"
          disabled={pending}
          onClick={() => {
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
          }}
        >
          {pending ? "Saving…" : "Save Trading Signal"}
        </button>
      </div>
      {parseError !== null ? (
        <p role="alert" style={{ color: "var(--down)", marginBottom: 0 }}>
          Not sent — invalid JSON: {parseError}
        </p>
      ) : null}
    </section>
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
// Mutation state lives HERE so the result survives the composer remount when
// the head moves (the Strategy/Portfolio lesson).
// ---------------------------------------------------------------------------

function DetailView({ rootId }: { rootId: string }) {
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

  return (
    <>
      <DetailHeaderCard data={data} />
      {data.current_revision_id !== null ? (
        <ExportCard
          disabled={exportSignal.isPending}
          onExport={() => exportSignal.mutate({ rootId })}
          error={exportSignal.isError ? exportSignal.error : null}
          result={exportSignal.data ?? null}
        />
      ) : null}
      {data.current_revision !== null ? <CurrentRevisionCard data={data} /> : null}
      {data.current_revision_id !== null && data.current_revision !== null ? (
        <RevisionComposer
          key={data.current_revision_id}
          headRevisionId={data.current_revision_id}
          seedPayload={data.current_revision.payload}
          pending={revise.isPending}
          onSubmit={(payload) =>
            revise.mutate({
              rootId,
              payload,
              expectedHeadRevisionId: data.current_revision_id ?? "",
            })
          }
        />
      ) : null}
      {revise.isError ? <MutationErrorCard error={revise.error} /> : null}
      {revise.data ? <RevisionResultCard result={revise.data} /> : null}
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

function RevisionComposer({
  headRevisionId,
  seedPayload,
  pending,
  onSubmit,
}: {
  headRevisionId: string;
  seedPayload: Record<string, unknown>;
  pending: boolean;
  onSubmit: (payload: Record<string, unknown>) => void;
}) {
  const [text, setText] = useState(() => JSON.stringify(seedPayload, null, 2));
  const [parseError, setParseError] = useState<string | null>(null);

  return (
    <section className="card" style={{ marginTop: 18 }} aria-labelledby="ts-revise-h">
      <h3 id="ts-revise-h" style={{ marginTop: 0 }}>
        Save new revision
      </h3>
      <p className="cp-note">
        Appends immutable revision N+1 guarded by the rendered head (<code>{headRevisionId}</code>
        ) — a stale tab gets a 409, never last-write-wins. The Mainboard item is NEVER
        auto-repinned: use “Use This Revision” on the Mainboard to change the active composition.
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
      <div style={{ marginTop: 10 }}>
        <button
          type="button"
          className="btn btn-primary"
          disabled={pending}
          onClick={() => {
            try {
              const parsed: unknown = JSON.parse(text);
              if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
                setParseError("The payload must be a JSON object.");
                return;
              }
              setParseError(null);
              onSubmit(parsed as Record<string, unknown>);
            } catch (error) {
              setParseError(error instanceof Error ? error.message : "Invalid JSON.");
            }
          }}
        >
          {pending ? "Saving…" : "Save new revision"}
        </button>
      </div>
      {parseError !== null ? (
        <p role="alert" style={{ color: "var(--down)", marginBottom: 0 }}>
          Not sent — invalid JSON: {parseError}
        </p>
      ) : null}
    </section>
  );
}

// Export As Package (doc 04 §7, Rule 17): produce the immutable
// source-mapping/provenance manifest for the pinned head revision. Read-only —
// the export never mutates the source (the button stays enabled). Owner/Admin is
// enforced server-side; a non-owner sees the 403 envelope verbatim.
function ExportCard({
  disabled,
  onExport,
  error,
  result,
}: {
  disabled: boolean;
  onExport: () => void;
  error: unknown;
  result: ExportTradingSignalResult | null;
}) {
  return (
    <section className="card" style={{ marginTop: 18 }} aria-labelledby="ts-export-h">
      <h3 id="ts-export-h" style={{ marginTop: 0 }}>
        Export As Package
      </h3>
      <p className="cp-note" style={{ marginTop: 0 }}>
        Produce the immutable source-mapping/provenance manifest for the pinned head revision. The
        export never mutates the source — repeated clicks return the same manifest hash.
      </p>
      <button className="btn btn-primary" type="button" disabled={disabled} onClick={onExport}>
        {disabled ? "Exporting…" : "Export manifest"}
      </button>
      {error ? <MutationErrorCard error={error} /> : null}
      {result ? (
        <dl className="kv" style={{ marginTop: 12 }}>
          <dt>Revision</dt>
          <dd>
            <code>{result.revision_id}</code>
          </dd>
          <dt>Manifest hash</dt>
          <dd>
            <code>{result.manifest_hash}</code>
          </dd>
        </dl>
      ) : null}
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
