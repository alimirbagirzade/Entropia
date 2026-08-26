import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { Portfolio } from "@/pages/Portfolio";
import { stubApi } from "./helpers/apiStub";

const MAINBOARD = {
  workspace_id: "ws_1",
  workspace_kind: "human_default",
  composition_hash: "hash_abc",
  row_version: 3,
  items: [
    {
      item_id: "item_1",
      item_kind: "strategy",
      work_object_root_id: "root_1",
      pinned_revision_id: "rev_1",
      position_index: 0,
      is_enabled: true,
      display_label_override: "Momentum A",
      row_version: 1,
    },
    {
      item_id: "item_2",
      item_kind: "trade_log",
      work_object_root_id: "root_2",
      pinned_revision_id: null,
      position_index: 1,
      is_enabled: false,
      display_label_override: null,
      row_version: 1,
    },
  ],
  ready_summary: { state: "not_ready", report_id: null },
  latest_result_summary: null,
};

// ADIM 3 containment: the server publishes its own executability verdict for
// shared capital on every draft read, and the page renders it verbatim — the
// browser never decides availability for itself.
const SHARED_MODE_CAPABILITY = {
  key: "portfolio.shared_capital_allocation",
  status: "future_dev",
  available: false,
  message:
    "Shared capital allocation is not available in this build. The engine replays each composition item independently.",
  remediation:
    "Turn the Portfolio Allocation toggle off and give each enabled Strategy its own Initial Capital.",
  dependency: "Needs a unified-clock multi-item co-simulation.",
  field_path: "enabled",
};

// No plan row yet — the default independent draft; row_version 0 IS the valid
// PUT creation token (doc 13 §7.2).
const DRAFT_EMPTY = {
  composition_id: "ws_1",
  plan_id: null,
  current_revision_id: null,
  row_version: 0,
  draft: {
    enabled: false,
    initial_capital: null,
    compounding_mode: null,
    reserve_cash_percent: null,
    entries: [],
  },
  candidate_items: [
    {
      composition_item_id: "item_1",
      item_type: "strategy",
      work_object_root_id: "root_1",
      is_enabled: true,
      position_index: 0,
      display_label_override: "Momentum A",
    },
  ],
  shared_mode_capability: SHARED_MODE_CAPABILITY,
};

const DRAFT_SAVED = {
  composition_id: "ws_1",
  plan_id: "plan_1",
  current_revision_id: null,
  row_version: 1,
  draft: {
    enabled: true,
    initial_capital: { amount: "10000", currency: "USDT" },
    compounding_mode: "COMPOUND_PORTFOLIO_EQUITY",
    reserve_cash_percent: "10",
    draft_fingerprint: "fp_1",
    entries: [
      {
        entry_id: "pae_1",
        composition_item_id: "item_1",
        item_type: "strategy",
        active: true,
        equity_share_percent: "90",
        position_index: 0,
        // Server-owned human label of the bound item (P-11) — the sleeve row and
        // example line name it; item_1 stays a secondary binding key.
        display_label_override: "Momentum A",
      },
    ],
  },
  candidate_items: [],
  shared_mode_capability: SHARED_MODE_CAPABILITY,
};

const SAVE_RESULT = {
  composition_id: "ws_1",
  plan_id: "plan_1",
  enabled: true,
  row_version: 1,
  draft_fingerprint: "fp_1",
  inline_issues: [
    {
      code: "TOTAL_ALLOCATION_UNDER_100",
      severity: "warning",
      message: "Active shares total 90%; 10% of available capital stays unallocated.",
      field: "entries",
      composition_item_id: null,
    },
  ],
  derived: {
    currency: "USDT",
    portfolio_initial_capital: "10000.00",
    reserved_cash: "1000.00",
    capital_available: "9000.00",
    total_allocated: "8100.00",
    unallocated: "900.00",
    active_share_total: "90",
    sleeves: [
      {
        composition_item_id: "item_1",
        equity_share_percent: "90",
        initial_sleeve_capital: "8100.00",
      },
    ],
  },
  readiness_invalidated: true,
};

