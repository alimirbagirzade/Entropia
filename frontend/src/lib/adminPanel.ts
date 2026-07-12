// Panel / Management / Logs data access (doc 19): Admin-only projections — the
// paged human user registry (the only role-assignment target), the read-only
// System Actor card, the canonical Role Scope Matrix, the filtered Admin Logs
// projection over immutable audit events, and the raw audit stream (M3 §8).
//
// Log/audit query keys start with the ["audit"] prefix so the SSE
// `audit.event.created` invalidation (lib/sse.ts EVENT_QUERY_KEYS) sweeps them.
// Management keys live under ["admin"] — the registry has no dedicated SSE
// event; those refresh via their own mutations and the `resource.changed`
// full sweep.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, apiRequest } from "./apiClient";

// ---------------------------------------------------------------------------
// Wire types (mirror backend application/queries/{user_registry,log_projection,
// audit_log}.py and application/commands/role_assignment.py verbatim)
// ---------------------------------------------------------------------------

export interface RegisteredUser {
  user_id: string;
  username: string;
  display_name: string | null;
  role: string;
  version: number;
  status: string;
  role_changed_at: string | null;
  role_changed_by: string | null;
  created_at: string | null;
}

export interface UsersPage {
  data: RegisteredUser[];
  meta: { cursor: string | null; has_more: boolean; limit: number };
}

export interface SystemActor {
  actor_type: string;
  actor_id: string;
  display_name: string;
  status: string;
  assignable: boolean;
}

export interface SystemActorsResponse {
  data: SystemActor[];
}

export interface RoleMatrixRow {
  role: string;
  is_system_actor: boolean;
  assignable: boolean;
  view_use: string;
  edit: string;
  delete: string;
  trash: string;
  role_assignment: string;
}

export interface RoleMatrix {
  policy_revision: string;
  columns: string[];
  rows: RoleMatrixRow[];
}

export interface AssignRoleResult {
  user_id: string;
  username: string;
  role: string;
  version: number;
  role_changed_at: string | null;
  role_changed_by: string | null;
  changed: boolean;
  audit_event_id: string | null;
  correlation_id: string | null;
}

export interface LogEventRow {
  event_id: string;
  occurred_at: string | null;
  event_kind: string;
  family: string;
  severity: string;
  actor_type: string;
  actor_id: string | null;
  subject_type: string | null;
  subject_id: string | null;
  correlation_id: string | null;
  causation_event_id: string | null;
  message: string;
}

export interface LogsPage {
  data: LogEventRow[];
  meta: { cursor: string | null; has_more: boolean; limit: number };
}

export interface LogEventDetail extends LogEventRow {
  previous_state: string | null;
  new_state: string | null;
  reason: string | null;
  subject_status: string | null;
  subject_deleted: boolean | null;
  technical: {
    trace_id: string | null;
    job_id: string | null;
    target_revision_id: string | number | null;
  };
  correlation_chain: LogEventRow[];
  causation_event: LogEventRow | null;
}

export interface AuditEventRow {
  event_id: string;
  occurred_at: string | null;
  event_kind: string;
  severity: string;
  actor_principal_id: string | null;
  actor_kind: string;
  target_entity_id: string | null;
  target_entity_type: string | null;
  previous_state: string | null;
  new_state: string | null;
  correlation_id: string | null;
}

export interface AuditEventsPage {
  data: AuditEventRow[];
  meta: { cursor: string | null; has_more: boolean };
}

// ---------------------------------------------------------------------------
// Server-owned log taxonomy (domain/admin_panel/log_taxonomy.py) mirrored for
// the filter option lists. The server rejects unknown values — these constants
// hydrate <select>s and are never client authority.
// ---------------------------------------------------------------------------

export const LOG_FAMILIES = [
  "all",
  "role_access",
  "backtest",
  "data",
  "package",
  "strategy",
  "agent",
  "trash_lifecycle",
  "system_other",
] as const;
export type LogFamily = (typeof LOG_FAMILIES)[number];

export const LOG_SEVERITIES = ["info", "warning", "error"] as const;

