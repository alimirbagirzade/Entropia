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
  const label = item.display_label_override ?? itemKindLabel(item.item_kind);
  const busy = patch.isPending || del.isPending;

  return (
    <div style={{ border: "1px solid var(--border)", borderRadius: 10, padding: "10px 14px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <button
          type="button"
          className="btn btn-ghost"
          aria-expanded={expanded}
          aria-label={expanded ? `Collapse ${label}` : `Expand ${label}`}
          onClick={() => setExpanded((v) => !v)}
        >
          {expanded ? "▲" : "▼"}
        </button>
        <strong style={{ flex: 1, minWidth: 160 }}>{label}</strong>
        <StatusBadge label={itemKindLabel(item.item_kind)} tone="neutral" />
        <StatusBadge
          label={item.is_enabled ? "Enabled" : "Disabled"}
          tone={item.is_enabled ? "ok" : "warn"}
        />
        <span style={noteStyle}>#{item.position_index}</span>
      </div>

      {expanded && (
        <div style={{ marginTop: 12, display: "grid", gap: 14 }}>
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
              aria-label={`Delete ${itemKindLabel(item.item_kind)}?`}
              style={{ border: "1px solid var(--down)", borderRadius: 8, padding: 12 }}
            >
              <strong>Delete {itemKindLabel(item.item_kind)}?</strong>
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
                × Delete
              </button>
            </div>
          )}

          {patch.isError && <p role="alert" style={alertStyle}>{errorMessage(patch.error)}</p>}
          {del.isError && <p role="alert" style={alertStyle}>{errorMessage(del.error)}</p>}
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
      <h3 id="add-wo-h" style={{ marginTop: 0 }}>Add work object</h3>
      <p style={noteStyle}>
        Create a work object, optionally append a revision, then attach its pinned revision to this
        Mainboard.
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
// Root page.                                                                   //
// --------------------------------------------------------------------------- //

export function Mainboard() {
  const board = useDefaultMainboard();
  const snapshot = useCreateSnapshot();

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
            <dt>Latest result</dt>
            <dd>No succeeded Backtest Result is available for this Mainboard yet.</dd>
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

        <section className="card" aria-labelledby="strategies-h">
          <h3 id="strategies-h" style={{ marginTop: 0 }}>Strategies</h3>
          {items.length === 0 ? (
            <div>
              <strong>Your Mainboard is empty.</strong>
              <p style={{ margin: "6px 0 0", fontSize: 13 }}>
                Add a Strategy, Trading Signal, or Trade Log to build a backtest composition. Unsaved
                drafts are not included in Backtest Ready Check or RUN.
              </p>
            </div>
          ) : (
            <div style={{ display: "grid", gap: 10 }}>
              {items.map((item) => (
                <ItemRow key={item.item_id} item={item} />
              ))}
            </div>
          )}
        </section>

        <OutsourceSignalCard />
        <AddWorkObjectCard workspaceId={data.workspace_id} />
      </div>
    </>
  );
}
