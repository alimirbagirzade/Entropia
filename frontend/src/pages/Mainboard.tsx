import { useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "@/lib/apiClient";
import { Loading } from "@/components/Loading";
import { ErrorState } from "@/components/ErrorState";
import { StatusBadge } from "@/components/StatusBadge";
import {
  EXTERNAL_DRAFT_KINDS,
  itemKindLabel,
  readyStatusText,
  readyStatusTone,
  useAttachItem,
  useCreateSnapshot,
  useCreateWorkObject,
  useCreateWorkObjectRevision,
  useDefaultMainboard,
  usePatchItem,
  useSoftDeleteWorkObject,
  useStartExternalDraft,
  type ExternalDraft,
  type LatestResultSummary,
  type MainboardItem,
  type WorkObjectResult,
} from "@/lib/mainboard";

// The canonical error envelope is shown verbatim (code: message) — the page
// never interprets a server rejection.
function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return `${error.code}: ${error.message}`;
  return error instanceof Error ? error.message : "Request failed.";
}

const alertStyle = { color: "var(--down)", margin: "8px 0 0", fontSize: 13 } as const;
const noteStyle = { color: "var(--text-dim)", fontSize: 13 } as const;

// --------------------------------------------------------------------------- //
// Type-specific editor host (doc 01 §3.1 — the inline details host opens the   //
// Strategy Details or external-data details editor for the row's kind, NOT a   //
// generic technical panel). The real per-kind field contract lives on the      //
// dedicated editor page; the Mainboard row deep-links to it (presentation      //
// only — route paths and data hooks are unchanged).                            //
// --------------------------------------------------------------------------- //

interface ItemEditorSpec {
  editorLabel: string;
  hint: string;
}

const ITEM_EDITORS: Record<string, ItemEditorSpec> = {
  strategy: {
    editorLabel: "Strategy Details",
    hint: "Edit the entry/exit rules, indicators, and execution model in the Strategy Details editor. Save a new revision there, then pin it for this Mainboard below.",
  },
  trading_signal: {
    editorLabel: "Trading Signal",
    hint: "Open the Trading Signal workbench to upload a source, run its import, and append a normalized revision. Pin the revision for this Mainboard below.",
  },
  trade_log: {
    editorLabel: "Trade Log",
    hint: "Open the Trade Log workbench to import records and append a normalized revision. Pin the revision for this Mainboard below.",
  },
};

function itemEditor(kind: string): ItemEditorSpec {
  return ITEM_EDITORS[kind] ?? { editorLabel: itemKindLabel(kind), hint: "" };
}

// Deep-link to the row's real type-specific editor page. A strategy item opens
// its root header (revision history + editing); external items open their
// workbench by root. Identity always travels as the work-object root id, never
// the display label (§14 rule 3).
function editorPath(item: MainboardItem): string {
  const root = encodeURIComponent(item.work_object_root_id);
  if (item.item_kind === "trading_signal") return `/trading-signal?root=${root}`;
  if (item.item_kind === "trade_log") return `/trade-log?root=${root}`;
  return `/strategy?strategy=${root}`;
}

// --------------------------------------------------------------------------- //
// Per-item composition operations (doc 01 §5.2 / §7 / §9.3). Every mutation    //
// carries the item's row_version as the expected_row_version OCC token.        //
// --------------------------------------------------------------------------- //

