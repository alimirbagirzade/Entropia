import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
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
      "GET /agent-tasks/atask_2": { ...TASK_DETAIL, task_id: "atask_2", title: "Vol regime scan" },
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

    fireEvent.click(screen.getByRole("button", { name: "Pause at next safe checkpoint" }));
    await waitFor(() => {
      const pauseCall = fetchMock.mock.calls.find(([url]) =>
        String(url).includes("/agent-runtime/pause"),
      );
      expect(pauseCall).toBeDefined();
      // OCC: the pause admission carries the runtime row_version as If-Match.
      const headers = (pauseCall?.[1] as RequestInit).headers as Record<string, string>;
      expect(headers["If-Match"]).toBe("4");
    });
  });

  it("refetches the overview when the SSE agent-tasks prefix is invalidated", async () => {
    const fetchMock = stubApi({
      "GET /agent-workspace/overview": OVERVIEW,
      "GET /hypotheses": HYPOTHESES,
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
    });
    renderPage();

    expect(await screen.findByText("Unable to load")).toBeInTheDocument();
    expect(
      screen.getByText("FORBIDDEN: Analysis Lab requires Admin or Supervisor."),
    ).toBeInTheDocument();
  });
});
