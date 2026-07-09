import { useState, type FormEvent } from "react";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { StatusBadge } from "@/components/StatusBadge";
import { ApiError } from "@/lib/apiClient";
import { formatUtc } from "@/lib/backtest";
import {
  MARKET_DATA_TYPES,
  linesToList,
  parseMappingLines,
  revisionStateTone,
  useApprovedBundle,
  useConfirmMapping,
  useCreateDataset,
  useFinalizeUpload,
  useMarketDataset,
  useMarketDatasets,
  useRequestAnalysis,
  useStartUpload,
  type MarketDatasetDetail,
  type MarketDatasetRow,
} from "@/lib/marketData";

// Command failures surface the backend canonical envelope verbatim — the client
// never invents market-data-domain messages (mirrors Rationale / Trash / Panel).
function mutationErrorText(error: unknown): string {
  if (error instanceof ApiError) return `${error.code}: ${error.message}`;
  return error instanceof Error ? error.message : "Request failed.";
}

// Forward-only opaque keyset cursors (server contract): Prev replays the cursor
// stack, the client never re-orders or fabricates a page.
function useCursorStack() {
  const [stack, setStack] = useState<string[]>([]);
  const cursor = stack.length > 0 ? (stack[stack.length - 1] ?? null) : null;
  return {
    cursor,
    canPrev: stack.length > 0,
    next: (nextCursor: string) => setStack((prev) => [...prev, nextCursor]),
    prev: () => setStack((prev) => prev.slice(0, -1)),
  };
}

// Market Data (doc 11): the primary price/execution layer for research and
// backtests — only OHLCV, tick/trades and spread/execution data live here. This
// slice binds the read surface + the owner ingest chain (upload -> analyze ->
// map). Revision lifecycle actions (revise / successor / Admin approve /
// deprecate) are a later slice; the detail row_version is their ready OCC token.
export function MarketData() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  return (
    <>
      <h1 className="page-title">Market Data</h1>
      <p className="page-sub">
        Primary price &amp; execution layer · OHLCV, tick/trades and spread/execution only · verified
        is distinct from approved — only an ACTIVE+APPROVED revision feeds research and backtests
      </p>
      <CreateDatasetCard onCreated={setSelectedId} />
      <RegistryCard selectedId={selectedId} onOpen={setSelectedId} />
      {selectedId !== null ? <DetailCard entityId={selectedId} /> : null}
    </>
  );
}

// ---------------------------------------------------------------------------
// Create dataset — Root + first DRAFT revision (workflow entry)
// ---------------------------------------------------------------------------

