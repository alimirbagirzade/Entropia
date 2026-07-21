import { useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "@/lib/apiClient";
import { StatusBadge } from "@/components/StatusBadge";
import { useEscapeToClose } from "@/components/useEscapeToClose";
import {
  DEFAULT_LIBRARY_FILTERS,
  approvalTone,
  useLibraryPackage,
  useLibraryPackages,
  validationTone,
  type LibraryPackageRow,
} from "@/lib/library";
import { useDeriveStrategyDraftFromPackage } from "@/lib/strategy";

// R2-03 (GAP madde 4): the real Mainboard "Add Package" selection popover.
// "Add Package" is NOT a Create Package link — it selects an accessible, usable
// Strategy Package revision and derives a NEW Strategy Draft from it (the
// source package is never modified; the exact revision is pinned as provenance
// by the existing POST /strategy-drafts source_package_* command, GAP-03).
//
// Eligibility is SERVER-truth: the list is the Library catalog filtered to
// type=strategy + lifecycle=active, and a row is selectable only when the
// server-computed permissions.can_use flag is true (the client never derives
// eligibility itself — an ineligible row renders disabled with the reason).
// Trading Signal / Trade Log package kinds are never listed (the catalog query
// is strategy-only). "Create new package" stays available as the visually
// secondary path into the CP Agent workspace (/packages/create).

function contractField(contract: Record<string, unknown> | undefined, key: string): string {
  const value = contract?.[key];
  // Honest boundary: the package input_contract is free-form — when it does not
  // declare the field, say so instead of fabricating a compatibility claim.
  return typeof value === "string" && value.trim() !== "" ? value : "not provided";
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return `${error.code}: ${error.message}`;
  return error instanceof Error ? error.message : "Request failed.";
}

// Short compatibility summary for the SELECTED package, read from the Library
// detail projection (doc 08 §4). Market / timeframe live in the free-form
// input_contract when the package declares them.
function SelectedPackageSummary({
  row,
  onDerive,
  deriving,
  deriveError,
}: {
  row: LibraryPackageRow;
  onDerive: () => void;
  deriving: boolean;
  deriveError: unknown;
}) {
  const detail = useLibraryPackage(row.entity_id);

  return (
    <div
      role="group"
      aria-label={`Selected package ${row.name ?? row.entity_id}`}
      style={{ display: "grid", gap: 6, borderTop: "1px solid var(--border)", paddingTop: 8 }}
    >
      <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
        <span className="pkg-picker-name">{row.name ?? row.entity_id}</span>
        <StatusBadge label={row.validation_state} tone={validationTone(row.validation_state)} />
        <StatusBadge label={row.approval_state} tone={approvalTone(row.approval_state)} />
      </div>
      <dl className="kv kv-compact">
        <dt>Exact revision</dt>
        <dd>
          rev {row.revision_no} — <code>{row.current_revision_id}</code>
        </dd>
        <dt>Market</dt>
        <dd>{detail.isLoading ? "…" : contractField(detail.data?.input_contract, "market")}</dd>
        <dt>Timeframe</dt>
        <dd>{detail.isLoading ? "…" : contractField(detail.data?.input_contract, "timeframe")}</dd>
      </dl>
      <p className="cp-note" style={{ margin: 0 }}>
        A new Strategy Draft is derived from this exact revision; the source package is never
        modified.
      </p>
      <button
        type="button"
        className="btn btn-primary"
        disabled={deriving}
        onClick={onDerive}
      >
        {deriving ? "Deriving…" : "Add Strategy From Package"}
      </button>
      {deriveError != null && (
        <p role="alert" style={{ color: "var(--down)", margin: 0, fontSize: 13 }}>
          {errorMessage(deriveError)}
        </p>
      )}
    </div>
  );
}

export function AddPackagePopover({
  onDerived,
  onClose,
}: {
  // Called with the new draft id after a successful derive — the Mainboard
  // opens the draft row with its inline Strategy Details editor.
  onDerived: (draftId: string) => void;
  onClose: () => void;
}) {
  const [q, setQ] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  useEscapeToClose(true, onClose);
  const query = useLibraryPackages(
    {
      ...DEFAULT_LIBRARY_FILTERS,
      type: "strategy",
      lifecycle_state: "active",
      q: q.trim() === "" ? null : q.trim(),
    },
    null,
  );
  const derive = useDeriveStrategyDraftFromPackage();
  const rows = query.data?.data ?? [];
  const selected = rows.find((r) => r.entity_id === selectedId) ?? null;

  function deriveFrom(row: LibraryPackageRow) {
    derive.mutate(
      {
        sourcePackageRootId: row.entity_id,
        sourcePackageRevisionId: row.current_revision_id,
      },
      { onSuccess: (result) => onDerived(result.draft_id) },
    );
  }

  return (
    <>
      <button
        type="button"
        aria-label="Close Add Package popover"
        onClick={onClose}
        style={{
          position: "fixed",
          inset: 0,
          zIndex: 39,
          background: "transparent",
          border: "none",
          cursor: "default",
        }}
      />
      <div className="package-picker-popover" role="dialog" aria-label="Add Package">
        <div className="package-picker-title">Add Package</div>
        <p className="cp-note" style={{ margin: 0 }}>
          Select a usable Strategy Package revision to derive a new Strategy Draft from.
        </p>
        <input
          aria-label="Search strategy packages"
          placeholder="Search strategy packages…"
          value={q}
          onChange={(event) => setQ(event.target.value)}
          spellCheck={false}
        />
        {query.isLoading ? (
          <p className="cp-note">Loading strategy packages…</p>
        ) : query.isError ? (
          <p role="alert" style={{ color: "var(--down)", margin: 0, fontSize: 13 }}>
            Could not load packages: {errorMessage(query.error)}
          </p>
        ) : rows.length === 0 ? (
          <p className="cp-note">No active strategy packages match.</p>
        ) : (
          <ul className="pkg-picker-list">
            {rows.map((row) => {
              const usable = row.permissions.can_use;
              return (
                <li key={row.entity_id}>
                  <button
                    type="button"
                    className="pkg-picker-row"
                    disabled={!usable}
                    title={
                      usable
                        ? undefined
                        : "Not usable: you lack use permission or the head revision is not validation-passed."
                    }
                    aria-label={`${row.name ?? row.entity_id}, rev ${row.revision_no}${
                      usable ? "" : " (not usable)"
                    }`}
                    onClick={() => setSelectedId(row.entity_id)}
                  >
                    <span className="pkg-picker-name">{row.name ?? row.entity_id}</span>
                    <span className={`badge badge-${validationTone(row.validation_state)}`}>
                      {row.validation_state}
                    </span>
                    <span className="pkg-picker-rev">rev {row.revision_no}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
        {query.data?.meta.has_more ? (
          <p className="cp-note">More packages exist — narrow the search to find them.</p>
        ) : null}
        {selected ? (
          <SelectedPackageSummary
            row={selected}
            onDerive={() => deriveFrom(selected)}
            deriving={derive.isPending}
            deriveError={derive.isError ? derive.error : null}
          />
        ) : null}
        <div className="package-picker-actions">
          {/* Secondary path: build a brand-new package in the CP Agent workspace
              (visually distinct from the primary derive action above). */}
          <Link to="/packages/create" className="btn btn-ghost" onClick={onClose}>
            Create new package →
          </Link>
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </>
  );
}
