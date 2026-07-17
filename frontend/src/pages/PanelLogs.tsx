import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { Pager } from "@/components/Pager";
import { StatusBadge } from "@/components/StatusBadge";
import {
  DEFAULT_LOG_FILTERS,
  LOG_ACTOR_TYPES,
  LOG_FAMILIES,
  LOG_SEVERITIES,
  SEVERITY_TONES,
  useAdminLogs,
  useAuditEvents,
  useLogEvent,
  useLogResourceTypes,
  type LogEventRow,
  type LogFamily,
  type LogFilters,
} from "@/lib/adminPanel";
import { formatUtc } from "@/lib/backtest";
import { useCursorStack } from "@/lib/hooks";

// PANEL / LOGS (doc 19, UI-19): the *reading* half of the Panel — the filtered
// projection over immutable audit events plus the raw append-only stream. It
// carries no registry and no role assignment; those live in the separate
// PANEL / MANAGEMENT work context at /panel/management. A hidden menu item is
// never authorization: the projection renders the server 403 envelope verbatim
// when denied.
export function PanelLogs() {
  return (
    <>
      <h1 className="page-title">PANEL / LOGS</h1>
      <p className="page-sub">
        Immutable event log projection and raw audit stream ·{" "}
        <Link to="/panel/management">Go to PANEL / MANAGEMENT</Link>
      </p>
      <LogsCard />
      <AuditStreamCard />
    </>
  );
}

// ---------------------------------------------------------------------------
// Logs — filtered projection over immutable audit events (doc 19 §4.3, §5)
// ---------------------------------------------------------------------------

