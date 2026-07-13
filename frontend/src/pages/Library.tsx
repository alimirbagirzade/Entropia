import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { StatusBadge } from "@/components/StatusBadge";
import { formatUtc } from "@/lib/backtest";
import { useRationaleFamilies } from "@/lib/createPackage";
import { useDeriveStrategyDraftFromPackage } from "@/lib/strategy";
import {
  APPROVAL_STATES,
  CATALOG_LIFECYCLE_STATES,
  CATALOG_PACKAGE_KINDS,
  DEFAULT_LIBRARY_FILTERS,
  PACKAGE_VALIDATION_STATES,
  PERFORMANCE_FIELDS,
  PERMISSION_FLAGS,
  UNASSIGNED_FAMILY,
  VISIBILITY_SCOPES,
  approvalTone,
  lifecycleTone,
  useDeprecatePackage,
  useLibraryPackage,
  useLibraryPackages,
  useSoftDeletePackage,
  validationTone,
  type LibraryFilters,
  type LibraryPackageDetail,
  type LibraryPackageRow,
  type PackageProvenance,
} from "@/lib/library";

// Wide JSON contracts wrap + scroll inside their own box (never widen the page).
const contractStyle = {
  fontFamily: "monospace",
  fontSize: 12,
  whiteSpace: "pre-wrap",
  wordBreak: "break-all",
  maxHeight: 240,
  overflow: "auto",
  margin: 0,
  padding: 8,
  border: "1px solid var(--border)",
  borderRadius: 6,
} as const;

// Forward-only opaque keyset cursors (server contract): Prev replays the
// cursor stack, the client never re-orders or fabricates a page.
function useCursorStack() {
  const [stack, setStack] = useState<string[]>([]);
  const cursor = stack.length > 0 ? stack[stack.length - 1] : null;
  return {
    cursor,
    canPrev: stack.length > 0,
    next: (nextCursor: string) => setStack((prev) => [...prev, nextCursor]),
    prev: () => setStack((prev) => prev.slice(0, -1)),
    reset: () => setStack([]),
  };
}

// Package Library (doc 08): the authentication-gated catalog over the four
// canonical package kinds. Visibility is enforced server-side; a Guest sees
// the 401 envelope verbatim (UI visibility is never authorization, doc 08 §2).
// This slice is read-only — every package action (revise / validate / publish)
// belongs to later slices; the catalog explains availability via the
// server-computed permission flags instead of hiding rows.
export function Library() {
  return (
    <>
      <h1 className="page-title">Package Library</h1>
      <p className="page-sub">
        Catalog of the four canonical package kinds · visibility and permissions are
        server-computed per role
      </p>
      <CatalogCard />
    </>
  );
}

