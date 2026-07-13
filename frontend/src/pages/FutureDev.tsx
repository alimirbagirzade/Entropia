import { useState, type FormEvent } from "react";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { StatusBadge } from "@/components/StatusBadge";
import { ApiError } from "@/lib/apiClient";
import { formatUtc } from "@/lib/backtest";
import {
  ACTIVATION_GATES,
  ANALYSIS_ARTIFACT_CAPABILITY,
  ANALYSIS_ARTIFACT_TYPES,
  STATE_TONES,
  allowedTargets,
  buildGatesSnapshot,
  gateComplete,
  useAnalysisArtifact,
  useAnalysisArtifactHistory,
  useCapabilities,
  useCapability,
  useCapabilityTransitions,
  useCreateAnalysisArtifact,
  useGraphicViewOverview,
  useQueryViewDataset,
  useTransitionCapability,
  useViewDataset,
  useViewDatasetHistory,
  type AnalysisArtifactRow,
  type Capability,
  type CapabilityDetail,
  type CapabilityTransition,
  type ViewDatasetRow,
} from "@/lib/capability";

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

// Future Dev (doc 22): the server-side Capability Registry rendered as-is —
// list/detail for any authenticated principal, the Admin-only lifecycle
// transition composer, the Graphic View overview, and the two gated
// operational composers (View Dataset + Analysis Artifact). The registry
// state shown here is display only; the server re-checks it on every command
// dispatch (CR-09, FD-02) and a denial renders the error envelope verbatim.
export function FutureDev() {
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  return (
    <>
      <h1 className="page-title">Future Dev</h1>
      <p className="page-sub">
        Capability registry — lifecycle states, activation gates, the Graphic View overview and
        the gated operational commands
      </p>
      <RegistryCard selectedKey={selectedKey} onSelect={setSelectedKey} />
      {selectedKey !== null ? <CapabilityDetailCard capabilityKey={selectedKey} /> : null}
      <GraphicViewCard />
      <AnalysisArtifactsCard />
    </>
  );
}

// ---------------------------------------------------------------------------
// Registry index (GET /capabilities, doc 22 §8)
// ---------------------------------------------------------------------------

function RegistryCard({
  selectedKey,
  onSelect,
}: {
  selectedKey: string | null;
  onSelect: (key: string) => void;
}) {
  const capabilities = useCapabilities();
  return (
    <section className="card" aria-labelledby="capabilities-h">
      <h3 id="capabilities-h" style={{ marginTop: 0 }}>
        Capabilities
      </h3>
      {capabilities.isLoading ? (
        <Loading label="Loading capability registry…" />
      ) : capabilities.isError ? (
        <ErrorState error={capabilities.error} onRetry={() => void capabilities.refetch()} />
      ) : capabilities.data ? (
        capabilities.data.capabilities.length === 0 ? (
          <EmptyState title="No capabilities registered" />
        ) : (
          <table className="metrics-table">
            <thead>
              <tr>
                <th scope="col">Capability</th>
                <th scope="col">Menu path</th>
                <th scope="col">State</th>
                <th scope="col">Operational</th>
                <th scope="col">Registry v</th>
                <th scope="col">Enabled</th>
                <th scope="col">Detail</th>
              </tr>
            </thead>
            <tbody>
              {capabilities.data.capabilities.map((row) => (
                <CapabilityRow
                  key={row.capability_key}
                  row={row}
                  isSelected={row.capability_key === selectedKey}
                  onSelect={() => onSelect(row.capability_key)}
                />
              ))}
            </tbody>
          </table>
        )
      ) : null}
    </section>
  );
}

function CapabilityRow({
  row,
  isSelected,
  onSelect,
}: {
  row: Capability;
  isSelected: boolean;
  onSelect: () => void;
}) {
  return (
    <tr>
      <td>
        <strong>{row.title}</strong>{" "}
        <code>{row.capability_key}</code>
      </td>
      <td>{row.menu_path}</td>
      <td>
        <StatusBadge label={row.lifecycle_state} tone={STATE_TONES[row.lifecycle_state] ?? "neutral"} />
      </td>
      <td>{row.is_operational ? "yes" : "no"}</td>
      <td>{row.registry_version}</td>
      <td>{formatUtc(row.enabled_at)}</td>
      <td>
        <button type="button" className="btn" disabled={isSelected} onClick={onSelect}>
          View
        </button>
      </td>
    </tr>
  );
}

