import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { StatusBadge } from "@/components/StatusBadge";
import {
  dataJobKindLabel,
  DEFAULT_LOG_FILTERS,
  LOG_ACTOR_TYPES,
  LOG_FAMILIES,
  LOG_SEVERITIES,
  SEVERITY_TONES,
  useAdminLogs,
  useAssignRole,
  useAuditEvents,
  useLogEvent,
  useLogResourceTypes,
  useRedeliverDataQueue,
  useRegisteredUsers,
  useRoleMatrix,
  useSystemActors,
  type DataQueueRedeliverResult,
  type LogEventRow,
  type LogFamily,
  type LogFilters,
  type RegisteredUser,
} from "@/lib/adminPanel";
import { ApiError } from "@/lib/apiClient";
import { formatUtc } from "@/lib/backtest";

// Command failures surface the backend canonical envelope verbatim — the
// client never invents admin-domain messages (mirrors AnalysisLab).
function mutationErrorText(error: unknown): string {
  if (error instanceof ApiError) return `${error.code}: ${error.message}`;
  return error instanceof Error ? error.message : "Request failed.";
}

// Forward-only opaque keyset cursors (server contract): Prev replays the
// cursor stack, the client never re-orders or fabricates a page.
function useCursorStack() {
  const [stack, setStack] = useState<string[]>([]);
  const cursor = stack.length > 0 ? stack[stack.length - 1] : null;
  return {
    cursor,
    canPrev: stack.length > 0,
    next: (nextCursor: string) => setStack((prev) => [...prev, nextCursor]),
    prev: () => setStack((prev) => prev.slice(0, -1)),
    reset: () => setStack([]),
  };
}

// Panel / Management / Logs (doc 19): Admin-only user registry + role
// assignment, read-only System Actors and Role Scope Matrix, and the
// immutable Logs projection. A hidden menu item is never authorization —
// every section renders the server 403 envelope verbatim when denied.
export function Panel() {
  return (
    <>
      <h1 className="page-title">Panel / Management / Logs</h1>
      <p className="page-sub">
        Admin-only user registry, role scope matrix and immutable event logs
      </p>
      <UsersCard />
      <SystemActorsCard />
      <RoleMatrixCard />
      <LogsCard />
      <AuditStreamCard />
      <OperatorRecoveryCard />
    </>
  );
}

// ---------------------------------------------------------------------------
// Operator recovery — data-queue redelivery (INF-03, doc 20 §6)
// ---------------------------------------------------------------------------

// The multi-actor `data` queue is deliberately excluded from the scheduler's
// auto-redelivery (the row alone cannot say which of the four actors a stuck job
// belongs to), so re-dispatch is an explicit operator action. This card
// lists+routes the jobs still QUEUED past the grace window back to their actor
// via the payload `job_kind`; legacy rows without a discriminator are reported as
// skipped, never guessed. Admin-only server-side — a non-Admin sees the 403
// envelope verbatim.
function OperatorRecoveryCard() {
  // Blank = the server's configured grace window; "0" sweeps every QUEUED data
  // job. The server validates (ge=0) and re-derives everything — this is a hint.
  const [graceInput, setGraceInput] = useState("");
  const redeliver = useRedeliverDataQueue();

  const trimmed = graceInput.trim();
  const graceNum = Number(trimmed);
  const graceInvalid = trimmed !== "" && (!Number.isInteger(graceNum) || graceNum < 0);

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (graceInvalid) return;
    redeliver.mutate({ grace_seconds: trimmed === "" ? null : graceNum });
  };

  return (
    <section className="card panel-card" aria-labelledby="recovery-h">
      <h3 id="recovery-h" style={{ marginTop: 0 }}>
        Operator recovery — data queue
      </h3>
      <p className="page-sub">
        Re-dispatch durable <code>data</code>-queue jobs still QUEUED past the redeliver grace
        window. The multi-actor data queue is not auto-redelivered by the scheduler — each stuck
        job is routed back to its actor via the payload <code>job_kind</code>. Redelivery is
        idempotent; the durable rows are untouched.
      </p>
      <form
        onSubmit={onSubmit}
        style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "flex-end" }}
      >
        <label htmlFor="grace-seconds">
          Grace seconds{" "}
          <input
            id="grace-seconds"
            inputMode="numeric"
            value={graceInput}
            onChange={(event) => setGraceInput(event.target.value)}
            placeholder="default window"
          />
        </label>
        <button type="submit" className="btn" disabled={redeliver.isPending || graceInvalid}>
          Redeliver stuck jobs
        </button>
      </form>
      <p className="page-sub" style={{ marginBottom: 0 }}>
        Leave blank for the configured window; <code>0</code> sweeps every QUEUED data job.
      </p>
      {graceInvalid ? (
        <p role="alert" style={{ color: "var(--down)", marginBottom: 0 }}>
          Grace seconds must be a whole number of seconds (0 or greater).
        </p>
      ) : null}
      {redeliver.isError ? (
        <p role="alert" style={{ color: "var(--down)", marginBottom: 0 }}>
          {mutationErrorText(redeliver.error)}
        </p>
      ) : null}
      {redeliver.data ? <RedeliverResult result={redeliver.data} /> : null}
    </section>
  );
}

