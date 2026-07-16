import { useState } from "react";
import { Link } from "react-router-dom";

import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { StatusBadge } from "@/components/StatusBadge";
import {
  ConflictCard,
  DataExecutionCard,
  PositionSizingCard,
  ProtectionStopCard,
} from "@/components/StrategyConfigForm";
import {
  LogicBasedStopCard,
  PositionEntryCard,
  PositionExitCard,
  RestrictionsCard,
  ScalingCard,
} from "@/components/StrategyGraphForm";
import { ApiError } from "@/lib/apiClient";
import { EM_DASH, formatUtc } from "@/lib/backtest";
import {
  type ClearDraftResult,
  type PatchDraftResult,
  type SaveRevisionResult,
  type StrategyDraft,
  type ValidateDraftResult,
  lifecycleLabel,
  lifecycleTone,
  useClearStrategyDraft,
  useCreateStrategyDraft,
  usePatchStrategyDraft,
  useSaveStrategyRevision,
  useStrategy,
  useStrategyDraft,
  useStrategyRevision,
  useStrategyRevisions,
  useValidateStrategyDraft,
  validationStatusTone,
} from "@/lib/strategy";
import { extractFlatSections } from "@/lib/strategyForm";
import {
  type IndicatorBlockForm,
  REQUIREMENT_OPTIONS,
  TRIGGER_SOURCE_OPTIONS,
  extractGraphSections,
  type SelectOption,
} from "@/lib/strategyGraph";

// UI-02 — the doc 02 §3 3-column Strategy Details editor (SETUP & DATA /
// DECISION LOGIC / RISK MANAGEMENT, 10 numbered sub-sections, sticky
// Save/Cancel/Validate/revision toolbar), reusable both INLINE inside a
// Mainboard row (the primary interaction, doc 02 §3) and on the standalone
// /strategy route (back-compat deep-link). Every hook/OCC token/Idempotency
// header/query key below is UNCHANGED from lib/strategy.ts — only the visual
// composition (which numbered card renders in which column, sticky toolbar
// placement, raw-JSON demoted to a collapsed Advanced disclosure) is new.

function mutationErrorText(error: unknown): string {
  if (error instanceof ApiError) return `${error.code}: ${error.message}`;
  return error instanceof Error ? error.message : "Request failed.";
}

function optionLabel(options: SelectOption[], value: string): string {
  return options.find((option) => option.value === value)?.label ?? (value || EM_DASH);
}