function FacetSelect({
  id,
  label,
  value,
  options,
  onChange,
}: {
  id: string;
  label: string;
  value: string | null;
  options: readonly string[];
  onChange: (value: string | null) => void;
}) {
  return (
    <label htmlFor={id}>
      {label}{" "}
      <select
        id={id}
        value={value ?? ""}
        onChange={(event) => onChange(event.target.value || null)}
      >
        <option value="">all</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

function CatalogCard() {
  const [filters, setFilters] = useState<LibraryFilters>(DEFAULT_LIBRARY_FILTERS);
  const [draftQ, setDraftQ] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const pager = useCursorStack();
  const packages = useLibraryPackages(filters, pager.cursor);
  // Family filter options come from the shared server list (first page), with
  // the `unassigned` sentinel for packages that pin no family.
  const families = useRationaleFamilies(null);

  const applyFilter = (patch: Partial<LibraryFilters>) => {
    setFilters((prev) => ({ ...prev, ...patch }));
    pager.reset();
  };

  const onSearch = (event: FormEvent) => {
    event.preventDefault();
    applyFilter({ q: draftQ.trim() || null });
  };

  return (
    <section className="card" aria-labelledby="library-h">
      <h3 id="library-h" style={{ marginTop: 0 }}>
        Catalog
      </h3>
      <form
        onSubmit={onSearch}
        style={{ display: "flex", flexWrap: "wrap", gap: 12, marginBottom: 12 }}
      >
        <FacetSelect
          id="lib-kind"
          label="Type"
          value={filters.type}
          options={CATALOG_PACKAGE_KINDS}
          onChange={(value) => applyFilter({ type: value })}
        />
        <FacetSelect
          id="lib-lifecycle"
          label="Lifecycle"
          value={filters.lifecycle_state}
          options={CATALOG_LIFECYCLE_STATES}
          onChange={(value) => applyFilter({ lifecycle_state: value })}
        />
        <FacetSelect
          id="lib-validation"
          label="Validation"
          value={filters.validation_state}
          options={PACKAGE_VALIDATION_STATES}
          onChange={(value) => applyFilter({ validation_state: value })}
        />
        <FacetSelect
          id="lib-approval"
          label="Approval"
          value={filters.approval_state}
          options={APPROVAL_STATES}
          onChange={(value) => applyFilter({ approval_state: value })}
        />
        <FacetSelect
          id="lib-visibility"
          label="Visibility"
          value={filters.visibility_scope}
          options={VISIBILITY_SCOPES}
          onChange={(value) => applyFilter({ visibility_scope: value })}
        />
        <label htmlFor="lib-family">
          Rationale family{" "}
          <select
            id="lib-family"
            value={filters.rationale_family_id ?? ""}
            onChange={(event) => applyFilter({ rationale_family_id: event.target.value || null })}
          >
            <option value="">all</option>
            <option value={UNASSIGNED_FAMILY}>unassigned</option>
            {(families.data?.data ?? []).map((family) => (
              <option key={family.entity_id} value={family.entity_id}>
                {family.display_name}
              </option>
            ))}
          </select>
        </label>
        <label htmlFor="lib-q">
          Search{" "}
          <input
            id="lib-q"
            value={draftQ}
            onChange={(event) => setDraftQ(event.target.value)}
            placeholder="package name"
          />
        </label>
        <button type="submit" className="btn">
          Search
        </button>
      </form>

      {packages.isLoading ? (
        <Loading label="Loading catalog…" />
      ) : packages.isError ? (
        <ErrorState error={packages.error} onRetry={() => void packages.refetch()} />
      ) : packages.data ? (
        <>
          {packages.data.data.length === 0 ? (
            <EmptyState title="No packages match the current filters" />
          ) : (
            <table className="metrics-table">
              <thead>
                <tr>
                  <th scope="col">Name</th>
                  <th scope="col">Type</th>
                  <th scope="col">Rev</th>
                  <th scope="col">Lifecycle</th>
                  <th scope="col">Validation</th>
                  <th scope="col">Approval</th>
                  <th scope="col">Visibility</th>
                  <th scope="col">Family</th>
                  <th scope="col" aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {packages.data.data.map((row) => (
                  <PackageRow
                    key={row.entity_id}
                    row={row}
                    onDetail={() => setSelectedId(row.entity_id)}
                  />
                ))}
              </tbody>
            </table>
          )}
          <Pager
            canPrev={pager.canPrev}
            nextCursor={packages.data.meta.cursor}
            onPrev={pager.prev}
            onNext={pager.next}
          />
        </>
      ) : null}

      {selectedId ? (
        <PackageDetail entityId={selectedId} onClose={() => setSelectedId(null)} />
      ) : null}
    </section>
  );
}

function PackageRow({ row, onDetail }: { row: LibraryPackageRow; onDetail: () => void }) {
  return (
    <tr>
      <td>{row.name ?? "—"}</td>
      <td>
        <code>{row.package_kind}</code>
      </td>
      <td>v{row.revision_no}</td>
      <td>
        <StatusBadge tone={lifecycleTone(row.lifecycle_state)} label={row.lifecycle_state} />
      </td>
      <td>
        <StatusBadge tone={validationTone(row.validation_state)} label={row.validation_state} />
      </td>
      <td>
        <StatusBadge tone={approvalTone(row.approval_state)} label={row.approval_state} />
      </td>
      <td>{row.visibility_scope}</td>
      <td>{row.rationale_family?.name ?? "—"}</td>
      <td>
        <button type="button" className="btn" onClick={onDetail}>
          Detail
        </button>
      </td>
    </tr>
  );
}

function PackageDetail({ entityId, onClose }: { entityId: string; onClose: () => void }) {
  const detail = useLibraryPackage(entityId);
  const pkg = detail.data;
  return (
    <div style={{ marginTop: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <h4 style={{ margin: 0 }}>Package detail</h4>
        <button type="button" className="btn" onClick={onClose}>
          Close
        </button>
      </div>
      {detail.isLoading ? (
        <Loading label="Loading package…" />
      ) : detail.isError ? (
        <ErrorState error={detail.error} onRetry={() => void detail.refetch()} />
      ) : pkg ? (
        <>
          <dl className="kv">
            <dt>Package</dt>
            <dd>
              {pkg.name ?? "—"} · <code>{pkg.package_kind}</code> (
              {pkg.entity_id})
            </dd>
            <dt>Head revision</dt>
            <dd>
              v{pkg.revision_no} · <code>{pkg.current_revision_id}</code>
              {pkg.change_note ? ` — ${pkg.change_note}` : ""}
            </dd>
            <dt>States</dt>
            <dd>
              <StatusBadge
                tone={lifecycleTone(pkg.lifecycle_state)}
                label={pkg.lifecycle_state}
              />{" "}
              <StatusBadge
                tone={validationTone(pkg.validation_state)}
                label={pkg.validation_state}
              />{" "}
              <StatusBadge
                tone={approvalTone(pkg.approval_state)}
                label={pkg.approval_state}
              />{" "}
              · {pkg.visibility_scope}
            </dd>
            <dt>Rationale family</dt>
            <dd>
              {pkg.rationale_family ? (
                <>
                  {pkg.rationale_family.name ?? "—"}
                  {!pkg.rationale_family.family_active ? " (family inactive)" : ""}
                  {pkg.rationale_family.pinned_name &&
                  pkg.rationale_family.pinned_name !== pkg.rationale_family.name
                    ? ` · pinned as ${pkg.rationale_family.pinned_name}`
                    : ""}
                </>
              ) : (
                "unassigned"
              )}
            </dd>
            <dt>Output kinds</dt>
            <dd>
              {pkg.output_kinds.length > 0 ? pkg.output_kinds.join(", ") : "—"}
            </dd>
            <dt>Origin</dt>
            <dd>
              owner {pkg.owner_principal_id ?? "—"}
              {pkg.derived_from_revision_id
                ? ` · derived from ${pkg.derived_from_revision_id}`
                : ""}
              {` · created ${formatUtc(pkg.created_at)}`}
            </dd>
            <dt>Content hash</dt>
            <dd>
              <code>{pkg.content_hash}</code>
            </dd>
          </dl>

          <h5 style={{ marginBottom: 4 }}>Permissions (server-computed)</h5>
          <ul style={{ display: "flex", flexWrap: "wrap", gap: 8, listStyle: "none", padding: 0 }}>
            {PERMISSION_FLAGS.map((flag) => (
              <li key={flag}>
                <code>{flag}</code>: {pkg.permissions[flag] ? "yes" : "no"}
              </li>
            ))}
          </ul>

          <DeriveStrategyBlock pkg={pkg} />
          <PackageActions pkg={pkg} onDeleted={onClose} />

          <h5 style={{ marginBottom: 4 }}>Performance</h5>
          <dl className="kv">
            {PERFORMANCE_FIELDS.map((field) => (
              <PerformanceField
                key={field}
                field={field}
                value={pkg.performance[field]}
              />
            ))}
          </dl>

          {pkg.provenance ? <ProvenanceBlock provenance={pkg.provenance} /> : null}

          <h5 style={{ marginBottom: 4 }}>Input contract</h5>
          <pre style={contractStyle}>{JSON.stringify(pkg.input_contract, null, 2)}</pre>
          <h5 style={{ marginBottom: 4 }}>Output contract</h5>
          <pre style={contractStyle}>{JSON.stringify(pkg.output_contract, null, 2)}</pre>
          {pkg.dependency_snapshot ? (
            <>
              <h5 style={{ marginBottom: 4 }}>Dependency snapshot</h5>
              <pre style={contractStyle}>
                {JSON.stringify(pkg.dependency_snapshot, null, 2)}
              </pre>
            </>
          ) : null}
          {pkg.validation_summary ? (
            <>
              <h5 style={{ marginBottom: 4 }}>Validation summary</h5>
              <pre style={contractStyle}>
                {JSON.stringify(pkg.validation_summary, null, 2)}
              </pre>
            </>
          ) : null}

          <h5 style={{ marginBottom: 4 }}>Revision history</h5>
          <table className="metrics-table">
            <thead>
              <tr>
                <th scope="col">Rev</th>
                <th scope="col">Validation</th>
                <th scope="col">Approval</th>
                <th scope="col">Note</th>
                <th scope="col">Created (UTC)</th>
              </tr>
            </thead>
            <tbody>
              {pkg.revisions.map((revision) => (
                <tr key={revision.revision_id}>
                  <td>v{revision.revision_no}</td>
                  <td>
                    <StatusBadge
                      tone={validationTone(revision.validation_state)}
                      label={revision.validation_state}
                    />
                  </td>
                  <td>
                    <StatusBadge
                      tone={approvalTone(revision.approval_state)}
                      label={revision.approval_state}
                    />
                  </td>
                  <td>{revision.change_note ?? "—"}</td>
                  <td>{formatUtc(revision.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : null}
    </div>
  );
}

// GAP-03: "Create Strategy Draft from Package (Strategy only)" (doc 08 §4.3). Shown
// only when the package is a Strategy kind AND the server marks the head usable
// (permissions.can_use = active + validation-passed). The UI never authorizes — the
// derive command re-validates kind/usability/visibility and renders 403/422 verbatim.
// On success it deep-links to the new draft (/strategy?draft=…); the source package
// is never modified (it is pinned as provenance).
function DeriveStrategyBlock({ pkg }: { pkg: LibraryPackageDetail }) {
  const navigate = useNavigate();
  const derive = useDeriveStrategyDraftFromPackage();
  if (pkg.package_kind !== "strategy" || !pkg.permissions.can_use) return null;
  const onDerive = () =>
    derive.mutate(
      {
        sourcePackageRootId: pkg.entity_id,
        sourcePackageRevisionId: pkg.current_revision_id,
      },
      {
        onSuccess: (result) =>
          navigate(`/strategy?draft=${encodeURIComponent(result.draft_id)}`),
      },
    );
  return (
    <div style={{ marginTop: 12 }}>
      <button type="button" className="btn" onClick={onDerive} disabled={derive.isPending}>
        {derive.isPending ? "Creating…" : "Create Strategy Draft from Package"}
      </button>
      <p className="page-sub" style={{ marginTop: 4 }}>
        Derives your own editable strategy draft, pinning this exact package revision as
        its source. The source package is never modified (doc 08 §4.3).
      </p>
      {derive.isError ? <ErrorState error={derive.error} /> : null}
    </div>
  );
}

// GAP-06 (epic slice 1): lifecycle actions on the detail panel (doc 08 §7).
// Each button is shown only when the SERVER marks the capability true, but the
// UI never authorizes — the command re-validates and renders 403/409 verbatim.
//   - Deprecate: active -> deprecated (owner/Admin), no OCC; the package stays
//     listed but is no longer offered for new work (can_use turns false).
//   - Move to Trash: a two-step soft delete under If-Match "rv-N" OCC; on
//     success the root leaves the catalog, so the panel closes.
function PackageActions({ pkg, onDeleted }: { pkg: LibraryPackageDetail; onDeleted: () => void }) {
  const deprecate = useDeprecatePackage();
  const softDelete = useSoftDeletePackage();
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  if (!pkg.permissions.can_deprecate && !pkg.permissions.can_soft_delete) return null;

  const onDeprecate = () => deprecate.mutate({ entityId: pkg.entity_id });
  const onConfirmDelete = () =>
    softDelete.mutate(
      { entityId: pkg.entity_id, rowVersion: pkg.row_version },
      {
        onSuccess: () => {
          setConfirmingDelete(false);
          onDeleted();
        },
      },
    );

  return (
    <div style={{ marginTop: 12 }}>
      <h5 style={{ marginBottom: 4 }}>Lifecycle actions</h5>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        {pkg.permissions.can_deprecate ? (
          <button
            type="button"
            className="btn"
            onClick={onDeprecate}
            disabled={deprecate.isPending}
          >
            {deprecate.isPending ? "Deprecating…" : "Deprecate"}
          </button>
        ) : null}
        {pkg.permissions.can_soft_delete && !confirmingDelete ? (
          <button type="button" className="btn" onClick={() => setConfirmingDelete(true)}>
            Move to Trash
          </button>
        ) : null}
        {pkg.permissions.can_soft_delete && confirmingDelete ? (
          <>
            <button
              type="button"
              className="btn btn-danger"
              onClick={onConfirmDelete}
              disabled={softDelete.isPending}
            >
              {softDelete.isPending ? "Deleting…" : "Confirm delete"}
            </button>
            <button
              type="button"
              className="btn"
              onClick={() => setConfirmingDelete(false)}
              disabled={softDelete.isPending}
            >
              Cancel
            </button>
          </>
        ) : null}
      </div>
      <p className="page-sub" style={{ marginTop: 4 }}>
        Deprecate keeps the package listed but stops new use; Move to Trash soft-deletes it
        (historical pins keep resolving) and an Admin can restore it from Trash (doc 08 §7, §8.4).
      </p>
      {deprecate.isError ? <ErrorState error={deprecate.error} /> : null}
      {softDelete.isError ? <ErrorState error={softDelete.error} /> : null}
    </div>
  );
}

// L4: a metric that does not apply renders its availability label verbatim,
// never a fabricated number.
function PerformanceField({ field, value }: { field: string; value: string | undefined }) {
  return (
    <>
      <dt>{field}</dt>
      <dd>{value === "not_applicable" ? "N/A (not applicable)" : (value ?? "—")}</dd>
    </>
  );
}

function ProvenanceBlock({
  provenance,
}: {
  provenance: PackageProvenance;
}) {
  return (
    <>
      <h5 style={{ marginBottom: 4 }}>Provenance (Create Package request)</h5>
      <dl className="kv">
        <dt>Request</dt>
        <dd>
          <code>{provenance.request_entity_id}</code> · {provenance.creation_mode} ·{" "}
          {provenance.source_kind}
          {provenance.source_language ? ` (${provenance.source_language})` : ""} →{" "}
          {provenance.target_runtime}
        </dd>
        {provenance.draft_revision_id ? (
          <>
            <dt>Draft revision</dt>
            <dd>
              <code>{provenance.draft_revision_id}</code>
            </dd>
          </>
        ) : null}
        {provenance.scan ? (
          <>
            <dt>Dependency scan</dt>
            <dd>
              {provenance.scan.status} (attempt {provenance.scan.attempt_no}) ·{" "}
              {provenance.scan.resolved_refs.length} resolved ·{" "}
              {provenance.scan.missing_calls.length} missing ·{" "}
              {provenance.scan.unsupported_calls.length} unsupported
            </dd>
          </>
        ) : null}
      </dl>
    </>
  );
}

function Pager({
  canPrev,
  nextCursor,
  onPrev,
  onNext,
}: {
  canPrev: boolean;
  nextCursor: string | null;
  onPrev: () => void;
  onNext: (cursor: string) => void;
}) {
  if (!canPrev && nextCursor === null) return null;
  return (
    <div style={{ display: "flex", gap: 12, marginTop: 12 }}>
      <button type="button" className="btn" disabled={!canPrev} onClick={onPrev}>
        Prev
      </button>
      <button
        type="button"
        className="btn"
        disabled={nextCursor === null}
        onClick={() => (nextCursor !== null ? onNext(nextCursor) : undefined)}
      >
        Next
      </button>
    </div>
  );
}