// ---------------------------------------------------------------------------
// Detail + Admin lifecycle transition (GET /capabilities/{key} +
// POST /capabilities/{key}/lifecycle-transitions, doc 22 §8, §9.1, §9.2)
// ---------------------------------------------------------------------------

function CapabilityDetailCard({ capabilityKey }: { capabilityKey: string }) {
  const detail = useCapability(capabilityKey);
  // Owned by the card, not the composer: a successful transition bumps
  // registry_version and remounts the composer — the accepted/denied message
  // must survive that remount (mirrors Panel's UsersCard).
  const transition = useTransitionCapability();
  return (
    <section className="card" aria-labelledby="capability-detail-h">
      <h3 id="capability-detail-h" style={{ marginTop: 0 }}>
        Capability detail
      </h3>
      {detail.isLoading ? (
        <Loading label="Loading capability detail…" />
      ) : detail.isError ? (
        <ErrorState error={detail.error} onRetry={() => void detail.refetch()} />
      ) : detail.data ? (
        <>
          <dl className="kv">
            <dt>Capability</dt>
            <dd>
              {detail.data.title} (<code>{detail.data.capability_key}</code>)
            </dd>
            <dt>State</dt>
            <dd>
              <StatusBadge
                label={detail.data.lifecycle_state}
                tone={STATE_TONES[detail.data.lifecycle_state] ?? "neutral"}
              />{" "}
              — {detail.data.status_message}
            </dd>
            <dt>Registry version</dt>
            <dd>{detail.data.registry_version}</dd>
            <dt>Last transition</dt>
            <dd>
              {detail.data.change_reason ?? "—"}
              {detail.data.changed_by_actor_id ? ` (by ${detail.data.changed_by_actor_id})` : ""}
            </dd>
            <dt>Enabled / retired</dt>
            <dd>
              {formatUtc(detail.data.enabled_at)} / {formatUtc(detail.data.retirement_at)}
            </dd>
          </dl>
          {/* Remount the composer whenever the server head moves so the draft
              re-seeds from the fresh snapshot (mirrors ArrangeMetrics). */}
          <TransitionComposer
            key={`${detail.data.capability_key}:${detail.data.registry_version}`}
            detail={detail.data}
            transition={transition}
          />
          <CapabilityTransitionHistory capabilityKey={detail.data.capability_key} />
        </>
      ) : null}
    </section>
  );
}

// Gate checklist + transition form. Target options come from the doc-22 §9.1
// edge taxonomy mirror; the server re-validates the edge, the gates and Admin
// on dispatch — an illegal or stale submit renders the envelope verbatim.
// Immutable lifecycle-transition timeline (doc 22 §9, §13) — read-only for any
// authenticated principal. The key lives under ["capabilities"], so an Admin
// transition (which invalidates ["capabilities"]) refreshes it in the same tab.
// A never-transitioned capability shows a real empty state, never a fake row.
function CapabilityTransitionHistory({ capabilityKey }: { capabilityKey: string }) {
  const history = useCapabilityTransitions(capabilityKey);
  return (
    <div style={{ marginTop: "1rem" }}>
      <h4>Transition history</h4>
      {history.isLoading ? (
        <Loading label="Loading transition history…" />
      ) : history.isError ? (
        <ErrorState error={history.error} onRetry={() => void history.refetch()} />
      ) : history.data ? (
        history.data.transitions.length === 0 ? (
          <EmptyState
            title="No transitions"
            description="No lifecycle transition has been recorded for this capability yet."
          />
        ) : (
          <table className="metrics-table">
            <thead>
              <tr>
                <th scope="col">Transition</th>
                <th scope="col">Reason</th>
                <th scope="col">Actor</th>
                <th scope="col">Registry</th>
                <th scope="col">When</th>
              </tr>
            </thead>
            <tbody>
              {history.data.transitions.map((event) => (
                <TransitionHistoryRow key={event.event_id} event={event} />
              ))}
            </tbody>
          </table>
        )
      ) : null}
    </div>
  );
}

