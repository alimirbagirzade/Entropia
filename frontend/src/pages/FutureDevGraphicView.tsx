import { useState, type FormEvent } from "react";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { StatusBadge } from "@/components/StatusBadge";
import { ApiError } from "@/lib/apiClient";
import { formatUtc } from "@/lib/backtest";
import {
  STATE_TONES,
  useGraphicViewOverview,
  useQueryViewDataset,
  useViewDataset,
  useViewDatasetHistory,
  type ViewDatasetRow,
} from "@/lib/capability";
import { useMe } from "@/lib/hooks";

// One immutable reference per line — trims and drops blanks (mirrors the
// CreatePackage declared-keys composer).
function parseRefLines(text: string): string[] {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
}

// Command failures surface the backend canonical envelope verbatim — the
// client never invents capability-domain messages (mirrors Panel).
function mutationErrorText(error: unknown): string {
  if (error instanceof ApiError) return `${error.code}: ${error.message}`;
  return error instanceof Error ? error.message : "Request failed.";
}

// doc 22 §7 futureDevNoHistory.empty copy — rendered verbatim, never a fake row.
const NO_OUTPUT_HISTORY =
  "No output exists because this capability has not produced an operational artifact in the current state.";

// Future Dev / Graphic View (doc 22 §4.1, spec §UI-22): the documented
// introduction plus the six static placeholder cards, all server-truth from
// GET /future-dev/graphic-view/overview (FD-01/03) — never a chart request, a
// job or fake progress (CR-09). While the capability is NOT operational the
// page is a pure placeholder: no input, table, lifecycle control or
// operational form renders (§UI-22 acceptance — an inactive capability
// exposes no usable operational control). The graphic_view-gated View Dataset
// command + its owner-scoped output history appear ONLY when the SERVER
// registry projection says the capability is operational (Limited/Active →
// `is_operational`) AND /me says the caller is authenticated — a presentation
// decision; the server still re-checks state + identity on every dispatch
// (CR-09, FD-02) and a denial renders the error envelope verbatim.
export function FutureDevGraphicView() {
  const overview = useGraphicViewOverview();
  const me = useMe();
  // Fail-closed: unknown state (loading/error) hides the operational surface.
  const operational = overview.data?.is_operational === true;
  const authenticated = me.data?.is_authenticated === true;
  return (
    <>
      <h1 className="page-title">Future Dev / Graphic View</h1>
      <p className="page-sub">
        Reserved chart and visual-review workspace — a controlled Future Dev placeholder (doc 22)
      </p>
      <section className="card" aria-labelledby="graphic-view-h">
        <h3 id="graphic-view-h" style={{ marginTop: 0 }}>
          Graphic View
        </h3>
        {overview.isLoading ? (
          <Loading label="Loading Graphic View overview…" />
        ) : overview.isError ? (
          <ErrorState error={overview.error} onRetry={() => void overview.refetch()} />
        ) : overview.data ? (
          <>
            <p>
              <StatusBadge
                label={overview.data.lifecycle_state}
                tone={STATE_TONES[overview.data.lifecycle_state] ?? "neutral"}
              />{" "}
              {overview.data.status_message}
            </p>
            <p>{overview.data.intro}</p>
            <div className="panel-grid">
              {overview.data.cards.map((card) => (
                <div className="panel-card" key={card.title}>
                  <b>{card.title}</b>
                  <p style={{ marginBottom: 0 }}>{card.text}</p>
                </div>
              ))}
            </div>
            {!operational ? (
              <p style={{ marginBottom: 0 }}>
                Operational View Dataset commands unlock when this capability reaches a Limited or
                Active state.
              </p>
            ) : null}
          </>
        ) : null}
      </section>
      {operational && authenticated ? <ViewDatasetCard /> : null}
    </>
  );
}

// ---------------------------------------------------------------------------
// View Dataset — the graphic_view-gated operational command (doc 22 §8, §10.2,
// FD-04) + its owner-scoped output history (doc 22 §7). Rendered only behind
// the server-truth operational/authenticated gate above (§UI-22).
// ---------------------------------------------------------------------------