function humanizeKey(key: string): string {
  const spaced = key.replace(/_/g, " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

function fieldText(value: unknown): string {
  if (value === "" || value === null || value === undefined) return EM_DASH;
  if (typeof value === "boolean") return value ? "yes" : "no";
  return String(value);
}

// Compact read-only key/value listing for a flat (scalar) section slice —
// typed labels from the extracted form, never a raw JSON dump.
function ReadOnlyFields({ data }: { data: Record<string, unknown> }) {
  const entries = Object.entries(data).filter(([key]) => key !== "raw");
  if (entries.length === 0) {
    return (
      <p className="cp-note" style={{ margin: 0 }}>
        No values recorded.
      </p>
    );
  }
  return (
    <dl className="kv kv-compact">
      {entries.map(([key, value]) => (
        <>
          <dt key={`${key}-dt`}>{humanizeKey(key)}</dt>
          <dd key={`${key}-dd`}>{fieldText(value)}</dd>
        </>
      ))}
    </dl>
  );
}

function ReadOnlyBlockSummary({ label, blocks }: { label: string; blocks: IndicatorBlockForm[] }) {
  if (blocks.length === 0) {
    return (
      <p className="cp-note" style={{ margin: "0 0 8px" }}>
        {label}: no blocks defined.
      </p>
    );
  }
  return (
    <div style={{ marginBottom: 8 }}>
      <strong style={{ fontSize: 13 }}>{label}</strong>
      <ul style={{ margin: "4px 0 0", paddingLeft: 18, fontSize: 13 }}>
        {blocks.map((block, index) => (
          <li key={block.key}>
            Block {index + 1}: {block.package_ref ? "package pinned" : "no package"} —{" "}
            {optionLabel(TRIGGER_SOURCE_OPTIONS, block.trigger_source)},{" "}
            {optionLabel(REQUIREMENT_OPTIONS, block.requirement)}
            {block.conditions.length > 0 ? `, ${block.conditions.length} condition(s)` : ""}
          </li>
        ))}
      </ul>
    </div>
  );
}

function MutationErrorNote({ error }: { error: unknown }) {
  const details = error instanceof ApiError ? error.details : [];
  return (
    <div className="card" style={{ marginTop: 12 }}>
      <p role="alert" style={{ color: "var(--down)", margin: 0 }}>
        {mutationErrorText(error)}
      </p>
      {details.length > 0 ? (
        <ul style={{ margin: "8px 0 0", paddingLeft: 18, fontSize: 13 }}>
          {details.map((detail, index) => (
            <li key={index}>
              <code>{JSON.stringify(detail)}</code>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// 1. Strategy Context (read-only identity — display_name/rationale family are
// server-owned at creation time, not yet part of the structured draft editor).
// ---------------------------------------------------------------------------

function StrategyContextCard({ rootId }: { rootId: string | null }) {
  const strategy = useStrategy(rootId);
  return (
    <div className="detail-card">
      <h4 className="detail-card-title">1. Strategy Context</h4>
      {rootId === null ? (
        <p className="cp-note" style={{ margin: 0 }}>
          Strategy root not yet created — save the draft to create it.
        </p>
      ) : strategy.isLoading ? (
        <Loading />
      ) : strategy.isError ? (
        <ErrorState error={strategy.error} onRetry={() => void strategy.refetch()} />
      ) : strategy.data ? (
        <dl className="kv kv-compact">
          <dt>Name</dt>
          <dd>{strategy.data.display_name}</dd>
          <dt>Rationale family</dt>
          <dd>{strategy.data.rationale_family_id ?? EM_DASH}</dd>
          <dt>Lifecycle</dt>
          <dd>
            <StatusBadge
              label={lifecycleLabel(strategy.data.lifecycle_state)}
              tone={lifecycleTone(strategy.data.lifecycle_state)}
            />
          </dd>
          <dt>Root</dt>
          <dd>
            <code>{strategy.data.strategy_root_id}</code>
          </dd>
        </dl>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Revision history — compact collapsed disclosure (edit / revision modes).
// ---------------------------------------------------------------------------

function RevisionHistoryDisclosure({ rootId }: { rootId: string | null }) {
  const revisions = useStrategyRevisions(rootId);
  return (
    <details className="panel-actions-history">
      <summary>Revision history{rootId !== null ? ` (${revisions.data?.length ?? "…"})` : ""}</summary>
      {rootId === null ? (
        <p className="cp-note">No revisions yet — this strategy has never been saved.</p>
      ) : revisions.isLoading ? (
        <Loading />
      ) : revisions.isError ? (
        <ErrorState error={revisions.error} onRetry={() => void revisions.refetch()} />
      ) : (revisions.data ?? []).length === 0 ? (
        <p className="cp-note">No revisions yet — save the draft to create the first one.</p>
      ) : (
        <table className="metrics-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Status</th>
              <th>Config hash</th>
              <th>Created</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {(revisions.data ?? []).map((row) => (
              <tr key={row.strategy_revision_id}>
                <td>{row.revision_number}</td>
                <td>
                  <StatusBadge
                    label={row.validation_status}
                    tone={validationStatusTone(row.validation_status)}
                  />
                </td>
                <td>
                  <code>{row.config_hash}</code>
                </td>
                <td>{formatUtc(row.created_at)}</td>
                <td>
                  <Link to={`/strategy?revision=${encodeURIComponent(row.strategy_revision_id)}`}>
                    Open full page ↗
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </details>
  );
}

// ---------------------------------------------------------------------------
// Advanced (raw payload) editor — the JSON escape hatch for each block's
// advanced fields (parameter overrides, reference chains) and any key not
// yet surfaced by a structured card. Collapsed by default (doc 02 UI-02: not
// the primary surface).
// ---------------------------------------------------------------------------

function AdvancedPayloadEditor({
  draft,
  pending,
  onApply,
}: {
  draft: StrategyDraft;
  pending: boolean;
  onApply: (payload: Record<string, unknown>) => void;
}) {
  const [text, setText] = useState(() => JSON.stringify(draft.payload, null, 2));
  const [parseError, setParseError] = useState<string | null>(null);

  return (
    <details className="panel-actions-history" style={{ marginTop: 10 }}>
      <summary>Advanced (raw payload)</summary>
      <p className="cp-note">
        Apply replaces the FULL draft payload (optimistic concurrency on row version{" "}
        {draft.row_version}). The numbered cards above cover the flat sections and the full
        package graph — this is the fallback for each block&apos;s advanced fields (parameter
        overrides, reference chains) and any key not yet surfaced.
      </p>
      <label className="cp-field cp-wide">
        <span>StrategyConfig payload</span>
        <textarea
          rows={12}
          value={text}
          onChange={(event) => setText(event.target.value)}
          spellCheck={false}
        />
      </label>
      <div style={{ marginTop: 10 }}>
        <button
          type="button"
          className="btn"
          disabled={pending}
          onClick={() => {
            try {
              const parsed: unknown = JSON.parse(text);
              if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
                setParseError("The payload must be a JSON object.");
                return;
              }
              setParseError(null);
              onApply(parsed as Record<string, unknown>);
            } catch (error) {
              setParseError(error instanceof Error ? error.message : "Invalid JSON.");
            }
          }}
        >
          {pending ? "Applying…" : "Apply payload"}
        </button>
      </div>
      {parseError !== null ? (
        <p role="alert" style={{ color: "var(--down)", marginBottom: 0 }}>
          Not sent — invalid JSON: {parseError}
        </p>
      ) : null}
    </details>
  );
}

// ---------------------------------------------------------------------------
// Sticky bottom toolbar — "10. Save / Package Actions" (doc 02 §3.1 row 10 —
// production label is "Save Strategy Revision", never V18's legacy "Save as
// Strategy Package", doc 02 §10).
// ---------------------------------------------------------------------------

function DraftToolbar({
  draft,
  onCancel,
  validatePending,
  savePending,
  clearPending,
  onValidate,
  onSave,
  onClear,
}: {
  draft: StrategyDraft;
  onCancel?: () => void;
  validatePending: boolean;
  savePending: boolean;
  clearPending: boolean;
  onValidate: () => void;
  onSave: () => void;
  onClear: () => void;
}) {
  const [confirmClear, setConfirmClear] = useState(false);

  return (
    <div className="panel-actions">
      <div className="panel-actions-title">10. Save / Package Actions</div>
      <button type="button" className="btn" disabled={validatePending} onClick={onValidate}>
        {validatePending ? "Validating…" : "Validate"}
      </button>
      <button
        type="button"
        className="panel-action-button primary"
        disabled={savePending}
        onClick={onSave}
      >
        {savePending ? "Saving…" : "Save Strategy Revision"}
      </button>
      {confirmClear ? (
        <>
          <button
            type="button"
            className="btn"
            style={{ borderColor: "var(--down)", color: "var(--down)" }}
            disabled={clearPending}
            onClick={() => {
              setConfirmClear(false);
              onClear();
            }}
          >
            {clearPending ? "Clearing…" : `Confirm clear (row version ${draft.row_version})`}
          </button>
          <button type="button" className="btn btn-ghost" onClick={() => setConfirmClear(false)}>
            Keep editing
          </button>
        </>
      ) : (
        <button type="button" className="panel-action-button" onClick={() => setConfirmClear(true)}>
          Clear draft…
        </button>
      )}
      {onCancel ? (
        <button type="button" className="btn btn-ghost" onClick={onCancel}>
          Cancel
        </button>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Edit mode (draftId present) — the full 3-column, 9-card interactive editor.
// ---------------------------------------------------------------------------

function DraftEditorGrid({ draftId, onCancel }: { draftId: string; onCancel?: () => void }) {
  const draftQuery = useStrategyDraft(draftId);
  const patch = usePatchStrategyDraft();
  const validate = useValidateStrategyDraft();
  const save = useSaveStrategyRevision();
  const clear = useClearStrategyDraft();

  if (draftQuery.isLoading) {
    return <Loading label="Loading strategy draft…" />;
  }
  if (draftQuery.isError) {
    return <ErrorState error={draftQuery.error} onRetry={() => void draftQuery.refetch()} />;
  }
  const draft = draftQuery.data;
  if (!draft) return null;

  // A patch replaces the FULL draft payload under BODY-form OCC (unchanged —
  // lib/strategy.ts). Every numbered card below funnels into this same call.
  const applyPayload = (payload: Record<string, unknown>) =>
    patch.mutate({ draftId, expectedRowVersion: draft.row_version, payload });

  const cardProps = { payload: draft.payload, pending: patch.isPending, onApply: applyPayload };

  return (
    <div>
      {/* key remounts every card on a server head move (patch/save success) — */}
      {/* each card re-seeds from the fresh payload, never a live client merge. */}
      <div className="details-grid" key={`grid-${draft.row_version}`}>
        <div className="details-column">
          <div className="column-title">Setup &amp; Data</div>
          <StrategyContextCard rootId={draft.strategy_root_id} />
          <DataExecutionCard {...cardProps} />
        </div>
        <div className="details-column">
          <div className="column-title">Decision Logic</div>
          <PositionEntryCard {...cardProps} />
          <PositionExitCard {...cardProps} />
        </div>
        <div className="details-column">
          <div className="column-title">Risk Management</div>
          <ProtectionStopCard {...cardProps} />
          <LogicBasedStopCard {...cardProps} />
          <PositionSizingCard {...cardProps} />
          <ScalingCard {...cardProps} />
          <RestrictionsCard {...cardProps} />
          <ConflictCard {...cardProps} />
        </div>
      </div>

      {patch.isError ? (
        <MutationErrorNote error={patch.error} />
      ) : patch.data ? (
        <PatchNote result={patch.data} />
      ) : null}

      <AdvancedPayloadEditor
        key={`adv-${draft.row_version}`}
        draft={draft}
        pending={patch.isPending}
        onApply={applyPayload}
      />

      <DraftToolbar
        draft={draft}
        onCancel={onCancel}
        validatePending={validate.isPending}
        savePending={save.isPending}
        clearPending={clear.isPending}
        onValidate={() => validate.mutate({ draftId })}
        onSave={() => save.mutate({ draftId, expectedRowVersion: draft.row_version })}
        onClear={() => clear.mutate({ draftId, expectedRowVersion: draft.row_version })}
      />
      {validate.isError ? <MutationErrorNote error={validate.error} /> : null}
      {validate.data ? <ValidateResultNote result={validate.data} /> : null}
      {save.isError ? <MutationErrorNote error={save.error} /> : null}
      {save.data ? <SaveResultNote result={save.data} /> : null}
      {clear.isError ? <MutationErrorNote error={clear.error} /> : null}
      {clear.data ? <ClearResultNote result={clear.data} /> : null}

      <RevisionHistoryDisclosure rootId={draft.strategy_root_id} />
    </div>
  );
}

function PatchNote({ result }: { result: PatchDraftResult }) {
  return (
    <p className="cp-note" style={{ marginTop: 10 }}>
      Payload applied — draft now at row version {result.row_version}
      {result.is_dirty ? " (unsaved changes pending Save)" : ""}.
    </p>
  );
}

function ValidateResultNote({ result }: { result: ValidateDraftResult }) {
  return (
    <div className="card" style={{ marginTop: 12 }} aria-labelledby="strat-validate-h">
      <h4 id="strat-validate-h" style={{ marginTop: 0 }}>
        Validation result
      </h4>
      <StatusBadge
        label={result.valid ? "Valid config" : `${result.issues.length} blocker(s)`}
        tone={result.valid ? "ok" : "down"}
      />
      {result.issues.length > 0 ? (
        <table className="metrics-table" style={{ marginTop: 12 }}>
          <thead>
            <tr>
              <th>Field</th>
              <th>Code</th>
              <th>Message</th>
            </tr>
          </thead>
          <tbody>
            {result.issues.map((issue, index) => (
              <tr key={index}>
                <td>
                  <code>{issue.field}</code>
                </td>
                <td>
                  <code>{issue.code}</code>
                </td>
                <td>{issue.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="cp-note" style={{ marginTop: 10 }}>
          No blockers — the draft can be saved as an immutable revision.
        </p>
      )}
    </div>
  );
}

function SaveResultNote({ result }: { result: SaveRevisionResult }) {
  return (
    <div className="card" style={{ marginTop: 12 }} aria-labelledby="strat-save-h">
      <h4 id="strat-save-h" style={{ marginTop: 0 }}>
        Revision saved
      </h4>
      <dl className="kv">
        <dt>Revision</dt>
        <dd>
          <Link to={`/strategy?revision=${encodeURIComponent(result.strategy_revision_id)}`}>
            <code>{result.strategy_revision_id}</code>
          </Link>{" "}
          (#{result.revision_number})
        </dd>
        <dt>Config hash</dt>
        <dd>
          <code>{result.config_hash}</code>
        </dd>
        <dt>Ready state</dt>
        <dd>
          <StatusBadge label={result.ready_state} tone="warn" />
        </dd>
      </dl>
      <p className="cp-note" style={{ marginTop: 10 }}>
        Save is never a Ready PASS — re-run the Backtest Ready Check before RUN.
      </p>
      {result.pinned_items.length > 0 ? (
        <table className="metrics-table" style={{ marginTop: 12 }}>
          <thead>
            <tr>
              <th>Re-pinned Mainboard item</th>
              <th>Pinned revision</th>
              <th>Composition hash</th>
            </tr>
          </thead>
          <tbody>
            {result.pinned_items.map((item) => (
              <tr key={item.item_id}>
                <td>
                  <code>{item.item_id}</code>
                </td>
                <td>
                  <code>{item.pinned_revision_id}</code>
                </td>
                <td>{item.composition_hash ? <code>{item.composition_hash}</code> : EM_DASH}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="cp-note" style={{ marginTop: 10 }}>
          No Mainboard items reference this strategy yet — nothing re-pinned.
        </p>
      )}
    </div>
  );
}

function ClearResultNote({ result }: { result: ClearDraftResult }) {
  return (
    <p className="cp-note" style={{ marginTop: 10 }}>
      Draft cleared — editor state reset (row version {result.row_version}). Saved revisions are
      untouched.
    </p>
  );
}

// ---------------------------------------------------------------------------
// Revision mode (revisionId present, no draftId) — read-only summary of an
// immutable revision, organized in the SAME 3-column/numbered layout. Editing
// an immutable revision is impossible by construction (doc 02 §11 rule 2) —
// "Edit" starts a NEW draft (the standalone page's create flow, relocated
// inline) rather than mutating this revision.
// ---------------------------------------------------------------------------

function RevisionSummaryGrid({
  revisionId,
  onDraftCreated,
  onCancel,
}: {
  revisionId: string;
  onDraftCreated?: (draftId: string) => void;
  onCancel?: () => void;
}) {
  const revision = useStrategyRevision(revisionId);
  const rootId = revision.data?.strategy_root_id ?? null;
  const strategy = useStrategy(rootId);
  const create = useCreateStrategyDraft();

  if (revision.isLoading) {
    return <Loading label="Loading revision…" />;
  }
  if (revision.isError) {
    return <ErrorState error={revision.error} onRetry={() => void revision.refetch()} />;
  }
  const data = revision.data;
  if (!data) return null;

  const flat = extractFlatSections(data.payload);
  const graph = extractGraphSections(data.payload);

  return (
    <div>
      <p className="cp-note">
        Viewing immutable revision #{data.revision_number} (read-only). Editing starts a new draft
        — the saved revision is never mutated in place (doc 02 §11).
      </p>
      <div className="details-grid">
        <div className="details-column">
          <div className="column-title">Setup &amp; Data</div>
          <div className="detail-card">
            <h4 className="detail-card-title">1. Strategy Context</h4>
            <dl className="kv kv-compact">
              <dt>Root</dt>
              <dd>
                <code>{data.strategy_root_id}</code>
              </dd>
              <dt>Validation</dt>
              <dd>
                <StatusBadge
                  label={data.validation_status}
                  tone={validationStatusTone(data.validation_status)}
                />
              </dd>
              <dt>Config hash</dt>
              <dd>
                <code>{data.config_hash}</code>
              </dd>
              <dt>Created</dt>
              <dd>{formatUtc(data.created_at)}</dd>
            </dl>
          </div>
          <div className="detail-card">
            <h4 className="detail-card-title">2. Data &amp; Execution</h4>
            <ReadOnlyFields data={flat.data as unknown as Record<string, unknown>} />
          </div>
        </div>
        <div className="details-column">
          <div className="column-title">Decision Logic</div>
          <div className="detail-card">
            <h4 className="detail-card-title">3–4. Position Entry / Exit Logic</h4>
            <ReadOnlyBlockSummary label="Entry" blocks={graph.entry.blocks} />
            <ReadOnlyBlockSummary
              label="Exit"
              blocks={graph.exit.active ? graph.exit.blocks : []}
            />
          </div>
        </div>
        <div className="details-column">
          <div className="column-title">Risk Management</div>
          <div className="detail-card">
            <h4 className="detail-card-title">5. Protection / Stop Logic</h4>
            <ReadOnlyFields data={flat.protection as unknown as Record<string, unknown>} />
            <p className="cp-note" style={{ margin: "8px 0 0" }}>
              {graph.stop.logic_blocks.length} logic-based stop block(s) pinned.
            </p>
          </div>
          <div className="detail-card">
            <h4 className="detail-card-title">6. Position Sizing</h4>
            <ReadOnlyFields data={flat.sizing as unknown as Record<string, unknown>} />
          </div>
          <div className="detail-card">
            <h4 className="detail-card-title">7. Scaling Logic</h4>
            <p className="cp-note" style={{ margin: 0 }}>
              {graph.scaling.enabled
                ? `Enabled — ${graph.scaling.method || "no additional-layer method"}`
                : "Disabled"}
            </p>
          </div>
          <div className="detail-card">
            <h4 className="detail-card-title">8. Restrictions / Filters</h4>
            <p className="cp-note" style={{ margin: 0 }}>
              Rule: {graph.restrictions.rule || EM_DASH} — {graph.restrictions.filters.length}{" "}
              filter(s)
            </p>
          </div>
          <div className="detail-card">
            <h4 className="detail-card-title">9. Conflict / Position Handling</h4>
            <ReadOnlyFields data={flat.conflict as unknown as Record<string, unknown>} />
          </div>
        </div>
      </div>

      <details className="panel-actions-history" style={{ marginTop: 10 }}>
        <summary>Pinned references ({data.references.length})</summary>
        {data.references.length === 0 ? (
          <p className="cp-note">No pinned references.</p>
        ) : (
          <table className="metrics-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Entity type</th>
                <th>Role</th>
                <th>Root</th>
                <th>Revision</th>
                <th>Content hash</th>
              </tr>
            </thead>
            <tbody>
              {data.references.map((ref) => (
                <tr key={`${ref.position_in_graph}-${ref.referenced_revision_id}`}>
                  <td>{ref.position_in_graph}</td>
                  <td>{ref.referenced_entity_type}</td>
                  <td>{ref.dependency_role}</td>
                  <td>
                    <code>{ref.referenced_root_id}</code>
                  </td>
                  <td>
                    <code>{ref.referenced_revision_id}</code>
                  </td>
                  <td>
                    <code>{ref.referenced_content_hash}</code>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </details>

      <details className="panel-actions-history" style={{ marginTop: 10 }}>
        <summary>Advanced (raw payload)</summary>
        <pre className="wire-table" style={{ whiteSpace: "pre-wrap", padding: 10 }}>
          {JSON.stringify(data.payload, null, 2)}
        </pre>
      </details>

      <div className="panel-actions">
        <div className="panel-actions-title">10. Save / Package Actions</div>
        <button
          type="button"
          className="panel-action-button primary"
          disabled={create.isPending}
          onClick={() =>
            create.mutate(
              {
                displayName: strategy.data?.display_name ?? "Untitled strategy",
                rationaleFamilyId: strategy.data?.rationale_family_id ?? null,
              },
              { onSuccess: (result) => onDraftCreated?.(result.draft_id) },
            )
          }
        >
          {create.isPending ? "Starting…" : "Edit this strategy (new draft)"}
        </button>
        {onCancel ? (
          <button type="button" className="btn btn-ghost" onClick={onCancel}>
            Cancel
          </button>
        ) : null}
      </div>
      {create.isError ? <MutationErrorNote error={create.error} /> : null}

      <RevisionHistoryDisclosure rootId={data.strategy_root_id} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Root-only mode (rootId present, no pinned revision yet) — header + full
// revision history, same "start editing" entry point as revision mode.
// ---------------------------------------------------------------------------

function RootSummary({
  rootId,
  onDraftCreated,
  onCancel,
}: {
  rootId: string;
  onDraftCreated?: (draftId: string) => void;
  onCancel?: () => void;
}) {
  const strategy = useStrategy(rootId);
  const create = useCreateStrategyDraft();

  return (
    <div>
      <div className="detail-card">
        <h4 className="detail-card-title">1. Strategy Context</h4>
        {strategy.isLoading ? (
          <Loading />
        ) : strategy.isError ? (
          <ErrorState error={strategy.error} onRetry={() => void strategy.refetch()} />
        ) : strategy.data ? (
          <dl className="kv kv-compact">
            <dt>Name</dt>
            <dd>{strategy.data.display_name}</dd>
            <dt>Lifecycle</dt>
            <dd>
              <StatusBadge
                label={lifecycleLabel(strategy.data.lifecycle_state)}
                tone={lifecycleTone(strategy.data.lifecycle_state)}
              />
            </dd>
            <dt>Current revision</dt>
            <dd>
              {strategy.data.current_revision_id !== null ? (
                <Link
                  to={`/strategy?revision=${encodeURIComponent(strategy.data.current_revision_id)}`}
                >
                  <code>{strategy.data.current_revision_id}</code>
                </Link>
              ) : (
                "none (unsaved draft only)"
              )}
            </dd>
          </dl>
        ) : null}
      </div>

      <div style={{ marginTop: 10 }}>
        <RevisionHistoryDisclosure rootId={rootId} />
      </div>

      <div className="panel-actions">
        <div className="panel-actions-title">10. Save / Package Actions</div>
        <button
          type="button"
          className="panel-action-button primary"
          disabled={create.isPending}
          onClick={() =>
            create.mutate(
              {
                displayName: strategy.data?.display_name ?? "Untitled strategy",
                rationaleFamilyId: strategy.data?.rationale_family_id ?? null,
              },
              { onSuccess: (result) => onDraftCreated?.(result.draft_id) },
            )
          }
        >
          {create.isPending ? "Starting…" : "Edit this strategy (new draft)"}
        </button>
        {onCancel ? (
          <button type="button" className="btn btn-ghost" onClick={onCancel}>
            Cancel
          </button>
        ) : null}
      </div>
      {create.isError ? <MutationErrorNote error={create.error} /> : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Mode router
// ---------------------------------------------------------------------------

export function StrategyDetailsPanel({
  rootId,
  revisionId,
  draftId,
  onDraftCreated,
  onCancel,
}: {
  rootId: string | null;
  revisionId: string | null;
  draftId: string | null;
  onDraftCreated?: (draftId: string) => void;
  onCancel?: () => void;
}) {
  if (draftId !== null) {
    return <DraftEditorGrid draftId={draftId} onCancel={onCancel} />;
  }
  if (revisionId !== null) {
    return (
      <RevisionSummaryGrid
        revisionId={revisionId}
        onDraftCreated={onDraftCreated}
        onCancel={onCancel}
      />
    );
  }
  if (rootId !== null) {
    return <RootSummary rootId={rootId} onDraftCreated={onDraftCreated} onCancel={onCancel} />;
  }
  return null;
}
