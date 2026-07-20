import { useState } from "react";

import { stateTone, useInstruments, type InstrumentRow } from "@/lib/instrument";

// R2-08 (GAP item 7) — an instrument is picked from the canonical Instrument
// Registry (GAP-16) by name/venue/symbol, never typed as a raw id. The
// immutable instrument_id travels system-side; it surfaces only as a read-only
// provenance line next to the selection. Deprecated instruments stay visible
// but cannot be picked. The picker is a convenience, never authorization —
// the server still resolves/validates the value it receives verbatim.

function instrumentLabel(row: InstrumentRow): string {
  return row.display_name || `${row.venue_id} · ${row.symbol}`;
}

function InstrumentBrowser({
  onPick,
  onCancel,
}: {
  onPick: (row: InstrumentRow) => void;
  onCancel: () => void;
}) {
  const [q, setQ] = useState("");
  const query = useInstruments(null, null);
  const rows = query.data?.data ?? [];
  const needle = q.trim().toLowerCase();
  const filtered =
    needle === ""
      ? rows
      : rows.filter((row) =>
          `${instrumentLabel(row)} ${row.venue_id} ${row.symbol}`.toLowerCase().includes(needle),
        );

  return (
    <div className="pkg-picker-browser">
      <div className="pkg-picker-search">
        <input
          value={q}
          placeholder="Search instruments…"
          onChange={(event) => setQ(event.target.value)}
          spellCheck={false}
          aria-label="Search instruments"
        />
        <button type="button" className="btn" onClick={onCancel}>
          Cancel
        </button>
      </div>
      {query.isLoading ? (
        <p className="cp-note">Loading instruments…</p>
      ) : query.isError ? (
        <p role="alert" style={{ color: "var(--down)" }}>
          Could not load the instrument registry.
        </p>
      ) : filtered.length === 0 ? (
        <p className="cp-note">No instruments match.</p>
      ) : (
        <ul className="pkg-picker-list">
          {filtered.map((row) => {
            const eligible = row.state === "active";
            return (
              <li key={row.instrument_id}>
                <button
                  type="button"
                  className="pkg-picker-row"
                  disabled={!eligible}
                  title={eligible ? undefined : `Not eligible — ${row.state}`}
                  onClick={() => onPick(row)}
                >
                  <span className="pkg-picker-name">{instrumentLabel(row)}</span>
                  <span className="pkg-picker-rev">
                    {row.venue_id} · {row.symbol} · {row.contract_type}
                  </span>
                  <span className={`badge badge-${stateTone(row.state)}`}>{row.state}</span>
                  {!eligible ? <span className="cp-note">not eligible — {row.state}</span> : null}
                </button>
              </li>
            );
          })}
        </ul>
      )}
      {query.data?.meta.has_more ? (
        <p className="cp-note">More instruments exist — narrow the search to find them.</p>
      ) : null}
    </div>
  );
}

// The pinned selection: registry name when the id resolves, otherwise the
// stored value verbatim (legacy datasets predate the canonical registry).
function SelectedInstrument({ value }: { value: string }) {
  const query = useInstruments(null, null);
  const match = (query.data?.data ?? []).find((row) => row.instrument_id === value);
  return (
    <div>
      <div className="pkg-picker-name" style={{ fontWeight: 600 }}>
        {match ? instrumentLabel(match) : value}
      </div>
      <small className="cp-note">
        Instrument id (system-carried): <code>{value}</code>
        {match ? ` · ${match.venue_id} · ${match.symbol} · ${match.contract_type}` : " · not in registry"}
      </small>
    </div>
  );
}

export function InstrumentPicker({
  label,
  value,
  onChange,
  required = false,
  disabled = false,
  error,
}: {
  label: string;
  value: string;
  onChange: (instrumentId: string) => void;
  required?: boolean;
  disabled?: boolean;
  error?: string;
}) {
  const [browsing, setBrowsing] = useState(false);

  return (
    <div className="pkg-picker cp-field cp-wide">
      <span className="field-head">
        <span className="pkg-picker-label">
          {label}
          {required ? <span aria-hidden="true"> *</span> : null}
        </span>
      </span>
      {value !== "" ? (
        <div className="pkg-picker-pinned">
          <SelectedInstrument value={value} />
          <div className="pkg-picker-actions">
            <button
              type="button"
              className="btn"
              disabled={disabled}
              onClick={() => setBrowsing((b) => !b)}
            >
              {browsing ? "Close" : "Change"}
            </button>
            {!required ? (
              <button type="button" className="btn" disabled={disabled} onClick={() => onChange("")}>
                Clear
              </button>
            ) : null}
          </div>
        </div>
      ) : (
        <div className="pkg-picker-empty">
          <span className="cp-note">No instrument selected.</span>
          <button
            type="button"
            className="btn"
            disabled={disabled}
            onClick={() => setBrowsing((b) => !b)}
          >
            {browsing ? "Close" : "Choose instrument"}
          </button>
        </div>
      )}
      {browsing && !disabled ? (
        <InstrumentBrowser
          onPick={(row) => {
            onChange(row.instrument_id);
            setBrowsing(false);
          }}
          onCancel={() => setBrowsing(false)}
        />
      ) : null}
      {error ? (
        <small role="alert" style={{ color: "var(--down)" }}>
          {error}
        </small>
      ) : null}
    </div>
  );
}
