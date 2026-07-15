import { useRef, useState, type ChangeEvent, type FormEvent } from "react";

import { useQueryClient } from "@tanstack/react-query";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { ResearchLifecycle } from "@/components/ResearchLifecycle";
import { StatusBadge } from "@/components/StatusBadge";
import { ApiError } from "@/lib/apiClient";
import { formatUtc } from "@/lib/backtest";
import {
  OTHER_CUSTOM_CATEGORY,
  RESEARCH_CATEGORIES,
  USAGE_SCOPES,
  invalidateAfterRawUpload,
  rawUploadPath,
  researchStateTone,
  useCreateDataset,
  useFinalizeUpload,
  useRequestAnalysis,
  useResearchDataset,
  useResearchDatasets,
  type ResearchDatasetDetail,
  type ResearchDatasetRow,
  type StartUploadResult,
} from "@/lib/researchData";
import { useFileUpload } from "@/lib/upload";

// Command failures surface the backend canonical envelope verbatim — the client
// never invents research-data-domain messages (mirrors Market Data / Rationale).
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

// Parse an optional JSON-object payload for transport only — an unserializable
// payload cannot be sent at all. Domain validation stays server-side. Returns the
// object, or null with the error message set via onError.
function parseJsonObject(
  text: string,
  onError: (message: string) => void,
): Record<string, unknown> | null {
  if (text.trim().length === 0) return {};
  try {
    const parsed: unknown = JSON.parse(text);
    if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
      onError("Payload must be a JSON object.");
      return null;
    }
    return parsed as Record<string, unknown>;
  } catch {
    onError("Payload is not valid JSON.");
    return null;
  }
}

// Research Data (doc 12): the secondary/context layer above Market Data — open
// interest, funding, liquidations, order-book, on-chain and macro datasets that
// feed Agent research and (after approval) Backtest evidence bundles. Every
// research dataset pins an ACTIVE+APPROVED Market Data dataset (DR3). This page
// binds the role-aware read surface, the owner ingest chain (create -> upload ->
// analyze) AND the full revision lifecycle (revise/time-policy/field+feature
// defs/Admin approve+revoke/evidence bundles — see ResearchLifecycle). Page access
// is Admin/Supervisor/Agent server-side — a denial renders the 403 envelope verbatim.
export function ResearchData() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  return (
    <>
      <h1 className="page-title">Research Data</h1>
      <p className="page-sub">
        Secondary context layer · open interest, funding, liquidations, order book, on-chain &amp;
        macro · every dataset pins an Approved Market Data dataset — only an ACTIVE+APPROVED revision
        feeds research and backtest evidence bundles
      </p>
      <CreateDatasetCard onCreated={setSelectedId} />
      <RegistryCard selectedId={selectedId} onOpen={setSelectedId} />
      {selectedId !== null ? <DetailCard entityId={selectedId} /> : null}
    </>
  );
}

// ---------------------------------------------------------------------------
// Create dataset — Root + first DRAFT revision pinned to an Approved market
// dataset (DR3). No approved market link -> 409 DEPENDENCY_BLOCKED verbatim.
// ---------------------------------------------------------------------------

