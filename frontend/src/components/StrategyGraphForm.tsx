import { useId, useState } from "react";

import { InfoPanel } from "@/components/InfoPanel";
import { PackagePicker } from "@/components/PackagePicker";
import type { InfoPanelContent } from "@/lib/strategyForm";
import {
  APPLIES_TO_OPTIONS,
  BLOCK_DIRECTION_OPTIONS,
  BLOCK_TIMEFRAME_OPTIONS,
  CONDITION_BLOCK_RULE_OPTIONS,
  CONDITION_MIN_SUPPORTING_RULE,
  CONDITION_REQUIRING_TRIGGERS,
  CONDITION_VALIDITY_OPTIONS,
  DIRECTION_MODE_OPTIONS,
  INDICATOR_VALIDITY_OPTIONS,
  PARTIAL_AFTERMATH_OPTIONS,
  REQUIREMENT_OPTIONS,
  SIGNAL_MIN_SUPPORTING_RULE,
  SIGNAL_RULE_OPTIONS,
  STRATEGY_GRAPH_PANELS,
  TRIGGER_SOURCE_OPTIONS,
  type ConditionBlockForm,
  type IndicatorBlockForm,
  type SelectOption,
  type StrategyGraphForm as GraphFormState,
  extractGraphSections,
  mergeGraphSections,
  newBlock,
  newCondition,
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

type Scope = "entry" | "exit";

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
// The structured graph form
// ---------------------------------------------------------------------------

export function StrategyGraphForm({
  payload,
  pending,
  onApply,
}: {
  payload: Record<string, unknown>;
  pending: boolean;
  onApply: (payload: Record<string, unknown>) => void;
}) {
  const [form, setForm] = useState<GraphFormState>(() => extractGraphSections(payload));

  const setEntry = (patch: Partial<GraphFormState["entry"]>) =>
    setForm((f) => ({ ...f, entry: { ...f.entry, ...patch } }));
  const setExit = (patch: Partial<GraphFormState["exit"]>) =>
    setForm((f) => ({ ...f, exit: { ...f.exit, ...patch } }));

  const e = form.entry;
  const x = form.exit;
  const entryShowMin = e.signal_rule === SIGNAL_MIN_SUPPORTING_RULE;
  const exitShowMin = x.signal_rule === SIGNAL_MIN_SUPPORTING_RULE;

  return (
    <section className="card" style={{ marginTop: 18 }} aria-labelledby="strat-graph-h">
      <h3 id="strat-graph-h" style={{ marginTop: 0 }}>
        Position graph (Entry / Exit Logic)
      </h3>
      <p className="cp-note">
        The structured editor for the package-graph decision sections — the sections that pin
        indicator / condition packages. Apply replaces the FULL draft payload (optimistic
        concurrency), preserving every other section and each block&apos;s advanced fields
        (parameter overrides, reference chains). Validation happens on the server — Validate / Save
        below.
      </p>

      {/* ---- Position Entry Logic (§5.3) ---- */}
      <h4 className="form-section-h">
        Position Entry Logic <InfoPanel panel={P.positionEntryLogic} />
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

      {/* ---- Position Exit Logic (§5.4) ---- */}
      <h4 className="form-section-h" style={{ marginTop: 20 }}>
        Position Exit Logic <InfoPanel panel={P.positionExitLogic} />
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

      {/* ---- Logic-Based Stop Block (§5.5) — honest boundary ---- */}
      <h4 className="form-section-h" style={{ marginTop: 20 }}>
        Logic-Based Stop Block <InfoPanel panel={P.logicBasedStopBlock} />
      </h4>
      <p className="cp-note">
        Logic-based stop blocks (an indicator + conditions that emit a stop signal) are a
        documented V18 spec feature (doc 02 §5.5) that the V1 backend engine does not yet implement
        — the compiled StrategyConfig has no <code>logic_blocks</code> field. The percentage /
        trailing / absolute stops are edited in the Strategy configuration form above; a
        logic-based stop is not composable here until the engine supports it.
      </p>

      <div style={{ marginTop: 14 }}>
        <button
          type="button"
          className="btn btn-primary"
          disabled={pending}
          onClick={() => onApply(mergeGraphSections(payload, form))}
        >
          {pending ? "Applying…" : "Apply graph changes"}
        </button>
      </div>
      <p className="cp-note" style={{ marginTop: 10 }}>
        Scaling and Restrictions / Filters are still edited in the Advanced (JSON) editor below.
      </p>
    </section>
  );
}
