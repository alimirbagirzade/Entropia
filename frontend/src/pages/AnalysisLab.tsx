import { useState } from "react";

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
  type HypothesisCard,
  type LabMessageCard,
} from "@/lib/agentLab";

// The mockup pill classes only style `active`/`paused`; every other runtime or
// queue state falls back to the neutral base pill (no fabricated colour).
const LAB_PILL_STATES = new Set(["active", "paused", "running", "queued", "waiting"]);
const HYPOTHESIS_PILL_STATES = new Set(["testing", "candidate", "exploring"]);

function pillState(status: string, allowed: Set<string>): string {
  return allowed.has(status) ? status : "";
}

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
// plane, laid out to the v18 mockup — a runtime topbar, a three-column grid
// (Lab Context · Lab Conversation · Work Queue) and a Hypothesis & Output board.
// Everything rendered here is the Coordinator's durable truth: the overview
// projection plus 202 control admissions (pause/resume/stop land at the next
// safe checkpoint, never instantly). Server policy (Admin/Supervisor) is
// authority — a denied caller sees the 403 envelope verbatim, never a hidden UI.
export function AnalysisLab() {
  const overview = useAgentOverview();

  return (
    <>
      <h1 className="page-title">Analysis Lab</h1>
      <div className="analysis-lab-intro">
        <b>Analysis Lab</b> is the operational research environment. The visible chat
        counterpart is the <b>Lab Assistant</b>; Alpha Agent continues its autonomous work
        from saved checkpoints and is not interrupted by normal messages or directives.
      </div>
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
      <LabTopbar overview={overview} />
      <div className="analysis-lab-grid">
        <LabContextPanel overview={overview} />
        <LabConversationPanel />
        <WorkQueuePanel
          overview={overview}
          selectedTaskId={selectedTaskId}
          onSelectTask={setSelectedTaskId}
        />
      </div>
      <TaskHistoryCard selectedTaskId={selectedTaskId} onSelectTask={setSelectedTaskId} />
      {selectedTaskId ? (
        <TaskDetailCard taskId={selectedTaskId} onClose={() => setSelectedTaskId(null)} />
      ) : null}
      <OutputBoard />
    </>
  );
}

// Runtime bar (mockup .lab-topbar): status pill + mode tag + current work on the
// left; Pause/Resume + Stop on the right. The buttons are NOT client role-gated
// — the command layer is authority; a denied caller gets the 403 verbatim below.
function LabTopbar({ overview }: { overview: AgentOverview }) {
  const { runtime, active_task: activeTask } = overview;
  const pause = usePauseRuntime();
  const resume = useResumeRuntime();
  const stopRun = useStopRun();
  const controlError = pause.error ?? resume.error ?? stopRun.error;

  return (
    <section aria-label="Agent runtime">
      <div className="lab-topbar">
        <div className="lab-topbar-left">
          <span className="lab-title-line">ALPHA AGENT</span>
          <span className={`lab-status-pill ${pillState(runtime.status, LAB_PILL_STATES)}`}>
            {runtime.status}
          </span>
          <span className="lab-tag">{runtime.mode.toUpperCase()} MODE</span>
          {runtime.pending_control ? (
            <span className="lab-tag">PENDING {runtime.pending_control.toUpperCase()}</span>
          ) : null}
          <span className="lab-status-detail">
            Current work:{" "}
            <strong>{activeTask ? `${activeTask.title} (${activeTask.status})` : "—"}</strong>
          </span>
        </div>
        <div className="lab-topbar-right">
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
      </div>
      {controlError ? (
        <p role="alert" style={{ color: "var(--down)", marginTop: -4, marginBottom: 12 }}>
          {mutationErrorText(controlError)}
        </p>
      ) : null}
    </section>
  );
}

