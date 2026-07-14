import { useState } from "react";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { StatusBadge } from "@/components/StatusBadge";
import {
  ALLOCATION_CURRENCIES,
  COMPOUNDING_MODES,
  COMPOUNDING_MODE_LABELS,
  type AllocationCandidate,
  type AllocationDraftInput,
  type AllocationDraftResponse,
  type AllocationEntry,
  type AllocationIssue,
  type AllocationValidationReport,
  type DerivedAmounts,
  type RevisionResult,
  type SaveDraftResult,
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

// A local editor row. `share` keeps the raw text so a partially-typed decimal
// is never coerced client-side — the server parses money/percent strings
// (doc 13 §13) and its validation errors render verbatim.
interface EntryRow {
  composition_item_id: string;
  item_type: string;
  active: boolean;
  share: string;
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
        ) : null}
      </section>

      {compositionId !== null ? (
        <>
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
                />
                {save.isError ? (
                  <div className="card" style={{ marginTop: 18 }}>
                    <p role="alert" style={{ color: "var(--down)", margin: 0 }}>
                      {mutationErrorText(save.error)}
                    </p>
                  </div>
                ) : null}
                {save.data ? <SaveResultCard result={save.data} /> : null}
                <ValidateCard
                  pending={validate.isPending}
                  error={validate.isError ? mutationErrorText(validate.error) : null}
                  report={validate.data ?? null}
                  onRun={() => validate.mutate({ compositionId })}
                />
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
        </>
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
}: {
  data: AllocationDraftResponse;
  saving: boolean;
  onSave: (draft: AllocationDraftInput) => void;
}) {
  const [enabled, setEnabled] = useState(data.draft.enabled);
  const [amount, setAmount] = useState(data.draft.initial_capital?.amount ?? "");
  const [currency, setCurrency] = useState(data.draft.initial_capital?.currency ?? "");
  const [mode, setMode] = useState(data.draft.compounding_mode ?? "");
  const [reserve, setReserve] = useState(data.draft.reserve_cash_percent ?? "");
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
    entries: entries.map((entry) => ({
      composition_item_id: entry.composition_item_id,
      active: entry.active,
      equity_share_percent: entry.share.trim() !== "" ? entry.share.trim() : null,
    })),
  });

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
            <label> wraps the checkbox so its accessible name stays the heading. */}
        <label className="mode-toggle">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(event) => setEnabled(event.target.checked)}
          />
          <div>
            <b>USE EQUITY ALLOCATION FOR THIS BACKTEST</b>
            <span>
              When enabled, the shared capital pool and equity shares below control every active
              Strategy, Trading Signal and Trade Log. When disabled, each item runs with its own
              Initial Capital.
            </span>
          </div>
        </label>

        {/* v18 mockup card 1 — SHARED CAPITAL POOL. */}
        <div className="portfolio-card">
          <div className="section-title-upper">1. Shared capital pool</div>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            <label className="auth-field" style={{ maxWidth: 180 }}>
              <span>Initial capital</span>
              <input
                className="auth-input"
                value={amount}
                placeholder="e.g. 10000"
                onChange={(event) => setAmount(event.target.value)}
              />
            </label>
            <label className="auth-field" style={{ maxWidth: 120 }}>
              <span>Currency</span>
              <select value={currency} onChange={(event) => setCurrency(event.target.value)}>
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
              <select value={mode} onChange={(event) => setMode(event.target.value)}>
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
                onChange={(event) => setReserve(event.target.value)}
              />
            </label>
          </div>
        </div>

        {/* v18 mockup card 2 — EQUITY ALLOCATION (per-item sleeves). */}
        <div className="portfolio-card">
          <div className="section-title-upper">2. Equity allocation</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <EntriesTable entries={entries} onChange={setEntries} />
            <CandidatePicker
              candidates={candidates}
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