function RedeliverResult({ result }: { result: DataQueueRedeliverResult }) {
  return (
    <div aria-live="polite" style={{ marginTop: 12 }}>
      <p style={{ marginBottom: 8 }}>
        Scanned {result.scanned} stuck {result.scanned === 1 ? "job" : "jobs"} · re-dispatched{" "}
        {result.redeliverable.length} · skipped {result.skipped_unknown_kind} un-routable.
      </p>
      {result.redeliverable.length > 0 ? (
        <table className="database-table">
          <thead>
            <tr>
              <th scope="col">Job kind</th>
              <th scope="col">Job id</th>
            </tr>
          </thead>
          <tbody>
            {result.redeliverable.map((item) => (
              <tr key={item.job_id}>
                <td>{dataJobKindLabel(item.job_kind)}</td>
                <td>
                  <code>{item.job_id}</code>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <EmptyState title="No routable data-queue jobs past the grace window" />
      )}
      {result.skipped_unknown_kind > 0 ? (
        <p className="page-sub" style={{ marginBottom: 0 }}>
          {result.skipped_unknown_kind} legacy row(s) carry no <code>job_kind</code> discriminator
          and were left untouched (never guessed).
        </p>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Management — human user registry + role assignment (doc 19 §4.1)
// ---------------------------------------------------------------------------

function UsersCard() {
  const pager = useCursorStack();
  const users = useRegisteredUsers(pager.cursor);
  const matrix = useRoleMatrix();
  const assign = useAssignRole();
  const [draftRoles, setDraftRoles] = useState<Record<string, string>>({});

  // Server truth: only matrix rows flagged assignable are offered (the Agent
  // system-actor row is present in the matrix but never assignable).
  const assignableRoles = (matrix.data?.rows ?? [])
    .filter((row) => row.assignable)
    .map((row) => row.role);

  return (
    <section className="card panel-card" aria-labelledby="users-h">
      <h3 id="users-h" style={{ marginTop: 0 }}>
        Registered users
      </h3>
      {users.isLoading ? (
        <Loading label="Loading user registry…" />
      ) : users.isError ? (
        <ErrorState error={users.error} onRetry={() => void users.refetch()} />
      ) : users.data ? (
        <>
          {users.data.data.length === 0 ? (
            <EmptyState title="No registered users" />
          ) : (
            <table className="database-table">
              <thead>
                <tr>
                  <th scope="col">Username</th>
                  <th scope="col">Display name</th>
                  <th scope="col">Role</th>
                  <th scope="col">Status</th>
                  <th scope="col">Role changed</th>
                  <th scope="col">Assign</th>
                </tr>
              </thead>
              <tbody>
                {users.data.data.map((user) => (
                  <UserRow
                    key={user.user_id}
                    user={user}
                    assignableRoles={assignableRoles}
                    draftRole={draftRoles[user.user_id] ?? user.role}
                    onDraftRole={(role) =>
                      setDraftRoles((prev) => ({ ...prev, [user.user_id]: role }))
                    }
                    onApply={(targetRole) =>
                      assign.mutate({
                        user_id: user.user_id,
                        target_role: targetRole,
                        expected_head_revision_id: user.version,
                      })
                    }
                    isPending={assign.isPending}
                  />
                ))}
              </tbody>
            </table>
          )}
          <Pager
            canPrev={pager.canPrev}
            nextCursor={users.data.meta.cursor}
            onPrev={pager.prev}
            onNext={pager.next}
          />
        </>
      ) : null}
      {assign.isError ? (
        <p role="alert" style={{ color: "var(--down)", marginBottom: 0 }}>
          {mutationErrorText(assign.error)}
        </p>
      ) : null}
      {assign.data ? (
        <p aria-live="polite">
          Role assignment accepted — {assign.data.username} → {assign.data.role} (v
          {assign.data.version}
          {assign.data.changed ? "" : ", unchanged"}).
        </p>
      ) : null}
    </section>
  );
}

function UserRow({
  user,
  assignableRoles,
  draftRole,
  onDraftRole,
  onApply,
  isPending,
}: {
  user: RegisteredUser;
  assignableRoles: string[];
  draftRole: string;
  onDraftRole: (role: string) => void;
  onApply: (targetRole: string) => void;
  isPending: boolean;
}) {
  return (
    <tr>
      <td>
        <code>{user.username}</code>
      </td>
      <td>{user.display_name ?? "—"}</td>
      <td>
        <span className="badge">{user.role}</span>
      </td>
      <td>{user.status}</td>
      <td>
        {formatUtc(user.role_changed_at)}
        {user.role_changed_by ? ` by ${user.role_changed_by}` : ""}
      </td>
      <td>
        <select
          aria-label={`Role for ${user.username}`}
          value={draftRole}
          onChange={(event) => onDraftRole(event.target.value)}
        >
          {assignableRoles.map((role) => (
            <option key={role} value={role}>
              {role}
            </option>
          ))}
        </select>{" "}
        <button
          type="button"
          className="btn"
          disabled={isPending || draftRole === user.role}
          onClick={() => onApply(draftRole)}
        >
          Apply
        </button>
      </td>
    </tr>
  );
}

// ---------------------------------------------------------------------------
// Management — read-only System Actors + Role Scope Matrix (doc 19 §3.3, §6.1)
// ---------------------------------------------------------------------------

function SystemActorsCard() {
  const actors = useSystemActors();
  return (
    <section className="card panel-card" aria-labelledby="actors-h">
      <h3 id="actors-h" style={{ marginTop: 0 }}>
        System actors
      </h3>
      {actors.isLoading ? (
        <Loading label="Loading system actors…" />
      ) : actors.isError ? (
        <ErrorState error={actors.error} onRetry={() => void actors.refetch()} />
      ) : actors.data ? (
        actors.data.data.length === 0 ? (
          <EmptyState title="No system actors" />
        ) : (
          <table className="database-table">
            <thead>
              <tr>
                <th scope="col">Actor</th>
                <th scope="col">Type</th>
                <th scope="col">Status</th>
                <th scope="col">Role assignment</th>
              </tr>
            </thead>
            <tbody>
              {actors.data.data.map((actor) => (
                <tr key={actor.actor_id}>
                  <td>{actor.display_name}</td>
                  <td>{actor.actor_type}</td>
                  <td>
                    <StatusBadge
                      tone={actor.status === "enabled" ? "ok" : "neutral"}
                      label={actor.status}
                    />
                  </td>
                  <td>{actor.assignable ? "assignable" : "not assignable"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )
      ) : null}
    </section>
  );
}

function RoleMatrixCard() {
  const matrix = useRoleMatrix();
  return (
    <section className="card panel-card" aria-labelledby="matrix-h">
      <h3 id="matrix-h" style={{ marginTop: 0 }}>
        Role scope matrix
      </h3>
      {matrix.isLoading ? (
        <Loading label="Loading role matrix…" />
      ) : matrix.isError ? (
        <ErrorState error={matrix.error} onRetry={() => void matrix.refetch()} />
      ) : matrix.data ? (
        <>
          <p className="page-sub">
            Read-only server policy · revision <code>{matrix.data.policy_revision}</code>
          </p>
          <table className="database-table">
            <thead>
              <tr>
                <th scope="col">Role</th>
                {matrix.data.columns.map((column) => (
                  <th scope="col" key={column}>
                    {column.replace(/_/g, " ")}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {matrix.data.rows.map((row) => (
                <tr key={row.role}>
                  <td>
                    <span className="badge">{row.role}</span>
                    {row.is_system_actor ? " (system actor)" : ""}
                  </td>
                  <td>{row.view_use}</td>
                  <td>{row.edit}</td>
                  <td>{row.delete}</td>
                  <td>{row.trash}</td>
                  <td>{row.role_assignment}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : null}
    </section>
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
