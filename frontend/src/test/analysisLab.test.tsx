import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import { AnalysisLab } from "@/pages/AnalysisLab";
import { stubApi } from "./helpers/apiStub";

const TASK = {
  task_id: "atask_1",
  title: "Momentum research",
  task_type: "research",
  source: "human_directive",
  priority: "normal",
  status: "running",
  stage: "collect",
  progress: 40,
};

const OVERVIEW = {
  runtime: {
    agent_id: "alpha",
    mode: "continuous",
    status: "active",
    pending_control: null,
    active_task_id: "atask_1",
    last_checkpoint_id: "cp_9",
    row_version: 4,
  },
  active_task: TASK,
  context_bundle: { context_manifest_id: "cm_1", note: "derived" },
  queue: {
    counts: { queued: 2, running: 1 },
    cards: [TASK, { ...TASK, task_id: "atask_2", title: "Vol regime scan", status: "queued" }],
  },
  output_board: { hypotheses: [] },
};

const HYPOTHESES = {
  hypotheses: [
    {
      artifact_id: "hyp_1",
      status: "proposed",
      title: "BTC momentum persists after HTF breakout",
      mechanism: "order-flow continuation",
      data_context: "BTCUSDT 1h 2026",
      next_action: "backtest with trailing stop",
      evidence_refs: ["res_1"],
      source_task_id: "atask_1",
    },
  ],
  next_cursor: null,
};

// Lab Conversation (GET /lab/messages) — the read-only projection of the
// append-only lab_message log, newest-first (assistant reply leads its human
// message). The human message is task-scoped so its tag renders.
const LAB_MESSAGES = {
  messages: [
    {
      message_id: "labmsg_2",
      type: "assistant",
      text: "Alpha Agent is active. This message was recorded and did not interrupt the active task.",
      task_id: null,
      author_principal_id: null,
      correlation_id: "corr_c",
      created_at: "2026-07-11T10:00:01Z",
    },
    {
      message_id: "labmsg_1",
      type: "message",
      text: "Which dataset revisions are pinned?",
      task_id: "atask_1",
      author_principal_id: "admin_1",
      correlation_id: "corr_c",
      created_at: "2026-07-11T10:00:00Z",
    },
  ],
  next_cursor: null,
};

// Task history list (GET /agent-tasks) — the aged-out record behind the bounded
// live queue. `next_cursor` is present so the Pager's Next is exercisable.
const TASK_HISTORY = {
  tasks: [
    {
      ...TASK,
      task_id: "atask_9",
      title: "Archived carry study",
      status: "succeeded",
      stage: "done",
    },
  ],
  next_cursor: "cur_2",
};

const TASK_DETAIL = {
  ...TASK,
  context_manifest_id: "cm_1",
  parent_task_id: null,
  waiting_reason: null,
  failure_reason: null,
  checkpoints: [
    { checkpoint_id: "cp_9", checkpoint_no: 9, stage: "collect", directive_cursor: null },
  ],
  directives: [
    {
      directive_id: "dir_1",
      priority: "high",
      status: "consumed",
      text: "Focus on BTCUSDT",
      consumed_checkpoint_id: "cp_9",
    },
  ],
};

const TOOL_CALLS = {
  tool_calls: [
    {
      tool_call_id: "tc_1",
      tool_name: "artifact.create",
      task_id: "atask_2",
      checkpoint_id: "cp_9",
      actor_kind: "agent",
      policy_scope: "research",
      status: "succeeded",
      artifact_output_ref: "hyp_9",
      failure_code: null,
      failure_message: null,
      correlation_id: "corr_1",
      created_at: "2026-07-11T10:00:00Z",
      updated_at: "2026-07-11T10:00:01Z",
    },
    {
      tool_call_id: "tc_2",
      tool_name: "data_bundle.resolve",
      task_id: "atask_2",
      checkpoint_id: null,
      actor_kind: "agent",
      policy_scope: "research",
      status: "failed",
      artifact_output_ref: null,
      failure_code: "RESEARCH_INPUT_BLOCKED",
      failure_message: "Agent-research-only data cannot enter an execution context.",
      correlation_id: "corr_2",
      created_at: "2026-07-11T10:01:00Z",
      updated_at: "2026-07-11T10:01:01Z",
    },
  ],
};