function CreateDatasetCard({ onCreated }: { onCreated: (entityId: string) => void }) {
  const create = useCreateDataset();
  const [dataType, setDataType] = useState<string>(MARKET_DATA_TYPES[0]);
  const [title, setTitle] = useState("");
  const [instrumentId, setInstrumentId] = useState("");
  const [payloadText, setPayloadText] = useState("");
  const [payloadError, setPayloadError] = useState<string | null>(null);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    // Transport shaping only: an unparseable payload cannot be serialized at
    // all. Domain validation stays server-side.
    let payload: Record<string, unknown> = {};
    if (payloadText.trim().length > 0) {
      try {
        const parsed: unknown = JSON.parse(payloadText);
        if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
          setPayloadError("Payload must be a JSON object.");
          return;
        }
        payload = parsed as Record<string, unknown>;
      } catch {
        setPayloadError("Payload is not valid JSON.");
        return;
      }
    }
    setPayloadError(null);
    create.mutate(
      {
        market_data_type: dataType,
        payload,
        title: title.trim() || null,
        instrument_id: instrumentId.trim() || null,
      },
      { onSuccess: (result) => onCreated(result.entity_id) },
    );
  };

  return (
    <section className="card" aria-labelledby="md-create-h">
      <h3 id="md-create-h" style={{ marginTop: 0 }}>
        Add market dataset
      </h3>
      <form onSubmit={submit}>
        <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
          <label htmlFor="md-type">
            Market data type
            <select id="md-type" value={dataType} onChange={(event) => setDataType(event.target.value)}>
              {MARKET_DATA_TYPES.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <label htmlFor="md-title">
            Title (optional)
            <input
              id="md-title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Binance Futures Core Universe · 15m OHLCV"
            />
          </label>
          <label htmlFor="md-instrument">
            Instrument id (optional)
            <input
              id="md-instrument"
              value={instrumentId}
              onChange={(event) => setInstrumentId(event.target.value)}
              placeholder="BTCUSDT"
            />
          </label>
          <label htmlFor="md-payload">
            Payload (optional JSON object)
            <textarea
              id="md-payload"
              rows={3}
              value={payloadText}
              onChange={(event) => setPayloadText(event.target.value)}
              placeholder='{"source": "binance_futures"}'
            />
          </label>
        </div>
        <button type="submit" className="btn btn-primary" disabled={create.isPending} style={{ marginTop: 8 }}>
          Create dataset
        </button>
      </form>
      {payloadError ? (
        <p role="alert" style={{ color: "var(--down)" }}>
          {payloadError}
        </p>
      ) : null}
      {create.isError ? (
        <p role="alert" style={{ color: "var(--down)" }}>
          {mutationErrorText(create.error)}
        </p>
      ) : null}
      {create.data ? (
        <p aria-live="polite">
          Created — {create.data.entity_id} ({create.data.revision_state}).
        </p>
      ) : null}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Registry — role-aware head-revision catalog (doc 11 §3.3)
// ---------------------------------------------------------------------------

function RegistryCard({
  selectedId,
  onOpen,
}: {
  selectedId: string | null;
  onOpen: (entityId: string) => void;
}) {
  const pager = useCursorStack();
  const datasets = useMarketDatasets(pager.cursor);

  return (
    <section className="card" aria-labelledby="md-registry-h">
      <h3 id="md-registry-h" style={{ marginTop: 0 }}>
        Dataset registry
        {datasets.data ? (
          <span className="page-sub" style={{ marginLeft: 8 }}>
            ({datasets.data.data.length} visible on this page)
          </span>
        ) : null}
      </h3>
      {datasets.isLoading ? (
        <Loading label="Loading market datasets…" />
      ) : datasets.isError ? (
        <ErrorState error={datasets.error} onRetry={() => void datasets.refetch()} />
      ) : datasets.data ? (
        <>
          {datasets.data.data.length === 0 ? (
            <EmptyState title="No market datasets visible yet — create the first one above" />
          ) : (
            <table className="metrics-table">
              <thead>
                <tr>
                  <th scope="col">Dataset</th>
                  <th scope="col">Type</th>
                  <th scope="col">Instrument</th>
                  <th scope="col">Revision state</th>
                  <th scope="col">Validation</th>
                  <th scope="col">Rev</th>
                  <th scope="col">Created (UTC)</th>
                  <th scope="col" aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {datasets.data.data.map((row) => (
                  <RegistryRow
                    key={row.entity_id}
                    row={row}
                    isOpen={selectedId === row.entity_id}
                    onOpen={() => onOpen(row.entity_id)}
                  />
                ))}
              </tbody>
            </table>
          )}
          <Pager
            canPrev={pager.canPrev}
            nextCursor={datasets.data.meta.cursor}
            onPrev={pager.prev}
            onNext={pager.next}
          />
        </>
      ) : null}
    </section>
  );
}

function RegistryRow({
  row,
  isOpen,
  onOpen,
}: {
  row: MarketDatasetRow;
  isOpen: boolean;
  onOpen: () => void;
}) {
  return (
    <tr style={isOpen ? { background: "var(--bg-elev)" } : undefined}>
      <td>{row.title ?? row.entity_id}</td>
      <td>
        <code>{row.market_data_type}</code>
      </td>
      <td>{row.instrument_id ?? "—"}</td>
      <td>
        <StatusBadge tone={revisionStateTone(row.revision_state)} label={row.revision_state} />
      </td>
      <td>{row.validation_status ?? "—"}</td>
      <td>v{row.revision_no}</td>
      <td>{formatUtc(row.created_at)}</td>
      <td>
        <button type="button" className="btn" onClick={onOpen}>
          Open
        </button>
      </td>
    </tr>
  );
}

// ---------------------------------------------------------------------------
// Detail — identity + revision history + ingest workflow + bundle probe
// ---------------------------------------------------------------------------

function DetailCard({ entityId }: { entityId: string }) {
  const detail = useMarketDataset(entityId);

  return (
    <section className="card" aria-labelledby="md-detail-h">
      <h3 id="md-detail-h" style={{ marginTop: 0 }}>
        Dataset detail
      </h3>
      {detail.isLoading ? (
        <Loading label="Loading dataset…" />
      ) : detail.isError ? (
        <ErrorState error={detail.error} onRetry={() => void detail.refetch()} />
      ) : detail.data ? (
        <>
          <IdentitySection detail={detail.data} />
          <IngestSection detail={detail.data} />
          <BundleProbe entityId={entityId} />
        </>
      ) : null}
    </section>
  );
}

function IdentitySection({ detail }: { detail: MarketDatasetDetail }) {
  return (
    <>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <strong>{detail.title ?? detail.entity_id}</strong>
        <StatusBadge tone={revisionStateTone(detail.revision_state)} label={detail.revision_state} />
        <StatusBadge label={detail.lifecycle_state} />
        {detail.validation_status !== null ? <StatusBadge label={detail.validation_status} /> : null}
      </div>
      <table className="metrics-table" style={{ marginTop: 12 }}>
        <tbody>
          <tr>
            <th scope="row">Root / revision</th>
            <td>
              <code>{detail.entity_id}</code> · <code>{detail.revision_id}</code> · v
              {detail.revision_no} <span className="page-sub">(rv {detail.row_version})</span>
            </td>
          </tr>
          <tr>
            <th scope="row">Type / instrument</th>
            <td>
              <code>{detail.market_data_type}</code> · {detail.instrument_id ?? "—"}
            </td>
          </tr>
          <tr>
            <th scope="row">Owner</th>
            <td>{detail.owner_principal_id ?? "—"}</td>
          </tr>
          <tr>
            <th scope="row">Content hash</th>
            <td>{detail.content_hash !== null ? <code>{detail.content_hash}</code> : "—"}</td>
          </tr>
          <tr>
            <th scope="row">Manifest hash</th>
            <td>{detail.manifest_hash !== null ? <code>{detail.manifest_hash}</code> : "—"}</td>
          </tr>
          <tr>
            <th scope="row">Created (UTC)</th>
            <td>{formatUtc(detail.created_at)}</td>
          </tr>
        </tbody>
      </table>
      <h4>Revision history</h4>
      {detail.revisions.length === 0 ? (
        <p className="page-sub">No revisions recorded.</p>
      ) : (
        <ul>
          {detail.revisions.map((revision) => (
            <li key={revision.revision_id}>
              v{revision.revision_no} · <code>{revision.revision_id}</code> ·{" "}
              {revision.revision_state}
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

// The owner ingest chain (doc 11 §3.1 ribbon): Step 1 register + finalize the
// raw asset, Step 2 run the durable analysis job and confirm the canonical
// schema mapping. Buttons are never role-pre-gated — the server's owner/Admin
// draft gate answers with the canonical envelope verbatim.
function IngestSection({ detail }: { detail: MarketDatasetDetail }) {
  return (
    <>
      <h4>Ingest workflow</h4>
      <UploadComposer entityId={detail.entity_id} />
      <AnalysisAction entityId={detail.entity_id} />
      <MappingComposer entityId={detail.entity_id} marketDataType={detail.market_data_type} />
    </>
  );
}

function UploadComposer({ entityId }: { entityId: string }) {
  const start = useStartUpload();
  const finalize = useFinalizeUpload();
  const [objectKey, setObjectKey] = useState("");
  const [digest, setDigest] = useState("");
  const [sizeBytes, setSizeBytes] = useState("");
  const [contentType, setContentType] = useState("");
  const [filename, setFilename] = useState("");
  const [assetId, setAssetId] = useState("");

  const submitStart = (event: FormEvent) => {
    event.preventDefault();
    start.mutate(
      {
        entity_id: entityId,
        object_key: objectKey.trim(),
        content_digest: digest.trim(),
        size_bytes: Number(sizeBytes),
        content_type: contentType.trim() || null,
        original_filename: filename.trim() || null,
      },
      { onSuccess: (result) => setAssetId(result.asset_id) },
    );
  };

  return (
    <div style={{ marginBottom: 16 }}>
      <strong>Step 1 — raw source</strong>
      <p className="page-sub" style={{ marginTop: 4 }}>
        Registers the immutable evidence row for an object already in storage (object key + digest);
        raw bytes never travel through this page.
      </p>
      <form onSubmit={submitStart}>
        <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))" }}>
          <label htmlFor="md-object-key">
            Object key
            <input
              id="md-object-key"
              value={objectKey}
              onChange={(event) => setObjectKey(event.target.value)}
              placeholder="raw/btcusdt-15m.csv"
              required
            />
          </label>
          <label htmlFor="md-digest">
            Content digest
            <input
              id="md-digest"
              value={digest}
              onChange={(event) => setDigest(event.target.value)}
              placeholder="sha256:…"
              required
            />
          </label>
          <label htmlFor="md-size">
            Size (bytes)
            <input
              id="md-size"
              type="number"
              min={0}
              value={sizeBytes}
              onChange={(event) => setSizeBytes(event.target.value)}
              required
            />
          </label>
          <label htmlFor="md-content-type">
            Content type (optional)
            <input
              id="md-content-type"
              value={contentType}
              onChange={(event) => setContentType(event.target.value)}
              placeholder="text/csv"
            />
          </label>
          <label htmlFor="md-filename">
            Original filename (optional)
            <input
              id="md-filename"
              value={filename}
              onChange={(event) => setFilename(event.target.value)}
            />
          </label>
        </div>
        <button type="submit" className="btn" disabled={start.isPending} style={{ marginTop: 8 }}>
          Start upload
        </button>
      </form>
      {start.isError ? (
        <p role="alert" style={{ color: "var(--down)" }}>
          {mutationErrorText(start.error)}
        </p>
      ) : null}
      {start.data ? (
        <p aria-live="polite">
          Upload started — asset <code>{start.data.asset_id}</code>.
        </p>
      ) : null}

      <div style={{ display: "flex", alignItems: "end", gap: 12, marginTop: 8, flexWrap: "wrap" }}>
        <label htmlFor="md-asset-id">
          Asset id to finalize
          <input
            id="md-asset-id"
            value={assetId}
            onChange={(event) => setAssetId(event.target.value)}
            placeholder="asset_…"
          />
        </label>
        <button
          type="button"
          className="btn"
          disabled={finalize.isPending || assetId.trim().length === 0}
          onClick={() => finalize.mutate({ entity_id: entityId, asset_id: assetId.trim() })}
        >
          Finalize upload
        </button>
      </div>
      {finalize.isError ? (
        <p role="alert" style={{ color: "var(--down)" }}>
          {mutationErrorText(finalize.error)}
        </p>
      ) : null}
      {finalize.data ? (
        <p aria-live="polite">
          Upload finalized — revision {finalize.data.revision_id} is now{" "}
          {finalize.data.revision_state}.
        </p>
      ) : null}
    </div>
  );
}

function AnalysisAction({ entityId }: { entityId: string }) {
  const analysis = useRequestAnalysis();
  return (
    <div style={{ marginBottom: 16 }}>
      <strong>Step 2 — analyze</strong>
      <p className="page-sub" style={{ marginTop: 4 }}>
        Enqueues the durable profile/mapping job on the data queue; the job row survives browser
        close and progress lands back on the revision state.
      </p>
      <button
        type="button"
        className="btn"
        disabled={analysis.isPending}
        onClick={() => analysis.mutate({ entity_id: entityId })}
      >
        Request analysis
      </button>
      {analysis.isError ? (
        <p role="alert" style={{ color: "var(--down)" }}>
          {mutationErrorText(analysis.error)}
        </p>
      ) : null}
      {analysis.data ? (
        <p aria-live="polite">
          Analysis accepted — job <code>{analysis.data.job_id}</code> on queue{" "}
          <code>{analysis.data.queue}</code> ({analysis.data.status}).
        </p>
      ) : null}
    </div>
  );
}

function MappingComposer({
  entityId,
  marketDataType,
}: {
  entityId: string;
  marketDataType: string;
}) {
  const confirm = useConfirmMapping();
  const [columnsText, setColumnsText] = useState("");
  const [mappingText, setMappingText] = useState("");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const confirmedLines = mappingText.trim();
    confirm.mutate({
      entity_id: entityId,
      market_data_type: marketDataType,
      source_columns: linesToList(columnsText),
      confirmed_mapping: confirmedLines.length > 0 ? parseMappingLines(mappingText) : undefined,
    });
  };

  return (
    <div>
      <strong>Step 2b — schema mapping</strong>
      <p className="page-sub" style={{ marginTop: 4 }}>
        Proposes the canonical mapping from your source columns; an unambiguous proposal
        auto-confirms, otherwise supply the explicit mapping (one “canonical: source” per line).
      </p>
      <form onSubmit={submit}>
        <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
          <label htmlFor="md-columns">
            Source columns (one per line)
            <textarea
              id="md-columns"
              rows={4}
              value={columnsText}
              onChange={(event) => setColumnsText(event.target.value)}
              placeholder={"timestamp\nopen\nhigh\nlow\nclose\nvolume"}
              required
            />
          </label>
          <label htmlFor="md-mapping">
            Confirmed mapping (optional, “canonical: source” per line)
            <textarea
              id="md-mapping"
              rows={4}
              value={mappingText}
              onChange={(event) => setMappingText(event.target.value)}
              placeholder={"timestamp: ts\nclose: last_price"}
            />
          </label>
        </div>
        <button type="submit" className="btn" disabled={confirm.isPending} style={{ marginTop: 8 }}>
          Confirm mapping
        </button>
      </form>
      {confirm.isError ? (
        <p role="alert" style={{ color: "var(--down)" }}>
          {mutationErrorText(confirm.error)}
        </p>
      ) : null}
      {confirm.data ? (
        <div aria-live="polite">
          <p style={{ marginBottom: 4 }}>
            Mapping saved — <code>{confirm.data.mapping_id}</code>
            {confirm.data.review_required ? " (review required)" : ""}.
          </p>
          {confirm.data.confirmed_mapping !== null ? (
            <ul style={{ marginTop: 0 }}>
              {Object.entries(confirm.data.confirmed_mapping).map(([canonical, source]) => (
                <li key={canonical}>
                  <code>{canonical}</code> ← {source !== null ? <code>{source}</code> : "unmapped"}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

// Read-only resolve probe: which exact APPROVED revision would a Run pin right
// now? A dataset without an ACTIVE+APPROVED revision answers 404 verbatim —
// consumers never silently bind to "latest".
function BundleProbe({ entityId }: { entityId: string }) {
  const [probed, setProbed] = useState(false);
  const bundle = useApprovedBundle(entityId, probed);

  return (
    <div style={{ marginTop: 16 }}>
      <h4>Approved bundle</h4>
      <button
        type="button"
        className="btn"
        onClick={() => (probed ? void bundle.refetch() : setProbed(true))}
        disabled={bundle.isFetching}
      >
        Resolve approved bundle
      </button>
      {probed && bundle.isError ? (
        <p role="alert" style={{ color: "var(--down)" }}>
          {mutationErrorText(bundle.error)}
        </p>
      ) : null}
      {bundle.data ? (
        <p aria-live="polite">
          Pinned — revision <code>{bundle.data.revision_id}</code> (v{bundle.data.revision_no},{" "}
          {bundle.data.revision_state}) · content{" "}
          <code>{bundle.data.content_hash ?? "—"}</code> · manifest{" "}
          <code>{bundle.data.manifest_hash ?? "—"}</code>
        </p>
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
