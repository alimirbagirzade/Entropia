import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { Pager } from "@/components/Pager";
import { StatusBadge } from "@/components/StatusBadge";
import {
  dataJobKindLabel,
  useAssignRole,
  useRedeliverDataQueue,
  useRegisteredUsers,
  useRoleMatrix,
  useSystemActors,
  type DataQueueRedeliverResult,
  type RegisteredUser,
} from "@/lib/adminPanel";
import { ApiError } from "@/lib/apiClient";
import { formatUtc } from "@/lib/backtest";
import { useCursorStack } from "@/lib/hooks";

// Command failures surface the backend canonical envelope verbatim — the
// client never invents admin-domain messages (mirrors AnalysisLab).
function mutationErrorText(error: unknown): string {
  if (error instanceof ApiError) return `${error.code}: ${error.message}`;
  return error instanceof Error ? error.message : "Request failed.";
}

// PANEL / MANAGEMENT (doc 19, UI-19): the *acting* half of the Panel — who is
// registered, what the system actors are, what each role may scope, and the
// operator recovery lever. The immutable read surface (Logs, Raw audit) is a
// separate work context at /panel/logs — the two are deliberately NOT one long
// page. A hidden menu item is never authorization: every section renders the
// server 403 envelope verbatim when denied.
export function PanelManagement() {
  return (
    <>
      <h1 className="page-title">PANEL / MANAGEMENT</h1>
      <p className="page-sub">
        Admin-only user registry, system actors and role scope matrix ·{" "}
        <Link to="/panel/logs">Go to PANEL / LOGS</Link>
      </p>
      <UsersCard />
      <SystemActorsCard />
      <RoleMatrixCard />
      <OperatorRecoveryCard />
    </>
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
// Operator recovery — data-queue redelivery (INF-03, doc 20 §6)
// ---------------------------------------------------------------------------

// The multi-actor `data` queue is deliberately excluded from the scheduler's
// auto-redelivery (the row alone cannot say which of the four actors a stuck job
// belongs to), so re-dispatch is an explicit operator action. This card
// lists+routes the jobs still QUEUED past the grace window back to their actor
// via the payload `job_kind`; legacy rows without a discriminator are reported as
// skipped, never guessed. Admin-only server-side — a non-Admin sees the 403
// envelope verbatim.
//
// UI-19: recovery is a SECONDARY flow, never a single click sitting on the
// primary surface. The form stays closed behind a disclosure, and dispatch
// requires an explicit confirm step (the Trash purge two-step precedent).
// The disclosure is presentation only — the server re-checks Admin on every call.
function OperatorRecoveryCard() {
  const [isOpen, setIsOpen] = useState(false);
  // Blank = the server's configured grace window; "0" sweeps every QUEUED data
  // job. The server validates (ge=0) and re-derives everything — this is a hint.
  const [graceInput, setGraceInput] = useState("");
  const [isConfirming, setIsConfirming] = useState(false);
  const redeliver = useRedeliverDataQueue();

  const trimmed = graceInput.trim();
  const graceNum = Number(trimmed);
  const graceInvalid = trimmed !== "" && (!Number.isInteger(graceNum) || graceNum < 0);

  const onRequestConfirm = (event: FormEvent) => {
    event.preventDefault();
    if (graceInvalid) return;
    setIsConfirming(true);
  };

  const onConfirm = () => {
    setIsConfirming(false);
    redeliver.mutate({ grace_seconds: trimmed === "" ? null : graceNum });
  };

  const close = () => {
    setIsOpen(false);
    setIsConfirming(false);
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
      {!isOpen ? (
        <>
          <p className="page-sub">
            Admin-only maintenance action. Kept off the primary surface — open it deliberately.
          </p>
          <button type="button" className="btn" onClick={() => setIsOpen(true)}>
            Open operator recovery
          </button>
        </>
      ) : (
        <>
          <form
            onSubmit={onRequestConfirm}
            style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "flex-end" }}
          >
            <label htmlFor="grace-seconds">
              Grace seconds{" "}
              <input
                id="grace-seconds"
                inputMode="numeric"
                value={graceInput}
                onChange={(event) => {
                  setGraceInput(event.target.value);
                  setIsConfirming(false);
                }}
                placeholder="default window"
              />
            </label>
            <button
              type="submit"
              className="btn"
              disabled={redeliver.isPending || graceInvalid || isConfirming}
            >
              Redeliver stuck jobs
            </button>
            <button type="button" className="btn" onClick={close}>
              Cancel
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
          {isConfirming ? (
            <div role="alert" style={{ marginTop: 12 }}>
              <p style={{ marginBottom: 8 }}>
                Re-dispatch every routable <code>data</code>-queue job still QUEUED past{" "}
                {trimmed === "" ? "the configured grace window" : `${trimmed}s`}? This enqueues real
                worker jobs.
              </p>
              <button
                type="button"
                className="btn btn-danger"
                disabled={redeliver.isPending}
                onClick={onConfirm}
              >
                Confirm redelivery
              </button>{" "}
              <button type="button" className="btn" onClick={() => setIsConfirming(false)}>
                Keep it closed
              </button>
            </div>
          ) : null}
        </>
      )}
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