function TransitionHistoryRow({ event }: { event: CapabilityTransition }) {
  return (
    <tr>
      <td>
        <StatusBadge label={event.from_state} tone={STATE_TONES[event.from_state] ?? "neutral"} /> →{" "}
        <StatusBadge label={event.to_state} tone={STATE_TONES[event.to_state] ?? "neutral"} />
      </td>
      <td>{event.reason}</td>
      <td>{event.actor_principal_id ?? "—"}</td>
      <td>
        v{event.prior_registry_version} → v{event.resulting_registry_version}
      </td>
      <td>{formatUtc(event.occurred_at)}</td>
    </tr>
  );
}

function TransitionComposer({
  detail,
  transition,
}: {
  detail: CapabilityDetail;
  transition: ReturnType<typeof useTransitionCapability>;
}) {
  const targets = allowedTargets(detail.lifecycle_state);
  const [toState, setToState] = useState<string>(targets[0] ?? "");
  const [reason, setReason] = useState("");
  const [gatesDirty, setGatesDirty] = useState(false);
  const [gatesDraft, setGatesDraft] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(
      ACTIVATION_GATES.map((gate) => [gate, gateComplete(detail.dependency_snapshot.gates?.[gate])]),
    ),
  );

  if (targets.length === 0) {
    return detail.lifecycle_state === "retired" ? (
      <p>Retired is terminal — no further lifecycle transitions.</p>
    ) : (
      <p>No client-known lifecycle transitions from state “{detail.lifecycle_state}”.</p>
    );
  }

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    transition.mutate({
      capability_key: detail.capability_key,
      to_state: toState,
      reason: reason.trim(),
      expected_registry_version: detail.registry_version,
      // Untouched checklist → omit: the server keeps its stored gate record.
      ...(gatesDirty
        ? { dependency_snapshot: buildGatesSnapshot(detail.dependency_snapshot, gatesDraft) }
        : {}),
    });
  };

  return (
    <form onSubmit={onSubmit} aria-labelledby="transition-h">
      <h4 id="transition-h">Lifecycle transition (Admin)</h4>
      <fieldset>
        <legend>Activation gates (doc 22 §9.2)</legend>
        {ACTIVATION_GATES.map((gate) => (
          <label key={gate} style={{ display: "inline-block", marginRight: "1rem" }}>
            <input
              type="checkbox"
              checked={gatesDraft[gate]}
              onChange={(event) => {
                setGatesDirty(true);
                setGatesDraft((prev) => ({ ...prev, [gate]: event.target.checked }));
              }}
            />{" "}
            {gate}
          </label>
        ))}
      </fieldset>
      <label>
        Target state{" "}
        <select
          aria-label="Target state"
          value={toState}
          onChange={(event) => setToState(event.target.value)}
        >
          {targets.map((state) => (
            <option key={state} value={state}>
              {state}
            </option>
          ))}
        </select>
      </label>{" "}
      <label>
        Reason{" "}
        <input
          aria-label="Transition reason"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          placeholder="Required — recorded on the activation event"
        />
      </label>{" "}
      <button
        type="submit"
        className="btn"
        disabled={transition.isPending || reason.trim().length === 0 || toState === ""}
      >
        Apply transition
      </button>
      {transition.isError ? (
        <p role="alert" style={{ color: "var(--down)", marginBottom: 0 }}>
          {mutationErrorText(transition.error)}
        </p>
      ) : null}
      {transition.data ? (
        <p aria-live="polite">
          Transition accepted — {transition.data.capability_key} → {transition.data.lifecycle_state}{" "}
          (registry v{transition.data.registry_version}, event{" "}
          <code>{transition.data.activation_event_id}</code>).
        </p>
      ) : null}
    </form>
  );
}

// ---------------------------------------------------------------------------
// Graphic View placeholder overview (GET /future-dev/graphic-view/overview,
// doc 22 §4.1, FD-01/03) — static copy + server lifecycle state; never a
// chart request, a job or fake progress (CR-09).
// ---------------------------------------------------------------------------

