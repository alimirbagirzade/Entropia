// Analysis Lab data access (Stage 6a, doc 18): the Agent Workspace overview
// (runtime + active task + queue + output board), keyset task/hypothesis pages,
// task detail, and the human control commands (directive / lab message /
// pause / resume / stop — all 202 admissions; the Coordinator's durable rows
// are the only truth, never a browser array).
//
// Every query key starts with the ["agent-tasks"] prefix so the SSE
// `agent.task.updated` invalidation (lib/sse.ts EVENT_QUERY_KEYS) sweeps them.
// The overview poll below is only the loss-tolerant fallback (INF-11).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, apiRequest } from "./apiClient";

// ---------------------------------------------------------------------------
// Wire types (mirror backend application/queries/agent_workspace.py projections)
// ---------------------------------------------------------------------------

export interface AgentTaskCard {
  task_id: string;
  title: string;
  task_type: string;
  source: string;
  priority: string;
  status: string;
  stage: string | null;
  progress: number | null;
}

export interface AgentRuntime {
  agent_id: string;
  mode: string;
  status: string;
  pending_control: string | null;
  active_task_id: string | null;
  last_checkpoint_id: string | null;
  row_version: number;
}

export interface HypothesisCard {
  artifact_id: string;
  status: string;
  title: string;
  mechanism: string | null;
  data_context: string | null;
  next_action: string | null;
  evidence_refs: string[];
  source_task_id: string | null;
}

export interface AgentOverview {
  runtime: AgentRuntime;
  active_task: AgentTaskCard | null;
  context_bundle: { context_manifest_id: string; note: string } | null;
  queue: { counts: Record<string, number>; cards: AgentTaskCard[] };
  output_board: { hypotheses: HypothesisCard[] };
}

export interface AgentTaskPage {
  tasks: AgentTaskCard[];
  next_cursor: string | null;
}

export interface AgentTaskDetail extends AgentTaskCard {
  context_manifest_id: string | null;
  parent_task_id: string | null;
  waiting_reason: string | null;
  failure_reason: string | null;
  checkpoints: Array<{
    checkpoint_id: string;
    checkpoint_no: number;
    stage: string | null;
    directive_cursor: string | null;
  }>;
  directives: Array<{
    directive_id: string;
    priority: string;
    status: string;
    text: string;
    consumed_checkpoint_id: string | null;
  }>;
}

export interface HypothesisPage {
  hypotheses: HypothesisCard[];
  next_cursor: string | null;
}