export const LOG_ACTOR_TYPES = ["human", "system_agent", "system"] as const;

export const LOG_RESOURCE_TYPES = [
  "user",
  "strategy",
  "package_revision",
  "dataset_revision",
  "backtest_run",
  "backtest_result",
  "artifact",
  "manual_document",
  "allocation_plan",
  "system",
] as const;

// Badge tones only — the wire severity stays a plain string.
export const SEVERITY_TONES: Record<string, "ok" | "warn" | "down" | "neutral"> = {
  info: "neutral",
  warning: "warn",
  error: "down",
};

export interface LogFilters {
  from: string | null;
  to: string | null;
  family: LogFamily;
  severity: string | null;
  actor_type: string | null;
  actor_id: string | null;
  resource_type: string | null;
  q: string | null;
  correlation_id: string | null;
}

export const DEFAULT_LOG_FILTERS: LogFilters = {
  from: null,
  to: null,
  family: "all",
  severity: null,
  actor_type: null,
  actor_id: null,
  resource_type: null,
  q: null,
  correlation_id: null,
};

// ---------------------------------------------------------------------------
// Query hooks — Management under ["admin"], Logs/Audit under the ["audit"]
// SSE-invalidation prefix
// ---------------------------------------------------------------------------

export function useRegisteredUsers(cursor: string | null) {
  return useQuery({
    queryKey: ["admin", "users", cursor],
    queryFn: () => {
      const params = new URLSearchParams();
      if (cursor !== null) params.set("cursor", cursor);
      const qs = params.toString();
      return api.get<UsersPage>(`/admin/users${qs ? `?${qs}` : ""}`);
    },
    // Keep the current table mounted while a page flip is in flight.
    placeholderData: (previous) => previous,
  });
}

export function useSystemActors() {
  return useQuery({
    queryKey: ["admin", "system-actors"],
    queryFn: () => api.get<SystemActorsResponse>("/admin/system-actors"),
  });
}

const ROLE_MATRIX_STALE_MS = 5 * 60 * 1000;

export function useRoleMatrix() {
  return useQuery({
    queryKey: ["admin", "role-matrix"],
    queryFn: () => api.get<RoleMatrix>("/admin/role-matrix"),
    // Versioned server policy (ROLE_MATRIX_REVISION) — safe to cache briefly.
    staleTime: ROLE_MATRIX_STALE_MS,
  });
}

export function useAdminLogs(filters: LogFilters, cursor: string | null) {
  return useQuery({
    queryKey: [
      "audit",
      "logs",
      filters.from,
      filters.to,
      filters.family,
      filters.severity,
      filters.actor_type,
      filters.actor_id,
      filters.resource_type,
      filters.q,
      filters.correlation_id,
      cursor,
    ],
    queryFn: () => {
      const params = new URLSearchParams();
      if (filters.from) params.set("from", filters.from);
      if (filters.to) params.set("to", filters.to);
      if (filters.family !== "all") params.set("family", filters.family);
      if (filters.severity) params.set("severity", filters.severity);
      if (filters.actor_type) params.set("actor_type", filters.actor_type);
      if (filters.actor_id) params.set("actor_id", filters.actor_id);
      if (filters.resource_type) params.set("resource_type", filters.resource_type);
      if (filters.q) params.set("q", filters.q);
      if (filters.correlation_id) params.set("correlation_id", filters.correlation_id);
      if (cursor !== null) params.set("cursor", cursor);
      const qs = params.toString();
      return api.get<LogsPage>(`/admin/logs${qs ? `?${qs}` : ""}`);
    },
    placeholderData: (previous) => previous,
  });
}

export function useLogEvent(eventId: string | null) {
  return useQuery({
    queryKey: ["audit", "log", eventId],
    queryFn: () => api.get<LogEventDetail>(`/admin/logs/${encodeURIComponent(eventId ?? "")}`),
    enabled: eventId !== null,
  });
}

