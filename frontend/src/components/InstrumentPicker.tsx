import { useState } from "react";

import { stateTone, useInstruments, type InstrumentRow } from "@/lib/instrument";

// R2-08 (GAP item 7) — an instrument is picked from the canonical Instrument
// Registry (GAP-16) by name/venue/symbol, never typed as a raw id. Deprecated
// instruments stay visible but cannot be picked. The picker is a convenience,
// never authorization — the server still resolves/validates the value it
// receives verbatim.
//
// `pickBy` controls WHICH field the picker hands back over the wire — the
// canonical registry id is correct where the consumer stores it verbatim
// (e.g. MarketData revision, TradingSignalConfig), but the Trading Signal /
// Trade Log DURABLE IMPORT request still matches each CSV row's raw `symbol`
// column against this exact string server-side (`domain/trading_signal/
// events.py` + `domain/trade_log/records.py` — a pre-existing, canonical-id-
// unaware check); those two call sites pass `pickBy="symbol"` so the wire
// value stays the legacy symbol text the row-matching logic expects, while
// the user still only ever BROWSES the registry, never hand-types an id.
type PickBy = "instrument_id" | "symbol";

function instrumentLabel(row: InstrumentRow): string {
  return row.display_name || `${row.venue_id} · ${row.symbol}`;
}

function keyFor(row: InstrumentRow, pickBy: PickBy): string {
  return pickBy === "symbol" ? row.symbol : row.instrument_id;
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

// The pinned selection: registry name when the value resolves, otherwise the
// stored value verbatim (legacy datasets predate the canonical registry, or a
// symbol matches more than one venue/contract — the provenance line is
// informational only, never the authoritative match).
function SelectedInstrument({ value, pickBy }: { value: string; pickBy: PickBy }) {
  const query = useInstruments(null, null);
  const match = (query.data?.data ?? []).find((row) => keyFor(row, pickBy) === value);
  return (
    <div>
      <div className="pkg-picker-name" style={{ fontWeight: 600 }}>
        {match ? instrumentLabel(match) : value}
      </div>
      <small className="cp-note">
        {pickBy === "symbol" ? "Symbol (system-carried): " : "Instrument id (system-carried): "}
        <code>{value}</code>
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
  pickBy = "instrument_id",
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
  disabled?: boolean;
  error?: string;
  pickBy?: PickBy;
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
          <SelectedInstrument value={value} pickBy={pickBy} />
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
            onChange(keyFor(row, pickBy));
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
