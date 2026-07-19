import { useState } from "react";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { StatusBadge } from "@/components/StatusBadge";
import {
  ALLOCATION_CURRENCIES,
  COMPOUNDING_MODES,
  COMPOUNDING_MODE_LABELS,
  CONFLICT_POLICIES,
  CONFLICT_POLICY_LABELS,
  type AllocationCandidate,
  type AllocationDraftInput,
  type AllocationDraftResponse,
  type AllocationEntry,
  type AllocationIssue,
  type AllocationValidationReport,
  type DerivedAmounts,
  type RevisionResult,
  type SaveDraftResult,
  type SleeveAmount,
  type SyncPreview,
  allocationStateLabel,
  allocationStateTone,
  useAllocationDraft,
  useCreateAllocationRevision,
  useSaveAllocationDraft,
  useSyncPreview,
  useValidateAllocation,
} from "@/lib/allocation";
import { ApiError } from "@/lib/apiClient";
import { EM_DASH, useDefaultMainboard } from "@/lib/backtest";
import { severityTone } from "@/lib/readiness";

// Failures surface the backend canonical envelope verbatim — the client never
// invents allocation-domain messages (mirrors ReadyCheck/BacktestRun). A stale
// OCC token arrives here as 409 ALLOCATION_DRAFT_CONFLICT (doc 13 §10.1).
function mutationErrorText(error: unknown): string {
  if (error instanceof ApiError) return `${error.code}: ${error.message}`;
  return error instanceof Error ? error.message : "Request failed.";
}

// Consistent inline mutation-error callout (doc 13 UI-13 "explicit error").
// Distinct from ErrorState, which is for query-load failures and always says
// "Unable to load" — a save/validate/sync failure needs its own copy.
function InlineError({ message }: { message: string }) {
  return (
    <p role="alert" className="alloc-error-box">
      {message}
    </p>
  );
}

// The two mode-note strings a toggle state renders (doc 13 §3.1, verbatim).
const MODE_NOTE_ON =
  "Equity Allocation is active. The shared pool below replaces individual Initial Capital values for this backtest only.";
const MODE_NOTE_OFF =
  "Equity Allocation is not selected. No shared capital pool is used; each Strategy, Trading Signal and Trade Log runs with the Initial Capital entered in its own details.";

// A local editor row. `share` keeps the raw text so a partially-typed decimal
// is never coerced client-side — the server parses money/percent strings
// (doc 13 §13) and its validation errors render verbatim.
interface EntryRow {
  composition_item_id: string;
  item_type: string;
  active: boolean;
  share: string;
}

// Friendly labels for the server-DERIVED MainboardItemKind (§8.2). The Type
// column in the sleeve table shows these (mockup "Strategy / Trading Signal /
// Trade Log"); an unknown token falls back to its raw wire value.
const ITEM_TYPE_LABELS: Record<string, string> = {
  strategy: "Strategy",
  trading_signal: "Trading Signal",
  trade_log: "Trade Log",
};

function itemTypeLabel(itemType: string): string {
  return ITEM_TYPE_LABELS[itemType] ?? itemType;
}

// Per-item sleeve capital rendered VERBATIM from the server derivation (never
// recomputed client-side, doc 13 §8.3) — appends the pool currency when known.
function sleeveCapitalText(sleeve: SleeveAmount | undefined, currency: string | null): string {
  if (!sleeve) return EM_DASH;
  return currency ? `${sleeve.initial_sleeve_capital} ${currency}` : sleeve.initial_sleeve_capital;
}