function GraphicViewCard() {
  const overview = useGraphicViewOverview();
  return (
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
          {overview.data.cards.map((card) => (
            <p key={card.title}>
              <strong>{card.title}</strong> — {card.text}
            </p>
          ))}
        </>
      ) : null}
      <ViewDatasetComposer />
      <ViewDatasetHistory />
    </section>
  );
}

// ---------------------------------------------------------------------------
// Operational POSTs (doc 22 §8, §10 — CR-09/FD-02). The composers are never
// pre-gated on the client's cached registry state: the SERVER re-checks
// Limited/Active on every dispatch and an inactive capability returns
// CAPABILITY_NOT_ACTIVE — rendered verbatim, no fake job or progress.
// ---------------------------------------------------------------------------

// POST /view-datasets/query — graphic_view-gated View Dataset preparation
// from pinned immutable source refs (doc 22 §10.2, FD-04).
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

// POST /analysis-artifacts — one immutable Analysis Artifact; the gating
// capability is derived from artifact_type SERVER-side (doc 22 §10.3-§10.6,
// FD-05/09). The per-type gate shown here is a display-only mirror.
function AnalysisArtifactsCard() {
  const [artifactType, setArtifactType] = useState<string>(ANALYSIS_ARTIFACT_TYPES[0] ?? "");
  const [inputRefs, setInputRefs] = useState("");
  const [methodVersion, setMethodVersion] = useState("");
  const [outputRef, setOutputRef] = useState("");
  const create = useCreateAnalysisArtifact();

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const output = outputRef.trim();
    create.mutate({
      artifact_type: artifactType,
      input_manifest_refs: parseRefLines(inputRefs),
      method_version: methodVersion.trim(),
      ...(output.length > 0 ? { output_ref: output } : {}),
    });
  };

  return (
    <section className="card" aria-labelledby="analysis-artifacts-h">
      <h3 id="analysis-artifacts-h" style={{ marginTop: 0 }}>
        Analysis Artifacts
      </h3>
      <form onSubmit={onSubmit}>
        <label>
          Artifact type{" "}
          <select
            aria-label="Artifact type"
            value={artifactType}
            onChange={(event) => setArtifactType(event.target.value)}
          >
            {ANALYSIS_ARTIFACT_TYPES.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
        </label>{" "}
        <span>
          Gated by <code>{ANALYSIS_ARTIFACT_CAPABILITY[artifactType] ?? "unknown"}</code> — the
          server re-checks Limited/Active on dispatch.
        </span>
        <label style={{ display: "block" }}>
          Input manifest refs{" "}
          <textarea
            aria-label="Input manifest refs"
            value={inputRefs}
            onChange={(event) => setInputRefs(event.target.value)}
            placeholder="One immutable manifest ref per line (required)"
            rows={3}
          />
        </label>
        <label>
          Method version{" "}
          <input
            aria-label="Method version"
            value={methodVersion}
            onChange={(event) => setMethodVersion(event.target.value)}
            placeholder="e.g. mc-v1"
          />
        </label>{" "}
        <label>
          Output ref{" "}
          <input
            aria-label="Output ref"
            value={outputRef}
            onChange={(event) => setOutputRef(event.target.value)}
            placeholder="Optional immutable output ref"
          />
        </label>{" "}
        <button
          type="submit"
          className="btn"
          disabled={
            create.isPending ||
            parseRefLines(inputRefs).length === 0 ||
            methodVersion.trim().length === 0
          }
        >
          Create analysis artifact
        </button>
        {create.isError ? (
          <p role="alert" style={{ color: "var(--down)", marginBottom: 0 }}>
            {mutationErrorText(create.error)}
          </p>
        ) : null}
        {create.data ? (
          <p aria-live="polite">
            Analysis artifact created — <code>{create.data.artifact_id}</code> (
            {create.data.artifact_type}, gated by <code>{create.data.capability_key}</code>).
          </p>
        ) : null}
      </form>
      <AnalysisArtifactHistory />
    </section>
  );
}