function LogsCard() {
  const [filters, setFilters] = useState<LogFilters>(DEFAULT_LOG_FILTERS);
  const [draftFrom, setDraftFrom] = useState("");
  const [draftTo, setDraftTo] = useState("");
  const [draftActorId, setDraftActorId] = useState("");
  const [draftQ, setDraftQ] = useState("");
  const [draftCorrelation, setDraftCorrelation] = useState("");
  const [filterError, setFilterError] = useState<string | null>(null);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const pager = useCursorStack();
  const logs = useAdminLogs(filters, pager.cursor);
  // Server-hydrated distinct emitted target_entity_type set — never a curated list.
  const resourceTypes = useLogResourceTypes();
  const resourceTypeOptions = resourceTypes.data?.resource_types ?? [];

  const applyFilter = (patch: Partial<LogFilters>) => {
    setFilters((prev) => ({ ...prev, ...patch }));
    pager.reset();
  };

  const onSearch = (event: FormEvent) => {
    event.preventDefault();
    const from = draftFrom ? new Date(draftFrom).toISOString() : null;
    const to = draftTo ? new Date(draftTo).toISOString() : null;
    if (from && to && from > to) {
      setFilterError("From must be earlier than or equal to To.");
      return;
    }
    setFilterError(null);
    applyFilter({
      from,
      to,
      actor_id: draftActorId.trim() || null,
      q: draftQ.trim() || null,
      correlation_id: draftCorrelation.trim() || null,
    });
  };

  return (
    <section className="card panel-card" aria-labelledby="logs-h">
      <h3 id="logs-h" style={{ marginTop: 0 }}>
        Logs
      </h3>
      <form onSubmit={onSearch} style={{ display: "flex", flexWrap: "wrap", gap: 12, marginBottom: 12 }}>
        <label htmlFor="log-from">
          From{" "}
          <input
            id="log-from"
            type="datetime-local"
            value={draftFrom}
            onChange={(event) => setDraftFrom(event.target.value)}
          />
        </label>
        <label htmlFor="log-to">
          To{" "}
          <input
            id="log-to"
            type="datetime-local"
            value={draftTo}
            onChange={(event) => setDraftTo(event.target.value)}
          />
        </label>
        <label htmlFor="log-family">
          Family{" "}
          <select
            id="log-family"
            value={filters.family}
            onChange={(event) => applyFilter({ family: event.target.value as LogFamily })}
          >
            {LOG_FAMILIES.map((family) => (
              <option key={family} value={family}>
                {family}
              </option>
            ))}
          </select>
        </label>
        <label htmlFor="log-severity">
          Severity{" "}
          <select
            id="log-severity"
            value={filters.severity ?? ""}
            onChange={(event) => applyFilter({ severity: event.target.value || null })}
          >
            <option value="">all</option>
            {LOG_SEVERITIES.map((severity) => (
              <option key={severity} value={severity}>
                {severity}
              </option>
            ))}
          </select>
        </label>
        <label htmlFor="log-actor-type">
          Actor type{" "}
          <select
            id="log-actor-type"
            value={filters.actor_type ?? ""}
            onChange={(event) => applyFilter({ actor_type: event.target.value || null })}
          >
            <option value="">all</option>
            {LOG_ACTOR_TYPES.map((actorType) => (
              <option key={actorType} value={actorType}>
                {actorType}
              </option>
            ))}
          </select>
        </label>
        <label htmlFor="log-actor-id">
          Actor ID{" "}
          <input
            id="log-actor-id"
            value={draftActorId}
            onChange={(event) => setDraftActorId(event.target.value)}
            placeholder="principal id"
          />
        </label>
        <label htmlFor="log-resource-type">
          Resource type{" "}
          <select
            id="log-resource-type"
            value={filters.resource_type ?? ""}
            onChange={(event) => applyFilter({ resource_type: event.target.value || null })}
          >
            <option value="">all</option>
            {resourceTypeOptions.map((resourceType) => (
              <option key={resourceType} value={resourceType}>
                {resourceType.replace(/_/g, " ")}
              </option>
            ))}
          </select>
        </label>
        <label htmlFor="log-q">
          Search{" "}
          <input
            id="log-q"
            value={draftQ}
            onChange={(event) => setDraftQ(event.target.value)}
            placeholder="kind / subject / reason"
          />
        </label>
        <label htmlFor="log-correlation">
          Correlation{" "}
          <input
            id="log-correlation"
            value={draftCorrelation}
            onChange={(event) => setDraftCorrelation(event.target.value)}
            placeholder="correlation id prefix"
          />
        </label>
        <button type="submit" className="btn">
          Search
        </button>
      </form>
      {filterError ? (
        <p role="alert" className="error-text">
          {filterError}
        </p>
      ) : null}
      {logs.isLoading ? (
        <Loading label="Loading logs…" />
      ) : logs.isError ? (
        <ErrorState error={logs.error} onRetry={() => void logs.refetch()} />
      ) : logs.data ? (
        <>
          {logs.data.data.length === 0 ? (
            <EmptyState title="No log events match the current filters" />
          ) : (
            <table className="database-table">
              <thead>
                <tr>
                  <th scope="col">Time (UTC)</th>
                  <th scope="col">Family</th>
                  <th scope="col">Severity</th>
                  <th scope="col">Event</th>
                  <th scope="col">Actor</th>
                  <th scope="col">Message</th>
                  <th scope="col" aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {logs.data.data.map((row) => (
                  <tr key={row.event_id}>
                    <td>{formatUtc(row.occurred_at)}</td>
                    <td>{row.family}</td>
                    <td>
                      <StatusBadge
                        tone={SEVERITY_TONES[row.severity] ?? "neutral"}
                        label={row.severity}
                      />
                    </td>
                    <td>
                      <code>{row.event_kind}</code>
                    </td>
                    <td>
                      {row.actor_type}
                      {row.actor_id ? ` · ${row.actor_id}` : ""}
                    </td>
                    <td>{row.message}</td>
                    <td>
                      <button
                        type="button"
                        className="btn"
                        onClick={() => setSelectedEventId(row.event_id)}
                      >
                        Detail
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <Pager
            canPrev={pager.canPrev}
            nextCursor={logs.data.meta.cursor}
            onPrev={pager.prev}
            onNext={pager.next}
          />
        </>
      ) : null}
      {selectedEventId ? (
        <LogDetail eventId={selectedEventId} onClose={() => setSelectedEventId(null)} />
      ) : null}
    </section>
  );
}

function LogDetail({ eventId, onClose }: { eventId: string; onClose: () => void }) {
  const detail = useLogEvent(eventId);
  return (
    <div style={{ marginTop: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <h4 style={{ margin: 0 }}>Event detail</h4>
        <button type="button" className="btn" onClick={onClose}>
          Close
        </button>
      </div>
      {detail.isLoading ? (
        <Loading label="Loading event…" />
      ) : detail.isError ? (
        <ErrorState error={detail.error} onRetry={() => void detail.refetch()} />
      ) : detail.data ? (
        <>
          <dl className="kv">
            <dt>Event</dt>
            <dd>
              <code>{detail.data.event_kind}</code> ({detail.data.event_id})
            </dd>
            <dt>State</dt>
            <dd>
              {detail.data.previous_state ?? "—"} → {detail.data.new_state ?? "—"}
            </dd>
            <dt>Reason</dt>
            <dd>{detail.data.reason ?? "—"}</dd>
            <dt>Subject</dt>
            <dd>
              {detail.data.subject_type ?? "—"}
              {detail.data.subject_id ? ` · ${detail.data.subject_id}` : ""}
              {detail.data.subject_status ? ` (${detail.data.subject_status})` : ""}
            </dd>
            <dt>Correlation</dt>
            <dd>{detail.data.correlation_id ?? "—"}</dd>
            <dt>Technical</dt>
            <dd>
              trace {detail.data.technical.trace_id ?? "—"} · job{" "}
              {detail.data.technical.job_id ?? "—"} · revision{" "}
              {detail.data.technical.target_revision_id ?? "—"}
            </dd>
          </dl>
          {detail.data.subject_deleted ? (
            <p role="status">
              Source is deleted. <Link to="/trash">See Trash.</Link>
            </p>
          ) : null}
          {detail.data.causation_event ? (
            <p>
              Caused by <code>{detail.data.causation_event.event_kind}</code> (
              {detail.data.causation_event.event_id})
            </p>
          ) : null}
          {detail.data.correlation_chain.length > 0 ? (
            <>
              <h5 style={{ marginBottom: 4 }}>
                Correlation chain ({detail.data.correlation_chain.length})
              </h5>
              <ul>
                {detail.data.correlation_chain.map((entry: LogEventRow) => (
                  <li key={entry.event_id}>
                    {formatUtc(entry.occurred_at)} — <code>{entry.event_kind}</code>
                  </li>
                ))}
              </ul>
            </>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Raw audit stream (M3 §8) — the unfiltered append-only event list
// ---------------------------------------------------------------------------

function AuditStreamCard() {
  const pager = useCursorStack();
  const events = useAuditEvents(pager.cursor);
  return (
    <section className="card panel-card" aria-labelledby="audit-h">
      <h3 id="audit-h" style={{ marginTop: 0 }}>
        Audit stream (raw)
      </h3>
      {events.isLoading ? (
        <Loading label="Loading audit events…" />
      ) : events.isError ? (
        <ErrorState error={events.error} onRetry={() => void events.refetch()} />
      ) : events.data ? (
        <>
          {events.data.data.length === 0 ? (
            <EmptyState title="No audit events" />
          ) : (
            <table className="database-table">
              <thead>
                <tr>
                  <th scope="col">Time (UTC)</th>
                  <th scope="col">Event</th>
                  <th scope="col">Actor</th>
                  <th scope="col">Target</th>
                  <th scope="col">State</th>
                </tr>
              </thead>
              <tbody>
                {events.data.data.map((event) => (
                  <tr key={event.event_id}>
                    <td>{formatUtc(event.occurred_at)}</td>
                    <td>
                      <code>{event.event_kind}</code>
                    </td>
                    <td>
                      {event.actor_kind}
                      {event.actor_principal_id ? ` · ${event.actor_principal_id}` : ""}
                    </td>
                    <td>
                      {event.target_entity_type ?? "—"}
                      {event.target_entity_id ? ` · ${event.target_entity_id}` : ""}
                    </td>
                    <td>
                      {event.previous_state ?? "—"} → {event.new_state ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <Pager
            canPrev={pager.canPrev}
            nextCursor={events.data.meta.cursor}
            onPrev={pager.prev}
            onNext={pager.next}
          />
        </>
      ) : null}
    </section>
  );
}
