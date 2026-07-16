import { useId, useState } from "react";

import { InfoPanel } from "@/components/InfoPanel";
import { PackagePicker } from "@/components/PackagePicker";
import type { InfoPanelContent } from "@/lib/strategyForm";
import {
  ADD_SIZE_OPTIONS,
  APPLIES_TO_OPTIONS,
  BLOCK_DIRECTION_OPTIONS,
  BLOCK_TIMEFRAME_OPTIONS,
  CONDITION_BLOCK_RULE_OPTIONS,
  CONDITION_MIN_SUPPORTING_RULE,
  CONDITION_REQUIRING_TRIGGERS,
  CONDITION_VALIDITY_OPTIONS,
  DIRECTION_MODE_OPTIONS,
  FILTER_TYPE_OPTIONS,
  FILTER_TYPE_PANEL_KEY,
  INDICATOR_VALIDITY_OPTIONS,
  PARTIAL_AFTERMATH_OPTIONS,
  REQUIREMENT_OPTIONS,
  RESTRICTION_RULE_OPTIONS,
  SCALING_METHOD_OPTIONS,
  SIGNAL_MIN_SUPPORTING_RULE,
  SIGNAL_RULE_OPTIONS,
  STOP_CONFLICT_RESOLUTION_OPTIONS,
  STOP_TRIGGER_REQUIREMENT_OPTIONS,
  STRATEGY_GRAPH_PANELS,
  TRIGGER_SOURCE_OPTIONS,
  type ConditionBlockForm,
  type IndicatorBlockForm,
  type RestrictionFilterForm,
  type RestrictionsForm,
  type ScalingForm,
  type SelectOption,
  type StrategyGraphForm as GraphFormState,
  extractGraphSections,
  firstInvalidFilterConfig,
  mergeGraphSections,
  newBlock,
  newCondition,
  newFilter,
} from "@/lib/strategyGraph";

// R6 / GAP-08 — the structured editor for the package-graph decision sections
// (doc 02 §5.3 Position Entry Logic, §5.4 Position Exit Logic). These are the
// sections that PIN indicator / condition packages; before R6 they lived only
// in the Advanced (JSON) editor. Apply produces the FULL payload via
// mergeGraphSections (the two covered sections overlaid, every other key —
// and every uncovered per-block advanced field — preserved) and hands it to
// the same PATCH the JSON editor uses. The form never validates strategy
// semantics — Validate / Save on the server are the sole authority. It seeds
// ONCE from the current draft (the parent remounts it via key={row_version}).

// ---------------------------------------------------------------------------
// Field primitives (panel is an InfoPanelContent object, decoupled from the
// flat-form panelKey record).
// ---------------------------------------------------------------------------

