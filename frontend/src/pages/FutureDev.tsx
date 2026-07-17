import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { StatusBadge } from "@/components/StatusBadge";
import { FUTURE_DEV_SUBPAGES } from "@/app/nav";
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
  useTransitionCapability,
  type AnalysisArtifactRow,
  type Capability,
  type CapabilityDetail,
  type CapabilityTransition,
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

// Future Dev (doc 22): the server-side Capability Registry rendered as-is —
// list/detail for any authenticated principal, the Admin-only lifecycle
// transition composer and the gated Analysis Artifact composer. §UI-22: the
// operational controls are never exposed in a placeholder view — the
// transition composer renders only for a server-confirmed Admin identity and
// the artifact composer only while at least one gating capability is
// operational (Limited/Active). Both gates are presentation decisions over
// SERVER projections (/me + the registry rows); the server independently
// re-checks role + state on every dispatch (CR-09, FD-02) and a denial
// renders the error envelope verbatim. The Graphic View placeholder + the
// graphic_view-gated View Dataset surface live on /future-dev/graphic-view.
export function FutureDev() {
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  return (
    <>
      <h1 className="page-title">Future Dev</h1>
      <p className="page-sub">
        Capability registry — lifecycle states, activation gates and the gated operational
        commands; each Future Dev menu area has its own placeholder page
      </p>
      <RegistryCard selectedKey={selectedKey} onSelect={setSelectedKey} />
      {selectedKey !== null ? <CapabilityDetailCard capabilityKey={selectedKey} /> : null}
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
  // UI-22: a capability with a dedicated sub-page links there (navigation
  // only — never an operational control). live_trade has no sub-page.
  const subpage = FUTURE_DEV_SUBPAGES.find(
    (candidate) => candidate.capabilityKey === row.capability_key,
  );
  return (
    <tr>
      <td>
        {subpage ? (
          <Link to={subpage.path}>
            <strong>{row.title}</strong>
          </Link>
        ) : (
          <strong>{row.title}</strong>
        )}{" "}
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
  // §UI-22: the lifecycle transition composer is a registry OPERATION — it
  // renders only for a server-confirmed Admin identity (/me projection,
  // fail-closed while unknown). Presentation only: the command layer still
  // enforces require_capability_admin on every dispatch.
  const me = useMe();
  const isAdmin = me.data?.is_admin === true;
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
          {isAdmin ? (
            /* Remount the composer whenever the server head moves so the draft
               re-seeds from the fresh snapshot (mirrors ArrangeMetrics). */
            <TransitionComposer
              key={`${detail.data.capability_key}:${detail.data.registry_version}`}
              detail={detail.data}
              transition={transition}
            />
          ) : (
            <p>
              Lifecycle transitions are an Admin operation — the transition controls are hidden
              for the current identity (the server enforces this on every dispatch).
            </p>
          )}
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
// Analysis Artifacts (doc 22 §8, §10.3-§10.6 — CR-09/FD-02/FD-05/09). §UI-22:
// the composer renders ONLY while the caller is authenticated AND at least
// one gating capability is operational (Limited/Active), and it offers ONLY
// artifact types whose gating capability is operational — an inactive
// capability exposes no usable operational control. Both gates are
// presentation over SERVER projections (/me + the registry rows; fail-closed
// while unknown): the server re-derives the gate from artifact_type on every
// dispatch and a stale client cache still gets CAPABILITY_NOT_ACTIVE —
// rendered verbatim, no fake job or progress. The owner-scoped output history
// (doc 22 §7) stays a read surface in every state.
// ---------------------------------------------------------------------------

function AnalysisArtifactsCard() {
  const capabilities = useCapabilities();
  const me = useMe();
  const operationalKeys = new Set(
    (capabilities.data?.capabilities ?? [])
      .filter((row) => row.is_operational)
      .map((row) => row.capability_key),
  );
  const enabledTypes = ANALYSIS_ARTIFACT_TYPES.filter((type) =>
    operationalKeys.has(ANALYSIS_ARTIFACT_CAPABILITY[type] ?? ""),
  );
  const authenticated = me.data?.is_authenticated === true;
  return (
    <section className="card" aria-labelledby="analysis-artifacts-h">
      <h3 id="analysis-artifacts-h" style={{ marginTop: 0 }}>
        Analysis Artifacts
      </h3>
      {authenticated && enabledTypes.length > 0 ? (
        /* Remount when the operational type set moves so the selected type
           always comes from the current server registry snapshot. */
        <AnalysisArtifactComposer key={enabledTypes.join(",")} enabledTypes={enabledTypes} />
      ) : (
        <p>
          Analysis Artifact commands are hidden — they require an authenticated identity and at
          least one gating capability in a Limited or Active state. Lifecycle progress is tracked
          in the registry above.
        </p>
      )}
      <AnalysisArtifactHistory />
    </section>
  );
}

// POST /analysis-artifacts — one immutable Analysis Artifact; the gating
// capability is derived from artifact_type SERVER-side (doc 22 §10.3-§10.6,
// FD-05/09). The per-type gate shown here is a display-only mirror.
function AnalysisArtifactComposer({ enabledTypes }: { enabledTypes: string[] }) {
  const [artifactType, setArtifactType] = useState<string>(enabledTypes[0] ?? "");
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
    <form onSubmit={onSubmit}>
      <label>
        Artifact type{" "}
        <select
          aria-label="Artifact type"
          value={artifactType}
          onChange={(event) => setArtifactType(event.target.value)}
        >
          {enabledTypes.map((type) => (
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
  );
}

// ---------------------------------------------------------------------------
// Operational output history (doc 22 §7) — the read surface for the artifacts
// the composer above creates. Owner-scoped, ACTIVE-only, newest-first; an
// empty page renders the futureDevNoHistory.empty copy verbatim (reachable in
// EVERY lifecycle state — the read surface is not an operational control). A
// forward keyset cursor stack pages back and forth; selecting a row opens its
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
