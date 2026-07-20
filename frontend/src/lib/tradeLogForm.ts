// Typed Trade Log config form model (R2-04, GAP item 3/9) — twin of
// lib/tradingSignalForm.ts. Mirrors domain/trade_log/config.py +
// compiler.py empirically: time_model (not time_policy + event_model),
// content_profile data quality, ledger price source with the
// approved-market-data ref, currency-carrying capital, and the record-batch
// import binding. Revision-level available_time stays null server-side (doc 05
// §10.4) — it is not a form field. The server compiler remains authoritative.

import { useState } from "react";

export const TRADE_LOG_SOURCE_KINDS = ["file", "integration"] as const;
export const TRADE_LOG_RESOLUTION_KINDS = [
  "event_based",
  "same_as_market_dataset",
  "bar_timeframe",
] as const;
export const TRADE_LOG_CONTENT_PROFILES = [
  "entry_exit_records_only",
  "trade_log_with_ohlcv",
  "trade_log_with_signal_events",
] as const;
export const TRADE_LOG_PRICE_SOURCES = [
  "trade_log_entry_exit_price",
  "ohlcv_close_if_needed",
  "ohlcv_intrabar_if_available",
] as const;
export const TRADE_LOG_OHLCV_USE_MODES = [
  "use_if_supplied_and_needed",
  "ignore",
  "use_for_price_context_and_validation",
] as const;

// compiler.py _OHLCV_FALLBACK_SOURCES (TL-10).
const OHLCV_FALLBACK_SOURCES: ReadonlySet<string> = new Set([
  "ohlcv_close_if_needed",
  "ohlcv_intrabar_if_available",
]);

const NAME_MAX = 160;
const PROVIDER_MAX = 200;
const SYMBOL_MAX = 64;

export interface TradeLogBinding {
  sourceAssetId: string;
  recordBatchRevisionId: string;
  mappingRevisionId: string;
}

export interface TradeLogFormState {
  displayName: string;
  providerName: string;
  sourceKind: string;
  instrumentId: string;
  displaySymbol: string;
  resolutionKind: string;
  baseTimeframe: string;
  rationaleFamilyId: string;
  contentProfile: string;
  sourceTimezone: string;
  priceSource: string;
  approvedMarketDataRevisionRef: string;
  ohlcvUseMode: string;
  independentInitialCapital: string;
  currency: string;
  binding: TradeLogBinding;
}

export type FormErrors = Partial<Record<string, string>>;