function EntriesTable({
  entries,
  onChange,
}: {
  entries: EntryRow[];
  onChange: (next: EntryRow[]) => void;
}) {
  if (entries.length === 0) {
    return (
      <p style={{ margin: 0, fontSize: 13, color: "var(--text-dim)" }}>
        No allocation entries yet — add composition items below.
      </p>
    );
  }
  const update = (id: string, patch: Partial<EntryRow>) =>
    onChange(entries.map((row) => (row.composition_item_id === id ? { ...row, ...patch } : row)));
  return (
    <table className="metrics-table">
      <thead>
        <tr>
          <th>Item</th>
          <th>Type</th>
          <th>Active</th>
          <th>Equity share %</th>
          <th />
        </tr>
      </thead>
      <tbody>
        {entries.map((row) => (
          <tr key={row.composition_item_id}>
            <td>
              <code>{row.composition_item_id}</code>
            </td>
            <td>{row.item_type}</td>
            <td>
              <input
                type="checkbox"
                aria-label={`active ${row.composition_item_id}`}
                checked={row.active}
                onChange={(event) => update(row.composition_item_id, { active: event.target.checked })}
              />
            </td>
            <td>
              <input
                aria-label={`share ${row.composition_item_id}`}
                value={row.share}
                style={{ maxWidth: 100 }}
                onChange={(event) => update(row.composition_item_id, { share: event.target.value })}
              />
            </td>
            <td>
              {/* Removal is applied by the explicit Save PUT — never silently (§14#9). */}
              <button
                type="button"
                className="btn btn-ghost"
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
  onAdd,
}: {
  candidates: AllocationCandidate[];
  onAdd: (candidate: AllocationCandidate) => void;
}) {
  if (candidates.length === 0) return null;
  return (
    <div>
      <h4 style={{ margin: "0 0 8px" }}>Unrepresented composition items</h4>
      <ul style={{ margin: 0, paddingLeft: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 6 }}>
        {candidates.map((candidate) => (
          <li key={candidate.composition_item_id} style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <code>{candidate.composition_item_id}</code>
            <span style={{ fontSize: 12, color: "var(--text-dim)" }}>
              {candidate.item_type}
              {candidate.display_label_override ? ` · ${candidate.display_label_override}` : ""}
              {candidate.is_enabled ? "" : " · disabled on Mainboard"}
            </span>
            <button type="button" className="btn btn-ghost" onClick={() => onAdd(candidate)}>
              Add
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Save result (inline issues + derived amounts from the PUT return)
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
      {result.derived ? <DerivedTable derived={result.derived} /> : null}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Validate (immutable report — a rerun is a NEW report id, §11.1)
// ---------------------------------------------------------------------------

function ValidateCard({
  pending,
  error,
  report,
  onRun,
}: {
  pending: boolean;
  error: string | null;
  report: AllocationValidationReport | null;
  onRun: () => void;
}) {
  return (
    <section className="card" style={{ marginTop: 18 }} aria-labelledby="alloc-validate-h">
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h3 id="alloc-validate-h" style={{ margin: 0 }}>
          Validation
        </h3>
        <button type="button" className="btn" disabled={pending} onClick={onRun}>
          {pending ? "Validating…" : "Validate saved draft"}
        </button>
      </div>
      <p style={{ fontSize: 12, color: "var(--text-dim)", margin: "8px 0 0" }}>
        Validates the last SAVED draft (not unsaved edits). Each run produces a new immutable
        report; no plan revision or run is created.
      </p>
      {error ? (
        <p role="alert" style={{ color: "var(--down)", margin: "10px 0 0" }}>
          {error}
        </p>
      ) : null}
      {report ? (
        <div style={{ marginTop: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
            <StatusBadge
              tone={allocationStateTone(report.state)}
              label={allocationStateLabel(report.state)}
            />
            <span style={{ fontSize: 12, color: "var(--text-dim)" }}>
              report <code>{report.validation_report_id}</code>
            </span>
            {report.config_hash ? (
              <span style={{ fontSize: 12, color: "var(--text-dim)" }}>
                config <code>{report.config_hash}</code>
              </span>
            ) : null}
          </div>
          <div style={{ marginTop: 12 }}>
            <IssuesTable issues={report.issues} emptyText="No blockers or warnings." />
          </div>
          {report.derived ? <DerivedTable derived={report.derived} /> : null}
        </div>
      ) : null}
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
          {pending ? "Previewing…" : "Preview sync"}
        </button>
      </div>
      <p style={{ fontSize: 12, color: "var(--text-dim)", margin: "8px 0 0" }}>
        Non-destructive preview of the saved entries against the current composition. Nothing is
        applied here — removals take effect only through an explicit Save of the merged entries.
      </p>
      {error ? (
        <p role="alert" style={{ color: "var(--down)", margin: "10px 0 0" }}>
          {error}
        </p>
      ) : null}
      {preview ? (
        <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 10 }}>
          {preview.requires_confirmation ? (
            <p role="alert" style={{ color: "var(--warn)", margin: 0, fontSize: 13 }}>
              Some planned entries no longer exist on the Mainboard — removing them is destructive
              and requires an explicit Save.
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
      {error ? (
        <p role="alert" style={{ color: "var(--down)", margin: "10px 0 0" }}>
          {error}
        </p>
      ) : null}
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

function DerivedTable({ derived }: { derived: DerivedAmounts }) {
  return (
    <div style={{ marginTop: 12 }}>
      <h4 style={{ margin: "0 0 8px" }}>
        Derived amounts{derived.currency ? ` (${derived.currency})` : ""}
      </h4>
      <dl className="kv">
        <dt>Initial capital</dt>
        <dd>{derived.portfolio_initial_capital}</dd>
        <dt>Reserved cash</dt>
        <dd>{derived.reserved_cash}</dd>
        <dt>Capital available</dt>
        <dd>{derived.capital_available}</dd>
        <dt>Total allocated</dt>
        <dd>{derived.total_allocated}</dd>
        <dt>Unallocated</dt>
        <dd>{derived.unallocated}</dd>
        <dt>Active share total</dt>
        <dd>{derived.active_share_total}%</dd>
      </dl>
      {derived.sleeves.length > 0 ? (
        <table className="metrics-table" style={{ marginTop: 10 }}>
          <thead>
            <tr>
              <th>Sleeve</th>
              <th>Share %</th>
              <th>Initial sleeve capital</th>
            </tr>
          </thead>
          <tbody>
            {derived.sleeves.map((sleeve) => (
              <tr key={sleeve.composition_item_id}>
                <td>
                  <code>{sleeve.composition_item_id}</code>
                </td>
                <td>{sleeve.equity_share_percent}</td>
                <td>{sleeve.initial_sleeve_capital}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </div>
  );
}