const TOOL_CALL_DETAIL = {
  ...TOOL_CALLS.tool_calls[0],
  agent_id: "alpha",
  actor_principal_id: "agent_alpha",
  input_manifest_id: "man_x",
  idempotency_key: "key_1",
  request: { title: "Funding edge", mechanism: "carry" },
  response_ref: { artifact_id: "hyp_9", status: "exploring" },
};

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/analysis-lab"]}>
        <AnalysisLab />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return client;
}

describe("Analysis Lab page", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders the runtime, queue and output board from the overview projection", async () => {
    stubApi({
      "GET /agent-workspace/overview": OVERVIEW,
      "GET /hypotheses": HYPOTHESES,
      "GET /lab/messages": LAB_MESSAGES,
      "GET /agent-tasks": TASK_HISTORY,
    });
    renderPage();

    expect(await screen.findByText("active")).toBeInTheDocument();
    expect(screen.getByText("alpha")).toBeInTheDocument();
    expect(screen.getByText("Momentum research (running)")).toBeInTheDocument();
    expect(screen.getByText("queued · 2")).toBeInTheDocument();
    expect(screen.getByText("Vol regime scan")).toBeInTheDocument();
    expect(
      await screen.findByText("BTC momentum persists after HTF breakout"),
    ).toBeInTheDocument();
  });

  it("opens the task detail with checkpoints and related directives", async () => {
    stubApi({
      "GET /agent-workspace/overview": OVERVIEW,
      "GET /hypotheses": HYPOTHESES,
      "GET /lab/messages": LAB_MESSAGES,
      // Ordered: the tool-calls fragment must precede the bare detail prefix so
      // "/agent-tasks/atask_2/tool-calls" does not match the detail stub.
      "GET /agent-tasks/atask_2/tool-calls": TOOL_CALLS,
      "GET /agent-tasks/atask_2": { ...TASK_DETAIL, task_id: "atask_2", title: "Vol regime scan" },
      // Ordered LAST: the bare list fragment must not shadow the detail/tool-calls stubs above.
      "GET /agent-tasks": TASK_HISTORY,
    });
    renderPage();
    await screen.findByText("Vol regime scan");

    const detailButtons = screen.getAllByRole("button", { name: "Detail" });
    fireEvent.click(detailButtons[1]);

    expect(await screen.findByText("atask_2")).toBeInTheDocument();
    expect(screen.getByText("[consumed] Focus on BTCUSDT")).toBeInTheDocument();
  });

  it("queues a directive and pauses with the runtime If-Match token", async () => {
    const fetchMock = stubApi({
      "GET /agent-workspace/overview": OVERVIEW,
      "GET /hypotheses": HYPOTHESES,
      "GET /lab/messages": LAB_MESSAGES,
      "GET /agent-tasks": TASK_HISTORY,
      "POST /agent-directives": {
        directive_id: "dir_2",
        status: "queued",
        priority: "high",
        target_agent_id: "alpha",
        related_task_id: null,
        delivery_policy: "next_safe_checkpoint",
        active_task_interrupted: false,
      },
      "POST /agent-runtime/pause": {
        agent_id: "alpha",
        control: "pause",
        status: "accepted",
        runtime_status: "active",
        delivery_policy: "next_safe_checkpoint",
        row_version: 4,
      },
    });
    renderPage();
    await screen.findByText("alpha");

    fireEvent.change(screen.getByLabelText("Directive"), {
      target: { value: "Prioritize BTCUSDT" },
    });
    fireEvent.change(screen.getByLabelText("Priority"), { target: { value: "high" } });
    fireEvent.click(screen.getByRole("button", { name: "Queue directive" }));

    expect(
      await screen.findByText("Directive queued — delivered at the next safe checkpoint."),
    ).toBeInTheDocument();
    const directiveCall = fetchMock.mock.calls.find(([url]) =>
      String(url).includes("/agent-directives"),
    );
    const directiveBody = JSON.parse(String((directiveCall?.[1] as RequestInit).body));
    expect(directiveBody).toEqual({
      text: "Prioritize BTCUSDT",
      priority: "high",
      related_task_id: null,
    });
    // GAP-13: the 202 admission has no OCC head — a fresh Idempotency-Key is the
    // only guard that dedups a network retry to a single directive.
    const directiveHeaders = (directiveCall?.[1] as RequestInit).headers as Record<
      string,
      string
    >;
    expect(directiveHeaders["Idempotency-Key"]).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Pause at next safe checkpoint" }));
    await waitFor(() => {
      const pauseCall = fetchMock.mock.calls.find(([url]) =>
        String(url).includes("/agent-runtime/pause"),
      );
      expect(pauseCall).toBeDefined();
      // OCC: the pause admission carries the runtime row_version as If-Match.
      const headers = (pauseCall?.[1] as RequestInit).headers as Record<string, string>;
      expect(headers["If-Match"]).toBe("4");
      // GAP-13: it also carries a fresh Idempotency-Key so a retry dedups.
      expect(headers["Idempotency-Key"]).toBeTruthy();
    });
  });

  it("refetches the overview when the SSE agent-tasks prefix is invalidated", async () => {
    const fetchMock = stubApi({
      "GET /agent-workspace/overview": OVERVIEW,
      "GET /hypotheses": HYPOTHESES,
      "GET /lab/messages": LAB_MESSAGES,
      "GET /agent-tasks": TASK_HISTORY,
    });
    const client = renderPage();
    await screen.findByText("alpha");
    const callsBefore = fetchMock.mock.calls.filter(([url]) =>
      String(url).includes("/agent-workspace/overview"),
    ).length;

    // What lib/sse.ts does on `agent.task.updated` — every lab key must be swept.
    await client.invalidateQueries({ queryKey: ["agent-tasks"] });

    await waitFor(() => {
      const callsAfter = fetchMock.mock.calls.filter(([url]) =>
        String(url).includes("/agent-workspace/overview"),
      ).length;
      expect(callsAfter).toBeGreaterThan(callsBefore);
    });
  });

  it("surfaces the server denial verbatim (server policy, not a UI hint)", async () => {
    stubApi({
      "GET /agent-workspace/overview": () => {
        throw new Error("FORBIDDEN: Analysis Lab requires Admin or Supervisor.");
      },
      "GET /hypotheses": HYPOTHESES,
      "GET /lab/messages": LAB_MESSAGES,
    });
    renderPage();

    expect(await screen.findByText("Unable to load")).toBeInTheDocument();
    expect(
      screen.getByText("FORBIDDEN: Analysis Lab requires Admin or Supervisor."),
    ).toBeInTheDocument();
  });

  it("lists the task's durable tool calls in the detail", async () => {
    stubApi({
      "GET /agent-workspace/overview": OVERVIEW,
      "GET /hypotheses": HYPOTHESES,
      "GET /lab/messages": LAB_MESSAGES,
      "GET /agent-tasks/atask_2/tool-calls": TOOL_CALLS,
      "GET /agent-tasks/atask_2": { ...TASK_DETAIL, task_id: "atask_2", title: "Vol regime scan" },
      // Ordered LAST: the bare list fragment must not shadow the detail/tool-calls stubs above.
      "GET /agent-tasks": TASK_HISTORY,
    });
    renderPage();
    await screen.findByText("Vol regime scan");
    fireEvent.click(screen.getAllByRole("button", { name: "Detail" })[1]);

    expect(await screen.findByText("artifact.create")).toBeInTheDocument();
    expect(screen.getByText("data_bundle.resolve")).toBeInTheDocument();
    // A failed/rejected call surfaces its recorded governance failure verbatim.
    expect(
      screen.getByText("Agent-research-only data cannot enter an execution context."),
    ).toBeInTheDocument();
  });

  it("expands a tool call to load its request/response detail on demand", async () => {
    const fetchMock = stubApi({
      "GET /agent-workspace/overview": OVERVIEW,
      "GET /hypotheses": HYPOTHESES,
      "GET /lab/messages": LAB_MESSAGES,
      "GET /agent-tool-calls/tc_1": TOOL_CALL_DETAIL,
      "GET /agent-tasks/atask_2/tool-calls": TOOL_CALLS,
      "GET /agent-tasks/atask_2": { ...TASK_DETAIL, task_id: "atask_2", title: "Vol regime scan" },
      // Ordered LAST: the bare list fragment must not shadow the detail/tool-calls stubs above.
      "GET /agent-tasks": TASK_HISTORY,
    });
    renderPage();
    await screen.findByText("Vol regime scan");
    fireEvent.click(screen.getAllByRole("button", { name: "Detail" })[1]);

    const row = await screen.findByText("artifact.create");
    // The detail (request/response bodies) is NOT fetched until the row expands.
    expect(
      fetchMock.mock.calls.some(([url]) => String(url).includes("/agent-tool-calls/tc_1")),
    ).toBe(false);
    fireEvent.click(row);

    expect(await screen.findByText(/Funding edge/)).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(([url]) => String(url).includes("/agent-tool-calls/tc_1")),
    ).toBe(true);
  });

  it("filters task history by status and pages with the server keyset cursor", async () => {
    const fetchMock = stubApi({
      "GET /agent-workspace/overview": OVERVIEW,
      "GET /hypotheses": HYPOTHESES,
      "GET /lab/messages": LAB_MESSAGES,
      "GET /agent-tasks": TASK_HISTORY,
    });
    renderPage();

    // The aged-out task shows in history, not in the bounded live queue.
    expect(await screen.findByText("Archived carry study")).toBeInTheDocument();

    // A status filter is sent as the server-validated `status` param (an unknown
    // value would 422) — never a client-side re-filter of the current page.
    fireEvent.change(screen.getByLabelText("Filter task history by status"), {
      target: { value: "succeeded" },
    });
    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(([url]) =>
          String(url).includes("/agent-tasks?status=succeeded"),
        ),
      ).toBe(true);
    });

    // Next replays the opaque cursor the server returned; the client never
    // fabricates a page key.
    const history = screen.getByRole("region", { name: "Task history" });
    fireEvent.click(within(history).getByRole("button", { name: "Next" }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url]) => String(url).includes("cursor=cur_2"))).toBe(
        true,
      );
    });
  });

  it("filters and pages the hypothesis output board with the server cursor", async () => {
    const HYP_PAGE = { hypotheses: HYPOTHESES.hypotheses, next_cursor: "hyp_2" };
    const fetchMock = stubApi({
      "GET /agent-workspace/overview": OVERVIEW,
      "GET /agent-tasks": TASK_HISTORY,
      "GET /hypotheses": HYP_PAGE,
      "GET /lab/messages": LAB_MESSAGES,
    });
    renderPage();

    expect(
      await screen.findByText("BTC momentum persists after HTF breakout"),
    ).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Filter hypotheses by status"), {
      target: { value: "candidate" },
    });
    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(([url]) =>
          String(url).includes("/hypotheses?status=candidate"),
        ),
      ).toBe(true);
    });

    const board = screen.getByRole("region", { name: "Hypothesis & output board" });
    fireEvent.click(within(board).getByRole("button", { name: "Next" }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url]) => String(url).includes("cursor=hyp_2"))).toBe(
        true,
      );
    });
  });

  it("renders the lab conversation cards from the read-only projection", async () => {
    const fetchMock = stubApi({
      "GET /agent-workspace/overview": OVERVIEW,
      "GET /hypotheses": HYPOTHESES,
      "GET /lab/messages": LAB_MESSAGES,
      "GET /agent-tasks": TASK_HISTORY,
    });
    renderPage();

    // Wait for the conversation query to resolve before reading its cards.
    expect(await screen.findByText("Which dataset revisions are pinned?")).toBeInTheDocument();
    const convo = screen.getByRole("region", { name: "Lab conversation" });
    // Type/tag/time/text cards (doc 18 §3.2) over the append-only log.
    expect(within(convo).getByText("assistant")).toBeInTheDocument();
    expect(within(convo).getByText("message")).toBeInTheDocument();
    // The task-scoped human message renders its task tag.
    expect(within(convo).getByText("atask_1")).toBeInTheDocument();
    // The panel shows the whole conversation — it never scopes with `task=`.
    const call = fetchMock.mock.calls.find(([url]) => String(url).includes("/lab/messages"));
    expect(String(call?.[0])).not.toContain("task=");
  });

  it("sweeps the lab conversation when the agent-tasks SSE prefix is invalidated", async () => {
    const fetchMock = stubApi({
      "GET /agent-workspace/overview": OVERVIEW,
      "GET /hypotheses": HYPOTHESES,
      "GET /lab/messages": LAB_MESSAGES,
      "GET /agent-tasks": TASK_HISTORY,
    });
    const client = renderPage();
    // Wait for the first conversation fetch to resolve before counting.
    await screen.findByText("Which dataset revisions are pinned?");
    const before = fetchMock.mock.calls.filter(([url]) =>
      String(url).includes("/lab/messages"),
    ).length;

    // A sent message (useSendLabMessage) and the SSE `agent.task.updated` both
    // invalidate ["agent-tasks"] — the conversation must be swept too.
    await client.invalidateQueries({ queryKey: ["agent-tasks"] });

    await waitFor(() => {
      const after = fetchMock.mock.calls.filter(([url]) =>
        String(url).includes("/lab/messages"),
      ).length;
      expect(after).toBeGreaterThan(before);
    });
  });
});
