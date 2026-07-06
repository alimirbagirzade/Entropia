import { useState, type FormEvent } from "react";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { StatusBadge } from "@/components/StatusBadge";
import { ApiError } from "@/lib/apiClient";
import {
  DIRECTIVE_PRIORITIES,
  TASK_STATUS_TONES,
  useAgentOverview,
  useAgentTask,
  useHypotheses,
  usePauseRuntime,
  useQueueDirective,
  useResumeRuntime,
  useSendLabMessage,
  useStopRun,
  type AgentOverview,
  type AgentTaskCard,
  type DirectivePriority,
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
      {selectedTaskId ? (
        <TaskDetailCard taskId={selectedTaskId} onClose={() => setSelectedTaskId(null)} />
      ) : null}
      <DirectiveCard />
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
        </>
      ) : null}
    </section>
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

function HypothesesCard() {
  const hypotheses = useHypotheses();
  const rows = hypotheses.data?.hypotheses ?? [];
  return (
    <section className="card" aria-labelledby="hypotheses-h" style={{ marginTop: 18 }}>
      <h3 id="hypotheses-h" style={{ marginTop: 0 }}>
        Hypothesis &amp; output board
      </h3>
      {hypotheses.isLoading ? (
        <Loading label="Loading hypotheses…" />
      ) : hypotheses.isError ? (
        <ErrorState error={hypotheses.error} onRetry={() => void hypotheses.refetch()} />
      ) : rows.length === 0 ? (
        <EmptyState
          glyph="◇"
          title="No hypotheses yet"
          description="Completed research tasks publish their hypotheses here."
        />
      ) : (
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
      )}
    </section>
  );
}