function CreateDatasetCard({ onCreated }: { onCreated: (entityId: string) => void }) {
  const create = useCreateDataset();
  const [marketEntityId, setMarketEntityId] = useState("");
  const [category, setCategory] = useState<string>(RESEARCH_CATEGORIES[0]);
  const [customCategory, setCustomCategory] = useState("");
  const [usageScope, setUsageScope] = useState<string>(USAGE_SCOPES[0]);
  const [displayName, setDisplayName] = useState("");
  const [providerName, setProviderName] = useState("");
  const [payloadText, setPayloadText] = useState("");
  const [payloadError, setPayloadError] = useState<string | null>(null);

  const isCustom = category === OTHER_CUSTOM_CATEGORY;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const payload = parseJsonObject(payloadText, setPayloadError);
    if (payload === null) return;
    setPayloadError(null);
    create.mutate(
      {
        market_entity_id: marketEntityId.trim(),
        payload,
        category,
        usage_scope: usageScope,
        // Only `other_custom` carries a custom category; switching away sends null
        // regardless of any stale text (the server rejects a stray value).
        custom_category: isCustom ? customCategory.trim() || null : null,
        display_name: displayName.trim() || null,
        provider_name: providerName.trim() || null,
      },
      { onSuccess: (result) => onCreated(result.entity_id) },
    );
  };

  return (
    <section className="card" aria-labelledby="rd-create-h">
      <h3 id="rd-create-h" style={{ marginTop: 0 }}>
        Add research dataset
      </h3>
      <p className="page-sub" style={{ marginTop: 0 }}>
        Link to the exact Market Data dataset whose Approved revision this pins (DR3). Without an
        ACTIVE+APPROVED market dataset the create is rejected with DEPENDENCY_BLOCKED.
      </p>
      <form onSubmit={submit}>
        <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
          <label htmlFor="rd-market">
            Linked Market Data entity id
            <input
              id="rd-market"
              value={marketEntityId}
              onChange={(event) => setMarketEntityId(event.target.value)}
              placeholder="md_…"
              required
            />
          </label>
          <label htmlFor="rd-category">
            Category
            <select id="rd-category" value={category} onChange={(event) => setCategory(event.target.value)}>
              {RESEARCH_CATEGORIES.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          {isCustom ? (
            <label htmlFor="rd-custom-category">
              Custom category (required for other_custom)
              <input
                id="rd-custom-category"
                value={customCategory}
                onChange={(event) => setCustomCategory(event.target.value)}
                placeholder="exchange_reserves"
                required
              />
            </label>
          ) : null}
          <label htmlFor="rd-usage">
            Usage scope
            <select id="rd-usage" value={usageScope} onChange={(event) => setUsageScope(event.target.value)}>
              {USAGE_SCOPES.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <label htmlFor="rd-display">
            Display name (optional)
            <input
              id="rd-display"
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              placeholder="Binance Futures Open Interest · 8h"
            />
          </label>
          <label htmlFor="rd-provider">
            Provider (optional)
            <input
              id="rd-provider"
              value={providerName}
              onChange={(event) => setProviderName(event.target.value)}
              placeholder="coinglass"
            />
          </label>
          <label htmlFor="rd-payload">
            Payload (optional JSON object)
            <textarea
              id="rd-payload"
              rows={3}
              value={payloadText}
              onChange={(event) => setPayloadText(event.target.value)}
              placeholder='{"instrument": "BTCUSDT"}'
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
// Registry — role-aware head-revision catalog (doc 12 §3)
// ---------------------------------------------------------------------------

function RegistryCard({
  selectedId,
  onOpen,
}: {
  selectedId: string | null;
  onOpen: (entityId: string) => void;
}) {
  const pager = useCursorStack();
  const datasets = useResearchDatasets(pager.cursor);

  return (
    <section className="card" aria-labelledby="rd-registry-h">
      <h3 id="rd-registry-h" style={{ marginTop: 0 }}>
        Dataset registry
        {datasets.data ? (
          <span className="page-sub" style={{ marginLeft: 8 }}>
            ({datasets.data.data.length} visible on this page)
          </span>
        ) : null}
      </h3>
      {datasets.isLoading ? (
        <Loading label="Loading research datasets…" />
      ) : datasets.isError ? (
        <ErrorState error={datasets.error} onRetry={() => void datasets.refetch()} />
      ) : datasets.data ? (
        <>
          {datasets.data.data.length === 0 ? (
            <EmptyState title="No research datasets visible yet — create the first one above" />
          ) : (
            <table className="metrics-table">
              <thead>
                <tr>
                  <th scope="col">Dataset</th>
                  <th scope="col">Category</th>
                  <th scope="col">Provider</th>
                  <th scope="col">Usage scope</th>
                  <th scope="col">Revision state</th>
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
  row: ResearchDatasetRow;
  isOpen: boolean;
  onOpen: () => void;
}) {
  return (
    <tr style={isOpen ? { background: "var(--bg-elev)" } : undefined}>
      <td>{row.display_name ?? row.entity_id}</td>
      <td>
        <code>{row.category_key ?? "—"}</code>
      </td>
      <td>{row.provider_name ?? "—"}</td>
      <td>{row.usage_scope ?? "—"}</td>
      <td>
        <StatusBadge tone={researchStateTone(row.revision_state)} label={row.revision_state} />
      </td>
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
// Detail — meaning, market link, timing, usage, ownership + revision history +
// the owner ingest workflow
// ---------------------------------------------------------------------------

function DetailCard({ entityId }: { entityId: string }) {
  const detail = useResearchDataset(entityId);

  return (
    <section className="card" aria-labelledby="rd-detail-h">
      <h3 id="rd-detail-h" style={{ marginTop: 0 }}>
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
          <ResearchLifecycle key={detail.data.entity_id} detail={detail.data} />
        </>
      ) : null}
    </section>
  );
}

function IdentitySection({ detail }: { detail: ResearchDatasetDetail }) {
  return (
    <>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <strong>{detail.display_name ?? detail.entity_id}</strong>
        <StatusBadge tone={researchStateTone(detail.revision_state)} label={detail.revision_state} />
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
            <th scope="row">Category</th>
            <td>
              <code>{detail.category_key ?? "—"}</code>
              {detail.custom_category !== null ? ` · custom: ${detail.custom_category}` : ""}
            </td>
          </tr>
          <tr>
            <th scope="row">Usage scope</th>
            <td>{detail.usage_scope ?? "—"}</td>
          </tr>
          <tr>
            <th scope="row">Provider</th>
            <td>{detail.provider_name ?? "—"}</td>
          </tr>
          <tr>
            <th scope="row">Linked market revision</th>
            <td>
              {detail.linked_market_dataset_revision_id !== null ? (
                <code>{detail.linked_market_dataset_revision_id}</code>
              ) : (
                "—"
              )}
            </td>
          </tr>
          <tr>
            <th scope="row">Event time</th>
            <td>{detail.event_time_semantics ?? "—"}</td>
          </tr>
          <tr>
            <th scope="row">Available time</th>
            <td>
              {detail.available_time_policy ?? "—"}
              {detail.available_delay_seconds !== null
                ? ` · delay ${detail.available_delay_seconds}s`
                : ""}
            </td>
          </tr>
          <tr>
            <th scope="row">Frequency</th>
            <td>{detail.frequency_policy ?? "—"}</td>
          </tr>
          <tr>
            <th scope="row">Source timezone</th>
            <td>
              {detail.source_timezone_mode ?? "—"}
              {detail.source_timezone_iana !== null ? ` · ${detail.source_timezone_iana}` : ""}
            </td>
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
            <th scope="row">Owner</th>
            <td>{detail.owner_principal_id ?? "—"}</td>
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
              v{revision.revision_no} · <code>{revision.revision_id}</code> · {revision.revision_state}
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

// The owner ingest chain (doc 12 §3 workflow strip): Step 1 register + finalize
// the raw asset, Step 2 run the durable analysis job (DRAFT -> ANALYZING).
// Buttons are never role-pre-gated — the server's owner/Admin draft gate answers
// with the canonical envelope verbatim. The revision lifecycle (revise,
// time-policy, field/feature definitions, Admin approve/revoke, evidence bundles)
// follows in the ResearchLifecycle section below.
function IngestSection({ detail }: { detail: ResearchDatasetDetail }) {
  return (
    <>
      <h4>Ingest workflow</h4>
      <UploadComposer entityId={detail.entity_id} />
      <AnalysisAction entityId={detail.entity_id} />
    </>
  );
}

// Bytes-per-unit thresholds for the human-readable progress label.
const KILOBYTE = 1024;
const MEGABYTE = KILOBYTE * 1024;

function formatBytes(bytes: number): string {
  if (bytes >= MEGABYTE) return `${(bytes / MEGABYTE).toFixed(1)} MB`;
  if (bytes >= KILOBYTE) return `${(bytes / KILOBYTE).toFixed(1)} KB`;
  return `${bytes} B`;
}

// Step 1 — native file chooser + real byte transfer (F-02). The client never
// supplies object key/digest/size/content-type; the server derives all of it
// from the transferred bytes and returns it in the response. Finalize then
// pins the raw asset onto the current draft revision.
function UploadComposer({ entityId }: { entityId: string }) {
  const queryClient = useQueryClient();
  const upload = useFileUpload<StartUploadResult>();
  const finalize = useFinalizeUpload();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const onFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    setSelectedFile(file);
    upload.reset();
  };

  const runUpload = () => {
    if (selectedFile === null) return;
    upload
      .upload(rawUploadPath(entityId), selectedFile, { idempotencyKey: crypto.randomUUID() })
      .then(() => invalidateAfterRawUpload(queryClient))
      .catch(() => {
        // Surfaced via upload.error below; nothing further to do here.
      });
  };

  const submitUpload = (event: FormEvent) => {
    event.preventDefault();
    runUpload();
  };

  const progressPercent =
    upload.progress && upload.progress.total > 0
      ? Math.round((upload.progress.loaded / upload.progress.total) * 100)
      : null;

  return (
    <div style={{ marginBottom: 16 }}>
      <strong>Step 1 — raw source</strong>
      <p className="page-sub" style={{ marginTop: 4 }}>
        Choose a local CSV/TXT file. The bytes are transferred to object storage and the object key,
        digest, size, and content type are generated automatically — you never enter storage metadata.
      </p>
      <form onSubmit={submitUpload}>
        <label htmlFor="rd-file">
          File
          <input
            id="rd-file"
            ref={fileInputRef}
            type="file"
            accept=".csv,.txt,text/csv,text/plain"
            onChange={onFileChange}
          />
        </label>
        <div style={{ display: "flex", gap: 8, marginTop: 8, alignItems: "center", flexWrap: "wrap" }}>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={selectedFile === null || upload.status === "uploading"}
          >
            Upload file
          </button>
          {upload.status === "uploading" ? (
            <button type="button" className="btn" onClick={upload.cancel}>
              Cancel
            </button>
          ) : null}
          {upload.status === "error" || upload.status === "cancelled" ? (
            <button type="button" className="btn" onClick={runUpload}>
              Retry
            </button>
          ) : null}
        </div>
      </form>

      {upload.status === "uploading" && upload.progress ? (
        <p aria-live="polite" style={{ marginTop: 8 }}>
          Uploading… {formatBytes(upload.progress.loaded)} / {formatBytes(upload.progress.total)}
          {progressPercent !== null ? ` (${progressPercent}%)` : ""}
        </p>
      ) : null}
      {upload.status === "cancelled" ? (
        <p role="alert" style={{ color: "var(--down)" }}>
          Upload cancelled.
        </p>
      ) : null}
      {upload.status === "error" ? (
        <p role="alert" style={{ color: "var(--down)" }}>
          {mutationErrorText(upload.error)}
        </p>
      ) : null}
      {upload.status === "success" && upload.data ? (
        <p aria-live="polite">
          {upload.data.deduplicated ? "Already uploaded — reused" : "Uploaded"} — asset{" "}
          <code>{upload.data.asset_id}</code> ({formatBytes(upload.data.size_bytes)}, digest{" "}
          <code>{upload.data.content_digest.slice(0, 12)}…</code>).
        </p>
      ) : null}

      <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 8, flexWrap: "wrap" }}>
        <button
          type="button"
          className="btn"
          disabled={finalize.isPending || upload.data === null}
          onClick={() =>
            upload.data
              ? finalize.mutate({ entity_id: entityId, asset_id: upload.data.asset_id })
              : undefined
          }
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
          Upload finalized — revision {finalize.data.revision_id} is now {finalize.data.revision_state}.
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
        Enqueues the durable analysis job on the data queue; the job row survives browser close and
        progress lands back on the revision state (DRAFT → ANALYZING).
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
