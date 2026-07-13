import { useState, type FormEvent } from "react";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { StatusBadge } from "@/components/StatusBadge";
import { ApiError } from "@/lib/apiClient";
import {
  AGENT_TASK_STATUS_FILTERS,
  DIRECTIVE_PRIORITIES,
  HYPOTHESIS_STATUS_FILTERS,
  LAB_MESSAGE_TYPE_TONES,
  TASK_STATUS_TONES,
  TOOL_CALL_STATUS_TONES,
  useAgentOverview,
  useAgentTask,
  useAgentTasks,
  useHypotheses,
  useLabMessages,
  usePauseRuntime,
  useQueueDirective,
  useResumeRuntime,
  useSendLabMessage,
  useStopRun,
  useTaskToolCalls,
  useToolCall,
  type AgentOverview,
  type AgentTaskCard,
  type AgentToolCallCard,
  type DirectivePriority,
  type LabMessageCard,
} from "@/lib/agentLab";

const RUNTIME_TONES: Record<string, "ok" | "warn" | "down" | "neutral"> = {
  active: "ok",
  paused: "neutral",
  stopping: "warn",
  recovering: "warn",
};

// Command failures surface the backend canonical envelope verbatim — the client
// never invents lab-domain messages (mirrors BacktestRun).
function mutationErrorText(error: unknown): string {
  if (error instanceof ApiError) return `${error.code}: ${error.message}`;
  return error instanceof Error ? error.message : "Request failed.";
}

// Forward-only opaque keyset cursors (server contract): Prev replays the cursor
// stack, the client never re-orders or fabricates a page (mirrors Panel).
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

// Analysis Lab (Stage 6a, doc 18): the Agent Workspace observation/control
// plane. Everything rendered here is the Coordinator's durable truth — the
// overview projection plus 202 control admissions (pause/resume/stop land at
// the next safe checkpoint, never instantly). Server policy (Admin/Supervisor)
// is authority: a denied caller sees the 403 envelope verbatim, not a hidden UI.
export function AnalysisLab() {
  const overview = useAgentOverview();

  return (
    <>
      <h1 className="page-title">Analysis Lab</h1>
      <p className="page-sub">
        Alpha Agent workspace · durable runtime, task queue and output board
      </p>
      {overview.isLoading ? (
        <Loading label="Loading agent workspace…" />
      ) : overview.isError ? (
        <ErrorState error={overview.error} onRetry={() => void overview.refetch()} />
      ) : overview.data ? (
        <Workspace overview={overview.data} />
      ) : null}
    </>
  );
}

function Workspace({ overview }: { overview: AgentOverview }) {
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  return (
    <>
      <RuntimeCard overview={overview} />
      <QueueCard
        overview={overview}
        selectedTaskId={selectedTaskId}
        onSelectTask={setSelectedTaskId}
      />
      <TaskHistoryCard selectedTaskId={selectedTaskId} onSelectTask={setSelectedTaskId} />
      {selectedTaskId ? (
        <TaskDetailCard taskId={selectedTaskId} onClose={() => setSelectedTaskId(null)} />
      ) : null}
      <DirectiveCard />
      <ConversationCard />
      <HypothesesCard />
    </>
  );
}

function RuntimeCard({ overview }: { overview: AgentOverview }) {
  const { runtime, active_task: activeTask, context_bundle: contextBundle } = overview;
  const pause = usePauseRuntime();
  const resume = useResumeRuntime();
  const stopRun = useStopRun();
  const controlError = pause.error ?? resume.error ?? stopRun.error;

  return (
    <section className="card" aria-labelledby="runtime-h">
      <h3 id="runtime-h" style={{ marginTop: 0 }}>
        Runtime
      </h3>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
        <StatusBadge tone={RUNTIME_TONES[runtime.status] ?? "neutral"} label={runtime.status} />
        <span className="badge">mode · {runtime.mode}</span>
        {runtime.pending_control ? (
          <StatusBadge tone="warn" label={`pending ${runtime.pending_control}`} />
        ) : null}
      </div>
      <dl className="kv">
        <dt>Agent</dt>
        <dd>
          <code>{runtime.agent_id}</code>
        </dd>
        <dt>Active task</dt>
        <dd>{activeTask ? `${activeTask.title} (${activeTask.status})` : "—"}</dd>
        {contextBundle ? (
          <>
            <dt>Context manifest</dt>
            <dd>
              <code>{contextBundle.context_manifest_id}</code>
            </dd>
          </>
        ) : null}
      </dl>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 14 }}>
        {runtime.status === "paused" ? (
          <button
            type="button"
            className="btn btn-primary"
            disabled={resume.isPending}
            onClick={() => resume.mutate(runtime.row_version)}
          >
            {resume.isPending ? "Resuming…" : "Resume"}
          </button>
        ) : (
          <button
            type="button"
            className="btn"
            disabled={pause.isPending || runtime.pending_control !== null}
            onClick={() => pause.mutate(runtime.row_version)}
          >
            {pause.isPending ? "Pausing…" : "Pause at next safe checkpoint"}
          </button>
        )}
        {activeTask ? (
          <button
            type="button"
            className="btn"
            disabled={stopRun.isPending}
            onClick={() =>
              stopRun.mutate({ run_id: activeTask.task_id, row_version: runtime.row_version })
            }
          >
            {stopRun.isPending ? "Stopping…" : "Stop active run"}
          </button>
        ) : null}
      </div>
      {controlError ? (
        <p role="alert" style={{ color: "var(--down)", marginBottom: 0 }}>
          {mutationErrorText(controlError)}
        </p>
      ) : null}
    </section>
  );
}