function ViewDatasetCard() {
  return (
    <section className="card" aria-labelledby="view-dataset-section-h">
      <h3 id="view-dataset-section-h" style={{ marginTop: 0 }}>
        View Dataset
      </h3>
      <ViewDatasetComposer />
      <ViewDatasetHistory />
    </section>
  );
}

// POST /view-datasets/query — View Dataset preparation from pinned immutable
// source refs (doc 22 §10.2, FD-04). The client-side gate is display only:
// the SERVER re-checks Limited/Active on every dispatch and a stale client
// cache still gets CAPABILITY_NOT_ACTIVE — rendered verbatim, no fake job.
function ViewDatasetComposer() {
  const [sourceRefs, setSourceRefs] = useState("");
  const [schemaVersion, setSchemaVersion] = useState("");
  const [seriesRefs, setSeriesRefs] = useState("");
  const [markerRefs, setMarkerRefs] = useState("");
  const prepare = useQueryViewDataset();

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const series = parseRefLines(seriesRefs);
    const markers = parseRefLines(markerRefs);
    prepare.mutate({
      source_manifest_refs: parseRefLines(sourceRefs),
      schema_version: schemaVersion.trim(),
      // Blank optional lists are OMITTED — the route treats absent and empty
      // alike, but the request mirrors exactly what the operator pinned.
      ...(series.length > 0 ? { series_refs: series } : {}),
      ...(markers.length > 0 ? { marker_refs: markers } : {}),
    });
  };

  return (
    <form onSubmit={onSubmit} aria-labelledby="view-dataset-h">
      <h4 id="view-dataset-h">Prepare View Dataset</h4>
      <label style={{ display: "block" }}>
        Source manifest refs{" "}
        <textarea
          aria-label="Source manifest refs"
          value={sourceRefs}
          onChange={(event) => setSourceRefs(event.target.value)}
          placeholder="One immutable manifest ref per line (required)"
          rows={3}
        />
      </label>
      <label>
        Schema version{" "}
        <input
          aria-label="Schema version"
          value={schemaVersion}
          onChange={(event) => setSchemaVersion(event.target.value)}
          placeholder="e.g. v1"
        />
      </label>{" "}
      <label>
        Series refs{" "}
        <textarea
          aria-label="Series refs"
          value={seriesRefs}
          onChange={(event) => setSeriesRefs(event.target.value)}
          placeholder="Optional — one per line"
          rows={2}
        />
      </label>{" "}
      <label>
        Marker refs{" "}
        <textarea
          aria-label="Marker refs"
          value={markerRefs}
          onChange={(event) => setMarkerRefs(event.target.value)}
          placeholder="Optional — one per line"
          rows={2}
        />
      </label>{" "}
      <button
        type="submit"
        className="btn"
        disabled={
          prepare.isPending ||
          parseRefLines(sourceRefs).length === 0 ||
          schemaVersion.trim().length === 0
        }
      >
        Prepare view dataset
      </button>
      {prepare.isError ? (
        <p role="alert" style={{ color: "var(--down)", marginBottom: 0 }}>
          {mutationErrorText(prepare.error)}
        </p>
      ) : null}
      {prepare.data ? (
        <p aria-live="polite">
          View dataset prepared — <code>{prepare.data.view_dataset_id}</code> (schema{" "}
          {prepare.data.schema_version}, {prepare.data.source_manifest_refs.length} source ref
          {prepare.data.source_manifest_refs.length === 1 ? "" : "s"}).
        </p>
      ) : null}
    </form>
  );
}