// Portfolio / Equity Allocation (Stage 4a, doc 13). Editor of the mutable
// allocation draft the Backtest Ready Check reads: the shared capital pool
// fields + per-item sleeve entries, the immutable validation report, the
// non-destructive Sync-From-Mainboard preview, and the plan-revision freeze.
// Reads the DEFAULT Mainboard composition for its context (RUN/Ready-Check
// pattern; a real Stage-3 Mainboard page may lift composition choice app-level).
export function Portfolio() {
  const mainboard = useDefaultMainboard();
  const composition = mainboard.data;
  const compositionId = composition?.workspace_id ?? null;

  const draftQuery = useAllocationDraft(compositionId);
  // Mutations live HERE so their results survive the DraftEditor remount when
  // a save bumps row_version (the FutureDev registry_version-bump lesson).
  const save = useSaveAllocationDraft();
  const validate = useValidateAllocation();
  const sync = useSyncPreview();
  const revision = useCreateAllocationRevision();

  return (
    <>
      <h1 className="page-title">Portfolio / Equity Allocation</h1>
      <p className="page-sub">
        Configure the shared capital pool and per-item equity sleeves for your default Mainboard
        composition — the draft the Backtest Ready Check validates
      </p>

      <section className="card" aria-labelledby="alloc-composition-h">
        <h3 id="alloc-composition-h" style={{ marginTop: 0 }}>
          Composition
        </h3>
        {mainboard.isLoading ? (
          <Loading />
        ) : mainboard.isError ? (
          <ErrorState error={mainboard.error} onRetry={() => void mainboard.refetch()} />
        ) : composition ? (
          <dl className="kv">
            <dt>Workspace</dt>
            <dd>
              <code>{composition.workspace_id}</code>
            </dd>
            <dt>Items</dt>
            <dd>
              {composition.items.length} ({composition.items.filter((i) => i.is_enabled).length}{" "}
              enabled)
            </dd>
          </dl>
        ) : (
          <EmptyState
            glyph="—"
            title="No composition available"
            description="This workspace has no default Mainboard composition yet."
          />
        )}
      </section>

      {compositionId !== null ? (
        <div style={{ marginTop: 18 }}>
          {draftQuery.isLoading ? (
            <div className="card">
              <Loading label="Loading allocation draft…" />
            </div>
          ) : draftQuery.isError ? (
            <div className="card">
              <ErrorState error={draftQuery.error} onRetry={() => void draftQuery.refetch()} />
            </div>
          ) : draftQuery.data ? (
            <>
              <DraftEditor
                key={draftQuery.data.row_version}
                data={draftQuery.data}
                saving={save.isPending}
                onSave={(draft) =>
                  save.mutate({
                    compositionId,
                    expectedRowVersion: draftQuery.data.row_version,
                    draft,
                  })
                }
                validatePending={validate.isPending}
                validateError={validate.isError ? mutationErrorText(validate.error) : null}
                validateReport={validate.data ?? null}
                onValidate={() => validate.mutate({ compositionId })}
                savedDerived={save.data?.derived ?? null}
              />
              {save.isError ? (
                <div className="card" style={{ marginTop: 18 }}>
                  <InlineError message={mutationErrorText(save.error)} />
                </div>
              ) : null}
              {save.data ? <SaveResultCard result={save.data} /> : null}
              <SyncCard
                pending={sync.isPending}
                error={sync.isError ? mutationErrorText(sync.error) : null}
                preview={sync.data ?? null}
                onRun={() => sync.mutate({ compositionId })}
              />
              <RevisionCard
                data={draftQuery.data}
                pending={revision.isPending}
                error={revision.isError ? mutationErrorText(revision.error) : null}
                result={revision.data ?? null}
                onRun={() =>
                  revision.mutate({
                    compositionId,
                    expectedRowVersion: draftQuery.data.row_version,
                  })
                }
              />
            </>
          ) : null}
        </div>
      ) : null}
    </>
  );
}

// ---------------------------------------------------------------------------
// Draft editor (remounts on every server head move via key={row_version} —
// the editor is always seeded from the latest server draft, never merged)
// ---------------------------------------------------------------------------