function QueueCard({
  overview,
  selectedTaskId,
  onSelectTask,
}: {
  overview: AgentOverview;
  selectedTaskId: string | null;
  onSelectTask: (taskId: string) => void;
}) {
  const counts = Object.entries(overview.queue.counts);
  const cards = overview.queue.cards;
  return (
    <section className="card" aria-labelledby="queue-h" style={{ marginTop: 18 }}>
      <h3 id="queue-h" style={{ marginTop: 0 }}>
        Task queue
      </h3>
      {counts.length > 0 ? (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginBottom: 12 }}>
          {counts.map(([status, count]) => (
            <span key={status} className="badge">
              {status} · {count}
            </span>
          ))}
        </div>
      ) : null}
      {cards.length === 0 ? (
        <EmptyState
          glyph="⧗"
          title="No agent tasks yet"
          description="Queue a directive below — the Coordinator turns it into a task."
        />
      ) : (
        <table className="metrics-table">
          <thead>
            <tr>
              <th scope="col">Task</th>
              <th scope="col">Type</th>
              <th scope="col">Priority</th>
              <th scope="col">Status</th>
              <th scope="col">Stage</th>
              <th scope="col" aria-label="Actions" />
            </tr>
          </thead>
          <tbody>
            {cards.map((task: AgentTaskCard) => (
              <tr key={task.task_id}>
                <td>{task.title}</td>
                <td>{task.task_type}</td>
                <td>{task.priority}</td>
                <td>
                  <StatusBadge tone={TASK_STATUS_TONES[task.status] ?? "neutral"} label={task.status} />
                </td>
                <td>{task.stage ?? "—"}</td>
                <td>
                  <button
                    type="button"
                    className="btn btn-ghost"
                    aria-pressed={selectedTaskId === task.task_id}
                    onClick={() => onSelectTask(task.task_id)}
                  >
                    Detail
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

// Task history — the full, browsable task record behind the bounded live queue.
// The overview queue only carries the Coordinator's current cards; aged-out
// tasks (succeeded / failed / cancelled) live here, filterable by status and
// paged with the server's opaque keyset cursor (doc 18 §9.2). The status filter
// is server-validated; an unknown value would 422, so the dropdown only offers
// the canonical AgentTaskStatus vocabulary.
function TaskHistoryCard({
  selectedTaskId,
  onSelectTask,
}: {
  selectedTaskId: string | null;
  onSelectTask: (taskId: string) => void;
}) {
  const [status, setStatus] = useState<string | null>(null);
  const pager = useCursorStack();
  const tasks = useAgentTasks(status, pager.cursor);
  const rows = tasks.data?.tasks ?? [];

  function onStatusChange(next: string) {
    setStatus(next === "" ? null : next);
    pager.reset();
  }

  return (
    <section className="card" aria-labelledby="task-history-h" style={{ marginTop: 18 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 12 }}>
        <h3 id="task-history-h" style={{ marginTop: 0 }}>
          Task history
        </h3>
        <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span>Status</span>
          <select
            value={status ?? ""}
            onChange={(event) => onStatusChange(event.target.value)}
            aria-label="Filter task history by status"
          >
            <option value="">All</option>
            {AGENT_TASK_STATUS_FILTERS.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
      </div>
      {tasks.isLoading ? (
        <Loading label="Loading task history…" />
      ) : tasks.isError ? (
        <ErrorState error={tasks.error} onRetry={() => void tasks.refetch()} />
      ) : rows.length === 0 ? (
        <EmptyState
          glyph="⧉"
          title={status === null ? "No tasks yet" : `No ${status} tasks`}
          description="The Coordinator records every task it runs here."
        />
      ) : (
        <>
          <table className="metrics-table">
            <thead>
              <tr>
                <th scope="col">Task</th>
                <th scope="col">Type</th>
                <th scope="col">Priority</th>
                <th scope="col">Status</th>
                <th scope="col">Stage</th>
                <th scope="col" aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {rows.map((task) => (
                <tr key={task.task_id}>
                  <td>{task.title}</td>
                  <td>{task.task_type}</td>
                  <td>{task.priority}</td>
                  <td>
                    <StatusBadge tone={TASK_STATUS_TONES[task.status] ?? "neutral"} label={task.status} />
                  </td>
                  <td>{task.stage ?? "—"}</td>
                  <td>
                    <button
                      type="button"
                      className="btn btn-ghost"
                      aria-pressed={selectedTaskId === task.task_id}
                      onClick={() => onSelectTask(task.task_id)}
                    >
                      Detail
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <Pager
            canPrev={pager.canPrev}
            nextCursor={tasks.data?.next_cursor ?? null}
            onPrev={pager.prev}
            onNext={pager.next}
          />
        </>
      )}
    </section>
  );
}

function TaskDetailCard({ taskId, onClose }: { taskId: string; onClose: () => void }) {
  const task = useAgentTask(taskId);
  return (
    <section className="card" aria-labelledby="task-detail-h" style={{ marginTop: 18 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <h3 id="task-detail-h" style={{ marginTop: 0 }}>
          Task detail
        </h3>
        <button type="button" className="btn btn-ghost" onClick={onClose}>
          Close
        </button>
      </div>
      {task.isLoading ? (
        <Loading label="Loading task…" />
      ) : task.isError ? (
        <ErrorState error={task.error} onRetry={() => void task.refetch()} />
      ) : task.data ? (
        <>
          <dl className="kv">
            <dt>Task</dt>
            <dd>
              <code>{task.data.task_id}</code>
            </dd>
            <dt>Title</dt>
            <dd>{task.data.title}</dd>
            <dt>Status</dt>
            <dd>{task.data.status}</dd>
            {task.data.waiting_reason ? (
              <>
                <dt>Waiting</dt>
                <dd>{task.data.waiting_reason}</dd>
              </>
            ) : null}
            {task.data.failure_reason ? (
              <>
                <dt>Failure</dt>
                <dd style={{ color: "var(--down)" }}>{task.data.failure_reason}</dd>
              </>
            ) : null}
            <dt>Checkpoints</dt>
            <dd>{task.data.checkpoints.length}</dd>
          </dl>
          {task.data.directives.length > 0 ? (
            <>
              <h4>Directives</h4>
              <ul>
                {task.data.directives.map((directive) => (
                  <li key={directive.directive_id}>
                    [{directive.status}] {directive.text}
                  </li>
                ))}
              </ul>
            </>
          ) : null}
          <ToolCallsSection taskId={taskId} />
        </>
      ) : null}
    </section>
  );
}

// Durable Tool Gateway call history for one task (doc 18 §9.2, §14) — the "safe
// observation" surface. The list is the Coordinator's truth; a row expands to
// the full request/terminal outcome, fetched on demand.
function ToolCallsSection({ taskId }: { taskId: string }) {
  const calls = useTaskToolCalls(taskId);
  const [openId, setOpenId] = useState<string | null>(null);
  return (
    <>
      <h4>Tool calls</h4>
      {calls.isLoading ? (
        <Loading label="Loading tool calls…" />
      ) : calls.isError ? (
        <ErrorState error={calls.error} onRetry={() => void calls.refetch()} />
      ) : calls.data && calls.data.tool_calls.length > 0 ? (
        <ul className="plain-list">
          {calls.data.tool_calls.map((call) => (
            <ToolCallRow
              key={call.tool_call_id}
              call={call}
              open={openId === call.tool_call_id}
              onToggle={() =>
                setOpenId((prev) => (prev === call.tool_call_id ? null : call.tool_call_id))
              }
            />
          ))}
        </ul>
      ) : (
        <EmptyState title="No tool calls recorded for this task yet." />
      )}
    </>
  );
}

function ToolCallRow({
  call,
  open,
  onToggle,
}: {
  call: AgentToolCallCard;
  open: boolean;
  onToggle: () => void;
}) {
  // Detail (request/response bodies) is fetched only while the row is expanded.
  const detail = useToolCall(open ? call.tool_call_id : null);
  return (
    <li>
      <button
        type="button"
        className="btn btn-ghost"
        onClick={onToggle}
        aria-expanded={open}
        style={{ display: "inline-flex", gap: 8, alignItems: "center" }}
      >
        <StatusBadge tone={TOOL_CALL_STATUS_TONES[call.status] ?? "neutral"} label={call.status} />
        <code>{call.tool_name}</code>
      </button>
      {call.failure_message ? (
        <span style={{ color: "var(--down)", marginLeft: 8 }}>{call.failure_message}</span>
      ) : null}
      {open ? (
        detail.isLoading ? (
          <Loading label="Loading tool call…" />
        ) : detail.isError ? (
          <ErrorState error={detail.error} onRetry={() => void detail.refetch()} />
        ) : detail.data ? (
          <pre style={{ whiteSpace: "pre-wrap", overflowX: "auto", marginTop: 6 }}>
            {JSON.stringify(
              { request: detail.data.request, response_ref: detail.data.response_ref },
              null,
              2,
            )}
          </pre>
        ) : null
      ) : null}
    </li>
  );
}

function DirectiveCard() {
  const directive = useQueueDirective();
  const message = useSendLabMessage();
  const [directiveText, setDirectiveText] = useState("");
  const [priority, setPriority] = useState<DirectivePriority>("normal");
  const [messageText, setMessageText] = useState("");

  const submitDirective = (event: FormEvent) => {
    event.preventDefault();
    const text = directiveText.trim();
    if (!text) return;
    directive.mutate({ text, priority }, { onSuccess: () => setDirectiveText("") });
  };

  const submitMessage = (event: FormEvent) => {
    event.preventDefault();
    const text = messageText.trim();
    if (!text) return;
    message.mutate({ text }, { onSuccess: () => setMessageText("") });
  };

  return (
    <section className="card" aria-labelledby="control-h" style={{ marginTop: 18 }}>
      <h3 id="control-h" style={{ marginTop: 0 }}>
        Direct the agent
      </h3>

      <form onSubmit={submitDirective}>
        <div className="auth-field">
          <label htmlFor="directive-text">Directive</label>
          <input
            id="directive-text"
            className="auth-input"
            value={directiveText}
            onChange={(event) => setDirectiveText(event.target.value)}
            placeholder="e.g. Prioritize BTCUSDT momentum research"
          />
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 10 }}>
          <label htmlFor="directive-priority" style={{ fontSize: 13, color: "var(--text-dim)" }}>
            Priority
          </label>
          <select
            id="directive-priority"
            className="auth-input"
            style={{ width: "auto" }}
            value={priority}
            onChange={(event) => setPriority(event.target.value as DirectivePriority)}
          >
            {DIRECTIVE_PRIORITIES.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={directive.isPending || directiveText.trim().length === 0}
          >
            {directive.isPending ? "Queueing…" : "Queue directive"}
          </button>
        </div>
        {directive.isError ? (
          <p role="alert" style={{ color: "var(--down)", marginBottom: 0 }}>
            {mutationErrorText(directive.error)}
          </p>
        ) : null}
        {directive.isSuccess ? (
          <p role="status" style={{ color: "var(--ok)", marginBottom: 0 }}>
            Directive queued — delivered at the {directive.data.delivery_policy.replaceAll("_", " ")}.
          </p>
        ) : null}
      </form>

      <form onSubmit={submitMessage} style={{ marginTop: 16 }}>
        <div className="auth-field">
          <label htmlFor="lab-message">Discussion message</label>
          <input
            id="lab-message"
            className="auth-input"
            value={messageText}
            onChange={(event) => setMessageText(event.target.value)}
            placeholder="Ask or note something — never interrupts the active task"
          />
        </div>
        <div style={{ marginTop: 10 }}>
          <button
            type="submit"
            className="btn"
            disabled={message.isPending || messageText.trim().length === 0}
          >
            {message.isPending ? "Sending…" : "Send message"}
          </button>
        </div>
        {message.isError ? (
          <p role="alert" style={{ color: "var(--down)", marginBottom: 0 }}>
            {mutationErrorText(message.error)}
          </p>
        ) : null}
        {message.isSuccess ? (
          <p role="status" style={{ marginBottom: 0 }}>
            Agent: {message.data.assistant_response.text}
          </p>
        ) : null}
      </form>
    </section>
  );
}

// Lab Conversation panel (doc 18 §3.2): read-only cards over the append-only
// conversation log (type/tag/time/text). The compose inputs live in the
// DirectiveCard above; this surface only observes — a sent message lands here
// via the ["agent-tasks"] invalidation, never a local echo.
function ConversationCard() {
  const pager = useCursorStack();
  const messages = useLabMessages(null, pager.cursor);
  const rows = messages.data?.messages ?? [];

  return (
    <section className="card" aria-labelledby="conversation-h" style={{ marginTop: 18 }}>
      <h3 id="conversation-h" style={{ marginTop: 0 }}>
        Lab conversation
      </h3>
      <p className="page-sub" style={{ marginTop: 0 }}>
        Read-only record of discussion messages and the assistant’s saved-context replies.
      </p>
      {messages.isLoading ? (
        <Loading label="Loading conversation…" />
      ) : messages.isError ? (
        <ErrorState error={messages.error} onRetry={() => void messages.refetch()} />
      ) : rows.length === 0 ? (
        <EmptyState
          glyph="◇"
          title="No conversation yet"
          description="Send a message above to start the conversation; the assistant replies from saved context."
        />
      ) : (
        <>
          <ul className="plain-list">
            {rows.map((row) => (
              <ConversationRow key={row.message_id} message={row} />
            ))}
          </ul>
          <Pager
            canPrev={pager.canPrev}
            nextCursor={messages.data?.next_cursor ?? null}
            onPrev={pager.prev}
            onNext={pager.next}
          />
        </>
      )}
    </section>
  );
}

function ConversationRow({ message }: { message: LabMessageCard }) {
  return (
    <li style={{ marginBottom: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <StatusBadge tone={LAB_MESSAGE_TYPE_TONES[message.type] ?? "neutral"} label={message.type} />
        {message.task_id ? (
          <span className="badge">
            task · <code>{message.task_id}</code>
          </span>
        ) : null}
        {message.created_at ? (
          <time
            dateTime={message.created_at}
            style={{ fontSize: 12, color: "var(--text-dim)", marginLeft: "auto" }}
          >
            {message.created_at}
          </time>
        ) : null}
      </div>
      <p style={{ margin: "6px 0 0", whiteSpace: "pre-wrap" }}>{message.text}</p>
    </li>
  );
}

function HypothesesCard() {
  const [status, setStatus] = useState<string | null>(null);
  const pager = useCursorStack();
  const hypotheses = useHypotheses(status, pager.cursor);
  const rows = hypotheses.data?.hypotheses ?? [];

  function onStatusChange(next: string) {
    setStatus(next === "" ? null : next);
    pager.reset();
  }

  return (
    <section className="card" aria-labelledby="hypotheses-h" style={{ marginTop: 18 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 12 }}>
        <h3 id="hypotheses-h" style={{ marginTop: 0 }}>
          Hypothesis &amp; output board
        </h3>
        <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span>Status</span>
          <select
            value={status ?? ""}
            onChange={(event) => onStatusChange(event.target.value)}
            aria-label="Filter hypotheses by status"
          >
            <option value="">All</option>
            {HYPOTHESIS_STATUS_FILTERS.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
      </div>
      {hypotheses.isLoading ? (
        <Loading label="Loading hypotheses…" />
      ) : hypotheses.isError ? (
        <ErrorState error={hypotheses.error} onRetry={() => void hypotheses.refetch()} />
      ) : rows.length === 0 ? (
        <EmptyState
          glyph="◇"
          title={status === null ? "No hypotheses yet" : `No ${status} hypotheses`}
          description="Completed research tasks publish their hypotheses here."
        />
      ) : (
        <>
          <table className="metrics-table">
            <thead>
              <tr>
                <th scope="col">Hypothesis</th>
                <th scope="col">Status</th>
                <th scope="col">Mechanism</th>
                <th scope="col">Next action</th>
                <th scope="col">Source task</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.artifact_id}>
                  <td>{row.title}</td>
                  <td>{row.status}</td>
                  <td>{row.mechanism ?? "—"}</td>
                  <td>{row.next_action ?? "—"}</td>
                  <td>{row.source_task_id ? <code>{row.source_task_id}</code> : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <Pager
            canPrev={pager.canPrev}
            nextCursor={hypotheses.data?.next_cursor ?? null}
            onPrev={pager.prev}
            onNext={pager.next}
          />
        </>
      )}
    </section>
  );
}