// LAB CONTEXT panel (mockup, read-only). The top card grid binds the live
// overview (agent id, mode, active task, last checkpoint); the sections below
// are the fixed mission / checkpoint / boundary copy from doc 18.
function LabContextPanel({ overview }: { overview: AgentOverview }) {
  const { runtime, active_task: activeTask, context_bundle: contextBundle } = overview;
  return (
    <section className="lab-panel" aria-label="Lab context">
      <div className="lab-panel-head">
        LAB CONTEXT <span className="lab-tag">READ ONLY</span>
      </div>
      <div className="lab-panel-body">
        <div className="agent-data-grid">
          <div className="agent-data-card">
            <div className="lab-context-label">AGENT</div>
            <div className="lab-context-value">
              <code>{runtime.agent_id}</code>
            </div>
          </div>
          <div className="agent-data-card">
            <div className="lab-context-label">MODE</div>
            <div className="lab-context-value">{runtime.mode}</div>
          </div>
          {activeTask ? (
            <div className="agent-data-card">
              <div className="lab-context-label">ACTIVE TASK</div>
              <div className="lab-context-value">{activeTask.title}</div>
            </div>
          ) : null}
          {runtime.last_checkpoint_id ? (
            <div className="agent-data-card">
              <div className="lab-context-label">CHECKPOINT</div>
              <div className="lab-context-value">
                <code>{runtime.last_checkpoint_id}</code>
              </div>
            </div>
          ) : null}
        </div>
        <div className="lab-context-section" style={{ marginTop: 10 }}>
          <div className="lab-context-label">PRIMARY MISSION</div>
          <div className="lab-context-value">
            Discover, test and refine robust, low-correlation trading strategies using Approved
            Market Data, Research Data and reusable Packages.
          </div>
        </div>
        {contextBundle ? (
          <div className="lab-context-section">
            <div className="lab-context-label">ACTIVE DATA BUNDLE</div>
            <div className="lab-context-value">
              <code>{contextBundle.context_manifest_id}</code>
            </div>
            {contextBundle.note ? (
              <div className="lab-context-value">{contextBundle.note}</div>
            ) : null}
            <ul className="lab-context-list">
              <li>Instrument mapping: Passed</li>
              <li>Available-time rules: Passed</li>
              <li>Dataset versions: Locked per run</li>
            </ul>
          </div>
        ) : null}
        <div className="lab-context-section">
          <div className="lab-context-label">SAFE CHECKPOINT RULE</div>
          <div className="lab-context-value">
            Directives are queued. Alpha Agent reads them only after the current planning,
            analysis or backtest checkpoint is completed.
          </div>
        </div>
        <div className="lab-context-section">
          <div className="lab-context-label">AGENT BOUNDARIES</div>
          <ul className="lab-context-list">
            <li>May create hypotheses, drafts and backtest requests.</li>
            <li>May use Approved data and usable packages.</li>
            <li>Cannot approve datasets, access Trash, alter roles or start live trading.</li>
          </ul>
        </div>
      </div>
    </section>
  );
}