function HistoryPager({
  hasMore,
  nextCursor,
  canGoBack,
  onNext,
  onPrev,
}: {
  hasMore: boolean;
  nextCursor: string | null;
  canGoBack: boolean;
  onNext: (next: string | null) => void;
  onPrev: () => void;
}) {
  if (!hasMore && !canGoBack) return null;
  return (
    <div style={{ marginTop: "0.5rem" }}>
      <button type="button" className="btn" disabled={!canGoBack} onClick={onPrev}>
        Previous
      </button>{" "}
      <button
        type="button"
        className="btn"
        disabled={!hasMore || nextCursor === null}
        onClick={() => onNext(nextCursor)}
      >
        Next
      </button>
    </div>
  );
}

function ViewDatasetHistory() {
  const [stack, setStack] = useState<(string | null)[]>([null]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const cursor = stack[stack.length - 1];
  const history = useViewDatasetHistory(cursor);

  return (
    <div style={{ marginTop: "1rem" }}>
      <h4>View Dataset history</h4>
      {history.isLoading ? (
        <Loading label="Loading view dataset history…" />
      ) : history.isError ? (
        <ErrorState error={history.error} onRetry={() => void history.refetch()} />
      ) : history.data ? (
        history.data.data.length === 0 ? (
          <EmptyState title="No output history" description={NO_OUTPUT_HISTORY} />
        ) : (
          <>
            <table className="metrics-table">
              <thead>
                <tr>
                  <th scope="col">View dataset</th>
                  <th scope="col">Schema</th>
                  <th scope="col">Source refs</th>
                  <th scope="col">Created</th>
                  <th scope="col">Detail</th>
                </tr>
              </thead>
              <tbody>
                {history.data.data.map((row) => (
                  <ViewDatasetHistoryRow
                    key={row.view_dataset_id}
                    row={row}
                    isSelected={row.view_dataset_id === selectedId}
                    onSelect={() => setSelectedId(row.view_dataset_id)}
                  />
                ))}
              </tbody>
            </table>
            <HistoryPager
              hasMore={history.data.meta.has_more}
              nextCursor={history.data.meta.cursor}
              canGoBack={stack.length > 1}
              onNext={(next) => setStack((prev) => [...prev, next])}
              onPrev={() => setStack((prev) => prev.slice(0, -1))}
            />
          </>
        )
      ) : null}
      {selectedId !== null ? <ViewDatasetDetailCard viewDatasetId={selectedId} /> : null}
    </div>
  );
}

function ViewDatasetHistoryRow({
  row,
  isSelected,
  onSelect,
}: {
  row: ViewDatasetRow;
  isSelected: boolean;
  onSelect: () => void;
}) {
  return (
    <tr>
      <td>
        <code>{row.view_dataset_id}</code>
      </td>
      <td>{row.schema_version}</td>
      <td>{row.source_manifest_refs.length}</td>
      <td>{formatUtc(row.created_at)}</td>
      <td>
        <button type="button" className="btn" disabled={isSelected} onClick={onSelect}>
          View
        </button>
      </td>
    </tr>
  );
}

function ViewDatasetDetailCard({ viewDatasetId }: { viewDatasetId: string }) {
  const detail = useViewDataset(viewDatasetId);
  if (detail.isLoading) return <Loading label="Loading view dataset…" />;
  if (detail.isError)
    return <ErrorState error={detail.error} onRetry={() => void detail.refetch()} />;
  if (!detail.data) return null;
  return (
    <dl className="kv">
      <dt>View dataset</dt>
      <dd>
        <code>{detail.data.view_dataset_id}</code>
      </dd>
      <dt>Capability</dt>
      <dd>{detail.data.capability_key}</dd>
      <dt>Schema</dt>
      <dd>{detail.data.schema_version}</dd>
      <dt>Source refs</dt>
      <dd>{detail.data.source_manifest_refs.join(", ") || "—"}</dd>
      <dt>Series / marker refs</dt>
      <dd>
        {detail.data.series_refs.join(", ") || "—"} / {detail.data.marker_refs.join(", ") || "—"}
      </dd>
      <dt>Owner</dt>
      <dd>{detail.data.owner_principal_id ?? "—"}</dd>
      <dt>Created</dt>
      <dd>{formatUtc(detail.data.created_at)}</dd>
    </dl>
  );
}
