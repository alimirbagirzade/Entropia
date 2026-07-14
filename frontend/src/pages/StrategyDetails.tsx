import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { StatusBadge } from "@/components/StatusBadge";
import { StrategyConfigForm } from "@/components/StrategyConfigForm";
import { StrategyGraphForm } from "@/components/StrategyGraphForm";
import { ApiError } from "@/lib/apiClient";
import { EM_DASH, formatUtc, useDefaultMainboard } from "@/lib/backtest";
import { useRationaleFamilies } from "@/lib/createPackage";
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

// Failures surface the backend canonical envelope verbatim — the client never
// invents strategy-domain messages. A stale OCC token arrives here as 409
// STRATEGY_DRAFT_CONFLICT (AT-19); a blocked save as a 422 whose details carry
// the compiler issue list (rendered by IssueDetails below).
function mutationErrorText(error: unknown): string {
  if (error instanceof ApiError) return `${error.code}: ${error.message}`;
  return error instanceof Error ? error.message : "Request failed.";
}

const preStyle = {
  whiteSpace: "pre-wrap",
  overflowX: "auto",
  background: "var(--bg-elev-2)",
  padding: 12,
  borderRadius: 8,
  fontSize: 13,
  margin: 0,
} as const;

// Strategy Details (Stage 3b, doc 02 §7–§9). The Strategy editor draft
// workflow: create a root+draft, edit the draft payload, run the pure
// validate pass, save immutable revisions (auto-re-pinning attached Mainboard
// items), and browse the revision history — the editor path that feeds
// attach → Ready Check → RUN. URL modes: ?draft= (durable editor handle —
// the backend exposes NO root→draft lookup, so losing this URL means the
// draft is only reachable again via a fresh create), ?strategy= (root header
// + revisions, discoverable from the default Mainboard), ?revision=
// (immutable deep-link).
export function StrategyDetails() {
  const [searchParams, setSearchParams] = useSearchParams();
  const revisionParam = searchParams.get("revision");
  const strategyParam = searchParams.get("strategy");
  const draftParam = searchParams.get("draft");

  return (
    <>
      <h1 className="page-title">Strategy Details</h1>
      <p className="page-sub">
        Compose and edit your strategy draft, validate the config, and save immutable revisions —
        the editor path feeding Ready Check and RUN
      </p>

      {revisionParam !== null ? (
        <RevisionDetailCard revisionId={revisionParam} />
      ) : draftParam !== null ? (
        <DraftWorkbench draftId={draftParam} />
      ) : strategyParam !== null ? (
        <StrategyView rootId={strategyParam} />
      ) : (
        <>
          <CreateStrategyCard onCreated={(draftId) => setSearchParams({ draft: draftId })} />
          <AttachedStrategiesCard />
        </>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Create (POST /strategy-drafts — no OCC, fresh Idempotency-Key)
// ---------------------------------------------------------------------------

function CreateStrategyCard({ onCreated }: { onCreated: (draftId: string) => void }) {
  const [name, setName] = useState("");
  const [familyId, setFamilyId] = useState("");
  const families = useRationaleFamilies(null);
  const create = useCreateStrategyDraft();

  return (
    <section className="card" aria-labelledby="strat-create-h">
      <h3 id="strat-create-h" style={{ marginTop: 0 }}>
        Create strategy
      </h3>
      <p className="cp-note">
        Creates the strategy root and its mutable editor draft. No revision exists until the first
        Save — an unsaved draft cannot enter Ready Check or RUN (AT-01). Keep the editor URL: the
        draft id is the only handle to the draft.
      </p>
      <form
        className="cp-form"
        onSubmit={(event) => {
          event.preventDefault();
          create.mutate(
            {
              displayName: name,
              rationaleFamilyId: familyId === "" ? null : familyId,
            },
            { onSuccess: (result) => onCreated(result.draft_id) },
          );
        }}
      >
        <label className="cp-field">
          <span>Display name</span>
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="e.g. Momentum breakout A"
            required
          />
        </label>
        <label className="cp-field">
          <span>Rationale family (optional)</span>
          <select value={familyId} onChange={(event) => setFamilyId(event.target.value)}>
            <option value="">None</option>
            {(families.data?.data ?? []).map((family) => (
              <option key={family.entity_id} value={family.entity_id}>
                {family.display_name}
              </option>
            ))}
          </select>
        </label>
        <div className="cp-field cp-wide">
          <button className="btn btn-primary" type="submit" disabled={create.isPending}>
            {create.isPending ? "Creating…" : "Create draft"}
          </button>
        </div>
      </form>
      {create.isError ? (
        <p role="alert" style={{ color: "var(--down)", marginBottom: 0 }}>
          {mutationErrorText(create.error)}
        </p>
      ) : null}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Discovery: strategy items attached to the default Mainboard (RUN/Ready-Check
// composition pattern). Only ATTACHED strategies appear here — a created but
// never-attached strategy stays reachable through its create-time ?draft= URL.
// ---------------------------------------------------------------------------

function AttachedStrategiesCard() {
  const mainboard = useDefaultMainboard();
  const strategyItems = (mainboard.data?.items ?? []).filter(
    (item) => item.item_kind === "strategy",
  );

  return (
    <section className="card" style={{ marginTop: 18 }} aria-labelledby="strat-attached-h">
      <h3 id="strat-attached-h" style={{ marginTop: 0 }}>
        Attached strategies
      </h3>
      {mainboard.isLoading ? (
        <Loading />
      ) : mainboard.isError ? (
        <ErrorState error={mainboard.error} onRetry={() => void mainboard.refetch()} />
      ) : strategyItems.length === 0 ? (
        <EmptyState
          title="No strategy items on the default Mainboard"
          description="Strategies appear here once attached to the composition. A fresh draft is reached through its editor URL."
        />
      ) : (
        <table className="metrics-table">
          <thead>
            <tr>
              <th>Label</th>
              <th>Strategy root</th>
              <th>Pinned revision</th>
              <th>Enabled</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {strategyItems.map((item) => (
              <tr key={item.item_id}>
                <td>{item.display_label_override ?? EM_DASH}</td>
                <td>
                  <code>{item.work_object_root_id}</code>
                </td>
                <td>{item.pinned_revision_id ? <code>{item.pinned_revision_id}</code> : EM_DASH}</td>
                <td>{item.is_enabled ? "yes" : "no"}</td>
                <td>
                  <Link to={`/strategy?strategy=${encodeURIComponent(item.work_object_root_id)}`}>
                    View
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Draft workbench (?draft=). Mutations live HERE so their results survive the
// PayloadEditor remount when a patch/save bumps row_version (the Portfolio /
// FutureDev lesson).
// ---------------------------------------------------------------------------

function DraftWorkbench({ draftId }: { draftId: string }) {
  const draftQuery = useStrategyDraft(draftId);
  const patch = usePatchStrategyDraft();
  const validate = useValidateStrategyDraft();
  const save = useSaveStrategyRevision();
  const clear = useClearStrategyDraft();

  if (draftQuery.isLoading) {
    return (
      <div className="card">
        <Loading label="Loading strategy draft…" />
      </div>
    );
  }
  if (draftQuery.isError) {
    return (
      <div className="card">
        <ErrorState error={draftQuery.error} onRetry={() => void draftQuery.refetch()} />
      </div>
    );
  }
  const draft = draftQuery.data;
  if (!draft) return null;

  // A patch replaces the FULL draft payload under BODY-form OCC. Both the
  // structured form (covered flat sections overlaid) and the Advanced JSON
  // editor (raw full payload) flow through this same PATCH.
  const applyPayload = (payload: Record<string, unknown>) =>
    patch.mutate({ draftId, expectedRowVersion: draft.row_version, payload });

  return (
    <>
      <DraftHeaderCard draft={draft} />
      <StrategyConfigForm
        key={`form-${draft.row_version}`}
        payload={draft.payload}
        pending={patch.isPending}
        onApply={applyPayload}
      />
      <StrategyGraphForm
        key={`graph-${draft.row_version}`}
        payload={draft.payload}
        pending={patch.isPending}
        onApply={applyPayload}
      />
      <PayloadEditor key={draft.row_version} draft={draft} pending={patch.isPending} onApply={applyPayload} />
      {patch.isError ? (
        <MutationErrorCard error={patch.error} />
      ) : patch.data ? (
        <PatchResultCard result={patch.data} />
      ) : null}

      <DraftActionsCard
        draft={draft}
        validatePending={validate.isPending}
        savePending={save.isPending}
        clearPending={clear.isPending}
        onValidate={() => validate.mutate({ draftId })}
        onSave={() => save.mutate({ draftId, expectedRowVersion: draft.row_version })}
        onClear={() => clear.mutate({ draftId, expectedRowVersion: draft.row_version })}
      />
      {validate.isError ? <MutationErrorCard error={validate.error} /> : null}
      {validate.data ? <ValidateResultCard result={validate.data} /> : null}
      {save.isError ? <MutationErrorCard error={save.error} /> : null}
      {save.data ? <SaveResultCard result={save.data} /> : null}
      {clear.isError ? <MutationErrorCard error={clear.error} /> : null}
      {clear.data ? <ClearResultCard result={clear.data} /> : null}

      {draft.strategy_root_id !== null ? <StrategyView rootId={draft.strategy_root_id} /> : null}
    </>
  );
}

function DraftHeaderCard({ draft }: { draft: StrategyDraft }) {
  return (
    <section className="card" aria-labelledby="strat-draft-h">
      <h3 id="strat-draft-h" style={{ marginTop: 0 }}>
        Editor draft
      </h3>
      <dl className="kv">
        <dt>Draft</dt>
        <dd>
          <code>{draft.draft_id}</code>
        </dd>
        <dt>Strategy root</dt>
        <dd>
          {draft.strategy_root_id !== null ? <code>{draft.strategy_root_id}</code> : EM_DASH}
        </dd>
        <dt>Row version</dt>
        <dd>{draft.row_version}</dd>
        <dt>Unsaved changes</dt>
        <dd>{draft.is_dirty ? "yes (dirty)" : "no"}</dd>
        <dt>Last saved revision</dt>
        <dd>
          {draft.last_saved_revision_id !== null ? (
            <Link to={`/strategy?revision=${encodeURIComponent(draft.last_saved_revision_id)}`}>
              <code>{draft.last_saved_revision_id}</code>
            </Link>
          ) : (
            "never saved"
          )}
        </dd>
        <dt>Updated</dt>
        <dd>{formatUtc(draft.updated_at)}</dd>
      </dl>
    </section>
  );
}

// Remounts on every server head move via key={row_version} — the editor is
// always seeded from the latest server draft, never merged. The textarea is
// raw JSON: parse failures stay CLIENT-side (nothing is sent); the server
// compiler remains the only authority on config semantics. Since R6 the
// structured forms above cover the flat sections AND the full package graph
// (Entry / Exit Logic, Scaling, Restrictions), so this is a genuine expert
// FALLBACK — used for each block's advanced fields (parameter overrides,
// reference chains) and any future key not yet surfaced by a structured field.
function PayloadEditor({
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
    <section className="card" style={{ marginTop: 18 }} aria-labelledby="strat-payload-h">
      <h3 id="strat-payload-h" style={{ marginTop: 0 }}>
        Advanced (JSON) editor
      </h3>
      <p className="cp-note">
        Apply replaces the FULL draft payload (optimistic concurrency on row version{" "}
        {draft.row_version}). The structured forms above now cover the flat sections and the full
        package graph (Entry / Exit Logic, Scaling, Restrictions) — this is the fallback for each
        block&apos;s advanced fields (parameter overrides, reference chains) and any key not yet
        surfaced. Validation happens on the server — Validate / Save below.
      </p>
      <label className="cp-field cp-wide">
        <span>StrategyConfig payload</span>
        <textarea
          rows={14}
          value={text}
          onChange={(event) => setText(event.target.value)}
          spellCheck={false}
        />
      </label>
      <div style={{ marginTop: 10 }}>
        <button
          type="button"
          className="btn btn-primary"
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
    </section>
  );
}

function DraftActionsCard({
  draft,
  validatePending,
  savePending,
  clearPending,
  onValidate,
  onSave,
  onClear,
}: {
  draft: StrategyDraft;
  validatePending: boolean;
  savePending: boolean;
  clearPending: boolean;
  onValidate: () => void;
  onSave: () => void;
  onClear: () => void;
}) {
  const [confirmClear, setConfirmClear] = useState(false);

  return (
    <section className="card" style={{ marginTop: 18 }} aria-labelledby="strat-actions-h">
      <h3 id="strat-actions-h" style={{ marginTop: 0 }}>
        Draft actions
      </h3>
      <p className="cp-note">
        Validate is a pure compiler pass over the SERVER draft (apply unsaved edits first). Save
        freezes an immutable revision and re-pins attached Mainboard items — the prior Ready
        report goes STALE. Clear resets unsaved editor state only.
      </p>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        <button type="button" className="btn" disabled={validatePending} onClick={onValidate}>
          {validatePending ? "Validating…" : "Validate"}
        </button>
        <button type="button" className="btn btn-primary" disabled={savePending} onClick={onSave}>
          {savePending ? "Saving…" : "Save revision"}
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
              Cancel
            </button>
          </>
        ) : (
          <button type="button" className="btn" onClick={() => setConfirmClear(true)}>
            Clear draft…
          </button>
        )}
      </div>
    </section>
  );
}

// Renders the canonical envelope verbatim; a 422 save failure additionally
// carries the compiler issue list in error.details — shown as-is.
function MutationErrorCard({ error }: { error: unknown }) {
  const details = error instanceof ApiError ? error.details : [];
  return (
    <div className="card" style={{ marginTop: 18 }}>
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

function PatchResultCard({ result }: { result: PatchDraftResult }) {
  return (
    <section className="card" style={{ marginTop: 18 }}>
      <p style={{ margin: 0 }}>
        Payload applied — draft now at row version {result.row_version}
        {result.is_dirty ? " (unsaved changes pending Save)" : ""}.
      </p>
    </section>
  );
}

function ValidateResultCard({ result }: { result: ValidateDraftResult }) {
  return (
    <section className="card" style={{ marginTop: 18 }} aria-labelledby="strat-validate-h">
      <h3 id="strat-validate-h" style={{ marginTop: 0 }}>
        Validation result
      </h3>
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
    </section>
  );
}

function SaveResultCard({ result }: { result: SaveRevisionResult }) {
  return (
    <section className="card" style={{ marginTop: 18 }} aria-labelledby="strat-save-h">
      <h3 id="strat-save-h" style={{ marginTop: 0 }}>
        Revision saved
      </h3>
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
        <dt>Mirror revision</dt>
        <dd>
          <code>{result.mirror_revision_id}</code>
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
    </section>
  );
}

function ClearResultCard({ result }: { result: ClearDraftResult }) {
  return (
    <section className="card" style={{ marginTop: 18 }}>
      <p style={{ margin: 0 }}>
        Draft cleared — editor state reset (row version {result.row_version}). Saved revisions are
        untouched.
      </p>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Strategy root header + revision history (?strategy= or inline under a draft)
// ---------------------------------------------------------------------------

function StrategyView({ rootId }: { rootId: string }) {
  const strategy = useStrategy(rootId);
  const revisions = useStrategyRevisions(rootId);

  return (
    <>
      <section className="card" style={{ marginTop: 18 }} aria-labelledby="strat-root-h">
        <h3 id="strat-root-h" style={{ marginTop: 0 }}>
          Strategy
        </h3>
        {strategy.isLoading ? (
          <Loading />
        ) : strategy.isError ? (
          <ErrorState error={strategy.error} onRetry={() => void strategy.refetch()} />
        ) : strategy.data ? (
          <dl className="kv">
            <dt>Name</dt>
            <dd>{strategy.data.display_name}</dd>
            <dt>Root</dt>
            <dd>
              <code>{strategy.data.strategy_root_id}</code>
            </dd>
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
            <dt>Rationale family</dt>
            <dd>
              {strategy.data.rationale_family_id !== null ? (
                <code>{strategy.data.rationale_family_id}</code>
              ) : (
                EM_DASH
              )}
            </dd>
            <dt>Deletion state</dt>
            <dd>{strategy.data.deletion_state}</dd>
          </dl>
        ) : null}
      </section>

      <section className="card" style={{ marginTop: 18 }} aria-labelledby="strat-revisions-h">
        <h3 id="strat-revisions-h" style={{ marginTop: 0 }}>
          Revision history
        </h3>
        {revisions.isLoading ? (
          <Loading />
        ) : revisions.isError ? (
          <ErrorState error={revisions.error} onRetry={() => void revisions.refetch()} />
        ) : (revisions.data ?? []).length === 0 ? (
          <EmptyState
            title="No revisions yet"
            description="Save the draft to create the first immutable revision."
          />
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
                    <Link
                      to={`/strategy?revision=${encodeURIComponent(row.strategy_revision_id)}`}
                    >
                      View
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </>
  );
}

// ---------------------------------------------------------------------------
// Immutable revision deep-link (?revision=)
// ---------------------------------------------------------------------------

function RevisionDetailCard({ revisionId }: { revisionId: string }) {
  const revision = useStrategyRevision(revisionId);

  if (revision.isLoading) {
    return (
      <div className="card">
        <Loading label="Loading revision…" />
      </div>
    );
  }
  if (revision.isError) {
    return (
      <div className="card">
        <ErrorState error={revision.error} onRetry={() => void revision.refetch()} />
      </div>
    );
  }
  const data = revision.data;
  if (!data) return null;

  return (
    <>
      <section className="card" aria-labelledby="strat-rev-h">
        <h3 id="strat-rev-h" style={{ marginTop: 0 }}>
          Strategy revision #{data.revision_number}
        </h3>
        <dl className="kv">
          <dt>Revision</dt>
          <dd>
            <code>{data.strategy_revision_id}</code>
          </dd>
          <dt>Strategy root</dt>
          <dd>
            <Link to={`/strategy?strategy=${encodeURIComponent(data.strategy_root_id)}`}>
              <code>{data.strategy_root_id}</code>
            </Link>
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
          <dt>Lifecycle snapshot</dt>
          <dd>{data.lifecycle_snapshot ?? EM_DASH}</dd>
          <dt>Family snapshot</dt>
          <dd>{data.family_snapshot !== null ? <code>{data.family_snapshot}</code> : EM_DASH}</dd>
          <dt>Created</dt>
          <dd>{formatUtc(data.created_at)}</dd>
        </dl>
      </section>

      <section className="card" style={{ marginTop: 18 }} aria-labelledby="strat-refs-h">
        <h3 id="strat-refs-h" style={{ marginTop: 0 }}>
          Pinned references
        </h3>
        {data.references.length === 0 ? (
          <EmptyState title="No pinned references" />
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
      </section>

      <section className="card" style={{ marginTop: 18 }} aria-labelledby="strat-payload-view-h">
        <h3 id="strat-payload-view-h" style={{ marginTop: 0 }}>
          Canonical payload
        </h3>
        <pre style={preStyle}>{JSON.stringify(data.payload, null, 2)}</pre>
      </section>
    </>
  );
}
