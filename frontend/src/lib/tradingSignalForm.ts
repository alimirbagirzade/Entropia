// Typed Trading Signal config form model (R2-04, GAP item 3/9). Pure state ↔
// payload mapping + client-side validation MIRRORING the backend authority
// (domain/trading_signal/config.py + compiler.py — enums, lengths and the
// cross-field event-model/OHLCV rules, read empirically). The server compiler
// remains the sole authority: these checks only surface the same blockers next
// to the fields before a request is attempted. Payload emission preserves the
// wire shape the JSON-textarea era sent (lib/tradingSignal.ts template) —
// optional subsections carry explicit nulls, mapping_revision_id is emitted
// only when present, so OCC/Idempotency behaviour is untouched.

import { useState } from "react";

export const SIGNAL_SOURCE_KINDS = ["file", "integration"] as const;
export const SIGNAL_RESOLUTION_KINDS = [
  "event_based",
  "same_as_market_dataset",
  "bar_timeframe",
] as const;
export const SIGNAL_DATA_QUALITY_MODES = [
  "signal_events_only",
  "signal_events_with_source_ohlcv",
  "signal_events_with_market_context",
] as const;
export const SIGNAL_PRICE_SOURCES = [
  "suggested_signal_price",
  "ohlcv_close_if_needed",
  "ohlcv_intrabar_if_available",
] as const;
export const SIGNAL_OHLCV_USE_MODES = [
  "use_if_supplied_and_needed",
  "ignore",
  "use_for_price_context_and_validation",
] as const;

const NAME_MAX = 160;
const PROVIDER_MAX = 200;
const SYMBOL_MAX = 64;

// Read-only import-binding provenance (system-carried — never user-typed).
export interface SignalBinding {
  sourceAssetId: string;
  normalizedEventRevisionId: string;
  mappingRevisionId: string;
}

export interface TradingSignalFormState {
  displayName: string;
  providerName: string;
  sourceKind: string;
  instrumentId: string;
  displaySymbol: string;
  resolutionKind: string;
  baseTimeframe: string;
  rationaleFamilyId: string;
  dataQualityMode: string;
  sourceTimezone: string;
  priceSource: string;
  priceFallback: string;
  ohlcvUseMode: string;
  independentInitialCapital: string;
  binding: SignalBinding;
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

// Tolerant payload → form seeding (template, revision head, or raw override).
export function signalFormFromPayload(
  payload: Record<string, unknown>,
): TradingSignalFormState {
  const identity = section(payload, "identity");
  const source = section(payload, "source");
  const scope = section(payload, "instrument_scope");
  const eventModel = section(payload, "event_model");
  const classification = section(payload, "classification");
  const dataQuality = section(payload, "data_quality");
  const timePolicy = section(payload, "time_policy");
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
    resolutionKind: str(eventModel.resolution_kind) || "event_based",
    baseTimeframe: str(eventModel.base_timeframe),
    rationaleFamilyId: str(classification.rationale_family_id),
    dataQualityMode: str(dataQuality.mode) || "signal_events_only",
    sourceTimezone: str(timePolicy.source_timezone) || "UTC",
    priceSource: str(pricePolicy.source) || "suggested_signal_price",
    priceFallback: str(pricePolicy.fallback),
    ohlcvUseMode: str(ohlcvPolicy.use_mode) || "ignore",
    independentInitialCapital:
      typeof capitalValue === "number" ? String(capitalValue) : str(capitalValue),
    binding: {
      sourceAssetId: str(binding.source_asset_id),
      normalizedEventRevisionId: str(binding.normalized_event_revision_id),
      mappingRevisionId: str(binding.mapping_revision_id),
    },
  };
}