// LAB CONVERSATION panel (mockup): the read-only message list (.lab-messages)
// over the append-only conversation log, plus the compose area. A discussion
// message and a queued directive share the one textarea (mockup Send Message /
// Send as Directive) but hit different endpoints — a sent message lands in the
// list via the ["agent-tasks"] invalidation, never a local echo.
function LabConversationPanel() {
  const pager = useCursorStack();
  const messages = useLabMessages(null, pager.cursor);
  const rows = messages.data?.messages ?? [];

  const directive = useQueueDirective();
  const message = useSendLabMessage();
  const [composeText, setComposeText] = useState("");
  const [priority, setPriority] = useState<DirectivePriority>("normal");

  const sendMessage = () => {
    const text = composeText.trim();
    if (!text) return;
    message.mutate({ text }, { onSuccess: () => setComposeText("") });
  };

  const sendDirective = () => {
    const text = composeText.trim();
    if (!text) return;
    directive.mutate({ text, priority }, { onSuccess: () => setComposeText("") });
  };

  return (
    <section className="lab-panel" aria-label="Lab conversation">
      <div className="lab-panel-head">
        LAB CONVERSATION <span className="lab-tag">LAB ASSISTANT</span>
      </div>
      <div className="lab-messages">
        {messages.isLoading ? (
          <Loading label="Loading conversation…" />
        ) : messages.isError ? (
          <ErrorState error={messages.error} onRetry={() => void messages.refetch()} />
        ) : rows.length === 0 ? (
          <EmptyState
            glyph="◇"
            title="No conversation yet"
            description="Send a message below to start the conversation; the assistant replies from saved context."
          />
        ) : (
          <>
            {rows.map((row) => (
              <ConversationBubble key={row.message_id} message={row} />
            ))}
            <Pager
              canPrev={pager.canPrev}
              nextCursor={messages.data?.next_cursor ?? null}
              onPrev={pager.prev}
              onNext={pager.next}
            />
          </>
        )}
      </div>
      <div className="lab-compose">
        <label htmlFor="lab-compose-text">Message</label>
        <textarea
          id="lab-compose-text"
          value={composeText}
          onChange={(event) => setComposeText(event.target.value)}
          placeholder="Ask the Lab Assistant about current work, data, findings or outputs. Use Send as Directive only for a queued research task."
        />
        <div className="lab-compose-actions">
          <button
            type="button"
            className="btn"
            disabled={message.isPending || composeText.trim().length === 0}
            onClick={sendMessage}
          >
            {message.isPending ? "Sending…" : "Send Message"}
          </button>
          <label htmlFor="lab-directive-priority">Directive Priority</label>
          <select
            id="lab-directive-priority"
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
            type="button"
            className="btn btn-primary"
            disabled={directive.isPending || composeText.trim().length === 0}
            onClick={sendDirective}
          >
            {directive.isPending ? "Queueing…" : "Send as Directive"}
          </button>
          <span className="lab-compose-note">
            Messages do not affect the active job. Directives enter the queue and run only after a
            safe checkpoint.
          </span>
        </div>
        {directive.isError ? (
          <p role="alert" style={{ color: "var(--down)", margin: "8px 0 0" }}>
            {mutationErrorText(directive.error)}
          </p>
        ) : null}
        {directive.isSuccess ? (
          <p role="status" style={{ color: "var(--ok)", margin: "8px 0 0" }}>
            Directive queued — delivered at the{" "}
            {directive.data.delivery_policy.replaceAll("_", " ")}.
          </p>
        ) : null}
        {message.isError ? (
          <p role="alert" style={{ color: "var(--down)", margin: "8px 0 0" }}>
            {mutationErrorText(message.error)}
          </p>
        ) : null}
        {message.isSuccess ? (
          <p role="status" style={{ margin: "8px 0 0" }}>
            Agent: {message.data.assistant_response.text}
          </p>
        ) : null}
      </div>
    </section>
  );
}

function ConversationBubble({ message }: { message: LabMessageCard }) {
  return (
    <div className={`lab-message ${message.type}`}>
      <div className="lab-message-tag">
        <StatusBadge tone={LAB_MESSAGE_TYPE_TONES[message.type] ?? "neutral"} label={message.type} />
        {message.task_id ? (
          <span className="badge">
            task · <code>{message.task_id}</code>
          </span>
        ) : null}
        {message.created_at ? (
          <time className="lab-message-time" dateTime={message.created_at}>
            {message.created_at}
          </time>
        ) : null}
      </div>
      <p className="lab-message-text">{message.text}</p>
    </div>
  );
}

