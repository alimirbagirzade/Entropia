import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import { ArrangeMetrics } from "@/pages/ArrangeMetrics";
import { stubApi } from "./helpers/apiStub";

const REGISTRY = {
  registry_version: "v1",
  metric_definitions: [
    {
      metric_code: "net_profit",
      label: "Net Profit",
      unit: "percent",
      value_format: "signed_percent",
      availability_status: "selectable",
      display_order: 1,
      formula_version: "v1",
      description: "Total return over the period",
      selectable: true,
    },
    {
      metric_code: "romad",
      label: "ROMAD",
      unit: "ratio",
      value_format: "decimal2",
      availability_status: "selectable",
      display_order: 2,
      formula_version: "v1",
      description: null,
      selectable: true,
    },
    {
      metric_code: "sortino",
      label: "Sortino Ratio",
      unit: "ratio",
      value_format: "decimal2",
      availability_status: "future",
      display_order: 3,
      formula_version: null,
      description: "Planned",
      selectable: false,
    },
  ],
};

const SYSTEM_DEFAULT_PROFILE = {
  profile_id: "system_default",
  scope: "system_default",
  is_personal: false,
  current_revision_id: null,
  selected_metric_codes: ["net_profit"],
  display_order: ["net_profit"],
  is_locked: false,
  registry_version: "v1",
  selected_metric_count: 1,
  editable_profile_id: "system_default",
};

const LOCKED_PROFILE = {
  ...SYSTEM_DEFAULT_PROFILE,
  profile_id: "mp_1",
  scope: "user",
  is_personal: true,
  current_revision_id: "mprev_3",
  is_locked: true,
  editable_profile_id: "mp_1",
};

const APPLY_RESPONSE = {
  profile_id: "mp_1",
  scope: "user",
  is_personal: true,
  current_revision_id: "mprev_1",
  profile_revision_id: "mprev_1",
  revision_no: 1,
  selected_metric_codes: ["net_profit", "romad"],
  display_order: ["net_profit", "romad"],
  is_locked: false,
  registry_version: "v1",
  row_version: 1,
  reason: "apply",
  selected_metric_count: 2,
};

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/backtest/metrics"]}>
        <ArrangeMetrics />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return client;
}

describe("Arrange Metrics page", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders the registry with the resolved selection layered on top", async () => {
    stubApi({
      "GET /metric-definitions": REGISTRY,
      "GET /metric-profiles/resolved": SYSTEM_DEFAULT_PROFILE,
    });
    renderPage();

    expect(await screen.findByText("System Default")).toBeInTheDocument();
    expect(screen.getByLabelText("Show Net Profit")).toBeChecked();
    expect(screen.getByLabelText("Show ROMAD")).not.toBeChecked();
    // A future (non-selectable) metric can never be chosen.
    expect(screen.getByLabelText("Show Sortino Ratio")).toBeDisabled();
    expect(
      screen.getByText(/first Apply creates a personal profile/),
    ).toBeInTheDocument();
  });

  it("applies an edited selection to the editable profile id", async () => {
    const fetchMock = stubApi({
      "GET /metric-definitions": REGISTRY,
      "GET /metric-profiles/resolved": SYSTEM_DEFAULT_PROFILE,
      "POST /metric-profiles/system_default/revisions": APPLY_RESPONSE,
    });
    renderPage();

    fireEvent.click(await screen.findByLabelText("Show ROMAD"));
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));

    expect(await screen.findByText("Saved — revision 1 (apply).")).toBeInTheDocument();
    const postCall = fetchMock.mock.calls.find(
      ([, init]) => (init as RequestInit | undefined)?.method === "POST",
    );
    expect(postCall).toBeDefined();
    const body = JSON.parse(String((postCall?.[1] as RequestInit).body));
    // Registry display order is preserved; the draft mirrors the server echo.
    expect(body.selected_metric_codes).toEqual(["net_profit", "romad"]);
    expect(body.is_locked).toBe(false);
    expect(body.expected_profile_revision_id).toBeNull();
  });

  it("refuses edits while locked and offers a pure unlock", async () => {
    const fetchMock = stubApi({
      "GET /metric-definitions": REGISTRY,
      "GET /metric-profiles/resolved": LOCKED_PROFILE,
      "POST /metric-profiles/mp_1/revisions": { ...APPLY_RESPONSE, reason: "unlock" },
    });
    renderPage();

    expect(await screen.findByText("Locked")).toBeInTheDocument();
    expect(screen.getByLabelText("Show Net Profit")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Apply" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Unlock" }));

    await waitFor(() => {
      const postCall = fetchMock.mock.calls.find(
        ([, init]) => (init as RequestInit | undefined)?.method === "POST",
      );
      expect(postCall).toBeDefined();
      const body = JSON.parse(String((postCall?.[1] as RequestInit).body));
      // A pure unlock re-submits the server's own selection with is_locked=false.
      expect(body.selected_metric_codes).toEqual(["net_profit"]);
      expect(body.is_locked).toBe(false);
      expect(body.expected_profile_revision_id).toBe("mprev_3");
    });
  });

  it("shows the error state when the registry cannot load", async () => {
    stubApi({
      "GET /metric-definitions": () => {
        throw new Error("registry unavailable");
      },
      "GET /metric-profiles/resolved": SYSTEM_DEFAULT_PROFILE,
    });
    renderPage();

    expect(await screen.findByText("Unable to load")).toBeInTheDocument();
    expect(screen.getByText("registry unavailable")).toBeInTheDocument();
  });
});