// ---------------------------------------------------------------------------
// Operational output history (doc 22 §7) — the read surface for the outputs
// the two composers above create. Owner-scoped, ACTIVE-only, newest-first;
// an empty page renders the futureDevNoHistory.empty copy verbatim. A forward
// keyset cursor stack pages back and forth; selecting a row opens its
// owner-scoped detail (provenance + full pinned refs).
// ---------------------------------------------------------------------------

// doc 22 §7 futureDevNoHistory.empty copy — rendered verbatim, never a fake row.
const NO_OUTPUT_HISTORY =
  "No output exists because this capability has not produced an operational artifact in the current state.";

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

function AnalysisArtifactHistory() {
  const [artifactType, setArtifactType] = useState<string>(""); // "" = all types
  const [stack, setStack] = useState<(string | null)[]>([null]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const cursor = stack[stack.length - 1];
  const history = useAnalysisArtifactHistory(artifactType === "" ? null : artifactType, cursor);

  // Changing the filter resets the keyset stack and any open detail.
  const onFilterChange = (value: string) => {
    setArtifactType(value);
    setStack([null]);
    setSelectedId(null);
  };

  return (
    <div style={{ marginTop: "1rem" }}>
      <h4>Analysis Artifact history</h4>
      <label>
        Filter by type{" "}
        <select
          aria-label="Filter artifact type"
          value={artifactType}
          onChange={(event) => onFilterChange(event.target.value)}
        >
          <option value="">All types</option>
          {ANALYSIS_ARTIFACT_TYPES.map((type) => (
            <option key={type} value={type}>
              {type}
            </option>
          ))}
        </select>
      </label>
      {history.isLoading ? (
        <Loading label="Loading analysis artifact history…" />
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
                  <th scope="col">Artifact</th>
                  <th scope="col">Type</th>
                  <th scope="col">Method</th>
                  <th scope="col">Created</th>
                  <th scope="col">Detail</th>
                </tr>
              </thead>
              <tbody>
                {history.data.data.map((row) => (
                  <AnalysisArtifactHistoryRow
                    key={row.artifact_id}
                    row={row}
                    isSelected={row.artifact_id === selectedId}
                    onSelect={() => setSelectedId(row.artifact_id)}
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
      {selectedId !== null ? <AnalysisArtifactDetailCard artifactId={selectedId} /> : null}
    </div>
  );
}

function AnalysisArtifactHistoryRow({
  row,
  isSelected,
  onSelect,
}: {
  row: AnalysisArtifactRow;
  isSelected: boolean;
  onSelect: () => void;
}) {
  return (
    <tr>
      <td>
        <code>{row.artifact_id}</code>
      </td>
      <td>{row.artifact_type}</td>
      <td>{row.method_version}</td>
      <td>{formatUtc(row.created_at)}</td>
      <td>
        <button type="button" className="btn" disabled={isSelected} onClick={onSelect}>
          View
        </button>
      </td>
    </tr>
  );
}

function AnalysisArtifactDetailCard({ artifactId }: { artifactId: string }) {
  const detail = useAnalysisArtifact(artifactId);
  if (detail.isLoading) return <Loading label="Loading analysis artifact…" />;
  if (detail.isError)
    return <ErrorState error={detail.error} onRetry={() => void detail.refetch()} />;
  if (!detail.data) return null;
  return (
    <dl className="kv">
      <dt>Artifact</dt>
      <dd>
        <code>{detail.data.artifact_id}</code>
      </dd>
      <dt>Type</dt>
      <dd>{detail.data.artifact_type}</dd>
      <dt>Gated by</dt>
      <dd>{detail.data.capability_key}</dd>
      <dt>Method version</dt>
      <dd>{detail.data.method_version}</dd>
      <dt>Input refs</dt>
      <dd>{detail.data.input_manifest_refs.join(", ") || "—"}</dd>
      <dt>Output ref</dt>
      <dd>{detail.data.output_ref ?? "—"}</dd>
      <dt>Owner</dt>
      <dd>{detail.data.owner_principal_id ?? "—"}</dd>
      <dt>Created</dt>
      <dd>{formatUtc(detail.data.created_at)}</dd>
    </dl>
  );
}
