// Typed Trade Log config editor (R2-04, GAP item 3) — twin of
// TradingSignalConfigForm.tsx. Twin diffs preserved verbatim: a single
// time_model group (not time_policy + event_model), content_profile data
// quality, ledger price source with the optional approved-market-data ref,
// currency-carrying capital, and the record-batch import binding. The
// revision-level available_time stays null server-side (doc 05 §10.4) so it is
// deliberately NOT a form field. Same Advanced raw-payload sync rule as the
// Trading Signal editor (admin-gated, fail-closed on /me).

import {
  FieldError,
  ProvenanceRow,
  SelectField,
  TextField,
} from "@/components/ConfigFormControls";
import { InstrumentPicker } from "@/components/InstrumentPicker";
import { RationaleFamilyPicker } from "@/components/RationaleFamilyPicker";
import { useMe } from "@/lib/hooks";
import {
  TRADE_LOG_CONTENT_PROFILES,
  TRADE_LOG_OHLCV_USE_MODES,
  TRADE_LOG_PRICE_SOURCES,
  TRADE_LOG_RESOLUTION_KINDS,
  TRADE_LOG_SOURCE_KINDS,
  tradeLogFormToPayload,
  type FormErrors,
  type TradeLogFormState,
} from "@/lib/tradeLogForm";

export function TradeLogConfigFields({
  state,
  errors,
  disabled,
  onChange,
}: {
  state: TradeLogFormState;
  errors: FormErrors;
  disabled: boolean;
  onChange: (next: TradeLogFormState) => void;
}) {
  const set = (patch: Partial<TradeLogFormState>) => onChange({ ...state, ...patch });
  return (
    <>
      <div className="strategy-form-grid">
        <TextField
          label="Display name"
          value={state.displayName}
          error={errors.displayName}
          disabled={disabled}
          onChange={(displayName) => set({ displayName })}
        />
        <TextField
          label="Provider name"
          value={state.providerName}
          error={errors.providerName}
          disabled={disabled}
          onChange={(providerName) => set({ providerName })}
        />
        <SelectField
          label="Source kind"
          value={state.sourceKind}
          options={TRADE_LOG_SOURCE_KINDS}
          error={errors.sourceKind}
          disabled={disabled}
          onChange={(sourceKind) => set({ sourceKind })}
        />
        <InstrumentPicker
          label="Instrument"
          required
          value={state.instrumentId}
          error={errors.instrumentId}
          disabled={disabled}
          onChange={(instrumentId) => set({ instrumentId })}
        />
        <TextField
          label="Display symbol"
          value={state.displaySymbol}
          error={errors.displaySymbol}
          disabled={disabled}
          onChange={(displaySymbol) => set({ displaySymbol })}
        />
        <SelectField
          label="Resolution kind"
          value={state.resolutionKind}
          options={TRADE_LOG_RESOLUTION_KINDS}
          error={errors.resolutionKind}
          disabled={disabled}
          onChange={(resolutionKind) => set({ resolutionKind })}
        />
        <TextField
          label="Base timeframe"
          value={state.baseTimeframe}
          error={errors.baseTimeframe}
          disabled={disabled}
          placeholder="1h"
          hint="Only for bar-aligned trade logs — event-based records leave this blank."
          onChange={(baseTimeframe) => set({ baseTimeframe })}
        />
        <SelectField
          label="Data quality (content profile)"
          value={state.contentProfile}
          options={TRADE_LOG_CONTENT_PROFILES}
          error={errors.contentProfile}
          disabled={disabled}
          onChange={(contentProfile) => set({ contentProfile })}
        />
        <TextField
          label="Source timezone"
          value={state.sourceTimezone}
          error={errors.sourceTimezone}
          disabled={disabled}
          hint="Normalization timezone is always UTC."
          onChange={(sourceTimezone) => set({ sourceTimezone })}
        />
        <SelectField
          label="Price source"
          value={state.priceSource}
          options={TRADE_LOG_PRICE_SOURCES}
          error={errors.priceSource}
          disabled={disabled}
          onChange={(priceSource) => set({ priceSource })}
        />
        <SelectField
          label="OHLCV use"
          value={state.ohlcvUseMode}
          options={TRADE_LOG_OHLCV_USE_MODES}
          error={errors.ohlcvUseMode}
          disabled={disabled}
          onChange={(ohlcvUseMode) => set({ ohlcvUseMode })}
        />
        <TextField
          label="Approved market data revision (optional)"
          value={state.approvedMarketDataRevisionRef}
          error={errors.approvedMarketDataRevisionRef}
          disabled={disabled}
          onChange={(approvedMarketDataRevisionRef) => set({ approvedMarketDataRevisionRef })}
        />
        <TextField
          label="Independent initial capital (optional)"
          value={state.independentInitialCapital}
          error={errors.independentInitialCapital}
          disabled={disabled}
          placeholder="10000"
          onChange={(independentInitialCapital) => set({ independentInitialCapital })}
        />
        <TextField
          label="Currency"
          value={state.currency}
          error={errors.currency}
          disabled={disabled}
          onChange={(currency) => set({ currency })}
        />
        <RationaleFamilyPicker
          label="Rationale family (optional)"
          value={state.rationaleFamilyId}
          error={errors.rationaleFamilyId}
          disabled={disabled}
          onChange={(rationaleFamilyId) => set({ rationaleFamilyId })}
        />
      </div>

      <h4 className="detail-card-title" style={{ marginTop: 14, marginBottom: 6 }}>
        Source binding (system-carried)
      </h4>
      <div className="strategy-form-grid">
        <ProvenanceRow label="Source asset" value={state.binding.sourceAssetId} />
        <ProvenanceRow
          label="Record batch revision"
          value={state.binding.recordBatchRevisionId}
        />
        {state.binding.mappingRevisionId !== "" ? (
          <ProvenanceRow label="Column-mapping hash" value={state.binding.mappingRevisionId} />
        ) : null}
      </div>
      <FieldError error={errors.binding} />
    </>
  );
}

