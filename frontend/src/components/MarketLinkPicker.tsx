import { useState } from "react";

import {
  revisionStateTone,
  useMarketDatasets,
  type MarketDatasetRow,
} from "@/lib/marketData";
import { probeErrorMessage, type MarketDependencyStatus } from "@/lib/marketDependency";

// R2-06 (GAP item 8) — the Research Data "Linked Market Data" dependency is
// server-truth, never client text. The user browses the role-aware Market Data
// registry by name and picks a dataset root; the exact ACTIVE+APPROVED revision
// is then resolved by the read-only approved-bundle probe (404/403 envelopes
// verbatim). The immutable ids travel system-side — there is no free-text id
// input, so "typing anything unlocks the workflow" cannot be reconstructed.
// The picker is a convenience, never authorization: create still hits the
// server's DR3 gate (DEPENDENCY_BLOCKED verbatim).

function datasetLabel(row: MarketDatasetRow): string {
  return row.title ?? row.instrument_id ?? row.entity_id;
}

// Registry browser (DatasetPicker pattern). Only a head revision the server
// reports as `approved` is selectable; every other state renders as a disabled
// row naming the reason — deprecated/rejected datasets are visible but cannot
// be picked. The list itself is already role-aware server-side.
function MarketLinkBrowser({
  onPick,
  onCancel,
}: {
  onPick: (entityId: string) => void;
  onCancel: () => void;
}) {
  const [q, setQ] = useState("");
  const query = useMarketDatasets(null);
  const rows = query.data?.data ?? [];
  const needle = q.trim().toLowerCase();
  const filtered =
    needle === "" ? rows : rows.filter((row) => datasetLabel(row).toLowerCase().includes(needle));

  return (
    <div className="pkg-picker-browser">
      <div className="pkg-picker-search">
        <input
          value={q}
          placeholder="Search market datasets…"
          onChange={(event) => setQ(event.target.value)}
          spellCheck={false}
          aria-label="Search market datasets"
        />
        <button type="button" className="btn" onClick={onCancel}>
          Cancel
        </button>
      </div>
      {query.isLoading ? (
        <p className="cp-note">Loading market datasets…</p>
      ) : query.isError ? (
        <p role="alert" style={{ color: "var(--down)" }}>
          Could not load market datasets: {probeErrorMessage(query.error)}
        </p>
      ) : filtered.length === 0 ? (
        <p className="cp-note">No market datasets match.</p>
      ) : (
        <ul className="pkg-picker-list">
          {filtered.map((row) => {
            const eligible = row.revision_state === "approved";
            return (
              <li key={row.revision_id}>
                <button
                  type="button"
                  className="pkg-picker-row"
                  disabled={!eligible}
                  title={eligible ? undefined : `Not eligible — ${row.revision_state}`}
                  onClick={() => onPick(row.entity_id)}
                >
                  <span className="pkg-picker-name">{datasetLabel(row)}</span>
                  <span className="pkg-picker-rev">{row.market_data_type}</span>
                  <span className={`badge badge-${revisionStateTone(row.revision_state)}`}>
                    {row.revision_state}
                  </span>
                  <span className="pkg-picker-rev">rev {row.revision_no}</span>
                  {!eligible ? (
                    <span className="cp-note">not eligible — {row.revision_state}</span>
                  ) : null}
                </button>
              </li>
            );
          })}
        </ul>
      )}
      {query.data?.meta.has_more ? (
        <p className="cp-note">More datasets exist — narrow the search to find them.</p>
      ) : null}
    </div>
  );
}

// The selected dataset + its live server verdict. The status line renders the
// probe result only — never a client-invented state.
function SelectedSummary({
  entityId,
  status,
}: {
  entityId: string;
  status: MarketDependencyStatus;
}) {
  const registry = useMarketDatasets(null);
  const match = (registry.data?.data ?? []).find((row) => row.entity_id === entityId);
  const label = match ? datasetLabel(match) : entityId;

  return (
    <div>
      <div className="pkg-picker-name" style={{ fontWeight: 600 }}>
        {label}
      </div>
      {status.kind === "checking" ? (
        <p className="cp-note" style={{ margin: "4px 0 0" }} aria-live="polite">
          Checking approval on the server…
        </p>
      ) : null}
      {status.kind === "ready" ? (
        <p className="cp-note" style={{ margin: "4px 0 0" }} aria-live="polite">
          Approved for use — revision <code>{status.bundle.revision_id}</code> (rev{" "}
          {status.bundle.revision_no}, {status.bundle.market_data_type})
        </p>
      ) : null}
      {status.kind === "blocked" || status.kind === "denied" ? (
        <p role="alert" style={{ margin: "4px 0 0", color: "var(--down)" }}>
          {status.message}
        </p>
      ) : null}
    </div>
  );
}

export function MarketLinkPicker({
  value,
  status,
  onChange,
  label = "Linked Market Data",
  required = true,
}: {
  value: string | null;
  status: MarketDependencyStatus;
  onChange: (entityId: string | null) => void;
  label?: string;
  required?: boolean;
}) {
  const [browsing, setBrowsing] = useState(false);

  return (
    <div className="pkg-picker cp-wide">
      <span className="field-head">
        <span className="pkg-picker-label">
          {label}
          {required ? <span aria-hidden="true"> *</span> : null}
        </span>
      </span>
      {value !== null ? (
        <div className="pkg-picker-pinned">
          <SelectedSummary entityId={value} status={status} />
          <div className="pkg-picker-actions">
            <button type="button" className="btn" onClick={() => setBrowsing((b) => !b)}>
              {browsing ? "Close" : "Change"}
            </button>
            <button type="button" className="btn" onClick={() => onChange(null)}>
              Clear
            </button>
          </div>
        </div>
      ) : (
        <div className="pkg-picker-empty">
          <span className="cp-note">No market dataset linked.</span>
          <button type="button" className="btn btn-primary" onClick={() => setBrowsing((b) => !b)}>
            {browsing ? "Close" : "Choose market dataset"}
          </button>
        </div>
      )}
      {browsing ? (
        <MarketLinkBrowser
          onPick={(entityId) => {
            onChange(entityId);
            setBrowsing(false);
          }}
          onCancel={() => setBrowsing(false)}
        />
      ) : null}
    </div>
  );
}
