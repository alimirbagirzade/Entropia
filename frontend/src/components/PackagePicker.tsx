import { useState } from "react";

import { InfoPanel } from "@/components/InfoPanel";
import {
  DEFAULT_LIBRARY_FILTERS,
  type LibraryPackageRow,
  useLibraryPackage,
  useLibraryPackages,
  validationTone,
} from "@/lib/library";
import type { PackageRefForm } from "@/lib/strategyGraph";
import type { InfoPanelContent } from "@/lib/strategyForm";

// R6 / GAP-08 — reusable indicator / condition Package picker (doc 02 §5.3).
// Pins a PackageReference {package_root_id, package_revision_id,
// package_content_hash} by browsing the Library catalog filtered to ACTIVE
// packages of the given kind. The server re-validates compatibility + access
// on Validate / Save (this picker is a convenience, never authorization).
//
// Honest boundary: the picker pins the row's CURRENT revision (the revision
// list summary carries no content_hash, so a historical pin still needs the
// Advanced JSON editor). It never invents a content_hash.

function refFromRow(row: LibraryPackageRow): PackageRefForm {
  return {
    package_root_id: row.entity_id,
    package_revision_id: row.current_revision_id,
    package_content_hash: row.content_hash,
  };
}

function PickerBrowser({
  kind,
  onPick,
  onCancel,
}: {
  kind: "indicator" | "condition";
  onPick: (ref: PackageRefForm) => void;
  onCancel: () => void;
}) {
  const [q, setQ] = useState("");
  const filters = {
    ...DEFAULT_LIBRARY_FILTERS,
    type: kind,
    lifecycle_state: "active",
    q: q.trim() === "" ? null : q.trim(),
  };
  const query = useLibraryPackages(filters, null);
  const rows = query.data?.data ?? [];

  return (
    <div className="pkg-picker-browser">
      <div className="pkg-picker-search">
        <input
          value={q}
          placeholder={`Search ${kind} packages…`}
          onChange={(event) => setQ(event.target.value)}
          spellCheck={false}
          aria-label={`Search ${kind} packages`}
        />
        <button type="button" className="btn" onClick={onCancel}>
          Cancel
        </button>
      </div>
      {query.isLoading ? (
        <p className="cp-note">Loading {kind} packages…</p>
      ) : query.isError ? (
        <p role="alert" style={{ color: "var(--down)" }}>
          Could not load packages: {query.error instanceof Error ? query.error.message : "error"}
        </p>
      ) : rows.length === 0 ? (
        <p className="cp-note">No active {kind} packages match.</p>
      ) : (
        <ul className="pkg-picker-list">
          {rows.map((row) => (
            <li key={row.entity_id}>
              <button type="button" className="pkg-picker-row" onClick={() => onPick(refFromRow(row))}>
                <span className="pkg-picker-name">{row.name ?? row.entity_id}</span>
                <span className={`badge badge-${validationTone(row.validation_state)}`}>
                  {row.validation_state}
                </span>
                <span className="pkg-picker-rev">rev {row.revision_no}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {query.data?.meta.has_more ? (
        <p className="cp-note">More packages exist — narrow the search to find them.</p>
      ) : null}
    </div>
  );
}

// F-19 — the pinned summary shows the package's human name (resolved from the
// pinned root id via the existing Library detail read) instead of the raw
// root/revision/hash ULIDs; the exact identifiers move to a collapsed
// "Technical identifiers" disclosure (verifiable, no longer the primary surface).
function PinnedPackageSummary({ value }: { value: PackageRefForm }) {
  const detail = useLibraryPackage(value.package_root_id || null);
  const name = detail.data?.name ?? null;

  return (
    <div>
      <div className="pkg-picker-name" style={{ fontWeight: 600 }}>
        {name ?? "Pinned package"}
        {detail.data ? (
          <span className="pkg-picker-rev"> — rev {detail.data.revision_no}</span>
        ) : null}
      </div>
      <details style={{ marginTop: 4 }}>
        <summary className="cp-note" style={{ cursor: "pointer" }}>
          Technical identifiers
        </summary>
        <dl className="kv kv-compact">
          <dt>Root</dt>
          <dd>
            <code>{value.package_root_id || "—"}</code>
          </dd>
          <dt>Revision</dt>
          <dd>
            <code>{value.package_revision_id || "—"}</code>
          </dd>
          <dt>Hash</dt>
          <dd>
            <code>{value.package_content_hash || "—"}</code>
          </dd>
        </dl>
      </details>
    </div>
  );
}

export function PackagePicker({
  kind,
  label,
  value,
  onChange,
  panel,
}: {
  kind: "indicator" | "condition";
  label: string;
  value: PackageRefForm | null;
  onChange: (ref: PackageRefForm | null) => void;
  panel?: InfoPanelContent;
}) {
  const [browsing, setBrowsing] = useState(false);

  return (
    <div className="pkg-picker cp-wide">
      <span className="field-head">
        <span className="pkg-picker-label">
          {label} <span aria-hidden="true">*</span>
        </span>
        {panel ? <InfoPanel panel={panel} /> : null}
      </span>
      {value ? (
        <div className="pkg-picker-pinned">
          <PinnedPackageSummary value={value} />
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
          <span className="cp-note">No package pinned.</span>
          <button type="button" className="btn btn-primary" onClick={() => setBrowsing((b) => !b)}>
            {browsing ? "Close" : `Choose ${kind}`}
          </button>
        </div>
      )}
      {browsing ? (
        <PickerBrowser
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