function TextField({
  label,
  value,
  onChange,
  panel,
  placeholder,
  required,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  panel?: InfoPanelContent;
  placeholder?: string;
  required?: boolean;
}) {
  const id = useId();
  return (
    <div className="cp-field">
      <span className="field-head">
        <label htmlFor={id}>
          {label}
          {required ? <span aria-hidden="true"> *</span> : null}
        </label>
        {panel ? <InfoPanel panel={panel} /> : null}
      </span>
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
  panel,
  placeholder,
  required,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
  panel?: InfoPanelContent;
  placeholder?: string;
  required?: boolean;
}) {
  const id = useId();
  return (
    <div className="cp-field">
      <span className="field-head">
        <label htmlFor={id}>
          {label}
          {required ? <span aria-hidden="true"> *</span> : null}
        </label>
        {panel ? <InfoPanel panel={panel} /> : null}
      </span>
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
  panel,
}: {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  panel?: InfoPanelContent;
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
        {panel ? <InfoPanel panel={panel} /> : null}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Per-scope panel selection (entry vs exit share the block structure but carry
// their own ⓘ text in doc 02 §6).
// ---------------------------------------------------------------------------

type Scope = "entry" | "exit" | "stop";

const P = STRATEGY_GRAPH_PANELS;

function blockPanels(scope: Scope) {
  return scope === "entry"
    ? {
        block: P.entryIndicatorBlock,
        requirement: P.indicatorRequirement,
        conditionBlock: P.entryConditionBlock,
        conditionRequirement: P.conditionRequirement,
        conditionValidity: P.conditionValidity,
      }
    : {
        block: P.exitIndicatorBlock,
        requirement: P.exitRequirement,
        conditionBlock: P.exitConditionBlock,
        conditionRequirement: P.exitConditionRequirement,
        conditionValidity: P.exitConditionValidity,
      };
}

// ---------------------------------------------------------------------------
// Condition block editor
// ---------------------------------------------------------------------------

function ConditionEditor({
  scope,
  condition,
  index,
  onChange,
  onRemove,
}: {
  scope: Scope;
  condition: ConditionBlockForm;
  index: number;
  onChange: (patch: Partial<ConditionBlockForm>) => void;
  onRemove: () => void;
}) {
  const panels = blockPanels(scope);
  return (
    <div className="graph-condition">
      <div className="graph-block-head">
        <span className="field-head">
          <strong>Condition Block {index + 1}</strong>
          <InfoPanel panel={panels.conditionBlock} />
        </span>
        <button type="button" className="btn" onClick={onRemove} aria-label={`Remove condition block ${index + 1}`}>
          Remove
        </button>
      </div>
      <div className="cp-form strategy-form-grid">
        <PackagePicker
          kind="condition"
          label="Condition package"
          value={condition.package_ref}
          onChange={(ref) => onChange({ package_ref: ref })}
        />
        <SelectField
          label="Requirement"
          required
          value={condition.requirement}
          onChange={(v) => onChange({ requirement: v })}
          options={REQUIREMENT_OPTIONS}
          placeholder="Choose requirement"
          panel={panels.conditionRequirement}
        />
        <SelectField
          label="Validity"
          value={condition.validity}
          onChange={(v) => onChange({ validity: v })}
          options={CONDITION_VALIDITY_OPTIONS}
          panel={panels.conditionValidity}
        />
        <CheckboxField
          label="Enabled"
          checked={condition.enabled}
          onChange={(checked) => onChange({ enabled: checked })}
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Indicator block editor (entry + exit)
// ---------------------------------------------------------------------------

function IndicatorBlockEditor({
  scope,
  block,
  index,
  total,
  onChange,
  onRemove,
  onMove,
}: {
  scope: Scope;
  block: IndicatorBlockForm;
  index: number;
  total: number;
  onChange: (patch: Partial<IndicatorBlockForm>) => void;
  onRemove: () => void;
  onMove: (direction: -1 | 1) => void;
}) {
  const panels = blockPanels(scope);
  const showConditionMin = block.condition_block_rule === CONDITION_MIN_SUPPORTING_RULE;
  const needsCondition =
    CONDITION_REQUIRING_TRIGGERS.has(block.trigger_source) && block.conditions.length === 0;

  const updateCondition = (i: number, patch: Partial<ConditionBlockForm>) =>
    onChange({
      conditions: block.conditions.map((c, idx) => (idx === i ? { ...c, ...patch } : c)),
    });
  const removeCondition = (i: number) =>
    onChange({ conditions: block.conditions.filter((_, idx) => idx !== i) });
  const addCondition = () => onChange({ conditions: [...block.conditions, newCondition()] });

  return (
    <div className="graph-block">
      <div className="graph-block-head">
        <span className="field-head">
          <strong>Indicator Block {index + 1}</strong>
          <InfoPanel panel={panels.block} />
        </span>
        <div className="graph-block-actions">
          <button
            type="button"
            className="btn"
            disabled={index === 0}
            onClick={() => onMove(-1)}
            aria-label={`Move indicator block ${index + 1} up`}
          >
            ↑
          </button>
          <button
            type="button"
            className="btn"
            disabled={index === total - 1}
            onClick={() => onMove(1)}
            aria-label={`Move indicator block ${index + 1} down`}
          >
            ↓
          </button>
          <button
            type="button"
            className="btn"
            onClick={onRemove}
            aria-label={`Remove indicator block ${index + 1}`}
          >
            Remove
          </button>
        </div>
      </div>
      <div className="cp-form strategy-form-grid">
        <PackagePicker
          kind="indicator"
          label="Indicator package"
          value={block.package_ref}
          onChange={(ref) => onChange({ package_ref: ref })}
        />
        <SelectField
          label="Trigger source"
          required
          value={block.trigger_source}
          onChange={(v) => onChange({ trigger_source: v })}
          options={TRIGGER_SOURCE_OPTIONS}
          placeholder="Choose trigger source"
        />
        <SelectField
          label="Direction"
          value={block.direction}
          onChange={(v) => onChange({ direction: v })}
          options={BLOCK_DIRECTION_OPTIONS}
        />
        <SelectField
          label="Timeframe"
          value={block.timeframe}
          onChange={(v) => onChange({ timeframe: v })}
          options={BLOCK_TIMEFRAME_OPTIONS}
        />
        <SelectField
          label="Validity"
          value={block.validity}
          onChange={(v) => onChange({ validity: v })}
          options={INDICATOR_VALIDITY_OPTIONS}
          panel={P.indicatorValidity}
        />
        <SelectField
          label="Requirement"
          required
          value={block.requirement}
          onChange={(v) => onChange({ requirement: v })}
          options={REQUIREMENT_OPTIONS}
          placeholder="Choose requirement"
          panel={panels.requirement}
        />
        <SelectField
          label="Condition block rule"
          value={block.condition_block_rule}
          onChange={(v) => onChange({ condition_block_rule: v })}
          options={CONDITION_BLOCK_RULE_OPTIONS}
          placeholder="None"
          panel={P.conditionRule}
        />
        {showConditionMin ? (
          <TextField
            label="Min. supporting condition blocks"
            value={block.min_supporting_condition_count}
            onChange={(v) => onChange({ min_supporting_condition_count: v })}
            placeholder="e.g. 1"
            panel={P.entryMinSupportingConditionCount}
          />
        ) : (
          <div className="cp-field" aria-hidden="true" />
        )}
        <CheckboxField
          label="Enabled"
          checked={block.enabled}
          onChange={(checked) => onChange({ enabled: checked })}
        />
      </div>

      {needsCondition ? (
        <p className="cp-note">
          This trigger source requires at least one active, compatible Condition Block (doc 02
          §5.3) — the server rejects a save without one.
        </p>
      ) : null}

      <div className="graph-conditions">
        {block.conditions.map((condition, i) => (
          <ConditionEditor
            key={condition.key}
            scope={scope}
            condition={condition}
            index={i}
            onChange={(patch) => updateCondition(i, patch)}
            onRemove={() => removeCondition(i)}
          />
        ))}
        <button type="button" className="btn" onClick={addCondition}>
          + Add Condition Block
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Block-list editor (shared by entry + exit)
// ---------------------------------------------------------------------------

function BlockList({
  scope,
  blocks,
  onChange,
}: {
  scope: Scope;
  blocks: IndicatorBlockForm[];
  onChange: (blocks: IndicatorBlockForm[]) => void;
}) {
  const update = (i: number, patch: Partial<IndicatorBlockForm>) =>
    onChange(blocks.map((b, idx) => (idx === i ? { ...b, ...patch } : b)));
  const remove = (i: number) => onChange(blocks.filter((_, idx) => idx !== i));
  const move = (i: number, direction: -1 | 1) => {
    const j = i + direction;
    if (j < 0 || j >= blocks.length) return;
    const next = [...blocks];
    [next[i], next[j]] = [next[j], next[i]];
    onChange(next);
  };
  const add = () => onChange([...blocks, newBlock()]);

  return (
    <>
      {blocks.map((block, i) => (
        <IndicatorBlockEditor
          key={block.key}
          scope={scope}
          block={block}
          index={i}
          total={blocks.length}
          onChange={(patch) => update(i, patch)}
          onRemove={() => remove(i)}
          onMove={(direction) => move(i, direction)}
        />
      ))}
      <button type="button" className="btn" onClick={add}>
        + Add Indicator Block
      </button>
    </>
  );
}

// ---------------------------------------------------------------------------
// Scaling Logic (§5.7)
// ---------------------------------------------------------------------------

function ScalingSection({
  scaling,
  onChange,
}: {
  scaling: ScalingForm;
  onChange: (patch: Partial<ScalingForm>) => void;
}) {
  return (
    <>
      <h4 className="detail-card-title">
        7. Scaling Logic <InfoPanel panel={P.scalingLogic} />
      </h4>
      <p className="cp-note">
        Scaling adds same-direction layers to an open position (doc 02 §5.7) — never a reverse
        layer. A disabled scaling section is collapsed to none on save.
      </p>
      <div className="cp-form strategy-form-grid">
        <CheckboxField
          label="Enable scaling"
          checked={scaling.enabled}
          onChange={(v) => onChange({ enabled: v })}
        />
        <SelectField
          label="Scaling timeframe"
          value={scaling.timeframe}
          onChange={(v) => onChange({ timeframe: v })}
          options={BLOCK_TIMEFRAME_OPTIONS}
          panel={P.scalingTimeframeStructure}
        />
        <SelectField
          label="Additional layer method"
          value={scaling.method}
          onChange={(v) => onChange({ method: v })}
          options={SCALING_METHOD_OPTIONS}
          placeholder="None"
          panel={P.additionalLayerMethod}
        />
        <div className="cp-field" aria-hidden="true" />
      </div>
      {scaling.method === "price_distance_scaling" ? (
        <div className="cp-form strategy-form-grid">
          <TextField
            label="Retracement distance %"
            required
            value={scaling.price.retracement_distance}
            onChange={(v) => onChange({ price: { ...scaling.price, retracement_distance: v } })}
            panel={P.priceDistanceScaling}
          />
          <TextField
            label="Layers"
            required
            value={scaling.price.layers}
            onChange={(v) => onChange({ price: { ...scaling.price, layers: v } })}
            placeholder="e.g. 3"
          />
        </div>
      ) : null}
      {scaling.method === "logic_based_scaling" ? (
        <>
          <p className="cp-note">
            <InfoPanel panel={P.logicBasedScaling} /> Layers are added when these indicator blocks
            confirm.
          </p>
          <BlockList
            scope="entry"
            blocks={scaling.logic_blocks}
            onChange={(blocks) => onChange({ logic_blocks: blocks })}
          />
        </>
      ) : null}
      <div className="cp-form strategy-form-grid">
        <SelectField
          label="Add size per scale"
          value={scaling.add_size}
          onChange={(v) => onChange({ add_size: v })}
          options={ADD_SIZE_OPTIONS}
          panel={P.addSizePerScale}
        />
        <TextField
          label="Add size value"
          value={scaling.add_size_value}
          onChange={(v) => onChange({ add_size_value: v })}
          placeholder="e.g. 50"
        />
        <TextField
          label="Max scaling layers"
          value={scaling.limits.max_scaling_layers}
          onChange={(v) => onChange({ limits: { ...scaling.limits, max_scaling_layers: v } })}
          panel={P.scalingLimits}
        />
        <TextField
          label="Max total position size"
          value={scaling.limits.max_total_position_size}
          onChange={(v) => onChange({ limits: { ...scaling.limits, max_total_position_size: v } })}
        />
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Restrictions / Filters (§5.8)
// ---------------------------------------------------------------------------

function FilterConfigField({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  const id = useId();
  return (
    <div className="cp-field cp-wide">
      <label htmlFor={id}>Config (JSON — type-specific)</label>
      <textarea
        id={id}
        rows={3}
        value={value}
        placeholder={'{ "threshold": 0.5 }'}
        onChange={(event) => onChange(event.target.value)}
        spellCheck={false}
      />
    </div>
  );
}

function RestrictionsSection({
  restrictions,
  onChange,
}: {
  restrictions: RestrictionsForm;
  onChange: (patch: Partial<RestrictionsForm>) => void;
}) {
  const updateFilter = (i: number, patch: Partial<RestrictionFilterForm>) =>
    onChange({
      filters: restrictions.filters.map((f, idx) => (idx === i ? { ...f, ...patch } : f)),
    });
  const removeFilter = (i: number) =>
    onChange({ filters: restrictions.filters.filter((_, idx) => idx !== i) });
  const addFilter = () => onChange({ filters: [...restrictions.filters, newFilter()] });

  return (
    <>
      <h4 className="detail-card-title">
        8. Restrictions / Filters <InfoPanel panel={P.restrictionRule} />
      </h4>
      <p className="cp-note">
        Filters block a new entry even when the signal is valid (doc 02 §5.8). Disabled filters are
        dropped from the saved revision. Each filter&apos;s typed config is edited as JSON — the V1
        backend config is an untyped dict.
      </p>
      <div className="cp-form strategy-form-grid">
        <SelectField
          label="Restriction rule"
          value={restrictions.rule}
          onChange={(v) => onChange({ rule: v })}
          options={RESTRICTION_RULE_OPTIONS}
          panel={P.restrictionRule}
        />
        <div className="cp-field" aria-hidden="true" />
      </div>
      {restrictions.filters.map((filter, i) => {
        const panelKey = FILTER_TYPE_PANEL_KEY[filter.filter_type];
        const panel = panelKey ? P[panelKey] : undefined;
        return (
          <div key={filter.key} className="graph-condition">
            <div className="graph-block-head">
              <span className="field-head">
                <strong>Filter {i + 1}</strong>
                {panel ? <InfoPanel panel={panel} /> : null}
              </span>
              <button
                type="button"
                className="btn"
                onClick={() => removeFilter(i)}
                aria-label={`Remove filter ${i + 1}`}
              >
                Remove
              </button>
            </div>
            <div className="cp-form strategy-form-grid">
              <SelectField
                label="Filter type"
                required
                value={filter.filter_type}
                onChange={(v) => updateFilter(i, { filter_type: v })}
                options={FILTER_TYPE_OPTIONS}
                placeholder="Choose filter type"
              />
              <CheckboxField
                label="Enabled"
                checked={filter.enabled}
                onChange={(checked) => updateFilter(i, { enabled: checked })}
              />
            </div>
            <FilterConfigField
              value={filter.config_text}
              onChange={(v) => updateFilter(i, { config_text: v })}
            />
          </div>
        );
      })}
      <button type="button" className="btn" onClick={addFilter}>
        + Add Restriction / Filter
      </button>
    </>
  );
}

// ---------------------------------------------------------------------------
// The structured graph form — split into independently-appliable, numbered
// section cards (doc 02 §3.1) so a caller can place each in its
// mockup-matching column (DECISION LOGIC / RISK MANAGEMENT). Each card seeds
// its own local GraphFormState slice from the SAME payload and Apply merges
// its edits back over the full payload via mergeGraphSections.
// ---------------------------------------------------------------------------

type GraphSetter<K extends keyof GraphFormState> = (patch: Partial<GraphFormState[K]>) => void;

function useGraphSection<K extends keyof GraphFormState>(
  payload: Record<string, unknown>,
  key: K,
): [GraphFormState[K], GraphSetter<K>, GraphFormState] {
  const [form, setForm] = useState<GraphFormState>(() => extractGraphSections(payload));
  const setSection: GraphSetter<K> = (patch) =>
    setForm((f) => ({ ...f, [key]: { ...f[key], ...patch } }));
  return [form[key], setSection, form];
}

interface GraphCardProps {
  payload: Record<string, unknown>;
  pending: boolean;
  onApply: (payload: Record<string, unknown>) => void;
}

// ---- 3. Position Entry Logic (§5.3) — DECISION LOGIC column ----
export function PositionEntryCard({ payload, pending, onApply }: GraphCardProps) {
  const [e, setEntry, form] = useGraphSection(payload, "entry");
  const entryShowMin = e.signal_rule === SIGNAL_MIN_SUPPORTING_RULE;

  return (
    <div className="detail-card">
      <h4 className="detail-card-title">
        3. Position Entry Logic <InfoPanel panel={P.positionEntryLogic} />
      </h4>
      <div className="cp-form strategy-form-grid">
        <SelectField
          label="Direction mode"
          value={e.direction_mode}
          onChange={(v) => setEntry({ direction_mode: v })}
          options={DIRECTION_MODE_OPTIONS}
        />
        <div className="cp-field" aria-hidden="true" />
        <SelectField
          label="Entry signal block rule"
          required
          value={e.signal_rule}
          onChange={(v) => setEntry({ signal_rule: v })}
          options={SIGNAL_RULE_OPTIONS}
          placeholder="Choose indicator block rule"
          panel={P.entryIndicatorRule}
        />
        {entryShowMin ? (
          <TextField
            label="Min. supporting indicator blocks"
            value={e.signal_min_supporting_count}
            onChange={(v) => setEntry({ signal_min_supporting_count: v })}
            placeholder="e.g. 1"
            panel={P.entryMinSupportingIndicatorCount}
          />
        ) : (
          <div className="cp-field" aria-hidden="true" />
        )}
      </div>
      <p className="cp-note">
        <InfoPanel panel={P.entrySignalBlock} /> At least one complete active Entry Indicator Block
        is required to save (doc 02 §5.3).
      </p>
      <BlockList scope="entry" blocks={e.blocks} onChange={(blocks) => setEntry({ blocks })} />
      <div style={{ marginTop: 14 }}>
        <button
          type="button"
          className="btn"
          disabled={pending}
          onClick={() => onApply(mergeGraphSections(payload, form))}
        >
          {pending ? "Applying…" : "Apply Position Entry changes"}
        </button>
      </div>
    </div>
  );
}

// ---- 4. Position Exit Logic (§5.4) — DECISION LOGIC column ----
export function PositionExitCard({ payload, pending, onApply }: GraphCardProps) {
  const [x, setExit, form] = useGraphSection(payload, "exit");
  const exitShowMin = x.signal_rule === SIGNAL_MIN_SUPPORTING_RULE;

  return (
    <div className="detail-card">
      <h4 className="detail-card-title">
        4. Position Exit Logic <InfoPanel panel={P.positionExitLogic} />
      </h4>
      <p className="cp-note">
        A blank exit block is an inactive placeholder — Stop Logic alone can protect the strategy
        (doc 02 §5.4). Enable exit indicator blocks to compose a signal-based exit.
      </p>
      <div className="cp-form strategy-form-grid">
        <SelectField
          label="Applies to position"
          value={x.applies_to_direction}
          onChange={(v) => setExit({ applies_to_direction: v })}
          options={APPLIES_TO_OPTIONS}
          panel={P.appliesToPosition}
        />
        <TextField
          label="Close percentage"
          value={x.close_percentage}
          onChange={(v) => setExit({ close_percentage: v })}
          placeholder="100"
          panel={P.exitAction}
        />
        <SelectField
          label="After partial close"
          value={x.partial_aftermath}
          onChange={(v) => setExit({ partial_aftermath: v })}
          options={PARTIAL_AFTERMATH_OPTIONS}
          panel={P.afterPartialClose}
        />
        <CheckboxField
          label="Define exit indicator blocks (signal-based exit)"
          checked={x.active}
          onChange={(checked) => setExit({ active: checked, blocks: checked && x.blocks.length === 0 ? [newBlock()] : x.blocks })}
          panel={P.exitSignalBlock}
        />
      </div>
      {x.active ? (
        <>
          <div className="cp-form strategy-form-grid">
            <SelectField
              label="Exit signal block rule"
              required
              value={x.signal_rule}
              onChange={(v) => setExit({ signal_rule: v })}
              options={SIGNAL_RULE_OPTIONS}
              placeholder="Choose indicator block rule"
              panel={P.exitIndicatorRule}
            />
            {exitShowMin ? (
              <TextField
                label="Min. supporting indicator blocks"
                value={x.signal_min_supporting_count}
                onChange={(v) => setExit({ signal_min_supporting_count: v })}
                placeholder="e.g. 1"
                panel={P.entryMinSupportingIndicatorCount}
              />
            ) : (
              <div className="cp-field" aria-hidden="true" />
            )}
          </div>
          <BlockList scope="exit" blocks={x.blocks} onChange={(blocks) => setExit({ blocks })} />
        </>
      ) : null}
      <div style={{ marginTop: 14 }}>
        <button
          type="button"
          className="btn"
          disabled={pending}
          onClick={() => onApply(mergeGraphSections(payload, form))}
        >
          {pending ? "Applying…" : "Apply Position Exit changes"}
        </button>
      </div>
    </div>
  );
}

// ---- Logic-Based Stop Block (§5.5 extension) — RISK MANAGEMENT column,
// alongside ProtectionStopCard's percentage/trailing/absolute rules ----
export function LogicBasedStopCard({ payload, pending, onApply }: GraphCardProps) {
  const [stop, setStop, form] = useGraphSection(payload, "stop");

  return (
    <div className="detail-card">
      <h4 className="detail-card-title">
        Logic-Based Stop Block <InfoPanel panel={P.logicBasedStopBlock} />
      </h4>
      <p className="cp-note">
        A logic-based stop pins an indicator + conditions that emit a stop signal against the
        open position (the strategy premise broke). Percentage / trailing / absolute price stops
        are edited in the Protection / Stop Logic card above; the stop mode below decides how every
        active stop rule combines.
      </p>
      <div className="cp-form strategy-form-grid">
        <SelectField
          label="Stop mode"
          value={stop.trigger_requirement}
          onChange={(v) => setStop({ trigger_requirement: v })}
          options={STOP_TRIGGER_REQUIREMENT_OPTIONS}
        />
        <SelectField
          label="Same-bar resolution"
          value={stop.conflict_resolution}
          onChange={(v) => setStop({ conflict_resolution: v })}
          options={STOP_CONFLICT_RESOLUTION_OPTIONS}
        />
      </div>
      <BlockList
        scope="stop"
        blocks={stop.logic_blocks}
        onChange={(logic_blocks) => setStop({ logic_blocks })}
      />
      <div style={{ marginTop: 14 }}>
        <button
          type="button"
          className="btn"
          disabled={pending}
          onClick={() => onApply(mergeGraphSections(payload, form))}
        >
          {pending ? "Applying…" : "Apply Logic-Based Stop changes"}
        </button>
      </div>
    </div>
  );
}

// ---- 7. Scaling Logic (§5.7) — RISK MANAGEMENT column ----
export function ScalingCard({ payload, pending, onApply }: GraphCardProps) {
  const [scaling, setScaling, form] = useGraphSection(payload, "scaling");

  return (
    <div className="detail-card">
      <ScalingSection scaling={scaling} onChange={setScaling} />
      <div style={{ marginTop: 14 }}>
        <button
          type="button"
          className="btn"
          disabled={pending}
          onClick={() => onApply(mergeGraphSections(payload, form))}
        >
          {pending ? "Applying…" : "Apply Scaling changes"}
        </button>
      </div>
    </div>
  );
}

// ---- 8. Restrictions / Filters (§5.8) — RISK MANAGEMENT column ----
export function RestrictionsCard({ payload, pending, onApply }: GraphCardProps) {
  const [restrictions, setRestrictions, form] = useGraphSection(payload, "restrictions");
  const [applyError, setApplyError] = useState<string | null>(null);

  const handleApply = () => {
    const invalidFilter = firstInvalidFilterConfig(form);
    if (invalidFilter !== null) {
      setApplyError(`Not sent — the "${invalidFilter}" filter config is not valid JSON.`);
      return;
    }
    setApplyError(null);
    onApply(mergeGraphSections(payload, form));
  };

  return (
    <div className="detail-card">
      <RestrictionsSection restrictions={restrictions} onChange={setRestrictions} />
      <div style={{ marginTop: 14 }}>
        <button type="button" className="btn btn-primary" disabled={pending} onClick={handleApply}>
          {pending ? "Applying…" : "Apply Restrictions changes"}
        </button>
      </div>
      {applyError !== null ? (
        <p role="alert" style={{ color: "var(--down)", marginBottom: 0 }}>
          {applyError}
        </p>
      ) : null}
      <p className="cp-note" style={{ marginTop: 10 }}>
        Each block&apos;s advanced fields (parameter overrides, reference chains) and any key not
        yet surfaced remain in the Advanced (raw payload) editor.
      </p>
    </div>
  );
}