// Form → §9.2 wire payload. The typed form is the single source of truth; the
// Advanced raw disclosure renders THIS output (R2-04 sync rule).
export function signalFormToPayload(
  state: TradingSignalFormState,
): Record<string, unknown> {
  const importBinding: Record<string, unknown> = {
    source_asset_id: state.binding.sourceAssetId,
    normalized_event_revision_id: state.binding.normalizedEventRevisionId,
  };
  if (state.binding.mappingRevisionId !== "") {
    importBinding.mapping_revision_id = state.binding.mappingRevisionId;
  }
  return {
    kind: "trading_signal",
    identity: { display_name: state.displayName.trim() },
    source: { provider_name: state.providerName.trim(), source_kind: state.sourceKind },
    instrument_scope: {
      instrument_id: state.instrumentId.trim(),
      display_symbol: state.displaySymbol.trim(),
    },
    event_model: {
      resolution_kind: state.resolutionKind,
      ...(state.baseTimeframe.trim() !== ""
        ? { base_timeframe: state.baseTimeframe.trim() }
        : {}),
    },
    ...(state.rationaleFamilyId.trim() !== ""
      ? { classification: { rationale_family_id: state.rationaleFamilyId.trim() } }
      : {}),
    data_quality: { mode: state.dataQualityMode },
    time_policy: {
      source_timezone: state.sourceTimezone.trim(),
      normalization_timezone: "UTC",
      availability_rule: "row_available_time",
    },
    price_policy: {
      source: state.priceSource,
      ...(state.priceFallback.trim() !== "" ? { fallback: state.priceFallback.trim() } : {}),
    },
    ohlcv_policy: { use_mode: state.ohlcvUseMode },
    ...(state.independentInitialCapital.trim() !== ""
      ? { capital: { independent_initial_capital: state.independentInitialCapital.trim() } }
      : {}),
    import_binding: importBinding,
  };
}

// Client-side mirror of config.py field rules + compiler.py cross-field rules.
// Keyed by stable field ids the form controls use for inline display.
export function validateSignalForm(state: TradingSignalFormState): FormErrors {
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
    errors.baseTimeframe = "Event-based signals carry no base timeframe.";
  }
  if (state.resolutionKind === "bar_timeframe" && state.baseTimeframe.trim() === "") {
    errors.baseTimeframe = "A bar-aligned signal requires a base timeframe.";
  }
  if (state.priceSource === "ohlcv_intrabar_if_available" && state.ohlcvUseMode === "ignore") {
    errors.ohlcvUseMode = "Intrabar price policy cannot ignore OHLCV context.";
  }
  if (
    state.dataQualityMode === "signal_events_only" &&
    state.ohlcvUseMode === "use_for_price_context_and_validation"
  ) {
    errors.ohlcvUseMode = "Signal-events-only data quality supplies no source OHLCV to use.";
  }
  const capital = state.independentInitialCapital.trim();
  if (capital !== "" && (!Number.isFinite(Number(capital)) || Number(capital) <= 0)) {
    errors.independentInitialCapital =
      "Independent initial capital must be a positive number.";
  }
  if (
    state.binding.sourceAssetId === "" ||
    state.binding.normalizedEventRevisionId === ""
  ) {
    errors.binding =
      "Complete a succeeded import first — the source binding is carried automatically.";
  }
  return errors;
}

// Shared submit-side helpers so the create/revision panels stay thin.
export function useSignalConfigEditorState(initialPayload: Record<string, unknown>) {
  const [state, setState] = useState<TradingSignalFormState>(() =>
    signalFormFromPayload(initialPayload),
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

  // Returns the payload to send, or null when validation blocks the send.
  const buildPayload = (): Record<string, unknown> | null => {
    setValidNote(null);
    if (rawMode) {
      const parsed = parseRaw();
      return parsed;
    }
    const nextErrors = validateSignalForm(state);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return null;
    return signalFormToPayload(state);
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
    const nextErrors = validateSignalForm(state);
    setErrors(nextErrors);
    setValidNote(
      Object.keys(nextErrors).length === 0
        ? "No blockers found (client-side check — the server compiler is authoritative)."
        : "Fix the highlighted fields.",
    );
  };

  const reset = (payload: Record<string, unknown>) => {
    setState(signalFormFromPayload(payload));
    setErrors({});
    setRawMode(false);
    setRawText("");
    setRawError(null);
    setValidNote(null);
  };

  const enterRawMode = (on: boolean) => {
    setRawMode(on);
    if (!on) {
      // Back to typed form: re-seed the controls from the raw JSON when it
      // parses; a broken document keeps raw mode with the error shown.
      try {
        const parsed: unknown = JSON.parse(rawText);
        if (parsed !== null && typeof parsed === "object" && !Array.isArray(parsed)) {
          setState(signalFormFromPayload(parsed as Record<string, unknown>));
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
