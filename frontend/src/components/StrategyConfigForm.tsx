import { useId, useState } from "react";

import { DatasetPicker } from "@/components/DatasetPicker";
import { InfoPanel } from "@/components/InfoPanel";
import {
  ENTRY_TIMING_OPTIONS,
  EXIT_TIMING_OPTIONS,
  FORMULA_TYPE_OPTIONS,
  LEVERAGE_MODE_OPTIONS,
  LIMIT_ORDER_TYPES,
  LIMIT_PRICE_RULE_OPTIONS,
  LIMIT_VALIDITY_OPTIONS,
  OPPOSITE_HEDGE_OPTIONS,
  ORDER_TYPE_OPTIONS,
  OVERLAPPING_SIGNAL_OPTIONS,
  PARTIAL_FILL_OPTIONS,
  SAME_DIRECTION_OPTIONS,
  SIGNAL_STRENGTH_OPTIONS,
  STOP_ACTIVATION_RULE_OPTIONS,
  STOP_EXIT_CONFLICT_OPTIONS,
  STOP_ORDER_TYPES,
  SIZING_METHOD_OPTIONS,
  SLIPPAGE_MODE_OPTIONS,
  STRATEGY_INFO_PANELS,
  type SelectOption,
  type StrategyFlatForm,
  TICK_POLICY_OPTIONS,
  UNFILLED_POLICY_OPTIONS,
  extractFlatSections,
  mergeFlatSections,
} from "@/lib/strategyForm";

// GAP-08 — the structured Strategy Details editor (doc 02 §5.2/§5.5/§5.6/§5.9).
// A non-expert form over the flat, package-picker-free sections of the
// StrategyConfig; the package-graph sections (Entry/Exit Logic, Scaling,
// Restrictions) remain in the retained Advanced (JSON) editor. Apply produces
// the FULL payload via mergeFlatSections (covered sections overlaid, every
// other key preserved) and hands it to the same PATCH the JSON editor uses. The
// form never validates strategy semantics — Validate / Save on the server are
// the sole authority. It seeds ONCE from the current draft (the parent remounts
// it via key={row_version} on every server head move) — never a live merge.

// ---------------------------------------------------------------------------
// Field primitives (label + optional * + optional ⓘ). The ⓘ lives OUTSIDE the
// <label> so clicking it never activates the control.
// ---------------------------------------------------------------------------

function FieldHead({
  id,
  label,
  required,
  panelKey,
}: {
  id: string;
  label: string;
  required?: boolean;
  panelKey?: keyof typeof STRATEGY_INFO_PANELS;
}) {
  return (
    <span className="field-head">
      <label htmlFor={id}>
        {label}
        {required ? <span aria-hidden="true"> *</span> : null}
      </label>
      {panelKey ? <InfoPanel panel={STRATEGY_INFO_PANELS[panelKey]} /> : null}
    </span>
  );
}

function TextField({
  label,
  value,
  onChange,
  required,
  panelKey,
  placeholder,
  wide,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
  panelKey?: keyof typeof STRATEGY_INFO_PANELS;
  placeholder?: string;
  wide?: boolean;
}) {
  const id = useId();
  return (
    <div className={`cp-field${wide ? " cp-wide" : ""}`}>
      <FieldHead id={id} label={label} required={required} panelKey={panelKey} />
      <input
        id={id}
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        spellCheck={false}
      />
    </div>
  );
}

