import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import { parseAliases, resolutionExpectations } from "./instrumentFixtures";
import { Instruments } from "@/pages/Instruments";
import { stubApi } from "./helpers/apiStub";

const BTC_ROW = {
  instrument_id: "instr_1",
  resolution_key: "binance:btcusdt:perpetual",
  venue_id: "binance",
  symbol: "BTCUSDT",
  contract_type: "perpetual",
  display_name: "BTCUSDT Perpetual",
  base_asset: "BTC",
  quote_asset: "USDT",
  settlement_asset: "USDT",
  multiplier: "1",
  market_class: "crypto",
  state: "active",
  registry_version: 1,
  deprecation_reason: null,
};

const SPOT_ROW = {
  ...BTC_ROW,
  instrument_id: "instr_2",
  resolution_key: "coinbase:btc-usd:spot",
  venue_id: "coinbase",
  symbol: "BTC-USD",
  contract_type: "spot",
  display_name: "BTC-USD Spot",
  state: "deprecated",
  registry_version: 2,
  deprecation_reason: "delisted",
};

const LIST_PAGE = { data: [BTC_ROW, SPOT_ROW], meta: { cursor: null, has_more: false } };

const BTC_DETAIL = {
  ...BTC_ROW,
  row_version: 1,
  aliases: [
    { alias_id: "a1", alias_norm: "btcusdt perpetual", alias_text: "BTCUSDT Perpetual" },
    { alias_id: "a2", alias_norm: "btcusdt.p", alias_text: "BTCUSDT.P" },
  ],
};

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Instruments />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Instruments page", () => {
  it("renders the registry rows with resolution keys", async () => {
    stubApi({ "GET /instruments": LIST_PAGE });
    renderPage();
    expect(await screen.findByText("binance:btcusdt:perpetual")).toBeInTheDocument();
    expect(screen.getByText("coinbase:btc-usd:spot")).toBeInTheDocument();
    // Spot vs perpetual are distinct rows (Master §8.1).
    expect(screen.getByText("BTCUSDT Perpetual")).toBeInTheDocument();
    expect(screen.getByText("BTC-USD Spot")).toBeInTheDocument();
  });

  it("opens the detail with aliases and a deprecate composer for an active instrument", async () => {
    stubApi({
      "GET /instruments/instr_1": BTC_DETAIL,
      "GET /instruments": LIST_PAGE,
    });
    renderPage();
    const detailButtons = await screen.findAllByRole("button", { name: "Detail" });
    fireEvent.click(detailButtons[0]);
    expect(await screen.findByText("Resolution aliases")).toBeInTheDocument();
    expect(screen.getByText("BTCUSDT.P")).toBeInTheDocument();
    // An active instrument offers the Admin-only deprecate action.
    expect(screen.getByRole("button", { name: "Deprecate instrument" })).toBeInTheDocument();
  });

  it("registers an instrument and shows the resolution key on success", async () => {
    const fetchMock = stubApi({
      "POST /instruments/resolve": { resolved: true },
      "POST /instruments": {
        instrument_id: "instr_9",
        resolution_key: "binance:ethusdt:perpetual",
        display_name: "ETHUSDT Perpetual",
        state: "active",
        registry_version: 1,
        alias_count: 1,
      },
      "GET /instruments": LIST_PAGE,
    });
    renderPage();
    const reg = within(
      (await screen.findByRole("heading", { name: "Register instrument" })).closest("section")!,
    );
    fireEvent.change(reg.getByLabelText(/Venue/), { target: { value: "binance" } });
    fireEvent.change(reg.getByLabelText(/Symbol/), { target: { value: "ETHUSDT" } });
    fireEvent.change(reg.getByLabelText(/Display name/), { target: { value: "ETHUSDT Perpetual" } });
    fireEvent.click(reg.getByRole("button", { name: "Register instrument" }));
    expect(await screen.findByText(/binance:ethusdt:perpetual/)).toBeInTheDocument();
    // The register POST carries a fresh Idempotency-Key (no OCC — a create has no head).
    const call = fetchMock.mock.calls.find(
      ([url, init]) => String(url).endsWith("/instruments") && init?.method === "POST",
    );
    expect((call?.[1]?.headers as Record<string, string>)["Idempotency-Key"]).toBeTruthy();
  });

  it("resolves a free-text alias to a canonical instrument", async () => {
    stubApi({
      "POST /instruments/resolve": { resolved: true, ...BTC_ROW },
      "GET /instruments": LIST_PAGE,
    });
    renderPage();
    const card = within(
      (await screen.findByRole("heading", { name: "Resolve scope" })).closest("section")!,
    );
    fireEvent.change(card.getByLabelText(/Alias/), { target: { value: "BTCUSDT Perpetual" } });
    fireEvent.click(card.getByRole("button", { name: "Resolve" }));
    await waitFor(() =>
      expect(card.getByText("instr_1")).toBeInTheDocument(),
    );
  });
});

describe("parseAliases", () => {
  it("splits lines and drops blanks", () => {
    expect(parseAliases("BTCUSDT Perpetual\n\n  BTCUSDT.P  \n")).toEqual([
      "BTCUSDT Perpetual",
      "BTCUSDT.P",
    ]);
    // Sanity: the fixture helper agrees with the exported parser.
    expect(resolutionExpectations()).toBe(true);
  });
});