export function TradeLogConfigEditor({
  state,
  errors,
  onChange,
  rawMode,
  rawText,
  rawError,
  onRawModeChange,
  onRawTextChange,
}: {
  state: TradeLogFormState;
  errors: FormErrors;
  onChange: (next: TradeLogFormState) => void;
  rawMode: boolean;
  rawText: string;
  rawError: string | null;
  onRawModeChange: (rawMode: boolean) => void;
  onRawTextChange: (text: string) => void;
}) {
  const me = useMe();
  const isAdmin = me.data?.is_admin === true;
  const generated = JSON.stringify(tradeLogFormToPayload(state), null, 2);
  return (
    <>
      <TradeLogConfigFields state={state} errors={errors} disabled={rawMode} onChange={onChange} />
      {isAdmin ? (
        <details style={{ marginTop: 14 }}>
          <summary>Advanced (raw payload)</summary>
          <p className="cp-note" style={{ marginTop: 8 }}>
            {rawMode
              ? "Raw override ON — the JSON below is what will be sent; the typed fields are disabled until you return to the form."
              : "Generated from the typed form (read-only). Turn on the raw override to hand-edit the payload."}
          </p>
          <label className="cp-field cp-wide">
            <span>TradeLogConfig payload</span>
            <textarea
              rows={16}
              value={rawMode ? rawText : generated}
              readOnly={!rawMode}
              spellCheck={false}
              onChange={(event) => onRawTextChange(event.target.value)}
            />
          </label>
          {rawError !== null ? (
            <p role="alert" style={{ color: "var(--down)", marginBottom: 0 }}>
              {rawError}
            </p>
          ) : null}
          <button
            type="button"
            className="btn"
            style={{ marginTop: 8 }}
            onClick={() => {
              if (!rawMode) onRawTextChange(generated);
              onRawModeChange(!rawMode);
            }}
          >
            {rawMode ? "Back to typed form" : "Edit raw payload"}
          </button>
        </details>
      ) : null}
    </>
  );
}