function ItemRow({ item }: { item: MainboardItem }) {
  const [expanded, setExpanded] = useState(false);
  const [revisionInput, setRevisionInput] = useState("");
  const [labelInput, setLabelInput] = useState(item.display_label_override ?? "");
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const patch = usePatchItem();
  const del = useSoftDeleteWorkObject();
  const kindLabel = itemKindLabel(item.item_kind);
  const label = item.display_label_override ?? kindLabel;
  const editor = itemEditor(item.item_kind);
  const busy = patch.isPending || del.isPending;

  return (
    <div className="strategy-package">
      <div className={`strategy-row${expanded ? " open" : ""}`}>
        <span className="strategy-text">
          <strong>{label}</strong>
          <StatusBadge label={kindLabel} tone="neutral" />
          <StatusBadge
            label={item.is_enabled ? "Enabled" : "Disabled"}
            tone={item.is_enabled ? "ok" : "warn"}
          />
          <span style={noteStyle}>#{item.position_index}</span>
        </span>
        <button
          type="button"
          className="strategy-arrow"
          aria-expanded={expanded}
          aria-label={expanded ? `Collapse ${label}` : `Expand ${label}`}
          onClick={() => setExpanded((v) => !v)}
        >
          {expanded ? "▲" : "▼"}
        </button>
      </div>

      {expanded && (
        <div className="strategy-details" style={{ display: "grid", gap: 16 }}>
          {/* Type-specific editor entry (§3.1). The expand reveals the real     */}
          {/* {Strategy Details | external data} editor — not a raw technical     */}
          {/* dump — via a deep-link into that page's editing surface.            */}
          <section
            aria-label={`${editor.editorLabel} editor for ${label}`}
            style={{ display: "grid", gap: 8 }}
          >
            <strong>{editor.editorLabel} editor</strong>
            {editor.hint && <p style={noteStyle}>{editor.hint}</p>}
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <Link className="btn btn-primary" to={editorPath(item)}>
                Edit in {editor.editorLabel} →
              </Link>
              {item.item_kind === "strategy" && item.pinned_revision_id && (
                <Link
                  className="btn"
                  to={`/strategy?revision=${encodeURIComponent(item.pinned_revision_id)}`}
                >
                  View pinned revision
                </Link>
              )}
            </div>
          </section>

          {/* Mainboard-owned composition controls (§5.2 / §7). Pin / enable /    */}
          {/* reorder change the composition hash and make the Ready report stale.*/}
          <section
            aria-label={`Composition controls for ${label}`}
            style={{ display: "grid", gap: 14 }}
          >
            <strong>Composition controls</strong>
            <dl className="kv">
              <dt>Work object</dt>
              <dd>{item.work_object_root_id}</dd>
              <dt>Pinned revision</dt>
              <dd>{item.pinned_revision_id ?? "—"}</dd>
              <dt>Row version</dt>
              <dd>{item.row_version}</dd>
            </dl>

            {/* Pin a specific revision — "Use This Revision" (no latest resolution, L5). */}
            <div className="cp-field">
              <span>Pin revision</span>
              <p className="cp-note">
                This Mainboard currently uses revision {item.pinned_revision_id ?? "—"}. Update the
                pinned revision only when you want a new Ready Check and Backtest Run to use the newer
                definition.
              </p>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <input
                  aria-label={`Revision id for ${label}`}
                  value={revisionInput}
                  onChange={(e) => setRevisionInput(e.target.value)}
                  placeholder="wor_…"
                  style={{ flex: 1, minWidth: 200 }}
                />
                <button
                  type="button"
                  className="btn"
                  disabled={busy || revisionInput.trim() === ""}
                  onClick={() =>
                    patch.mutate({
                      itemId: item.item_id,
                      intent: "pin_revision",
                      expectedRowVersion: item.row_version,
                      revision_id: revisionInput.trim(),
                    })
                  }
                >
                  Use This Revision
                </button>
              </div>
            </div>

            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button
                type="button"
                className="btn"
                disabled={busy}
                onClick={() =>
                  patch.mutate({
                    itemId: item.item_id,
                    intent: "set_enabled",
                    expectedRowVersion: item.row_version,
                    is_enabled: !item.is_enabled,
                  })
                }
              >
                {item.is_enabled ? "Disable" : "Enable"}
              </button>
              <button
                type="button"
                className="btn"
                disabled={busy || item.position_index <= 0}
                onClick={() =>
                  patch.mutate({
                    itemId: item.item_id,
                    intent: "reorder",
                    expectedRowVersion: item.row_version,
                    position_index: item.position_index - 1,
                  })
                }
              >
                Move up
              </button>
              <button
                type="button"
                className="btn"
                disabled={busy}
                onClick={() =>
                  patch.mutate({
                    itemId: item.item_id,
                    intent: "reorder",
                    expectedRowVersion: item.row_version,
                    position_index: item.position_index + 1,
                  })
                }
              >
                Move down
              </button>
            </div>

            {/* Presentation-only display label override. */}
            <div className="cp-field">
              <span>Display label</span>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <input
                  aria-label={`Display label for ${label}`}
                  value={labelInput}
                  onChange={(e) => setLabelInput(e.target.value)}
                  style={{ flex: 1, minWidth: 200 }}
                />
                <button
                  type="button"
                  className="btn"
                  disabled={busy}
                  onClick={() =>
                    patch.mutate({
                      itemId: item.item_id,
                      intent: "set_label",
                      expectedRowVersion: item.row_version,
                      display_label_override: labelInput,
                    })
                  }
                >
                  Save label
                </button>
              </div>
            </div>

            {/* Type-specific soft delete (× action). Two-step confirmation. */}
            {confirmingDelete ? (
              <div
                role="alertdialog"
                aria-label={`Delete ${kindLabel}?`}
                style={{ border: "1px solid var(--down)", borderRadius: 4, padding: 12 }}
              >
                <strong>Delete {kindLabel}?</strong>
                <p style={{ margin: "6px 0", fontSize: 13 }}>
                  You are about to soft-delete “{label}”. It will be removed from the active Mainboard
                  and new selection lists. Existing Backtest Runs and Results keep their historical
                  pinned revision references.
                </p>
                <p style={{ ...noteStyle, margin: "0 0 8px" }}>
                  Only an Admin can restore this item from Trash.
                </p>
                <div style={{ display: "flex", gap: 8 }}>
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={del.isPending}
                    onClick={() => del.mutate(item.work_object_root_id)}
                  >
                    Move to Trash
                  </button>
                  <button
                    type="button"
                    className="btn"
                    disabled={del.isPending}
                    onClick={() => setConfirmingDelete(false)}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div>
                <button
                  type="button"
                  className="btn"
                  disabled={busy}
                  aria-label={`Delete ${label}`}
                  onClick={() => setConfirmingDelete(true)}
                >
                  × Delete {kindLabel}
                </button>
              </div>
            )}

            {patch.isError && <p role="alert" style={alertStyle}>{errorMessage(patch.error)}</p>}
            {del.isError && <p role="alert" style={alertStyle}>{errorMessage(del.error)}</p>}
          </section>
        </div>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Advanced generic work-object path: create root+revision, append a revision, //
// then attach the pinned revision to the workspace.                           //
// --------------------------------------------------------------------------- //

function AddWorkObjectCard({ workspaceId }: { workspaceId: string }) {
  const [objectKind, setObjectKind] = useState("strategy");
  const [payloadText, setPayloadText] = useState("{}");
  const [jsonError, setJsonError] = useState<string | null>(null);
  const [created, setCreated] = useState<{ rootId: string; revisionId: string } | null>(null);

  const create = useCreateWorkObject();
  const revise = useCreateWorkObjectRevision();
  const attach = useAttachItem();

  function parsePayload(): Record<string, unknown> | null {
    try {
      const parsed = JSON.parse(payloadText === "" ? "{}" : payloadText);
      if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
        setJsonError("Payload must be a JSON object.");
        return null;
      }
      setJsonError(null);
      return parsed as Record<string, unknown>;
    } catch {
      setJsonError("Payload is not valid JSON.");
      return null;
    }
  }

  return (
    <section className="card" aria-labelledby="add-wo-h">
      <h3 id="add-wo-h" style={{ marginTop: 0 }}>Advanced: create work object</h3>
      <p style={noteStyle}>
        Create a work object, optionally append a revision, then attach its pinned revision to this
        Mainboard. Prefer the dedicated editors above; this raw path is for advanced use.
      </p>
      <div className="cp-field">
        <span>Object kind</span>
        <select value={objectKind} onChange={(e) => setObjectKind(e.target.value)}>
          <option value="strategy">Strategy</option>
          <option value="trading_signal">Trading Signal</option>
          <option value="trade_log">Trade Log</option>
        </select>
      </div>
      <div className="cp-field cp-wide">
        <span>Payload (JSON)</span>
        <textarea value={payloadText} onChange={(e) => setPayloadText(e.target.value)} />
      </div>
      {jsonError && <p role="alert" style={alertStyle}>{jsonError}</p>}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 4 }}>
        <button
          type="button"
          className="btn btn-primary"
          disabled={create.isPending}
          onClick={() => {
            const payload = parsePayload();
            if (payload === null) return;
            create.mutate(
              { object_kind: objectKind, payload },
              {
                onSuccess: (r: WorkObjectResult) =>
                  setCreated({ rootId: r.root_id, revisionId: r.revision_id }),
              },
            );
          }}
        >
          Create work object
        </button>
      </div>
      {create.isError && <p role="alert" style={alertStyle}>{errorMessage(create.error)}</p>}

      {created && (
        <div style={{ marginTop: 12, display: "grid", gap: 12 }}>
          <dl className="kv">
            <dt>Root</dt>
            <dd>{created.rootId}</dd>
            <dt>Pending revision</dt>
            <dd>{created.revisionId}</dd>
          </dl>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button
              type="button"
              className="btn"
              disabled={revise.isPending}
              onClick={() => {
                const payload = parsePayload();
                if (payload === null) return;
                revise.mutate(
                  {
                    rootId: created.rootId,
                    payload,
                    expectedHeadRevisionId: created.revisionId,
                  },
                  {
                    onSuccess: (r) =>
                      setCreated({ rootId: r.root_id, revisionId: r.revision_id }),
                  },
                );
              }}
            >
              Append revision
            </button>
            <button
              type="button"
              className="btn btn-primary"
              disabled={attach.isPending}
              onClick={() =>
                attach.mutate({
                  workspaceId,
                  root_id: created.rootId,
                  revision_id: created.revisionId,
                })
              }
            >
              Attach to Mainboard
            </button>
          </div>
          {revise.isError && <p role="alert" style={alertStyle}>{errorMessage(revise.error)}</p>}
          {attach.isError && <p role="alert" style={alertStyle}>{errorMessage(attach.error)}</p>}
        </div>
      )}
    </section>
  );
}

// --------------------------------------------------------------------------- //
// Add Outsource Signal opener: start a transient external draft, then deep-link //
// to the TS/TL workbench where the real object is created (CR-01, doc 03).      //
// --------------------------------------------------------------------------- //

function OutsourceSignalCard() {
  const start = useStartExternalDraft();
  const draft = start.data as ExternalDraft | undefined;
  const target = draft ? EXTERNAL_DRAFT_KINDS.find((k) => k.value === draft.kind) : undefined;

  return (
    <section className="card" aria-labelledby="add-os-h">
      <h3 id="add-os-h" style={{ marginTop: 0 }}>Add Outsource Signal</h3>
      <p style={noteStyle}>
        Open a Trading Signal or Trade Log draft, then continue in its workbench. Unsaved drafts are
        not included in Backtest Ready Check or RUN.
      </p>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {EXTERNAL_DRAFT_KINDS.map((k) => (
          <button
            key={k.value}
            type="button"
            className="btn"
            disabled={start.isPending}
            onClick={() => start.mutate(k.value)}
          >
            {k.label}
          </button>
        ))}
      </div>
      {start.isError && <p role="alert" style={alertStyle}>{errorMessage(start.error)}</p>}
      {draft && target && (
        <div style={{ marginTop: 12 }}>
          <StatusBadge label="Unsaved" tone="warn" />
          <p style={{ margin: "8px 0" }}>
            {target.label} draft opened.{" "}
            <Link to={target.path}>Continue in the {target.label} workbench →</Link>
          </p>
        </div>
      )}
    </section>
  );
}

// --------------------------------------------------------------------------- //
// Add menu popover: the prototype Mainboard "Add" menu (doc 01 §3.1/§3.2 —      //
// Add Strategy, Add Package, Add Outsource Signal ▸ Trading Signal / Trade Log, //
// Portfolio / Equity Allocation). Add Strategy / Add Package deep-link to the   //
// dedicated editor pages; Outsource opens the TS/TL external-draft card; the    //
// advanced raw work-object path stays available for power users. There is no    //
// "pick an existing package" list because the backend exposes no attachable-    //
// package list endpoint (CR-01).                                                //
// --------------------------------------------------------------------------- //

type AddMode = null | "outsource" | "advanced";

function AddMenu({ mode, onPick }: { mode: AddMode; onPick: (mode: AddMode) => void }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="cp-popover-anchor">
      <button
        type="button"
        className="btn btn-primary"
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        + Add
      </button>
      {open && (
        <>
          <button
            type="button"
            aria-label="Close Add menu"
            onClick={() => setOpen(false)}
            style={{
              position: "fixed",
              inset: 0,
              zIndex: 39,
              background: "transparent",
              border: "none",
              cursor: "default",
            }}
          />
          <div className="package-picker-popover" role="dialog" aria-label="Add to Mainboard">
            <div className="package-picker-title">Add to Mainboard</div>
            <p style={{ ...noteStyle, margin: 0 }}>
              Choose what to add to this Mainboard composition.
            </p>
            <Link to="/strategy" className="btn" onClick={() => setOpen(false)}>
              Add Strategy
            </Link>
            <Link to="/packages/create" className="btn" onClick={() => setOpen(false)}>
              Add Package
            </Link>
            <button
              type="button"
              className={mode === "outsource" ? "btn btn-primary" : "btn"}
              onClick={() => {
                onPick("outsource");
                setOpen(false);
              }}
            >
              Add Outsource Signal
            </button>
            <button
              type="button"
              className={mode === "advanced" ? "btn btn-primary" : "btn"}
              onClick={() => {
                onPick("advanced");
                setOpen(false);
              }}
            >
              Advanced: create work object
            </button>
            <Link to="/portfolio" className="btn btn-ghost" onClick={() => setOpen(false)}>
              Portfolio / Equity Allocation →
            </Link>
            <div className="package-picker-actions">
              <button type="button" className="btn btn-ghost" onClick={() => setOpen(false)}>
                Close
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Root page.                                                                   //
// --------------------------------------------------------------------------- //

// A single-line headline for the latest-result summary (kept as one text node so
// the digest reads cleanly and is straightforward to assert).
function latestResultLine(s: NonNullable<LatestResultSummary["summary"]>): string {
  const period = s.period_start && s.period_end ? ` · ${s.period_start} → ${s.period_end}` : "";
  return `${s.symbol ?? "—"} · ${s.timeframe ?? "—"} · ${s.total_trades} trade(s)${period}`;
}

// The most recent succeeded Result for this composition (doc 15 §9.4). The row is
// always readable; when the live composition has moved past the result's pinned
// fingerprint the server flags snapshot_differs and we label it — the result is
// never treated as a current test of the modified composition.
function LatestResultCard({ result }: { result: LatestResultSummary }) {
  const s = result.summary;
  return (
    <div style={{ display: "grid", gap: 6 }}>
      <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
        <Link to={`/backtest/run?result=${encodeURIComponent(result.result_id)}`}>
          {result.result_id}
        </Link>
        {result.snapshot_differs && (
          <StatusBadge
            label="Result snapshot differs from current Mainboard composition"
            tone="warn"
          />
        )}
      </div>
      <div style={{ fontSize: 13 }}>
        {s ? latestResultLine(s) : "Summary not available for this result."}
      </div>
    </div>
  );
}

export function Mainboard() {
  const board = useDefaultMainboard();
  const snapshot = useCreateSnapshot();
  const [addMode, setAddMode] = useState<AddMode>(null);

  if (board.isLoading) return <Loading label="Loading Mainboard…" />;
  if (board.isError || !board.data) {
    return <ErrorState error={board.error} onRetry={() => void board.refetch()} />;
  }

  const data = board.data;
  const items = [...data.items].sort((a, b) => a.position_index - b.position_index);
  const readyState = data.ready_summary?.state ?? "not_ready";

  return (
    <>
      <h1 className="page-title">Mainboard</h1>
      <p className="page-sub">Backtest composition · {data.workspace_kind}</p>

      <div style={{ display: "grid", gap: 18 }}>
        <section aria-labelledby="strategies-h">
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 12,
              flexWrap: "wrap",
            }}
          >
            <h2 id="strategies-h" className="strategies-title" style={{ margin: 0 }}>
              STRATEGIES
            </h2>
            <AddMenu mode={addMode} onPick={setAddMode} />
          </div>
          {items.length === 0 ? (
            <div className="card">
              <strong>Your Mainboard is empty.</strong>
              <p style={{ margin: "6px 0 0", fontSize: 13 }}>
                Add a Strategy, Trading Signal, or Trade Log to build a backtest composition. Unsaved
                drafts are not included in Backtest Ready Check or RUN.
              </p>
            </div>
          ) : (
            <div className="strategy-list">
              {items.map((item) => (
                <ItemRow key={item.item_id} item={item} />
              ))}
            </div>
          )}
        </section>

        <section aria-labelledby="results-h">
          <h2 id="results-h" className="results-title">BACKTEST RESULTS</h2>
          {data.latest_result_summary ? (
            <div className="result-row">
              <LatestResultCard result={data.latest_result_summary} />
            </div>
          ) : (
            <p style={{ ...noteStyle, margin: 0 }}>
              No succeeded Backtest Result is available for this Mainboard yet.
            </p>
          )}
        </section>

        <section className="card" aria-labelledby="summary-h">
          <h3 id="summary-h" style={{ marginTop: 0 }}>Composition</h3>
          <div style={{ display: "flex", gap: 14, alignItems: "center", flexWrap: "wrap" }}>
            <StatusBadge label={readyStatusText(readyState)} tone={readyStatusTone(readyState)} />
          </div>
          <dl className="kv" style={{ marginTop: 12 }}>
            <dt>Composition hash</dt>
            <dd>{data.composition_hash ?? "—"}</dd>
            <dt>Workspace version</dt>
            <dd>{data.row_version}</dd>
          </dl>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 14 }}>
            <Link to="/backtest/ready-check" className="btn">Backtest Ready Check</Link>
            <Link to="/backtest/run" className="btn btn-primary">RUN</Link>
            <button
              type="button"
              className="btn"
              disabled={snapshot.isPending}
              onClick={() => snapshot.mutate(data.workspace_id)}
            >
              Freeze composition
            </button>
          </div>
          <p style={{ ...noteStyle, margin: "10px 0 0" }}>
            RUN is available only after a current Backtest Ready Check passes.
          </p>
          {snapshot.isError && <p role="alert" style={alertStyle}>{errorMessage(snapshot.error)}</p>}
          {snapshot.data && (
            <p style={{ margin: "8px 0 0", fontSize: 13 }}>
              Snapshot {snapshot.data.snapshot_id} · {snapshot.data.item_count} enabled item(s).
            </p>
          )}
        </section>

        {addMode === "outsource" && <OutsourceSignalCard />}
        {addMode === "advanced" && <AddWorkObjectCard workspaceId={data.workspace_id} />}
      </div>
    </>
  );
}