function SelectField({
  label,
  value,
  onChange,
  options,
  required,
  panelKey,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
  required?: boolean;
  panelKey?: keyof typeof STRATEGY_INFO_PANELS;
  placeholder?: string;
}) {
  const id = useId();
  return (
    <div className="cp-field">
      <FieldHead id={id} label={label} required={required} panelKey={panelKey} />
      <select id={id} value={value} onChange={(event) => onChange(event.target.value)}>
        {placeholder !== undefined ? <option value="">{placeholder}</option> : null}
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}

function CheckboxField({
  label,
  checked,
  onChange,
  panelKey,
}: {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  panelKey?: keyof typeof STRATEGY_INFO_PANELS;
}) {
  return (
    <div className="cp-field cp-wide">
      <span className="field-head">
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={checked}
            onChange={(event) => onChange(event.target.checked)}
          />
          {label}
        </label>
        {panelKey ? <InfoPanel panel={STRATEGY_INFO_PANELS[panelKey]} /> : null}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// The structured form — split into independently-appliable, numbered section
// cards (doc 02 §3.1) so a caller can place each in its mockup-matching
// column (SETUP & DATA / RISK MANAGEMENT). Each card seeds its own local
// StrategyFlatForm slice from the SAME payload and Apply merges its edits
// back over the full payload via mergeFlatSections — sections another card
// hasn't touched round-trip unchanged, so applying card A never clobbers
// unsaved edits already applied from card B (each Apply is its own PATCH).
// ---------------------------------------------------------------------------

type FlatSetter<K extends keyof StrategyFlatForm> = (
  patch: Partial<StrategyFlatForm[K]>,
) => void;

function useFlatSection<K extends keyof StrategyFlatForm>(
  payload: Record<string, unknown>,
  key: K,
): [StrategyFlatForm[K], FlatSetter<K>, StrategyFlatForm] {
  const [form, setForm] = useState<StrategyFlatForm>(() => extractFlatSections(payload));
  const setSection: FlatSetter<K> = (patch) =>
    setForm((f) => ({ ...f, [key]: { ...f[key], ...patch } }));
  return [form[key], setSection, form];
}

// ---- 2. Data & Execution (§5.2) — SETUP & DATA column ----
export function DataExecutionCard({
  payload,
  pending,
  onApply,
}: {
  payload: Record<string, unknown>;
  pending: boolean;
  onApply: (payload: Record<string, unknown>) => void;
}) {
  const [d, setData, form] = useFlatSection(payload, "data");
  const showLimit = LIMIT_ORDER_TYPES.has(d.order_type);
  const showStop = STOP_ORDER_TYPES.has(d.order_type);
  const showSlippageValue = d.slippage_mode === "percentage_slippage";

  return (
    <div className="detail-card" aria-labelledby="strat-form-h">
      <h4 id="strat-form-h" className="detail-card-title">
        2. Data &amp; Execution
      </h4>
      <div className="cp-form strategy-form-grid">
        <TextField
          label="Market (instrument)"
          required
          value={d.instrument_id}
          onChange={(v) => setData({ instrument_id: v })}
          placeholder="e.g. BTCUSDT"
        />
        <TextField
          label="Initial capital"
          required
          value={d.initial_capital}
          onChange={(v) => setData({ initial_capital: v })}
          placeholder="e.g. 10000"
        />
        <DatasetPicker
          kind="market"
          label="Market data source"
          required
          value={{
            rootId: d.market_dataset_root_id,
            revisionId: d.market_dataset_revision_id,
            contentHash: d.market_dataset_content_hash,
          }}
          onChange={(ref) =>
            setData({
              market_dataset_root_id: ref.rootId,
              market_dataset_revision_id: ref.revisionId,
              market_dataset_content_hash: ref.contentHash,
            })
          }
        />
        <TextField
          label="Backtest range — start"
          required
          value={d.backtest_start}
          onChange={(v) => setData({ backtest_start: v })}
          placeholder="2020-01-01T00:00:00Z"
        />
        <TextField
          label="Backtest range — end"
          required
          value={d.backtest_end}
          onChange={(v) => setData({ backtest_end: v })}
          placeholder="2025-12-31T00:00:00Z"
        />
        <SelectField
          label="Entry execution"
          required
          value={d.entry_timing}
          onChange={(v) => setData({ entry_timing: v })}
          options={ENTRY_TIMING_OPTIONS}
          placeholder="Choose Entry Execution"
        />
        <SelectField
          label="Exit execution"
          required
          value={d.exit_timing}
          onChange={(v) => setData({ exit_timing: v })}
          options={EXIT_TIMING_OPTIONS}
          placeholder="Choose Exit Execution"
        />
        <SelectField
          label="Order type"
          value={d.order_type}
          onChange={(v) => setData({ order_type: v })}
          options={ORDER_TYPE_OPTIONS}
          panelKey="orderType"
        />
        <div className="cp-field" aria-hidden="true" />
        {showStop ? (
          <>
            <SelectField
              label="Stop activation rule"
              required
              value={d.stop_activation_rule}
              onChange={(v) => setData({ stop_activation_rule: v })}
              options={STOP_ACTIVATION_RULE_OPTIONS}
              placeholder="Choose activation rule"
            />
            <TextField
              label="Stop trigger offset"
              value={d.stop_trigger_offset}
              onChange={(v) => setData({ stop_trigger_offset: v })}
            />
          </>
        ) : null}
        {showLimit ? (
          <>
            <SelectField
              label="Limit price rule"
              required
              value={d.limit_price_rule}
              onChange={(v) => setData({ limit_price_rule: v })}
              options={LIMIT_PRICE_RULE_OPTIONS}
              placeholder="Choose price rule"
              panelKey="limitPriceRule"
            />
            <TextField
              label="Limit price offset"
              value={d.limit_price_offset}
              onChange={(v) => setData({ limit_price_offset: v })}
            />
            <SelectField
              label="Order validity"
              value={d.limit_validity}
              onChange={(v) => setData({ limit_validity: v })}
              options={LIMIT_VALIDITY_OPTIONS}
              panelKey="orderValidity"
            />
            <SelectField
              label="If not filled"
              required
              value={d.limit_unfilled_policy}
              onChange={(v) => setData({ limit_unfilled_policy: v })}
              options={UNFILLED_POLICY_OPTIONS}
              placeholder="Choose policy"
              panelKey="ifNotFilled"
            />
            <SelectField
              label="Partial fill"
              value={d.limit_partial_fill_policy}
              onChange={(v) => setData({ limit_partial_fill_policy: v })}
              options={PARTIAL_FILL_OPTIONS}
              panelKey="partialFill"
            />
            <div className="cp-field" aria-hidden="true" />
          </>
        ) : null}
        <TextField
          label="Commission"
          value={d.commission}
          onChange={(v) => setData({ commission: v })}
        />
        <TextField label="Spread" value={d.spread} onChange={(v) => setData({ spread: v })} />
        <SelectField
          label="Slippage model"
          value={d.slippage_mode}
          onChange={(v) => setData({ slippage_mode: v })}
          options={SLIPPAGE_MODE_OPTIONS}
        />
        {showSlippageValue ? (
          <TextField
            label="Slippage value"
            required
            value={d.slippage_value}
            onChange={(v) => setData({ slippage_value: v })}
          />
        ) : (
          <div className="cp-field" aria-hidden="true" />
        )}
        <SelectField
          label="Use tick data"
          value={d.tick_policy}
          onChange={(v) => setData({ tick_policy: v })}
          options={TICK_POLICY_OPTIONS}
          panelKey="useTickData"
        />
        <div className="cp-field" aria-hidden="true" />
        <CheckboxField
          label="Funding fee (use historical funding data)"
          checked={d.funding_enabled}
          onChange={(checked) => setData({ funding_enabled: checked })}
          panelKey="fundingFee"
        />
        {d.funding_enabled ? (
          <DatasetPicker
            kind="funding"
            label="Funding data source"
            panel={STRATEGY_INFO_PANELS.fundingSource}
            value={{
              rootId: d.funding_source_root_id,
              revisionId: d.funding_source_revision_id,
              contentHash: d.funding_source_content_hash,
            }}
            onChange={(ref) =>
              setData({
                funding_source_root_id: ref.rootId,
                funding_source_revision_id: ref.revisionId,
                funding_source_content_hash: ref.contentHash,
              })
            }
          />
        ) : null}
      </div>
      <div style={{ marginTop: 14 }}>
        <button
          type="button"
          className="btn"
          disabled={pending}
          onClick={() => onApply(mergeFlatSections(payload, form))}
        >
          {pending ? "Applying…" : "Apply Data & Execution changes"}
        </button>
      </div>
    </div>
  );
}

// ---- 5. Protection / Stop Logic (§5.5, percentage/trailing/absolute) — RISK MANAGEMENT column ----
export function ProtectionStopCard({
  payload,
  pending,
  onApply,
}: {
  payload: Record<string, unknown>;
  pending: boolean;
  onApply: (payload: Record<string, unknown>) => void;
}) {
  const [p, setProtection, form] = useFlatSection(payload, "protection");

  return (
    <div className="detail-card">
      <h4 className="detail-card-title">
        5. Protection / Stop Logic <InfoPanel panel={STRATEGY_INFO_PANELS.protectionStopLogic} />
        <InfoPanel panel={STRATEGY_INFO_PANELS.stopRules} />
      </h4>
      <p className="cp-note">
        Disabled stops are dropped from the saved revision. A revision with no active stop is
        allowed only in Research Only state; Ready Check surfaces a high-severity risk warning
        (doc 02 §5.5).
      </p>
      <div className="cp-form strategy-form-grid">
        <CheckboxField
          label="Percentage stop"
          checked={p.percentage_enabled}
          onChange={(checked) => setProtection({ percentage_enabled: checked })}
          panelKey="percentageStop"
        />
        {p.percentage_enabled ? (
          <TextField
            label="Stop distance %"
            required
            value={p.percentage_loss}
            onChange={(v) => setProtection({ percentage_loss: v })}
          />
        ) : null}
        <CheckboxField
          label="Trailing stop"
          checked={p.trailing_enabled}
          onChange={(checked) => setProtection({ trailing_enabled: checked })}
          panelKey="trailingStop"
        />
        {p.trailing_enabled ? (
          <>
            <TextField
              label="Trailing distance %"
              required
              value={p.trailing_trail}
              onChange={(v) => setProtection({ trailing_trail: v })}
            />
            <TextField
              label="Activate after profit % (profit lock)"
              value={p.trailing_lock_in}
              onChange={(v) => setProtection({ trailing_lock_in: v })}
            />
          </>
        ) : null}
        <CheckboxField
          label="Absolute price stop"
          checked={p.absolute_enabled}
          onChange={(checked) => setProtection({ absolute_enabled: checked })}
        />
        {p.absolute_enabled ? (
          <TextField
            label="Stop price"
            required
            value={p.absolute_price}
            onChange={(v) => setProtection({ absolute_price: v })}
          />
        ) : null}
      </div>
      <div style={{ marginTop: 14 }}>
        <button
          type="button"
          className="btn"
          disabled={pending}
          onClick={() => onApply(mergeFlatSections(payload, form))}
        >
          {pending ? "Applying…" : "Apply Protection / Stop changes"}
        </button>
      </div>
    </div>
  );
}

// ---- 6. Position Sizing (§5.6) — RISK MANAGEMENT column ----
export function PositionSizingCard({
  payload,
  pending,
  onApply,
}: {
  payload: Record<string, unknown>;
  pending: boolean;
  onApply: (payload: Record<string, unknown>) => void;
}) {
  const [s, setSizing, form] = useFlatSection(payload, "sizing");

  return (
    <div className="detail-card">
      <h4 className="detail-card-title">6. Position Sizing</h4>
      <p className="cp-note">
        Exactly one sizing method is active per revision — the server rejects a multi-method
        config with SIZING_METHOD_NOT_EXCLUSIVE (doc 02 §5.6).
      </p>
      <div className="cp-form strategy-form-grid">
        <SelectField
          label="Sizing method"
          value={s.method}
          onChange={(v) => setSizing({ method: v })}
          options={SIZING_METHOD_OPTIONS}
          panelKey={
            s.method === "base_position_size"
              ? "basePositionSize"
              : s.method === "risk_based_sizing"
                ? "riskPerTrade"
                : "customFormula"
          }
        />
        <div className="cp-field" aria-hidden="true" />
        {s.method === "base_position_size" ? (
          <TextField
            label="Base position size"
            required
            value={s.base_position_size}
            onChange={(v) => setSizing({ base_position_size: v })}
            panelKey="basePositionSize"
          />
        ) : null}
        {s.method === "risk_based_sizing" ? (
          <>
            <TextField
              label="Risk % per trade"
              required
              value={s.risk_percentage_per_trade}
              onChange={(v) => setSizing({ risk_percentage_per_trade: v })}
              panelKey="riskPerTrade"
            />
            <TextField
              label="Stop loss point"
              required
              value={s.risk_stop_loss_point}
              onChange={(v) => setSizing({ risk_stop_loss_point: v })}
            />
          </>
        ) : null}
        {s.method === "formula_based_sizing" ? (
          <SelectField
            label="Formula type"
            value={s.formula_type}
            onChange={(v) => setSizing({ formula_type: v })}
            options={FORMULA_TYPE_OPTIONS}
            panelKey="customFormula"
          />
        ) : null}
        <SelectField
          label="Signal strength adjustment"
          value={s.signal_strength_adjustment}
          onChange={(v) => setSizing({ signal_strength_adjustment: v })}
          options={SIGNAL_STRENGTH_OPTIONS}
          panelKey="signalStrengthSizing"
        />
        <SelectField
          label="Leverage mode"
          value={s.leverage_mode}
          onChange={(v) => setSizing({ leverage_mode: v })}
          options={LEVERAGE_MODE_OPTIONS}
          panelKey="leverageMode"
        />
        <TextField
          label="Min position size"
          value={s.min_position_size}
          onChange={(v) => setSizing({ min_position_size: v })}
        />
        <TextField
          label="Max position size"
          value={s.max_position_size}
          onChange={(v) => setSizing({ max_position_size: v })}
          panelKey="maxSinglePosition"
        />
      </div>
      {s.method === "formula_based_sizing" ? (
        <p className="cp-note">
          Formula parameters (e.g. Kelly inputs) are preserved from the Advanced (JSON) editor —
          this form edits the formula type only.
        </p>
      ) : null}
      <div style={{ marginTop: 14 }}>
        <button
          type="button"
          className="btn"
          disabled={pending}
          onClick={() => onApply(mergeFlatSections(payload, form))}
        >
          {pending ? "Applying…" : "Apply Position Sizing changes"}
        </button>
      </div>
    </div>
  );
}

// ---- 9. Conflict / Position Handling (§5.9) — RISK MANAGEMENT column ----
export function ConflictCard({
  payload,
  pending,
  onApply,
}: {
  payload: Record<string, unknown>;
  pending: boolean;
  onApply: (payload: Record<string, unknown>) => void;
}) {
  const [c, setConflict, form] = useFlatSection(payload, "conflict");

  return (
    <div className="detail-card">
      <h4 className="detail-card-title">
        9. Conflict / Position Handling <InfoPanel panel={STRATEGY_INFO_PANELS.stopExitConflict} />
        <InfoPanel panel={STRATEGY_INFO_PANELS.multipleStopsConflict} />
      </h4>
      <div className="cp-form strategy-form-grid">
        <SelectField
          label="Overlapping signal policy"
          value={c.overlapping_signal_policy}
          onChange={(v) => setConflict({ overlapping_signal_policy: v })}
          options={OVERLAPPING_SIGNAL_OPTIONS}
        />
        <SelectField
          label="Same-direction stacking"
          value={c.same_direction_stacking}
          onChange={(v) => setConflict({ same_direction_stacking: v })}
          options={SAME_DIRECTION_OPTIONS}
        />
        <SelectField
          label="Opposite-direction hedge"
          value={c.opposite_direction_hedge}
          onChange={(v) => setConflict({ opposite_direction_hedge: v })}
          options={OPPOSITE_HEDGE_OPTIONS}
        />
        <SelectField
          label="Stop + Exit conflict"
          value={c.stop_exit_conflict}
          onChange={(v) => setConflict({ stop_exit_conflict: v })}
          options={STOP_EXIT_CONFLICT_OPTIONS}
        />
        <CheckboxField
          label="Exit on opposite signal"
          checked={c.exit_on_opposite_signal}
          onChange={(checked) => setConflict({ exit_on_opposite_signal: checked })}
        />
      </div>
      <div style={{ marginTop: 14 }}>
        <button
          type="button"
          className="btn btn-primary"
          disabled={pending}
          onClick={() => onApply(mergeFlatSections(payload, form))}
        >
          {pending ? "Applying…" : "Apply Conflict / Position Handling changes"}
        </button>
      </div>
    </div>
  );
}
