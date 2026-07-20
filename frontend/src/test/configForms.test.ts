// R2-04 — typed-form payload production + validation (pure lib tests).
// The forms MIRROR backend authority (domain/{trading_signal,trade_log}/
// config.py + compiler.py): these tests pin the wire shape the form produces
// and the client-side blockers that mirror the compiler cross-field rules.
import { describe, expect, it } from "vitest";

import { buildSignalPayloadTemplate } from "@/lib/tradingSignal";
import {
  signalFormFromPayload,
  signalFormToPayload,
  validateSignalForm,
} from "@/lib/tradingSignalForm";
import { buildTradeLogPayloadTemplate } from "@/lib/tradeLog";
import {
  tradeLogFormFromPayload,
  tradeLogFormToPayload,
  validateTradeLogForm,
} from "@/lib/tradeLogForm";

const SIGNAL_TEMPLATE = buildSignalPayloadTemplate({
  sourceAssetId: "srcasset_1",
  normalizedEventRevisionId: "nser_1",
  instrumentId: "BTCUSDT",
  sourceTimezone: "UTC",
});

const TRADE_LOG_TEMPLATE = buildTradeLogPayloadTemplate({
  sourceAssetId: "srcasset_9",
  recordBatchRevisionId: "ctrb_1",
  instrumentId: "ETHUSDT",
  sourceTimezone: "UTC",
});

describe("tradingSignalForm", () => {
  it("round-trips the report-seeded template byte-for-byte once identity is filled", () => {
    const state = signalFormFromPayload(SIGNAL_TEMPLATE);
    // Template ships blank identity; the wire shape must otherwise be identical.
    state.displayName = "Provider signals";
    state.providerName = "acme";
    const payload = signalFormToPayload(state);
    expect(payload).toEqual({
      ...SIGNAL_TEMPLATE,
      identity: { display_name: "Provider signals" },
      source: { provider_name: "acme", source_kind: "file" },
    });
  });

  it("keeps the mapping hash in the import binding when the report carried one", () => {
    const template = buildSignalPayloadTemplate({
      sourceAssetId: "srcasset_1",
      normalizedEventRevisionId: "nser_1",
      instrumentId: "BTCUSDT",
      sourceTimezone: "UTC",
      mappingRevisionId: "maphash_1",
    });
    const payload = signalFormToPayload(signalFormFromPayload(template));
    expect((payload.import_binding as Record<string, unknown>).mapping_revision_id).toBe(
      "maphash_1",
    );
  });

  it("mirrors the compiler cross-field rules next to their fields", () => {
    const state = signalFormFromPayload(SIGNAL_TEMPLATE);
    state.displayName = "x";
    state.providerName = "y";
    // Event-based + base timeframe → EVENT_MODEL_POLICY_CONFLICT.
    state.baseTimeframe = "1h";
    expect(validateSignalForm(state).baseTimeframe).toMatch(/no base timeframe/);
    // Bar-aligned without base timeframe.
    state.baseTimeframe = "";
    state.resolutionKind = "bar_timeframe";
    expect(validateSignalForm(state).baseTimeframe).toMatch(/requires a base timeframe/);
    // Intrabar price + ignore OHLCV → OHLCV_POLICY_CONFLICT.
    state.resolutionKind = "event_based";
    state.priceSource = "ohlcv_intrabar_if_available";
    state.ohlcvUseMode = "ignore";
    expect(validateSignalForm(state).ohlcvUseMode).toMatch(/cannot ignore OHLCV/);
    // signal_events_only + use_for_price_context_and_validation.
    state.priceSource = "suggested_signal_price";
    state.ohlcvUseMode = "use_for_price_context_and_validation";
    expect(validateSignalForm(state).ohlcvUseMode).toMatch(/no source OHLCV/);
  });

  it("requires identity, symbols and a system-carried binding", () => {
    const errors = validateSignalForm(
      signalFormFromPayload({
        ...SIGNAL_TEMPLATE,
        instrument_scope: { instrument_id: "", display_symbol: "" },
        import_binding: {},
      }),
    );
    expect(errors.displayName).toBeTruthy();
    expect(errors.providerName).toBeTruthy();
    expect(errors.instrumentId).toBeTruthy();
    expect(errors.displaySymbol).toBeTruthy();
    expect(errors.binding).toMatch(/succeeded import/);
  });

  it("rejects a non-positive independent initial capital", () => {
    const state = signalFormFromPayload(SIGNAL_TEMPLATE);
    state.displayName = "x";
    state.providerName = "y";
    state.independentInitialCapital = "-5";
    expect(validateSignalForm(state).independentInitialCapital).toMatch(/positive/);
    state.independentInitialCapital = "10000";
    expect(validateSignalForm(state)).toEqual({});
    expect(
      (signalFormToPayload(state).capital as Record<string, unknown>)
        .independent_initial_capital,
    ).toBe("10000");
  });
});

describe("tradeLogForm", () => {
  it("round-trips the report-seeded template byte-for-byte once identity is filled", () => {
    const state = tradeLogFormFromPayload(TRADE_LOG_TEMPLATE);
    state.displayName = "Broker ledger";
    state.providerName = "broker";
    const payload = tradeLogFormToPayload(state);
    expect(payload).toEqual({
      ...TRADE_LOG_TEMPLATE,
      identity: { display_name: "Broker ledger" },
      source: { provider_name: "broker", source_kind: "file" },
    });
    // Twin diff preserved: a single time_model group, no time_policy/event_model.
    expect("time_policy" in payload).toBe(false);
    expect("event_model" in payload).toBe(false);
  });

  it("mirrors the TL-10 price-context rules", () => {
    const state = tradeLogFormFromPayload(TRADE_LOG_TEMPLATE);
    state.displayName = "x";
    state.providerName = "y";
    // OHLCV fallback price + Ignore OHLCV → PRICE_CONTEXT_CONFLICT.
    state.priceSource = "ohlcv_close_if_needed";
    state.ohlcvUseMode = "ignore";
    expect(validateTradeLogForm(state).ohlcvUseMode).toMatch(/cannot be used while OHLCV Use/);
    // entry_exit_records_only + use_for_price_context_and_validation.
    state.priceSource = "trade_log_entry_exit_price";
    state.ohlcvUseMode = "use_for_price_context_and_validation";
    expect(validateTradeLogForm(state).ohlcvUseMode).toMatch(/no source OHLCV/);
  });

  it("emits the currency-carrying capital group only when it differs from defaults", () => {
    const state = tradeLogFormFromPayload(TRADE_LOG_TEMPLATE);
    state.displayName = "x";
    state.providerName = "y";
    expect("capital" in tradeLogFormToPayload(state)).toBe(false);
    state.independentInitialCapital = "5000";
    expect(tradeLogFormToPayload(state).capital).toEqual({
      independent_initial_capital: "5000",
      currency: "USDT",
    });
    state.currency = "";
    expect(validateTradeLogForm(state).currency).toMatch(/required/);
  });

  it("requires the record-batch binding", () => {
    const errors = validateTradeLogForm(
      tradeLogFormFromPayload({ ...TRADE_LOG_TEMPLATE, import_binding: {} }),
    );
    expect(errors.binding).toMatch(/succeeded import/);
  });
});