function DraftEditor({
  data,
  saving,
  onSave,
  validatePending,
  validateError,
  validateReport,
  onValidate,
  savedDerived,
}: {
  data: AllocationDraftResponse;
  saving: boolean;
  onSave: (draft: AllocationDraftInput) => void;
  validatePending: boolean;
  validateError: string | null;
  validateReport: AllocationValidationReport | null;
  onValidate: () => void;
  savedDerived: DerivedAmounts | null;
}) {
  const [enabled, setEnabled] = useState(data.draft.enabled);
  const [amount, setAmount] = useState(data.draft.initial_capital?.amount ?? "");
  const [currency, setCurrency] = useState(data.draft.initial_capital?.currency ?? "");
  const [mode, setMode] = useState(data.draft.compounding_mode ?? "");
  const [reserve, setReserve] = useState(data.draft.reserve_cash_percent ?? "");
  const [maxExposure, setMaxExposure] = useState(data.draft.max_total_exposure_percent ?? "");
  const [conflictPolicy, setConflictPolicy] = useState(data.draft.conflict_policy ?? "");
  const [entries, setEntries] = useState<EntryRow[]>(
    data.draft.entries.map((entry) => ({
      composition_item_id: entry.composition_item_id,
      item_type: entry.item_type,
      active: entry.active,
      share: entry.equity_share_percent ?? "",
    })),
  );

  const represented = new Set(entries.map((entry) => entry.composition_item_id));
  const candidates = data.candidate_items.filter(
    (candidate) => !represented.has(candidate.composition_item_id),
  );

  const buildInput = (): AllocationDraftInput => ({
    enabled,
    // The server requires amount+currency together; a filled amount travels
    // with whatever currency is picked and any mismatch fails verbatim (§10.1).
    initial_capital: amount.trim() !== "" ? { amount: amount.trim(), currency } : null,
    compounding_mode: mode !== "" ? mode : null,
    reserve_cash_percent: reserve.trim() !== "" ? reserve.trim() : null,
    max_total_exposure_percent: maxExposure.trim() !== "" ? maxExposure.trim() : null,
    conflict_policy: conflictPolicy !== "" ? conflictPolicy : null,
    entries: entries.map((entry) => ({
      composition_item_id: entry.composition_item_id,
      active: entry.active,
      equity_share_percent: entry.share.trim() !== "" ? entry.share.trim() : null,
    })),
  });

  // Derived preview for Card 3 — the latest report wins over a plain save,
  // since Validate is the authoritative allocation-readiness computation;
  // never recomputed client-side (doc 13 §8.3).
  const previewDerived = validateReport?.derived ?? savedDerived;

  return (
    <section className="card" aria-labelledby="alloc-draft-h">
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h3 id="alloc-draft-h" style={{ margin: 0 }}>
          Allocation draft
        </h3>
        <StatusBadge
          tone={data.draft.enabled ? "ok" : "neutral"}
          label={data.draft.enabled ? "shared allocation" : "independent (off)"}
        />
        <span style={{ fontSize: 12, color: "var(--text-dim)" }}>
          rv {data.row_version}
          {data.plan_id ? (
            <>
              {" · "}
              <code>{data.plan_id}</code>
            </>
          ) : (
            " · no plan row yet"
          )}
        </span>
      </div>

      <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 14 }}>
        {/* v18 mockup "USE EQUITY ALLOCATION FOR THIS BACKTEST" banner. The
            <label> wraps the checkbox so its accessible name stays the heading.
            Always interactive — toggling back on must never itself be blocked. */}
        <label className="mode-toggle">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(event) => setEnabled(event.target.checked)}
          />
          <div>
            <b>USE EQUITY ALLOCATION FOR THIS BACKTEST</b>
            <span>{enabled ? MODE_NOTE_ON : MODE_NOTE_OFF}</span>
          </div>
        </label>

        {/* v18 mockup workspace — 4 numbered cards. Toggle off fades + blocks
            pointer input (mockup .equity-allocation-disabled: opacity .42,
            grayscale, pointer-events none); every field/button inside also
            carries a native `disabled` so keyboard activation is blocked too,
            not just the mouse (UI-13). */}
        <div
          className={`alloc-workspace${enabled ? "" : " alloc-workspace-disabled"}`}
          aria-disabled={!enabled}
        >
          {/* Card 1 — SHARED CAPITAL POOL. */}
          <div className="portfolio-card">
            <div className="section-title-upper">1. Shared capital pool</div>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
              <label className="auth-field" style={{ maxWidth: 180 }}>
                <span>Initial capital</span>
                <input
                  className="auth-input"
                  value={amount}
                  placeholder="e.g. 10000"
                  disabled={!enabled}
                  onChange={(event) => setAmount(event.target.value)}
                />
              </label>
              <label className="auth-field" style={{ maxWidth: 120 }}>
                <span>Currency</span>
                <select
                  value={currency}
                  disabled={!enabled}
                  onChange={(event) => setCurrency(event.target.value)}
                >
                  <option value="">—</option>
                  {ALLOCATION_CURRENCIES.map((token) => (
                    <option key={token} value={token}>
                      {token}
                    </option>
                  ))}
                </select>
              </label>
              <label className="auth-field" style={{ maxWidth: 260 }}>
                <span>Compounding mode</span>
                <select value={mode} disabled={!enabled} onChange={(event) => setMode(event.target.value)}>
                  <option value="">—</option>
                  {COMPOUNDING_MODES.map((token) => (
                    <option key={token} value={token}>
                      {COMPOUNDING_MODE_LABELS[token] ?? token}
                    </option>
                  ))}
                </select>
              </label>
              <label className="auth-field" style={{ maxWidth: 160 }}>
                <span>Reserve cash %</span>
                <input
                  className="auth-input"
                  value={reserve}
                  placeholder="e.g. 10"
                  disabled={!enabled}
                  onChange={(event) => setReserve(event.target.value)}
                />
              </label>
            </div>
            {/* Portfolio-level rules (doc 13 §8.4, cross-item). Both optional —
                blank = no cap / keep separate (the pre-rules behaviour). The
                server validates and pre-discloses the NET V1 downgrade as an
                inline warning, rendered verbatim below. */}
            <div className="section-title-upper" style={{ marginTop: 12 }}>
              Portfolio rules
            </div>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
              <label className="auth-field" style={{ maxWidth: 200 }}>
                <span>Max total exposure %</span>
                <input
                  className="auth-input"
                  value={maxExposure}
                  placeholder="e.g. 150 (blank = no cap)"
                  disabled={!enabled}
                  onChange={(event) => setMaxExposure(event.target.value)}
                />
              </label>
              <label className="auth-field" style={{ maxWidth: 320 }}>
                <span>Conflicting signals (same instrument)</span>
                <select
                  value={conflictPolicy}
                  disabled={!enabled}
                  onChange={(event) => setConflictPolicy(event.target.value)}
                >
                  <option value="">— (keep separate)</option>
                  {CONFLICT_POLICIES.map((token) => (
                    <option key={token} value={token}>
                      {CONFLICT_POLICY_LABELS[token] ?? token}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>

          {/* Card 2 — EQUITY ALLOCATION (per-item sleeves + Add Item picker). */}
          <div className="portfolio-card">
            <div className="section-title-upper">2. Equity allocation</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <EntriesTable
                entries={entries}
                onChange={setEntries}
                disabled={!enabled}
                derived={previewDerived}
              />
              <CandidatePicker
                candidates={candidates}
                totalCandidates={data.candidate_items.length}
                disabled={!enabled}
                onAdd={(candidate) =>
                  setEntries((previous) => [
                    ...previous,
                    {
                      composition_item_id: candidate.composition_item_id,
                      item_type: candidate.item_type,
                      active: true,
                      share: "",
                    },
                  ])
                }
              />
            </div>
          </div>

          {/* Card 3 — CALCULATION PREVIEW (server-derived, never recomputed
              client-side; sourced from the latest Save or Validate result). */}
          <div className="portfolio-card">
            <div className="section-title-upper">3. Calculation preview</div>
            {!enabled ? (
              <p className="alloc-muted">Not in use.</p>
            ) : previewDerived ? (
              <>
                <CalculationPreview derived={previewDerived} />
                <AllocationExampleText derived={previewDerived} />
              </>
            ) : (
              <EmptyState
                glyph="Σ"
                title="No calculation yet"
                description="Save the draft or run Validate below to see derived amounts."
              />
            )}
          </div>

          {/* Card 4 — ALLOCATION CHECK (immutable validation report; each run
              mints a new report id, §11.1 — nothing here is auto-computed). */}
          <div className="portfolio-card">
            <div className="section-title-upper">4. Allocation check</div>
            {!enabled ? (
              <StatusBadge
                tone={allocationStateTone("NOT_SELECTED")}
                label={allocationStateLabel("NOT_SELECTED")}
              />
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                  <button type="button" className="btn" disabled={validatePending} onClick={onValidate}>
                    {validatePending ? "Validating…" : "Validate saved draft"}
                  </button>
                  <span style={{ fontSize: 12, color: "var(--text-dim)" }}>
                    Validates the last SAVED draft, not unsaved edits.
                  </span>
                </div>
                {validateError ? <InlineError message={validateError} /> : null}
                {validateReport ? (
                  <>
                    <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                      <StatusBadge
                        tone={allocationStateTone(validateReport.state)}
                        label={allocationStateLabel(validateReport.state)}
                      />
                      <span style={{ fontSize: 12, color: "var(--text-dim)" }}>
                        report <code>{validateReport.validation_report_id}</code>
                      </span>
                      {validateReport.config_hash ? (
                        <span style={{ fontSize: 12, color: "var(--text-dim)" }}>
                          config <code>{validateReport.config_hash}</code>
                        </span>
                      ) : null}
                    </div>
                    <IssuesTable issues={validateReport.issues} emptyText="No blockers or warnings." />
                  </>
                ) : (
                  <EmptyState
                    glyph="?"
                    title="Not yet checked"
                    description="Run Validate to see whether this allocation is ready for a backtest."
                  />
                )}
              </div>
            )}
          </div>
        </div>

        {/* Outside the disabled workspace — saving "off" is a normal action. */}
        <div>
          <button
            type="button"
            className="btn btn-primary"
            disabled={saving}
            onClick={() => onSave(buildInput())}
          >
            {saving ? "Saving…" : "Save draft"}
          </button>
        </div>
      </div>
    </section>
  );
}

function CalculationPreview({ derived }: { derived: DerivedAmounts }) {
  return (
    <>
      <dl className="kv">
        <dt>Portfolio initial capital</dt>
        <dd>
          {derived.portfolio_initial_capital}
          {derived.currency ? ` ${derived.currency}` : ""}
        </dd>
        <dt>Reserved cash</dt>
        <dd>{derived.reserved_cash}</dd>
        <dt>Capital available</dt>
        <dd>{derived.capital_available}</dd>
        <dt>Total allocated</dt>
        <dd>{derived.total_allocated}</dd>
        <dt>Unallocated</dt>
        <dd>{derived.unallocated}</dd>
      </dl>
      <p className="alloc-muted" style={{ marginTop: 8 }}>
        From the most recent Save or Validate — not recalculated as you type.
      </p>
    </>
  );
}

// Live example line (mockup #allocationExampleText). Built from the SERVER
// derivation's first active sleeve — the sleeve capital and share are rendered
// verbatim, never recomputed client-side (doc 13 §8.3). With no active sleeve
// yet, the mockup's neutral placeholder stands in.
function AllocationExampleText({ derived }: { derived: DerivedAmounts }) {
  const sleeve = derived.sleeves[0];
  if (!sleeve) {
    return (
      <p className="portfolio-allocation-note">
        Allocation preview appears here when shared Equity Allocation is enabled.
      </p>
    );
  }
  return (
    <p className="portfolio-allocation-note">
      <b>Example:</b> <code>{sleeve.composition_item_id}</code> gets{" "}
      {sleeve.equity_share_percent}% of the shared pool:{" "}
      {sleeveCapitalText(sleeve, derived.currency)}. Position Sizing uses this allocated capital as
      its base.
    </p>
  );
}

// Per-item equity sleeve rows (mockup Card 2 "2. EQUITY ALLOCATION" — the
// Active | Item | Type | Equity Share | Capital | Sizing Base grid). The Item
// column carries composition_item_id (the wire binding key, §8.2) and Type its
// server-derived kind; the Capital column shows the server-DERIVED per-sleeve
// amount verbatim (never recomputed here), and Sizing Base is the fixed
// "Allocation" base the mockup renders for every allocated sleeve.
function EntriesTable({
  entries,
  onChange,
  disabled,
  derived,
}: {
  entries: EntryRow[];
  onChange: (next: EntryRow[]) => void;
  disabled: boolean;
  derived: DerivedAmounts | null;
}) {
  if (entries.length === 0) {
    return (
      <EmptyState
        glyph="◦"
        title="No allocation entries yet"
        description="Add a composition item below to give it a capital sleeve."
      />
    );
  }
  const sleeveByItem = new Map(
    (derived?.sleeves ?? []).map((sleeve) => [sleeve.composition_item_id, sleeve]),
  );
  const update = (id: string, patch: Partial<EntryRow>) =>
    onChange(entries.map((row) => (row.composition_item_id === id ? { ...row, ...patch } : row)));
  return (
    <table className="metrics-table">
      <thead>
        <tr>
          <th>Active</th>
          <th>Item</th>
          <th>Type</th>
          <th>Equity share %</th>
          <th>Capital</th>
          <th>Sizing base</th>
          <th />
        </tr>
      </thead>
      <tbody>
        {entries.map((row) => (
          <tr key={row.composition_item_id}>
            <td>
              <input
                type="checkbox"
                aria-label={`active ${row.composition_item_id}`}
                checked={row.active}
                disabled={disabled}
                onChange={(event) => update(row.composition_item_id, { active: event.target.checked })}
              />
            </td>
            <td>
              <code>{row.composition_item_id}</code>
            </td>
            <td>{itemTypeLabel(row.item_type)}</td>
            <td>
              <input
                aria-label={`share ${row.composition_item_id}`}
                value={row.share}
                style={{ maxWidth: 100 }}
                disabled={disabled}
                onChange={(event) => update(row.composition_item_id, { share: event.target.value })}
              />
            </td>
            <td>
              {/* Server-derived sleeve capital, verbatim; EM_DASH until a Save
                  or Validate has computed one (never recomputed client-side). */}
              {sleeveCapitalText(sleeveByItem.get(row.composition_item_id), derived?.currency ?? null)}
            </td>
            <td>Allocation</td>
            <td>
              {/* Removal is applied by the explicit Save PUT — never silently (§14#9). */}
              <button
                type="button"
                className="btn btn-ghost"
                disabled={disabled}
                onClick={() =>
                  onChange(entries.filter((r) => r.composition_item_id !== row.composition_item_id))
                }
              >
                Remove
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function CandidatePicker({
  candidates,
  totalCandidates,
  disabled,
  onAdd,
}: {
  candidates: AllocationCandidate[];
  totalCandidates: number;
  disabled: boolean;
  onAdd: (candidate: AllocationCandidate) => void;
}) {
  if (candidates.length === 0) {
    return (
      <div>
        <h4 style={{ margin: "0 0 8px" }}>+ Add item</h4>
        <EmptyState
          glyph="◦"
          title={totalCandidates === 0 ? "No compatible items" : "Every item is already allocated"}
          description={
            totalCandidates === 0
              ? "No compatible Mainboard items are available for allocation. Add a Strategy, Trading Signal, or Trade Log item to the composition first."
              : "Every compatible item in this composition already has an allocation row. Remove an existing row to add a different one, or change the Mainboard composition."
          }
        />
      </div>
    );
  }
  return (
    <div>
      <h4 style={{ margin: "0 0 8px" }}>+ Add item</h4>
      <p className="alloc-muted" style={{ marginBottom: 8 }}>
        Choose a Mainboard item without an allocation row in this composition. Strategy, Trading
        Signal, and Trade Log items are not separate Package types — they simply receive a capital
        sleeve for this run.
      </p>
      <ul style={{ margin: 0, paddingLeft: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 6 }}>
        {candidates.map((candidate) => (
          <li key={candidate.composition_item_id} style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <code>{candidate.composition_item_id}</code>
            <span style={{ fontSize: 12, color: "var(--text-dim)" }}>
              {candidate.item_type}
              {candidate.display_label_override ? ` · ${candidate.display_label_override}` : ""}
              {candidate.is_enabled ? "" : " · disabled on Mainboard"}
            </span>
            <button
              type="button"
              className="btn btn-ghost"
              disabled={disabled}
              onClick={() => onAdd(candidate)}
            >
              Add
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Save result (inline issues from the PUT return — Card 3 covers the derived
// amounts, so this stays focused on the save confirmation + inline issues)
// ---------------------------------------------------------------------------

function SaveResultCard({ result }: { result: SaveDraftResult }) {
  return (
    <section className="card" style={{ marginTop: 18 }} aria-labelledby="alloc-saved-h">
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h3 id="alloc-saved-h" style={{ margin: 0 }}>
          Draft saved
        </h3>
        <StatusBadge tone="ok" label={`rv ${result.row_version}`} />
        <span style={{ fontSize: 12, color: "var(--text-dim)" }}>
          fingerprint <code>{result.draft_fingerprint}</code>
        </span>
      </div>
      {result.readiness_invalidated ? (
        <p style={{ fontSize: 13, color: "var(--warn)", margin: "10px 0 0" }}>
          Any prior Ready Check report no longer reflects this draft — re-run the Ready Check.
        </p>
      ) : null}
      <div style={{ marginTop: 12 }}>
        <IssuesTable issues={result.inline_issues} emptyText="No inline issues." />
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Sync-From-Mainboard preview (non-destructive Flow D)
// ---------------------------------------------------------------------------

function SyncCard({
  pending,
  error,
  preview,
  onRun,
}: {
  pending: boolean;
  error: string | null;
  preview: SyncPreview | null;
  onRun: () => void;
}) {
  return (
    <section className="card" style={{ marginTop: 18 }} aria-labelledby="alloc-sync-h">
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h3 id="alloc-sync-h" style={{ margin: 0 }}>
          Sync from Mainboard
        </h3>
        <button type="button" className="btn" disabled={pending} onClick={onRun}>
          {pending ? "Previewing…" : "Sync From Mainboard"}
        </button>
      </div>
      <p style={{ fontSize: 12, color: "var(--text-dim)", margin: "8px 0 0" }}>
        Non-destructive preview of the saved entries against the current composition. Nothing is
        applied here — removals take effect only through an explicit Save of the merged entries.
      </p>
      {error ? <InlineError message={error} /> : null}
      {preview ? (
        <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 10 }}>
          {preview.requires_confirmation ? (
            <p role="alert" className="alloc-confirm-box">
              Some planned entries no longer exist on the Mainboard — removing them is destructive
              and requires an explicit Save to confirm.
            </p>
          ) : null}
          <SyncEntryList label="Retained" entries={preview.retained} />
          <SyncEntryList label="Missing from composition" entries={preview.missing} />
          <div>
            <h4 style={{ margin: "0 0 6px" }}>New candidates ({preview.new_candidates.length})</h4>
            {preview.new_candidates.length === 0 ? (
              <p style={{ margin: 0, fontSize: 13, color: "var(--text-dim)" }}>{EM_DASH}</p>
            ) : (
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13 }}>
                {preview.new_candidates.map((candidate) => (
                  <li key={candidate.composition_item_id}>
                    <code>{candidate.composition_item_id}</code> · {candidate.item_type}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function SyncEntryList({ label, entries }: { label: string; entries: AllocationEntry[] }) {
  return (
    <div>
      <h4 style={{ margin: "0 0 6px" }}>
        {label} ({entries.length})
      </h4>
      {entries.length === 0 ? (
        <p style={{ margin: 0, fontSize: 13, color: "var(--text-dim)" }}>{EM_DASH}</p>
      ) : (
        <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13 }}>
          {entries.map((entry) => (
            <li key={entry.entry_id}>
              <code>{entry.composition_item_id}</code> · {entry.item_type} ·{" "}
              {entry.active ? "active" : "inactive"}
              {entry.equity_share_percent !== null ? ` · ${entry.equity_share_percent}%` : ""}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Plan revision (immutable freeze of a blocker-free enabled draft, §8.5)
// ---------------------------------------------------------------------------

function RevisionCard({
  data,
  pending,
  error,
  result,
  onRun,
}: {
  data: AllocationDraftResponse;
  pending: boolean;
  error: string | null;
  result: RevisionResult | null;
  onRun: () => void;
}) {
  return (
    <section className="card" style={{ marginTop: 18 }} aria-labelledby="alloc-revision-h">
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h3 id="alloc-revision-h" style={{ margin: 0 }}>
          Plan revision
        </h3>
        <button type="button" className="btn" disabled={pending} onClick={onRun}>
          {pending ? "Creating…" : "Create plan revision"}
        </button>
        <span style={{ fontSize: 12, color: "var(--text-dim)" }}>
          current: {data.current_revision_id ? <code>{data.current_revision_id}</code> : "none"}
        </span>
      </div>
      <p style={{ fontSize: 12, color: "var(--text-dim)", margin: "8px 0 0" }}>
        Freezes the saved draft into an immutable revision. The server requires shared mode
        (enabled) and a blocker-free validation — denials render verbatim.
      </p>
      {error ? <InlineError message={error} /> : null}
      {result ? (
        <dl className="kv" style={{ marginTop: 12 }}>
          <dt>Revision</dt>
          <dd>
            <code>{result.plan_revision_id}</code> (no. {result.revision_no})
          </dd>
          <dt>Config hash</dt>
          <dd>
            <code>{result.config_hash}</code>
          </dd>
          <dt>Draft rv</dt>
          <dd>{result.row_version}</dd>
        </dl>
      ) : null}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Shared render helpers (issues verbatim + server-derived amounts, never
// recomputed client-side)
// ---------------------------------------------------------------------------

function IssuesTable({ issues, emptyText }: { issues: AllocationIssue[]; emptyText: string }) {
  if (issues.length === 0) {
    return <EmptyState glyph="✓" title={emptyText} description="" />;
  }
  return (
    <table className="metrics-table">
      <thead>
        <tr>
          <th>Severity</th>
          <th>Code</th>
          <th>Detail</th>
        </tr>
      </thead>
      <tbody>
        {issues.map((issue, index) => (
          <tr key={`${issue.code}-${issue.composition_item_id ?? issue.field ?? index}`}>
            <td>
              <StatusBadge tone={severityTone(issue.severity)} label={issue.severity} />
            </td>
            <td>
              <code>{issue.code}</code>
            </td>
            <td>
              <div>{issue.message}</div>
              {issue.field ? (
                <div style={{ fontSize: 12, color: "var(--text-dim)" }}>{issue.field}</div>
              ) : null}
              {issue.composition_item_id ? (
                <div style={{ fontSize: 12, color: "var(--text-dim)" }}>
                  <code>{issue.composition_item_id}</code>
                </div>
              ) : null}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
