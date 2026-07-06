import { useState, type FormEvent } from "react";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { StatusBadge } from "@/components/StatusBadge";
import { ApiError } from "@/lib/apiClient";
import { formatUtc } from "@/lib/backtest";
import {
  ACTIVATION_GATES,
  STATE_TONES,
  allowedTargets,
  buildGatesSnapshot,
  gateComplete,
  useCapabilities,
  useCapability,
  useGraphicViewOverview,
  useTransitionCapability,
  type Capability,
  type CapabilityDetail,
} from "@/lib/capability";

// Command failures surface the backend canonical envelope verbatim — the
// client never invents capability-domain messages (mirrors Panel).
function mutationErrorText(error: unknown): string {
  if (error instanceof ApiError) return `${error.code}: ${error.message}`;
  return error instanceof Error ? error.message : "Request failed.";
}

// Future Dev (doc 22): the server-side Capability Registry rendered as-is —
// list/detail for any authenticated principal, the Admin-only lifecycle
// transition composer, and the static Graphic View placeholder overview.
// The registry state shown here is display only; the server re-checks it on
// every command dispatch (CR-09, FD-02) and a denied transition renders the
// server error envelope verbatim.
export function FutureDev() {
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  return (
    <>
      <h1 className="page-title">Future Dev</h1>
      <p className="page-sub">
        Capability registry — lifecycle states, activation gates and the Graphic View placeholder
      </p>
      <RegistryCard selectedKey={selectedKey} onSelect={setSelectedKey} />
      {selectedKey !== null ? <CapabilityDetailCard capabilityKey={selectedKey} /> : null}
      <GraphicViewCard />
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
        </>
      ) : null}
    </section>
  );
}

// Gate checklist + transition form. Target options come from the doc-22 §9.1
// edge taxonomy mirror; the server re-validates the edge, the gates and Admin
// on dispatch — an illegal or stale submit renders the envelope verbatim.
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
// Graphic View placeholder overview (GET /future-dev/graphic_view/overview,
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
    </section>
  );
}
