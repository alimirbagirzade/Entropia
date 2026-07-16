import { useState } from "react";

import { InfoPanel } from "@/components/InfoPanel";
import {
  type MarketDatasetRow,
  revisionStateTone,
  useMarketDatasets,
} from "@/lib/marketData";
import type { InfoPanelContent } from "@/lib/strategyForm";

// F-19 — user-facing data-source picker (doc 02 §5.2). Replaces the raw
// root/revision/hash infra-ID text inputs on the Strategy Details editor with a
// browse-by-name picker over the Market Data registry. It pins the SAME three
// StrategyConfig fields (market_dataset_* / funding_source_*) the config already
// carries — presentation only: no route path, react-query key, OCC token,
// Idempotency-Key, hook, SSE taxonomy, API call, or lib/*.ts data logic changes.
// The exact identifiers move to a collapsed "Technical identifiers" disclosure
// (verifiable, no longer primary). The server re-validates the pinned revision on
// Validate / Save (the picker is a convenience, never authorization).
//
// Honest boundary: the registry list is the first keyset page, so a pinned
// dataset that is not on that page resolves to a generic label (its identifiers
// stay visible in the disclosure). The picker never invents a content hash — a
// row with no content hash pins an empty hash, exactly as a blank field did.

export interface DatasetRefValue {
  rootId: string;
  revisionId: string;
  contentHash: string;
}

const EMPTY_REF: DatasetRefValue = { rootId: "", revisionId: "", contentHash: "" };

function refFromRow(row: MarketDatasetRow): DatasetRefValue {
  return {
    rootId: row.entity_id,
    revisionId: row.revision_id,
    contentHash: row.content_hash ?? "",
  };
}

function datasetLabel(row: MarketDatasetRow): string {
  return row.title ?? row.instrument_id ?? row.entity_id;
}

function isPinned(value: DatasetRefValue): boolean {
  return value.rootId !== "" || value.revisionId !== "" || value.contentHash !== "";
}

function DatasetBrowser({
  kind,
  onPick,
  onCancel,
}: {
  kind: string;
  onPick: (ref: DatasetRefValue) => void;
  onCancel: () => void;
}) {
  const [q, setQ] = useState("");
  const query = useMarketDatasets(null);
  const rows = query.data?.data ?? [];
  const needle = q.trim().toLowerCase();
  const filtered =
    needle === ""
      ? rows
      : rows.filter((row) => datasetLabel(row).toLowerCase().includes(needle));

  return (
    <div className="pkg-picker-browser">
      <div className="pkg-picker-search">
        <input
          value={q}
          placeholder={`Search ${kind} datasets…`}
          onChange={(event) => setQ(event.target.value)}
          spellCheck={false}
          aria-label={`Search ${kind} datasets`}
        />
        <button type="button" className="btn" onClick={onCancel}>
          Cancel
        </button>
      </div>
      {query.isLoading ? (
        <p className="cp-note">Loading datasets…</p>
      ) : query.isError ? (
        <p role="alert" style={{ color: "var(--down)" }}>
          Could not load datasets: {query.error instanceof Error ? query.error.message : "error"}
        </p>
      ) : filtered.length === 0 ? (
        <p className="cp-note">No datasets match.</p>
      ) : (
        <ul className="pkg-picker-list">
          {filtered.map((row) => (
            <li key={row.revision_id}>
              <button
                type="button"
                className="pkg-picker-row"
                onClick={() => onPick(refFromRow(row))}
              >
                <span className="pkg-picker-name">{datasetLabel(row)}</span>
                <span className={`badge badge-${revisionStateTone(row.revision_state)}`}>
                  {row.revision_state}
                </span>
                <span className="pkg-picker-rev">rev {row.revision_no}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {query.data?.meta.has_more ? (
        <p className="cp-note">More datasets exist — narrow the search to find them.</p>
      ) : null}
    </div>
  );
}

// The pinned summary resolves the pinned root id back to a human label from the
// loaded registry page (no extra request); an off-page pin shows a generic
// label. Either way the exact identifiers live in the collapsed disclosure.
function PinnedSummary({ value }: { value: DatasetRefValue }) {
  const registry = useMarketDatasets(null);
  const match = (registry.data?.data ?? []).find((row) => row.entity_id === value.rootId);
  const label = match ? datasetLabel(match) : "Pinned dataset";

  return (
    <div>
      <div className="pkg-picker-name" style={{ fontWeight: 600 }}>
        {label}
        {match ? <span className="pkg-picker-rev"> — rev {match.revision_no}</span> : null}
      </div>
      <details style={{ marginTop: 4 }}>
        <summary className="cp-note" style={{ cursor: "pointer" }}>
          Technical identifiers
        </summary>
        <dl className="kv kv-compact">
          <dt>Root</dt>
          <dd>
            <code>{value.rootId || "—"}</code>
          </dd>
          <dt>Revision</dt>
          <dd>
            <code>{value.revisionId || "—"}</code>
          </dd>
          <dt>Content hash</dt>
          <dd>
            <code>{value.contentHash || "—"}</code>
          </dd>
        </dl>
      </details>
    </div>
  );
}

export function DatasetPicker({
  kind,
  label,
  required,
  value,
  onChange,
  panel,
}: {
  kind: "market" | "funding";
  label: string;
  required?: boolean;
  value: DatasetRefValue;
  onChange: (ref: DatasetRefValue) => void;
  panel?: InfoPanelContent;
}) {
  const [browsing, setBrowsing] = useState(false);
  const pinned = isPinned(value);

  return (
    <div className="pkg-picker cp-wide">
      <span className="field-head">
        <span className="pkg-picker-label">
          {label}
          {required ? <span aria-hidden="true"> *</span> : null}
        </span>
        {panel ? <InfoPanel panel={panel} /> : null}
      </span>
      {pinned ? (
        <div className="pkg-picker-pinned">
          <PinnedSummary value={value} />
          <div className="pkg-picker-actions">
            <button type="button" className="btn" onClick={() => setBrowsing((b) => !b)}>
              {browsing ? "Close" : "Change"}
            </button>
            <button type="button" className="btn" onClick={() => onChange({ ...EMPTY_REF })}>
              Clear
            </button>
          </div>
        </div>
      ) : (
        <div className="pkg-picker-empty">
          <span className="cp-note">No dataset selected.</span>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => setBrowsing((b) => !b)}
          >
            {browsing ? "Close" : `Choose ${kind} dataset`}
          </button>
        </div>
      )}
      {browsing ? (
        <DatasetBrowser
          kind={kind}
          onPick={(ref) => {
            onChange(ref);
            setBrowsing(false);
          }}
          onCancel={() => setBrowsing(false)}
        />
      ) : null}
    </div>
  );
}