const VALIDATION_REPORT = {
  validation_report_id: "parpt_1",
  composition_id: "ws_1",
  enabled: true,
  state: "READY_WITH_WARNINGS",
  valid: true,
  issues: [
    {
      code: "TOTAL_ALLOCATION_UNDER_100",
      severity: "warning",
      message: "Active shares total 90%; 10% of available capital stays unallocated.",
      field: "entries",
      composition_item_id: null,
    },
  ],
  warnings: [],
  derived: SAVE_RESULT.derived,
  config_hash: "cfg_1",
};

const SYNC_PREVIEW = {
  composition_id: "ws_1",
  retained: [
    {
      entry_id: "pae_1",
      composition_item_id: "item_1",
      item_type: "strategy",
      active: true,
      equity_share_percent: "90",
      position_index: 0,
      display_label_override: "Momentum A",
    },
  ],
  missing: [
    {
      entry_id: "pae_9",
      composition_item_id: "item_gone",
      item_type: "strategy",
      active: true,
      equity_share_percent: "10",
      position_index: 1,
      // Item no longer in the composition → server resolves label to null; the
      // client falls back to the item-kind label.
      display_label_override: null,
    },
  ],
  new_candidates: [
    {
      composition_item_id: "item_2",
      item_type: "trade_log",
      work_object_root_id: "root_2",
      is_enabled: false,
      position_index: 1,
      display_label_override: null,
    },
  ],
  requires_confirmation: true,
};

