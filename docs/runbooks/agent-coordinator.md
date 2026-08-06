# Runbook — Agent coordinator

**No alert fires on the coordinator.** It has no counters of any kind: no tick
count, no cycle duration, no state-transition, task, checkpoint or ToolCall error
metric. Diagnosis is entirely from structured logs and SQL.

The consequence to internalise: **a coordinator looping without making progress
looks exactly like an idle one.** Nothing will page you.

---

## Vocabulary that matters here

* An **Agent is not a human account**, not a browser, not a human session.
* **Lab Assistant and Alpha Agent are different actors.** Do not merge their
  symptoms when reading logs.

---

## What the coordinator emits

Logger `agent_coordinator`, one cycle every 10s:

| Event | Fields |
|---|---|
| `agent_coordinator.start` | — |
| `agent_coordinator.cycle` | `runtime_status`, `consumed_directive`, `followup_task_id`, `executor_job_id` |
| `agent_coordinator.dispatch_failed` | `error` |
| `agent_coordinator.cycle_failed` | `error` |
| `agent_coordinator.stop` | — |

```bash
docker compose logs --tail=200 --no-color agent-coordinator
```

---

## Discriminate

| Observation | Meaning | Action |
|---|---|---|
| No `.cycle` lines | Coordinator stopped | Restart `agent-coordinator` |
| `.cycle` every 10s, all fields null | Genuinely idle — **normal** | Nothing to do |
| `.cycle_failed` repeating | Cycle body throwing; line carries `error` | Read the error; usually Postgres |
| `.dispatch_failed` repeating | Enqueue to `agent-executor` failing | [redis.md](redis.md) |
| `.cycle` sets `executor_job_id` but nothing runs | **The executor is starved** | See below |

### The starved-executor trap

This is the failure mode the deployment is explicitly shaped to avoid, and it is
worth recognising by hand because it is silent.

The coordinator dispatches every Agent task onto the `agent-executor` queue, and
the scheduler **auto-redelivers** that queue. If nothing consumes it, the two
combine into an infinite loop: tasks are enqueued, re-sent every grace window,
and never run — and **each send succeeds**, so nothing reports a fault.

`worker-agent-executor` exists as its own service for exactly this reason.

```bash
docker compose ps worker-agent-executor
```

```sql
SELECT status, count(*) FROM jobs WHERE queue = 'agent-executor' GROUP BY status;
```

A growing `queued` count with no `running` is the loop. `EntropiaQueueNeverDrains`
does catch this once work is pending — it is the only alert that touches the
Agent plane at all.

---

## Task-level state

```sql
SELECT status, count(*) FROM agent_task GROUP BY status;
SELECT task_id, task_type, status, stage, progress, waiting_reason, failure_reason
  FROM agent_task WHERE status NOT IN ('succeeded', 'failed', 'cancelled') LIMIT 20;
```

Tool-call failures are readable through the API
(`GET /api/v1/agent-tasks/{task_id}/tool-calls`) but are **not aggregated**
anywhere — there is no error-rate signal.

---

## Recovery

`.cycle` lines resume at their 10s cadence, the `agent-executor` queue drains,
and no `.cycle_failed` / `.dispatch_failed` appears for 30m.

---

## What this cannot tell you

* Whether the coordinator is **progressing**, as opposed to cycling.
* Cycle duration, or a stalled cycle that never returns.
* ToolCall error rate, checkpoint counts, state-transition counts.
* Anything about Agent task latency.

A future slice that wants alerting here must emit metrics first.