// WORK QUEUE panel (mockup): current task + the Coordinator's bounded live queue
// as .lab-queue-item cards with status pills. Each item's Detail opens the task
// detail below the grid.
function WorkQueuePanel({
  overview,
  selectedTaskId,
  onSelectTask,
}: {
  overview: AgentOverview;
  selectedTaskId: string | null;
  onSelectTask: (taskId: string) => void;
}) {
  const { active_task: activeTask } = overview;
  const counts = Object.entries(overview.queue.counts);
  const cards = overview.queue.cards;
  return (
    <section className="lab-panel" aria-label="Work queue">
      <div className="lab-panel-head">
        WORK QUEUE <span className="lab-tag">{cards.length} ITEMS</span>
      </div>
      <div className="lab-panel-body">
        {counts.length > 0 ? (
          <div className="lab-queue-counts">
            {counts.map(([status, count]) => (
              <span key={status} className="badge">
                {status} · {count}
              </span>
            ))}
          </div>
        ) : null}
        {activeTask ? (
          <div className="lab-context-section">
            <div className="lab-context-label">CURRENT TASK</div>
            <div className="lab-queue-name">{activeTask.title}</div>
            <div className="lab-queue-meta">
              Stage: {activeTask.stage ?? "—"} · Progress: {activeTask.progress ?? "—"}
            </div>
          </div>
        ) : null}
        {cards.length === 0 ? (
          <EmptyState
            glyph="⧗"
            title="No agent tasks yet"
            description="Queue a directive — the Coordinator turns it into a task."
          />
        ) : (
          cards.map((task: AgentTaskCard) => (
            <div key={task.task_id} className="lab-queue-item">
              <div className="lab-queue-name">{task.title}</div>
              <div className="lab-queue-meta">
                {task.task_type} · Priority: {task.priority}
              </div>
              <div className="lab-queue-row">
                <span className={`lab-queue-status ${pillState(task.status, LAB_PILL_STATES)}`}>
                  {task.status}
                </span>
                <button
                  type="button"
                  className="btn btn-ghost"
                  aria-pressed={selectedTaskId === task.task_id}
                  onClick={() => onSelectTask(task.task_id)}
                >
                  Detail
                </button>
              </div>
            </div>
          ))
        )}
      </div>
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

// HYPOTHESIS & OUTPUT BOARD (mockup .lab-output-board): the persistent research
// outputs, evidence and next actions, filterable by status and paged with the
// server keyset cursor — recorded independently from the conversation.
function OutputBoard() {
  const [status, setStatus] = useState<string | null>(null);
  const pager = useCursorStack();
  const hypotheses = useHypotheses(status, pager.cursor);
  const rows = hypotheses.data?.hypotheses ?? [];

  function onStatusChange(next: string) {
    setStatus(next === "" ? null : next);
    pager.reset();
  }

  return (
    <section className="lab-output-board" aria-label="Hypothesis & output board">
      <div className="lab-output-toolbar">
        <div className="section-title-upper" style={{ margin: 0, padding: 0, border: 0 }}>
          Hypothesis &amp; Output Board
        </div>
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
      <p className="lab-status-detail" style={{ margin: "0 0 10px" }}>
        Persistent outputs, evidence and next actions are recorded independently from chat.
      </p>
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
          <div className="lab-output-grid">
            {rows.map((row: HypothesisCard) => (
              <div key={row.artifact_id} className="lab-hypothesis-card">
                <div className="lab-hypothesis-title">{row.title}</div>
                <span
                  className={`lab-hypothesis-status ${pillState(row.status, HYPOTHESIS_PILL_STATES)}`}
                >
                  {row.status}
                </span>
                <p>
                  <b>Mechanism:</b> {row.mechanism ?? "—"}
                </p>
                <p>
                  <b>Data:</b> {row.data_context ?? "—"}
                </p>
                <p>
                  <b>Next action:</b> {row.next_action ?? "—"}
                </p>
                {row.source_task_id ? (
                  <p className="lab-hypothesis-meta">
                    Source task: <code>{row.source_task_id}</code>
                  </p>
                ) : null}
              </div>
            ))}
          </div>
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