export function useAuditEvents(cursor: string | null) {
  return useQuery({
    queryKey: ["audit", "events", cursor],
    queryFn: () => {
      const params = new URLSearchParams();
      if (cursor !== null) params.set("cursor", cursor);
      const qs = params.toString();
      return api.get<AuditEventsPage>(`/audit-events${qs ? `?${qs}` : ""}`);
    },
    placeholderData: (previous) => previous,
  });
}

// ---------------------------------------------------------------------------
// Mutation — role assignment (PATCH /admin/users/{id}/role)
// ---------------------------------------------------------------------------

// OCC: expected_head_revision_id carries the registry row's `version` so a
// stale tab gets the 409 envelope verbatim instead of silently clobbering a
// concurrent change. The offered role list comes from the server role matrix
// (assignable rows only) — never a hard-coded client list.
export function useAssignRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      user_id: string;
      target_role: string;
      expected_head_revision_id: number;
      reason?: string | null;
    }) =>
      // Body-form OCC (expected_head_revision_id) blocks a stale overwrite; a
      // fresh Idempotency-Key additionally dedups a network retry to one role
      // change instead of two audit events (the route reads the header).
      apiRequest<AssignRoleResult>(`/admin/users/${encodeURIComponent(input.user_id)}/role`, {
        method: "PATCH",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: {
          target_role: input.target_role,
          expected_head_revision_id: input.expected_head_revision_id,
          ...(input.reason ? { reason: input.reason } : {}),
        },
      }),
    onSuccess: () => {
      // The registry row changed AND the command emitted an audit event.
      void queryClient.invalidateQueries({ queryKey: ["admin"] });
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}

// ---------------------------------------------------------------------------
// Operator recovery — data-queue redelivery (INF-03, doc 20 §6)
// ---------------------------------------------------------------------------

// The `data` queue multiplexes four durable actors (market/research analysis,
// Trading Signal / Trade Log import). A lost broker message leaves the durable
// job QUEUED forever; the scheduler deliberately does NOT auto-redeliver it —
// the row alone cannot say which of the four actors to re-dispatch. This
// Admin-only action lists the rows still QUEUED past the grace window and routes
// each back to its actor via the payload `job_kind` discriminator. Rows that
// predate the discriminator carry no `job_kind` → counted as un-routable, never
// guessed.

// Mirror of application/jobs/data_queue.py DATA_JOB_KINDS — hydrates the result
// labels only; the server is the sole authority on which kinds route.
export const DATA_JOB_KIND_LABELS: Record<string, string> = {
  market_data_analysis: "Market data analysis",
  research_data_analysis: "Research data analysis",
  trading_signal_import: "Trading Signal import",
  trade_log_import: "Trade Log import",
};

export function dataJobKindLabel(kind: string): string {
  return DATA_JOB_KIND_LABELS[kind] ?? kind;
}

export interface DataQueueRedeliverable {
  job_kind: string;
  job_id: string;
}

// Mirrors commands/data_queue.py redeliver_data_queue_jobs return dict verbatim.
export interface DataQueueRedeliverResult {
  scanned: number;
  redeliverable: DataQueueRedeliverable[];
  skipped_unknown_kind: number;
}

// POST /admin/data-queue/redeliver — Admin-only operator recovery. `grace_seconds`
// is an optional query param (the configured window when omitted; 0 sweeps every
// QUEUED data job). No OCC token / Idempotency-Key — the route reads only the
// query and the durable rows are the source of truth (redelivery is idempotent
// server-side). The command emits one `data_queue.redelivery_requested` audit +
// outbox event, so success sweeps the ["audit"] projection (Logs / Audit stream).
export function useRedeliverDataQueue() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { grace_seconds?: number | null }) => {
      const params = new URLSearchParams();
      if (input.grace_seconds !== null && input.grace_seconds !== undefined) {
        params.set("grace_seconds", String(input.grace_seconds));
      }
      const qs = params.toString();
      return api.post<DataQueueRedeliverResult>(
        `/admin/data-queue/redeliver${qs ? `?${qs}` : ""}`,
      );
    },
    onSuccess: () => {
      // The command emitted an audit + outbox event; no data-queue read surface
      // exists, so only the audit projection needs a sweep.
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}