function str(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function section(payload: Record<string, unknown>, key: string): Record<string, unknown> {
  const value = payload[key];
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

export function tradeLogFormFromPayload(payload: Record<string, unknown>): TradeLogFormState {
  const identity = section(payload, "identity");
  const source = section(payload, "source");
  const scope = section(payload, "instrument_scope");
  const timeModel = section(payload, "time_model");
  const classification = section(payload, "classification");
  const dataQuality = section(payload, "data_quality");
  const pricePolicy = section(payload, "price_policy");
  const ohlcvPolicy = section(payload, "ohlcv_policy");
  const capital = section(payload, "capital");
  const binding = section(payload, "import_binding");
  const capitalValue = capital.independent_initial_capital;
  return {
    displayName: str(identity.display_name),
    providerName: str(source.provider_name),
    sourceKind: str(source.source_kind) || "file",
    instrumentId: str(scope.instrument_id),
    displaySymbol: str(scope.display_symbol),
    resolutionKind: str(timeModel.resolution_kind) || "event_based",
    baseTimeframe: str(timeModel.base_timeframe),
    rationaleFamilyId: str(classification.rationale_family_id),
    contentProfile: str(dataQuality.content_profile) || "entry_exit_records_only",
    sourceTimezone: str(timeModel.source_timezone) || "UTC",
    priceSource: str(pricePolicy.source) || "trade_log_entry_exit_price",
    approvedMarketDataRevisionRef: str(pricePolicy.approved_market_data_revision_ref),
    ohlcvUseMode: str(ohlcvPolicy.use_mode) || "ignore",
    independentInitialCapital:
      typeof capitalValue === "number" ? String(capitalValue) : str(capitalValue),
    currency: str(capital.currency) || "USDT",
    binding: {
      sourceAssetId: str(binding.source_asset_id),
      recordBatchRevisionId: str(binding.record_batch_revision_id),
      mappingRevisionId: str(binding.mapping_revision_id),
    },
  };
}

export function tradeLogFormToPayload(state: TradeLogFormState): Record<string, unknown> {
  const importBinding: Record<string, unknown> = {
    source_asset_id: state.binding.sourceAssetId,
    record_batch_revision_id: state.binding.recordBatchRevisionId,
  };
  if (state.binding.mappingRevisionId !== "") {
    importBinding.mapping_revision_id = state.binding.mappingRevisionId;
  }
  return {
    kind: "trade_log",
    identity: { display_name: state.displayName.trim() },
    source: { provider_name: state.providerName.trim(), source_kind: state.sourceKind },
    instrument_scope: {
      instrument_id: state.instrumentId.trim(),
      display_symbol: state.displaySymbol.trim(),
    },
    time_model: {
      resolution_kind: state.resolutionKind,
      ...(state.baseTimeframe.trim() !== ""
        ? { base_timeframe: state.baseTimeframe.trim() }
        : {}),
      source_timezone: state.sourceTimezone.trim(),
      normalization_timezone: "UTC",
    },
    ...(state.rationaleFamilyId.trim() !== ""
      ? { classification: { rationale_family_id: state.rationaleFamilyId.trim() } }
      : {}),
    data_quality: { content_profile: state.contentProfile },
    price_policy: {
      source: state.priceSource,
      ...(state.approvedMarketDataRevisionRef.trim() !== ""
        ? { approved_market_data_revision_ref: state.approvedMarketDataRevisionRef.trim() }
        : {}),
    },
    ohlcv_policy: { use_mode: state.ohlcvUseMode },
    ...(state.independentInitialCapital.trim() !== "" || state.currency.trim() !== "USDT"
      ? {
          capital: {
            ...(state.independentInitialCapital.trim() !== ""
              ? { independent_initial_capital: state.independentInitialCapital.trim() }
              : {}),
            currency: state.currency.trim() || "USDT",
          },
        }
      : {}),
    import_binding: importBinding,
  };
}

export function validateTradeLogForm(state: TradeLogFormState): FormErrors {
  const errors: FormErrors = {};
  const name = state.displayName.trim();
  if (name.length < 1 || name.length > NAME_MAX) {
    errors.displayName = `Display name must be 1..${NAME_MAX} characters.`;
  }
  const provider = state.providerName.trim();
  if (provider.length < 1 || provider.length > PROVIDER_MAX) {
    errors.providerName = `Provider name must be 1..${PROVIDER_MAX} characters.`;
  }
  for (const [key, value] of [
    ["instrumentId", state.instrumentId],
    ["displaySymbol", state.displaySymbol],
  ] as const) {
    const trimmed = value.trim();
    if (trimmed.length < 1 || trimmed.length > SYMBOL_MAX) {
      errors[key] = "Value must be 1..64 characters.";
    }
  }
  if (state.sourceTimezone.trim() === "") {
    errors.sourceTimezone = "Source timezone is required.";
  }
  if (state.resolutionKind === "event_based" && state.baseTimeframe.trim() !== "") {
    errors.baseTimeframe = "Event-based trade records carry no base timeframe.";
  }
  if (state.resolutionKind === "bar_timeframe" && state.baseTimeframe.trim() === "") {
    errors.baseTimeframe = "A bar-aligned trade log requires a base timeframe.";
  }
  if (OHLCV_FALLBACK_SOURCES.has(state.priceSource) && state.ohlcvUseMode === "ignore") {
    errors.ohlcvUseMode = "OHLCV fallback cannot be used while OHLCV Use is set to Ignore.";
  }
  if (
    state.contentProfile === "entry_exit_records_only" &&
    state.ohlcvUseMode === "use_for_price_context_and_validation"
  ) {
    errors.ohlcvUseMode = "Entry/exit-only data quality supplies no source OHLCV to use.";
  }
  const capital = state.independentInitialCapital.trim();
  if (capital !== "" && (!Number.isFinite(Number(capital)) || Number(capital) <= 0)) {
    errors.independentInitialCapital =
      "Independent initial capital must be a positive number.";
  }
  if (state.currency.trim() === "") {
    errors.currency = "Currency is required.";
  }
  if (state.binding.sourceAssetId === "" || state.binding.recordBatchRevisionId === "") {
    errors.binding =
      "Complete a succeeded import first — the source binding is carried automatically.";
  }
  return errors;
}

export function useTradeLogConfigEditorState(initialPayload: Record<string, unknown>) {
  const [state, setState] = useState<TradeLogFormState>(() =>
    tradeLogFormFromPayload(initialPayload),
  );
  const [errors, setErrors] = useState<FormErrors>({});
  const [rawMode, setRawMode] = useState(false);
  const [rawText, setRawText] = useState("");
  const [rawError, setRawError] = useState<string | null>(null);
  const [validNote, setValidNote] = useState<string | null>(null);

  const parseRaw = (): Record<string, unknown> | null => {
    try {
      const parsed: unknown = JSON.parse(rawText);
      if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
        setRawError("The payload must be a JSON object.");
        return null;
      }
      setRawError(null);
      return parsed as Record<string, unknown>;
    } catch (error) {
      setRawError(error instanceof Error ? error.message : "Invalid JSON.");
      return null;
    }
  };

  const buildPayload = (): Record<string, unknown> | null => {
    setValidNote(null);
    if (rawMode) return parseRaw();
    const nextErrors = validateTradeLogForm(state);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return null;
    return tradeLogFormToPayload(state);
  };

  const validate = () => {
    if (rawMode) {
      setValidNote(
        parseRaw() !== null
          ? "Raw payload is a valid JSON object (client-side check — the server compiler is authoritative)."
          : null,
      );
      return;
    }
    const nextErrors = validateTradeLogForm(state);
    setErrors(nextErrors);
    setValidNote(
      Object.keys(nextErrors).length === 0
        ? "No blockers found (client-side check — the server compiler is authoritative)."
        : "Fix the highlighted fields.",
    );
  };

  const reset = (payload: Record<string, unknown>) => {
    setState(tradeLogFormFromPayload(payload));
    setErrors({});
    setRawMode(false);
    setRawText("");
    setRawError(null);
    setValidNote(null);
  };

  const enterRawMode = (on: boolean) => {
    setRawMode(on);
    if (!on) {
      try {
        const parsed: unknown = JSON.parse(rawText);
        if (parsed !== null && typeof parsed === "object" && !Array.isArray(parsed)) {
          setState(tradeLogFormFromPayload(parsed as Record<string, unknown>));
          setRawError(null);
        } else {
          setRawMode(true);
          setRawError("The payload must be a JSON object.");
        }
      } catch (error) {
        setRawMode(true);
        setRawError(error instanceof Error ? error.message : "Invalid JSON.");
      }
    }
  };

  return {
    state,
    setState,
    errors,
    rawMode,
    rawText,
    setRawText,
    rawError,
    validNote,
    buildPayload,
    validate,
    reset,
    enterRawMode,
  };
}