// One durable Tool Gateway call, summary form (doc 18 §9.2). The `request` /
// `response_ref` payload bodies live only on the detail read.
export interface AgentToolCallCard {
  tool_call_id: string;
  tool_name: string;
  task_id: string | null;
  checkpoint_id: string | null;
  actor_kind: string;
  policy_scope: string;
  status: string;
  artifact_output_ref: string | null;
  failure_code: string | null;
  failure_message: string | null;
  correlation_id: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface AgentToolCallDetail extends AgentToolCallCard {
  agent_id: string;
  actor_principal_id: string | null;
  input_manifest_id: string | null;
  idempotency_key: string | null;
  request: Record<string, unknown>;
  response_ref: Record<string, unknown> | null;
}

export interface AgentToolCallList {
  tool_calls: AgentToolCallCard[];
}

export interface DirectiveAdmission {
  directive_id: string;
  status: string;
  priority: string;
  target_agent_id: string;
  related_task_id: string | null;
  delivery_policy: string;
  active_task_interrupted: boolean;
}

export interface LabMessageResponse {
  message: { message_id: string; type: string; text: string; task_id: string | null };
  assistant_response: { message_id: string; type: string; text: string };
  active_task_interrupted: boolean;
}

export interface RuntimeControlAccepted {
  agent_id: string;
  control: string;
  status: string;
  runtime_status?: string;
  run_id?: string;
  delivery_policy?: string;
  row_version: number;
}

// Canonical AgentTask lifecycle (backend domain/agent_lab/enums.py) — the wire
// value stays a plain string; this map only picks a badge tone.
export const TASK_STATUS_TONES: Record<string, "ok" | "warn" | "down" | "neutral"> = {
  queued: "neutral",
  running: "warn",
  waiting: "warn",
  checkpointing: "warn",
  paused: "neutral",
  succeeded: "ok",
  failed: "down",
  cancelled: "down",
};

// Human-selectable directive priorities. `autonomous` is Coordinator-generated
// only and is NEVER offered here (doc 18 §9.1, §11).
export const DIRECTIVE_PRIORITIES = ["normal", "high"] as const;
export type DirectivePriority = (typeof DIRECTIVE_PRIORITIES)[number];

// ---------------------------------------------------------------------------
// Query hooks — all under the ["agent-tasks"] SSE-invalidation prefix
// ---------------------------------------------------------------------------

const OVERVIEW_POLL_INTERVAL_MS = 15_000;

export function useAgentOverview() {
  return useQuery({
    queryKey: ["agent-tasks", "overview"],
    queryFn: () => api.get<AgentOverview>("/agent-workspace/overview"),
    // SSE agent.task.updated is the primary freshness signal; this poll is the
    // loss-tolerant fallback (INF-11).
    refetchInterval: OVERVIEW_POLL_INTERVAL_MS,
  });
}

export function useAgentTasks(status: string | null, cursor: string | null) {
  return useQuery({
    queryKey: ["agent-tasks", "list", status, cursor],
    queryFn: () => {
      const params = new URLSearchParams();
      if (status !== null) params.set("status", status);
      if (cursor !== null) params.set("cursor", cursor);
      const qs = params.toString();
      return api.get<AgentTaskPage>(`/agent-tasks${qs ? `?${qs}` : ""}`);
    },
    // Keep the current table mounted while a filter/cursor flip is in flight.
    placeholderData: (previous) => previous,
  });
}

export function useAgentTask(taskId: string | null) {
  return useQuery({
    queryKey: ["agent-tasks", "detail", taskId],
    queryFn: () => api.get<AgentTaskDetail>(`/agent-tasks/${encodeURIComponent(taskId ?? "")}`),
    enabled: taskId !== null,
  });
}

// Durable tool-call lifecycle (backend ToolCallStatus). The wire value stays a
// plain string; this map only picks a badge tone. REJECTED is a recorded
// governance denial (doc 18 §11 AL-11), rendered like a failure.
export const TOOL_CALL_STATUS_TONES: Record<string, "ok" | "warn" | "down" | "neutral"> = {
  queued: "neutral",
  running: "warn",
  succeeded: "ok",
  failed: "down",
  rejected: "down",
};

export function useTaskToolCalls(taskId: string | null) {
  return useQuery({
    queryKey: ["agent-tasks", "tool-calls", taskId],
    queryFn: () =>
      api.get<AgentToolCallList>(`/agent-tasks/${encodeURIComponent(taskId ?? "")}/tool-calls`),
    enabled: taskId !== null,
  });
}

export function useToolCall(toolCallId: string | null) {
  return useQuery({
    queryKey: ["agent-tasks", "tool-call", toolCallId],
    queryFn: () =>
      api.get<AgentToolCallDetail>(`/agent-tool-calls/${encodeURIComponent(toolCallId ?? "")}`),
    enabled: toolCallId !== null,
  });
}

export function useHypotheses() {
  return useQuery({
    queryKey: ["agent-tasks", "hypotheses"],
    queryFn: () => api.get<HypothesisPage>("/hypotheses"),
  });
}

// ---------------------------------------------------------------------------
// Mutations (202 admissions — controls land at the next safe checkpoint,
// doc 18 §8.4; the client never mutates runtime state locally)
// ---------------------------------------------------------------------------

function invalidateLab(queryClient: ReturnType<typeof useQueryClient>): void {
  void queryClient.invalidateQueries({ queryKey: ["agent-tasks"] });
}

// Pause/Resume/Stop carry the runtime row_version as an If-Match OCC token so a
// stale tab gets a 409 instead of silently clobbering a concurrent control.
function postWithIfMatch<T>(path: string, rowVersion: number): Promise<T> {
  return apiRequest<T>(path, {
    method: "POST",
    headers: { "If-Match": String(rowVersion) },
  });
}

export function useQueueDirective() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      text: string;
      priority: DirectivePriority;
      related_task_id?: string | null;
    }) =>
      api.post<DirectiveAdmission>("/agent-directives", {
        text: input.text,
        priority: input.priority,
        related_task_id: input.related_task_id ?? null,
      }),
    onSuccess: () => invalidateLab(queryClient),
  });
}

export function useSendLabMessage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { text: string; related_task_id?: string | null }) =>
      api.post<LabMessageResponse>("/lab/messages", {
        text: input.text,
        related_task_id: input.related_task_id ?? null,
      }),
    onSuccess: () => invalidateLab(queryClient),
  });
}

export function usePauseRuntime() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (rowVersion: number) =>
      postWithIfMatch<RuntimeControlAccepted>("/agent-runtime/pause", rowVersion),
    onSuccess: () => invalidateLab(queryClient),
  });
}

export function useResumeRuntime() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (rowVersion: number) =>
      postWithIfMatch<RuntimeControlAccepted>("/agent-runtime/resume", rowVersion),
    onSuccess: () => invalidateLab(queryClient),
  });
}

export function useStopRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { run_id: string; row_version: number }) =>
      postWithIfMatch<RuntimeControlAccepted>(
        `/agent-runs/${encodeURIComponent(input.run_id)}/stop`,
        input.row_version,
      ),
    onSuccess: () => invalidateLab(queryClient),
  });
}
