// Typed Trading Signal config editor (R2-04, GAP item 3). Replaces the raw
// TradingSignalConfig JSON textarea in BOTH the create panel and the revision
// composer: every documented §9.2 field is a typed control (enum → select,
// number → input, system ids → read-only provenance) and the payload is
// PRODUCED from the form (lib/tradingSignalForm.ts — the single source of
// truth). Raw JSON survives only as a closed "Advanced (raw payload)"
// disclosure gated on the /me server-truth admin projection (fail-closed:
// hidden until is_admin === true). Sync rule: while the Advanced raw override
// is OFF the disclosure renders the generated payload read-only; turning the
// override ON snapshots that payload into an editable textarea, disables the
// typed controls, and Validate/Save parse the raw text instead — "Back to
// typed form" re-seeds the controls from the raw JSON (parse failure keeps you
// in raw mode with the error shown).

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
  SIGNAL_DATA_QUALITY_MODES,
  SIGNAL_OHLCV_USE_MODES,
  SIGNAL_PRICE_SOURCES,
  SIGNAL_RESOLUTION_KINDS,
  SIGNAL_SOURCE_KINDS,
  signalFormToPayload,
  type FormErrors,
  type TradingSignalFormState,
} from "@/lib/tradingSignalForm";

export function TradingSignalConfigFields({
  state,
  errors,
  disabled,
  onChange,
}: {
  state: TradingSignalFormState;
  errors: FormErrors;
  disabled: boolean;
  onChange: (next: TradingSignalFormState) => void;
}) {
  const set = (patch: Partial<TradingSignalFormState>) => onChange({ ...state, ...patch });
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
          options={SIGNAL_SOURCE_KINDS}
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
          options={SIGNAL_RESOLUTION_KINDS}
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
          hint="Only for bar-aligned signals — event-based signals leave this blank."
          onChange={(baseTimeframe) => set({ baseTimeframe })}
        />
        <SelectField
          label="Data quality"
          value={state.dataQualityMode}
          options={SIGNAL_DATA_QUALITY_MODES}
          error={errors.dataQualityMode}
          disabled={disabled}
          onChange={(dataQualityMode) => set({ dataQualityMode })}
        />
        <TextField
          label="Source timezone"
          value={state.sourceTimezone}
          error={errors.sourceTimezone}
          disabled={disabled}
          hint="Normalization timezone is always UTC (row_available_time rule)."
          onChange={(sourceTimezone) => set({ sourceTimezone })}
        />
        <SelectField
          label="Price source"
          value={state.priceSource}
          options={SIGNAL_PRICE_SOURCES}
          error={errors.priceSource}
          disabled={disabled}
          onChange={(priceSource) => set({ priceSource })}
        />
        <SelectField
          label="OHLCV use"
          value={state.ohlcvUseMode}
          options={SIGNAL_OHLCV_USE_MODES}
          error={errors.ohlcvUseMode}
          disabled={disabled}
          onChange={(ohlcvUseMode) => set({ ohlcvUseMode })}
        />
        <TextField
          label="Independent initial capital (optional)"
          value={state.independentInitialCapital}
          error={errors.independentInitialCapital}
          disabled={disabled}
          placeholder="10000"
          onChange={(independentInitialCapital) => set({ independentInitialCapital })}
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
          label="Normalized event revision"
          value={state.binding.normalizedEventRevisionId}
        />
        {state.binding.mappingRevisionId !== "" ? (
          <ProvenanceRow label="Column-mapping hash" value={state.binding.mappingRevisionId} />
        ) : null}
      </div>
      <FieldError error={errors.binding} />
    </>
  );
}

// Full config editor body: typed fields + admin-gated Advanced raw disclosure.
// Used by the create panel and the revision composer (report- or head-seeded).
export function TradingSignalConfigEditor({
  state,
  errors,
  onChange,
  rawMode,
  rawText,
  rawError,
  onRawModeChange,
  onRawTextChange,
}: {
  state: TradingSignalFormState;
  errors: FormErrors;
  onChange: (next: TradingSignalFormState) => void;
  rawMode: boolean;
  rawText: string;
  rawError: string | null;
  onRawModeChange: (rawMode: boolean) => void;
  onRawTextChange: (text: string) => void;
}) {
  const me = useMe();
  // Fail-closed role gate (R2-09 pattern): the raw payload disclosure renders
  // only once /me proves is_admin — loading, error and non-admin all hide it.
  const isAdmin = me.data?.is_admin === true;
  const generated = JSON.stringify(signalFormToPayload(state), null, 2);
  return (
    <>
      <TradingSignalConfigFields
        state={state}
        errors={errors}
        disabled={rawMode}
        onChange={onChange}
      />
      {isAdmin ? (
        <details style={{ marginTop: 14 }}>
          <summary>Advanced (raw payload)</summary>
          <p className="cp-note" style={{ marginTop: 8 }}>
            {rawMode
              ? "Raw override ON — the JSON below is what will be sent; the typed fields are disabled until you return to the form."
              : "Generated from the typed form (read-only). Turn on the raw override to hand-edit the payload."}
          </p>
          <label className="cp-field cp-wide">
            <span>TradingSignalConfig payload</span>
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
