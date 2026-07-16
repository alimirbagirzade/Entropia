import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { DatasetPicker, type DatasetRefValue } from "@/components/DatasetPicker";
import { stubApi } from "./helpers/apiStub";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

// A minimal-but-complete Market Data registry page. The picker browses this by
// name and pins {rootId, revisionId, contentHash} onto the SAME flat config
// fields the raw ID inputs used to write (presentation-only, F-19).
const REGISTRY = {
  data: [
    {
      entity_id: "mkt_btc",
      revision_id: "mrev_btc",
      revision_no: 3,
      revision_state: "approved",
      market_data_type: "ohlcv",
      validation_status: "passed",
      title: "BTC Perp 1m",
      instrument_id: "BTCUSDT",
      content_hash: "sha256:btc",
      manifest_hash: "sha256:mbtc",
      owner_principal_id: "prin_1",
      row_version: 1,
      lifecycle_state: "active",
      created_at: "2026-01-01T00:00:00Z",
    },
    {
      entity_id: "mkt_eth",
      revision_id: "mrev_eth",
      revision_no: 1,
      revision_state: "draft",
      market_data_type: "ohlcv",
      validation_status: null,
      title: "ETH Perp 1m",
      instrument_id: "ETHUSDT",
      content_hash: null,
      manifest_hash: null,
      owner_principal_id: "prin_1",
      row_version: 1,
      lifecycle_state: "active",
      created_at: "2026-01-02T00:00:00Z",
    },
  ],
  meta: { cursor: null, has_more: false },
};

const EMPTY: DatasetRefValue = { rootId: "", revisionId: "", contentHash: "" };

function renderPicker(value: DatasetRefValue, onChange = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <DatasetPicker kind="market" label="Market data source" required value={value} onChange={onChange} />
    </QueryClientProvider>,
  );
  return onChange;
}

describe("DatasetPicker", () => {
  it("shows the empty state with no infra-ID text inputs", () => {
    renderPicker(EMPTY);
    expect(screen.getByRole("button", { name: "Choose market dataset" })).toBeTruthy();
    // The raw ID fields are gone — no root/revision/hash textbox in the primary surface.
    expect(screen.queryByLabelText(/root id/i)).toBeNull();
    expect(screen.queryByLabelText(/content hash/i)).toBeNull();
  });

  it("browses the registry by name and pins root/revision/hash on pick", async () => {
    stubApi({ "GET /market-datasets": REGISTRY });
    const onChange = renderPicker(EMPTY);
    fireEvent.click(screen.getByRole("button", { name: "Choose market dataset" }));

    // Datasets listed by their human name, not their ULIDs.
    const row = await screen.findByRole("button", { name: /BTC Perp 1m/ });
    fireEvent.click(row);

    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange.mock.calls[0][0]).toEqual({
      rootId: "mkt_btc",
      revisionId: "mrev_btc",
      contentHash: "sha256:btc",
    });
  });

  it("filters the registry list by the search query", async () => {
    stubApi({ "GET /market-datasets": REGISTRY });
    renderPicker(EMPTY);
    fireEvent.click(screen.getByRole("button", { name: "Choose market dataset" }));
    await screen.findByRole("button", { name: /BTC Perp 1m/ });

    fireEvent.change(screen.getByLabelText("Search market datasets"), {
      target: { value: "eth" },
    });
    expect(screen.queryByRole("button", { name: /BTC Perp 1m/ })).toBeNull();
    expect(screen.getByRole("button", { name: /ETH Perp 1m/ })).toBeTruthy();
  });

  it("pins a dataset whose content hash is absent as an empty hash (never invented)", async () => {
    stubApi({ "GET /market-datasets": REGISTRY });
    const onChange = renderPicker(EMPTY);
    fireEvent.click(screen.getByRole("button", { name: "Choose market dataset" }));
    fireEvent.click(await screen.findByRole("button", { name: /ETH Perp 1m/ }));
    expect(onChange.mock.calls[0][0]).toEqual({
      rootId: "mkt_eth",
      revisionId: "mrev_eth",
      contentHash: "",
    });
  });

  it("resolves a pinned dataset to its name and keeps the ids in the disclosure", async () => {
    stubApi({ "GET /market-datasets": REGISTRY });
    renderPicker({ rootId: "mkt_btc", revisionId: "mrev_btc", contentHash: "sha256:btc" });

    // Human name is the primary label; raw ids live in the collapsed disclosure.
    expect(await screen.findByText(/BTC Perp 1m/)).toBeTruthy();
    const disclosure = screen.getByText("Technical identifiers").closest("details") as HTMLElement;
    expect(within(disclosure).getByText("mkt_btc")).toBeTruthy();
    expect(within(disclosure).getByText("sha256:btc")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Change" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Clear" })).toBeTruthy();
  });

  it("clears the pin back to an empty ref", async () => {
    stubApi({ "GET /market-datasets": REGISTRY });
    const onChange = renderPicker({ rootId: "mkt_btc", revisionId: "mrev_btc", contentHash: "sha256:btc" });
    await screen.findByText(/BTC Perp 1m/);
    fireEvent.click(screen.getByRole("button", { name: "Clear" }));
    expect(onChange).toHaveBeenCalledWith({ rootId: "", revisionId: "", contentHash: "" });
  });
});