const REVISION_RESULT = {
  composition_id: "ws_1",
  plan_id: "plan_1",
  plan_revision_id: "parev_1",
  revision_no: 1,
  config_hash: "cfg_1",
  current_revision_id: "parev_1",
  row_version: 2,
  derived: SAVE_RESULT.derived,
};

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/portfolio"]}>
        <Routes>
          <Route path="/portfolio" element={<Portfolio />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function callFor(
  fetchMock: ReturnType<typeof stubApi>,
  method: string,
  fragment: string,
): RequestInit {
  const call = fetchMock.mock.calls.find(
    ([url, init]) =>
      String(url).includes(fragment) && ((init?.method ?? "GET") as string) === method,
  );
  expect(call).toBeTruthy();
  return call?.[1] as RequestInit;
}

describe("Portfolio / Equity Allocation page", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders the composition, the independent empty draft and the candidate picker", async () => {
    stubApi({
      // Action/draft routes BEFORE any list-ish prefix (apiStub ordered match).
      "GET /mainboard-compositions/ws_1/portfolio-allocation-draft": DRAFT_EMPTY,
      "GET /mainboards/default": MAINBOARD,
    });
    renderPage();

    expect(await screen.findByText("ws_1")).toBeInTheDocument();
    // The draft loads as a second wave once the composition id resolves.
    expect(await screen.findByText("independent (off)")).toBeInTheDocument();
    expect(screen.getByText(/no plan row yet/)).toBeInTheDocument();
    // Toggle off (the draft's default) fades and blocks the whole workspace,
    // incl. the Add Item picker — the "Add" button is present but disabled.
    expect(screen.getByText(/Equity Allocation is not selected/)).toBeInTheDocument();
    const picker = screen.getByText("+ Add item").closest("div");
    expect(within(picker as HTMLElement).getByText("item_1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add" })).toBeDisabled();
    // Card 3/4 show their toggle-off placeholders, never a live computation.
    expect(screen.getByText("Not in use.")).toBeInTheDocument();
    expect(screen.getByText("Not selected (independent)")).toBeInTheDocument();
  });

  it("saves the draft with the body-form OCC token and a fresh Idempotency-Key", async () => {
    let saved = false;
    const fetchMock = stubApi({
      "PUT /mainboard-compositions/ws_1/portfolio-allocation-draft": () => {
        saved = true;
        return SAVE_RESULT;
      },
      "GET /mainboard-compositions/ws_1/portfolio-allocation-draft": () =>
        saved ? DRAFT_SAVED : DRAFT_EMPTY,
      "GET /mainboards/default": MAINBOARD,
    });
    renderPage();

    // The Add Item picker only accepts input once the toggle is on (UI-13
    // toggle-off disable) — flip it on first, then add the candidate.
    fireEvent.click(await screen.findByLabelText(/USE EQUITY ALLOCATION FOR THIS BACKTEST/));
    fireEvent.click(screen.getByRole("button", { name: "Add" }));
    fireEvent.change(screen.getByLabelText("Initial capital"), { target: { value: "10000" } });
    fireEvent.change(screen.getByLabelText("Currency"), { target: { value: "USDT" } });
    fireEvent.change(screen.getByLabelText("Compounding mode"), {
      target: { value: "COMPOUND_PORTFOLIO_EQUITY" },
    });
    fireEvent.change(screen.getByLabelText("Reserve cash %"), { target: { value: "10" } });
    fireEvent.change(screen.getByLabelText("share item_1"), { target: { value: "90" } });
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));

    // The PUT return renders inline issues verbatim; the derived amounts it
    // carries feed Card 3 "Calculation preview" (server-derived, never
    // recomputed client-side).
    expect(await screen.findByText("Draft saved")).toBeInTheDocument();
    expect(screen.getByText("TOTAL_ALLOCATION_UNDER_100")).toBeInTheDocument();
    expect(screen.getByText("9000.00")).toBeInTheDocument();
    expect(screen.getByText("8100.00")).toBeInTheDocument();

    const init = callFor(fetchMock, "PUT", "/portfolio-allocation-draft");
    const body = JSON.parse(String(init.body));
    // OCC travels BODY-form (0 = creation token); item_type is never sent —
    // the server derives it from the composition item (doc 13 §8.2).
    expect(body).toEqual({
      expected_row_version: 0,
      enabled: true,
      initial_capital: { amount: "10000", currency: "USDT" },
      compounding_mode: "COMPOUND_PORTFOLIO_EQUITY",
      reserve_cash_percent: "10",
      // Portfolio rules untouched -> nulls travel (no cap / keep separate, the
      // pre-rules behaviour — doc 13 §8.4).
      max_total_exposure_percent: null,
      conflict_policy: null,
      entries: [{ composition_item_id: "item_1", active: true, equity_share_percent: "90" }],
    });
    const headers = init.headers as Record<string, string>;
    expect(headers["Idempotency-Key"]).toBeTruthy();

    // The invalidation refetch re-seeds the editor from the new server head
    // (the DRAFT_SAVED head is enabled → the editor badge flips). Under the ADIM 3
    // containment the enabled badge also carries the server's verdict, so the
    // badge text is the "not available in this build" variant.
    expect(
      await screen.findByText("shared allocation — not available in this build"),
    ).toBeInTheDocument();

    // §6 per-item sleeve row + live example: the Capital cell renders the
    // SERVER-derived sleeve amount verbatim (never recomputed client-side) with
    // the fixed Allocation sizing base; the example line names the sleeve's
    // composition item + share and its server-derived capital.
    expect(screen.getByText("8100.00 USDT")).toBeInTheDocument();
    expect(screen.getByText("Allocation")).toBeInTheDocument();
    expect(
      screen.getByText(/gets 90% of the shared pool: 8100.00 USDT/),
    ).toBeInTheDocument();
  });

  it("sends the portfolio rules (max exposure + conflict policy) when set", async () => {
    const fetchMock = stubApi({
      "PUT /mainboard-compositions/ws_1/portfolio-allocation-draft": SAVE_RESULT,
      "GET /mainboard-compositions/ws_1/portfolio-allocation-draft": DRAFT_EMPTY,
      "GET /mainboards/default": MAINBOARD,
    });
    renderPage();

    fireEvent.click(await screen.findByLabelText(/USE EQUITY ALLOCATION FOR THIS BACKTEST/));
    fireEvent.change(screen.getByLabelText("Max total exposure %"), {
      target: { value: "150" },
    });
    fireEvent.change(screen.getByLabelText("Conflicting signals (same instrument)"), {
      target: { value: "NET" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
    expect(await screen.findByText("Draft saved")).toBeInTheDocument();

    const init = callFor(fetchMock, "PUT", "/portfolio-allocation-draft");
    const body = JSON.parse(String(init.body));
    expect(body.max_total_exposure_percent).toBe("150");
    expect(body.conflict_policy).toBe("NET");
  });

  it("surfaces a stale-draft conflict verbatim", async () => {
    stubApi({
      "PUT /mainboard-compositions/ws_1/portfolio-allocation-draft": () => {
        throw new Error(
          "ALLOCATION_DRAFT_CONFLICT: This allocation draft changed elsewhere. Refresh, compare, then reapply your update.",
        );
      },
      "GET /mainboard-compositions/ws_1/portfolio-allocation-draft": DRAFT_SAVED,
      "GET /mainboards/default": MAINBOARD,
    });
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Save draft" }));

    expect(
      await screen.findByText(
        "ALLOCATION_DRAFT_CONFLICT: This allocation draft changed elsewhere. Refresh, compare, then reapply your update.",
      ),
    ).toBeInTheDocument();
  });

  it("validates the saved draft and renders the immutable report verbatim", async () => {
    const fetchMock = stubApi({
      "POST /portfolio-allocation/validate": VALIDATION_REPORT,
      "GET /mainboard-compositions/ws_1/portfolio-allocation-draft": DRAFT_SAVED,
      "GET /mainboards/default": MAINBOARD,
    });
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Validate saved draft" }));

    expect(await screen.findByText("Ready with warnings")).toBeInTheDocument();
    expect(screen.getByText("parpt_1")).toBeInTheDocument();
    expect(screen.getByText("cfg_1")).toBeInTheDocument();
    expect(screen.getByText("TOTAL_ALLOCATION_UNDER_100")).toBeInTheDocument();

    // The route reads NO body and NO headers — nothing idempotency-shaped travels.
    const init = callFor(fetchMock, "POST", "/portfolio-allocation/validate");
    expect(init.body).toBeUndefined();
    const headers = init.headers as Record<string, string>;
    expect(headers["Idempotency-Key"]).toBeUndefined();
  });

  it("previews sync-from-mainboard as a pure read with a destructive-removal hint", async () => {
    const fetchMock = stubApi({
      "POST /portfolio-allocation/sync": SYNC_PREVIEW,
      "GET /mainboard-compositions/ws_1/portfolio-allocation-draft": DRAFT_SAVED,
      "GET /mainboards/default": MAINBOARD,
    });
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Sync From Mainboard" }));

    expect(await screen.findByText("Retained (1)")).toBeInTheDocument();
    expect(screen.getByText("Missing from composition (1)")).toBeInTheDocument();
    expect(screen.getByText("item_gone")).toBeInTheDocument();
    expect(screen.getByText("New candidates (1)")).toBeInTheDocument();
    expect(screen.getByText(/removing them is destructive/)).toBeInTheDocument();

    // PURE READ preview: no Idempotency-Key (the query layer writes nothing).
    const init = callFor(fetchMock, "POST", "/portfolio-allocation/sync");
    const headers = init.headers as Record<string, string>;
    expect(headers["Idempotency-Key"]).toBeUndefined();
  });

  it("creates a plan revision with the OCC token and renders the freeze result", async () => {
    const fetchMock = stubApi({
      "POST /portfolio-allocation/revisions": REVISION_RESULT,
      "GET /mainboard-compositions/ws_1/portfolio-allocation-draft": DRAFT_SAVED,
      "GET /mainboards/default": MAINBOARD,
    });
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Create plan revision" }));

    expect(await screen.findByText("parev_1")).toBeInTheDocument();
    expect(screen.getByText("(no. 1)")).toBeInTheDocument();

    const init = callFor(fetchMock, "POST", "/portfolio-allocation/revisions");
    expect(JSON.parse(String(init.body))).toEqual({ expected_row_version: 1 });
    const headers = init.headers as Record<string, string>;
    expect(headers["Idempotency-Key"]).toBeTruthy();
  });

  it("surfaces a blocker denial on the revision freeze verbatim", async () => {
    stubApi({
      "POST /portfolio-allocation/revisions": () => {
        throw new Error(
          "ALLOCATION_HAS_BLOCKERS: The allocation configuration has blocking issues and cannot become a plan revision.",
        );
      },
      "GET /mainboard-compositions/ws_1/portfolio-allocation-draft": DRAFT_SAVED,
      "GET /mainboards/default": MAINBOARD,
    });
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Create plan revision" }));

    expect(
      await screen.findByText(
        "ALLOCATION_HAS_BLOCKERS: The allocation configuration has blocking issues and cannot become a plan revision.",
      ),
    ).toBeInTheDocument();
  });

  it("fades and blocks the workspace on toggle-off, and restores it on toggle-on", async () => {
    stubApi({
      "GET /mainboard-compositions/ws_1/portfolio-allocation-draft": DRAFT_SAVED,
      "GET /mainboards/default": MAINBOARD,
    });
    renderPage();

    // DRAFT_SAVED starts enabled=true: the workspace is interactive and Card
    // 3/4 show live content, not the toggle-off placeholders.
    const toggle = await screen.findByLabelText(/USE EQUITY ALLOCATION FOR THIS BACKTEST/);
    expect(toggle).toBeChecked();
    expect(screen.getByLabelText("Initial capital")).not.toBeDisabled();
    expect(screen.queryByText("Not in use.")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Validate saved draft" })).toBeInTheDocument();

    fireEvent.click(toggle);

    expect(screen.getByText(/Equity Allocation is not selected/)).toBeInTheDocument();
    // Every field/button inside the workspace carries a native `disabled` —
    // pointer-events:none alone would not block keyboard activation (UI-13).
    expect(screen.getByLabelText("Initial capital")).toBeDisabled();
    expect(screen.getByLabelText("share item_1")).toBeDisabled();
    expect(screen.getByText("Not in use.")).toBeInTheDocument();
    expect(screen.getByText("Not selected (independent)")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Validate saved draft" })).not.toBeInTheDocument();
    // The toggle itself is never inside the disabled treatment.
    expect(toggle).not.toBeDisabled();
  });

  it("names sleeve rows by the server display label and keeps the id as a binding key (P-11)", async () => {
    stubApi({
      "GET /mainboard-compositions/ws_1/portfolio-allocation-draft": DRAFT_SAVED,
      "GET /mainboards/default": MAINBOARD,
    });
    renderPage();

    // The saved draft's entry carries display_label_override "Momentum A": the
    // sleeve row's Item column AND the example line name it (audit P-11 / F-07 —
    // the browser never reconstructs a name from the raw mbi_ id).
    const labels = await screen.findAllByText("Momentum A");
    expect(labels.length).toBeGreaterThan(0);
    // The composition_item_id stays present as a secondary binding key (<code>).
    expect(screen.getAllByText("item_1").length).toBeGreaterThan(0);
  });

  it("names the item a validation issue points at, instead of a bare id (F-07)", async () => {
    // The issue binds to composition item "item_1", whose server-owned label is
    // "Momentum A". Before this sweep the issue row showed ONLY the raw id, so a
    // reader had to recognize an opaque identifier to know which item was at
    // fault — the exact defect F-07 names. The label is now the primary text and
    // the id stays beneath it as the binding key.
    const itemScopedReport = {
      ...VALIDATION_REPORT,
      issues: [{ ...VALIDATION_REPORT.issues[0], composition_item_id: "item_1" }],
    };
    stubApi({
      "POST /portfolio-allocation/validate": itemScopedReport,
      "GET /mainboard-compositions/ws_1/portfolio-allocation-draft": DRAFT_SAVED,
      "GET /mainboards/default": MAINBOARD,
    });
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Validate saved draft" }));

    const issueRow = (await screen.findByText("TOTAL_ALLOCATION_UNDER_100")).closest("tr");
    expect(issueRow).not.toBeNull();
    // The human label is inside the issue row itself, not merely elsewhere on the page.
    expect(within(issueRow as HTMLElement).getByText("Momentum A")).toBeInTheDocument();
    // The raw id is kept for support/audit, but only as the secondary key.
    expect(within(issueRow as HTMLElement).getByText("item_1")).toBeInTheDocument();
  });

  it("distinguishes the two Add Item empty states", async () => {
    // Every candidate the composition offers already has an allocation row —
    // distinct from there being no compatible items at all.
    const allRepresentedDraft = {
      ...DRAFT_SAVED,
      candidate_items: [
        {
          composition_item_id: "item_1",
          item_type: "strategy",
          work_object_root_id: "root_1",
          is_enabled: true,
          position_index: 0,
          display_label_override: "Momentum A",
        },
      ],
    };
    stubApi({
      "GET /mainboard-compositions/ws_1/portfolio-allocation-draft": allRepresentedDraft,
      "GET /mainboards/default": MAINBOARD,
    });
    renderPage();

    expect(await screen.findByText("Every item is already allocated")).toBeInTheDocument();

    cleanup();
    // DRAFT_SAVED's own candidate_items is [] — no compatible item exists.
    stubApi({
      "GET /mainboard-compositions/ws_1/portfolio-allocation-draft": DRAFT_SAVED,
      "GET /mainboards/default": MAINBOARD,
    });
    renderPage();

    expect(await screen.findByText("No compatible items")).toBeInTheDocument();
  });

  // ADIM 3 containment ------------------------------------------------------ //

  it("renders the server's shared-mode containment verdict verbatim", async () => {
    stubApi({
      "GET /mainboard-compositions/ws_1/portfolio-allocation-draft": DRAFT_SAVED,
      "GET /mainboards/default": MAINBOARD,
    });
    renderPage();

    const note = await screen.findByTestId("alloc-containment-note");
    // Every string comes from the server block — none is authored in the browser.
    expect(note).toHaveTextContent(SHARED_MODE_CAPABILITY.message);
    expect(note).toHaveTextContent(SHARED_MODE_CAPABILITY.remediation);
    expect(note).toHaveTextContent(SHARED_MODE_CAPABILITY.dependency);
    expect(
      screen.getByText("shared allocation — not available in this build"),
    ).toBeInTheDocument();
  });

  it("keeps the shared plan authorable — the notice is not an input lock", async () => {
    // UI hidden/disabled state is presentation, never authorization: the refusal
    // lives in the allocation blocker + the run-admission guard. The user must
    // still be able to edit and save the plan (and to toggle the mode back off,
    // which is exactly what the remediation asks for).
    stubApi({
      "GET /mainboard-compositions/ws_1/portfolio-allocation-draft": DRAFT_SAVED,
      "GET /mainboards/default": MAINBOARD,
    });
    renderPage();

    await screen.findByTestId("alloc-containment-note");
    const toggle = screen.getByRole("checkbox", {
      name: /USE EQUITY ALLOCATION FOR THIS BACKTEST/i,
    });
    expect(toggle).toBeEnabled();
    expect(screen.getByRole("button", { name: /save draft/i })).toBeEnabled();
  });

  it("shows no containment notice while the composition is in independent mode", async () => {
    stubApi({
      "GET /mainboard-compositions/ws_1/portfolio-allocation-draft": DRAFT_EMPTY,
      "GET /mainboards/default": MAINBOARD,
    });
    renderPage();

    expect(await screen.findByText("independent (off)")).toBeInTheDocument();
    expect(screen.queryByTestId("alloc-containment-note")).not.toBeInTheDocument();
  });

  // P-E6 / C8: the OTHER world -------------------------------------------- //
  //
  // Every containment assertion above renders `available: false`, because the fixture
  // hard-codes it and the server has shipped `future_dev` since ADIM 3. So the `true`
  // arm of `Portfolio.tsx`'s `containmentActive` was never rendered by any test: the
  // page's behaviour on the day the containment lifts was unverified. This closes that
  // half. It asserts what the page must do when the SERVER says available — it does not
  // predict when the server will say it, and it changes no shipped fixture.
  it("drops the containment notice when the server reports the mode available", async () => {
    stubApi({
      "GET /mainboard-compositions/ws_1/portfolio-allocation-draft": {
        ...DRAFT_SAVED,
        shared_mode_capability: {
          ...SHARED_MODE_CAPABILITY,
          status: "active_v1",
          available: true,
        },
      },
      "GET /mainboards/default": MAINBOARD,
    });
    renderPage();

    // The badge flips to the plain mode name, and the "not available" wording is gone.
    expect(await screen.findByText("shared allocation")).toBeInTheDocument();
    expect(
      screen.queryByText("shared allocation — not available in this build"),
    ).not.toBeInTheDocument();
    // The notice — and with it all three server strings — must not render. This is what
    // keeps the measured backend defect off the screen: `capability.message` still says
    // "not available in this build" in that world, and the page is only safe because it
    // gates on `available` rather than printing the text unconditionally.
    expect(screen.queryByTestId("alloc-containment-note")).not.toBeInTheDocument();
    expect(screen.queryByText(SHARED_MODE_CAPABILITY.message)).not.toBeInTheDocument();
    // The plan stays exactly as authorable as it was — the notice was never the lock.
    expect(
      screen.getByRole("checkbox", { name: /USE EQUITY ALLOCATION FOR THIS BACKTEST/i }),
    ).toBeEnabled();
    expect(screen.getByRole("button", { name: /save draft/i })).toBeEnabled();
  });
});

describe("Portfolio — the NET conflict policy notice (G14 / GH #544)", () => {
  // The label used to read "Net (V1: executed as Block opposite)" — a SECOND copy of a
  // finding the server already sends, frozen at the moment it was typed. It went stale
  // twice over: containment means no shared plan reaches an engine at all, and the
  // unified-clock phase loop REFUSES NET rather than downgrading it. The fix is not a
  // better frozen sentence; it is to stop stating the outcome here at all.
  it("names the option without announcing an outcome the server owns", async () => {
    stubApi({
      "GET /mainboard-compositions/ws_1/portfolio-allocation-draft": DRAFT_EMPTY,
      "GET /mainboards/default": MAINBOARD,
    });
    renderPage();

    fireEvent.click(await screen.findByLabelText(/USE EQUITY ALLOCATION FOR THIS BACKTEST/));
    const select = screen.getByLabelText("Conflicting signals (same instrument)");
    const net = within(select).getByRole("option", { name: /^Net\b/ });

    // The wire token is untouched — this is a presentation assertion, not a contract one.
    expect(net).toHaveValue("NET");

    // The label must not re-state what running NET does. "Block opposite" is a SIBLING
    // option's label, so claiming it here is precisely the confusion that shipped.
    expect(net).not.toHaveTextContent(/block/i);
    expect(net).not.toHaveTextContent(/executed as/i);
    // ... and it must point the reader at the authority instead of replacing it.
    expect(net).toHaveTextContent(/warning/i);
  });

  it("renders the server's NET finding verbatim rather than a client paraphrase", async () => {
    // The server words this against the CURRENT containment flag, which is exactly why the
    // page may not keep its own copy: a copy would be frozen in one world. Sent here as an
    // opaque string — if the page paraphrased or truncated it, this fails.
    const serverNotice =
      "Shared capital allocation does not execute in this build, so no plan carrying " +
      "this policy reaches an engine at all and the downgrade described below does not " +
      "happen. NET has no canonical definition.";
    stubApi({
      "PUT /mainboard-compositions/ws_1/portfolio-allocation-draft": {
        ...SAVE_RESULT,
        inline_issues: [
          {
            code: "CONFLICT_POLICY_NET_V1",
            severity: "warning",
            message: serverNotice,
            field: "conflict_policy",
            composition_item_id: null,
          },
        ],
      },
      "GET /mainboard-compositions/ws_1/portfolio-allocation-draft": DRAFT_EMPTY,
      "GET /mainboards/default": MAINBOARD,
    });
    renderPage();

    fireEvent.click(await screen.findByLabelText(/USE EQUITY ALLOCATION FOR THIS BACKTEST/));
    fireEvent.change(screen.getByLabelText("Conflicting signals (same instrument)"), {
      target: { value: "NET" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));

    expect(await screen.findByText("Draft saved")).toBeInTheDocument();
    expect(screen.getByText("CONFLICT_POLICY_NET_V1")).toBeInTheDocument();
    expect(screen.getByText(serverNotice)).toBeInTheDocument();
  });
});
