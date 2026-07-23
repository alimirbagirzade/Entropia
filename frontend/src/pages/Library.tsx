import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { StatusBadge } from "@/components/StatusBadge";
import { formatUtc } from "@/lib/backtest";
import { useRationaleFamilies } from "@/lib/createPackage";
import {
  packageImportTone,
  usePackageImportReport,
  usePackageImports,
  useSubmitPackageImport,
  type PackageImportReport,
} from "@/lib/packageImport";
import {
  usePackageShares,
  useRevokeShare,
  useSharePackage,
  type PackageShare,
} from "@/lib/sharing";
import { useDeriveStrategyDraftFromPackage } from "@/lib/strategy";
import {
  APPROVAL_STATES,
  CATALOG_LIFECYCLE_STATES,
  CATALOG_PACKAGE_KINDS,
  DEFAULT_LIBRARY_FILTERS,
  PACKAGE_VALIDATION_STATES,
  PERFORMANCE_FIELDS,
  PERMISSION_FLAGS,
  TIMEFRAME_SCOPES,
  UNASSIGNED_FAMILY,
  VISIBILITY_SCOPES,
  approvalTone,
  lifecycleTone,
  scopeLabel,
  useApprovePackage,
  useCreatePackageRevision,
  useDeprecatePackage,
  useDerivePackage,
  useExportPackage,
  useLibraryPackage,
  useLibraryPackages,
  useRequestApproval,
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
      <ImportCard />
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

// v18 mockup groups the catalog into per-type sections (§3.1). Production only
// has the four canonical kinds; the order below is the mockup's submenu order.
// A row whose kind is outside this list is surfaced under its own bucket, never
// silently hidden (doc 08 §3.2 "unsupported values not silently hidden").
const CATALOG_SECTIONS: readonly { kind: string; label: string }[] = [
  { kind: "strategy", label: "Strategy Packages" },
  { kind: "indicator", label: "Indicator Packages" },
  { kind: "condition", label: "Condition Packages" },
  { kind: "embedded_system", label: "Embedded System Packages" },
];

// Sort By is a CLIENT-LOCAL presentation control (mockup §3.2 "local
// numeric/string sort"): it reorders the rows already on the current keyset page
// over fields the row projection carries. It is never a server query param — the
// ["library"] contract is untouched. Performance sorts are omitted here: every
// non-Strategy row is `not_applicable` and no runs are linked (doc 08 §3.2, L4).
type LibrarySort = "created" | "name";
const LIBRARY_SORTS: readonly { value: LibrarySort; label: string }[] = [
  { value: "created", label: "Created Date" },
  { value: "name", label: "Name" },
];

function sortRows(rows: LibraryPackageRow[], sort: LibrarySort): LibraryPackageRow[] {
  const ordered = [...rows];
  if (sort === "name") {
    ordered.sort((a, b) => (a.name ?? "").localeCompare(b.name ?? ""));
  } else {
    // Newest first; rows without a timestamp sort last (stable, deterministic).
    ordered.sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""));
  }
  return ordered;
}

// Group the current page's rows into the canonical sections, then any leftover
// kinds, dropping empty sections. Sorting is applied per section.
function groupRows(
  rows: LibraryPackageRow[],
  sort: LibrarySort,
): { kind: string; label: string; rows: LibraryPackageRow[] }[] {
  const canonicalKinds = new Set(CATALOG_SECTIONS.map((section) => section.kind));
  const sections = CATALOG_SECTIONS.map((section) => ({
    ...section,
    rows: sortRows(
      rows.filter((row) => row.package_kind === section.kind),
      sort,
    ),
  }));
  const leftoverKinds = [
    ...new Set(
      rows.filter((row) => !canonicalKinds.has(row.package_kind)).map((r) => r.package_kind),
    ),
  ];
  const extras = leftoverKinds.map((kind) => ({
    kind,
    label: `${kind} Packages`,
    rows: sortRows(
      rows.filter((row) => row.package_kind === kind),
      sort,
    ),
  }));
  return [...sections, ...extras].filter((section) => section.rows.length > 0);
}

function CatalogCard() {
  const [filters, setFilters] = useState<LibraryFilters>(DEFAULT_LIBRARY_FILTERS);
  const [draftQ, setDraftQ] = useState("");
  const [sortBy, setSortBy] = useState<LibrarySort>("created");
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

  const onClearFilters = () => {
    setFilters(DEFAULT_LIBRARY_FILTERS);
    setDraftQ("");
    pager.reset();
  };

  const sections = packages.data ? groupRows(packages.data.data, sortBy) : [];
  // Market is an OPEN scope (doc 08 §3.2, finding P-06): offer the values the current
  // catalog page actually carries (plus the System/Unspecified sentinels and any active
  // selection) — the client shows only values the projection supplies, never a
  // fabricated list. Timeframe is a closed capability vocabulary (TIMEFRAME_SCOPES).
  const marketOptions = Array.from(
    new Set<string>([
      "system",
      "unspecified",
      ...(packages.data?.data ?? []).map((row) => row.market_scope),
      ...(filters.market ? [filters.market] : []),
    ]),
  ).sort();

  return (
    <section className="card" aria-labelledby="library-h">
      <h3 id="library-h" style={{ marginTop: 0 }}>
        Catalog
      </h3>
      {/* v18 mockup .package-pool-intro — role/permission summary banner. */}
      <div className="package-pool-intro">
        Packages are reusable building blocks. Admin, Supervisor and Agent can view and use every
        package object; Supervisor and Agent may edit or delete only objects they own. Visibility
        and permissions are computed by the server per role.
      </div>
      {/* v18 mockup filter bar: a responsive grid of facet selects + a
          client-local Sort By. The V18 "Status" control is split into the
          orthogonal server facets it conflates (lifecycle / validation /
          approval / visibility, doc 08 §3.2 "Canonical alignment"). Market and
          Timeframe are server-queryable catalog facets (doc 08 §3.2, finding
          P-06): the derived scope is ESP -> System and a declared/unspecified scope
          otherwise, filtered server-side — never hidden, coerced or fabricated. */}
      <form onSubmit={onSearch} className="package-filter-bar">
        <div className="package-filter-grid">
          <FacetSelect
            id="lib-kind"
            label="Type"
            value={filters.type}
            options={CATALOG_PACKAGE_KINDS}
            onChange={(value) => applyFilter({ type: value })}
          />
          <FacetSelect
            id="lib-market"
            label="Market"
            value={filters.market}
            options={marketOptions}
            onChange={(value) => applyFilter({ market: value })}
          />
          <FacetSelect
            id="lib-timeframe"
            label="Timeframe"
            value={filters.timeframe}
            options={TIMEFRAME_SCOPES}
            onChange={(value) => applyFilter({ timeframe: value })}
          />
          <label htmlFor="lib-family">
            Rationale family
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
          <label htmlFor="lib-sort">
            Sort by
            <select
              id="lib-sort"
              value={sortBy}
              onChange={(event) => setSortBy(event.target.value as LibrarySort)}
            >
              {LIBRARY_SORTS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label htmlFor="lib-q">
            Search
            <input
              id="lib-q"
              value={draftQ}
              onChange={(event) => setDraftQ(event.target.value)}
              placeholder="package name"
            />
          </label>
        </div>
        <div className="package-filter-actions">
          <button type="submit" className="btn">
            Search
          </button>
          <button type="button" className="btn" onClick={onClearFilters}>
            Clear filters
          </button>
        </div>
      </form>

      {packages.isLoading ? (
        <Loading label="Loading catalog…" />
      ) : packages.isError ? (
        <ErrorState error={packages.error} onRetry={() => void packages.refetch()} />
      ) : packages.data ? (
        <>
          {sections.length === 0 ? (
            <EmptyState title="No packages matched the current filters" />
          ) : (
            // v18 mockup: rows grouped into per-type sections; each row is an
            // expandable .package-row (open → light-cyan) that embeds its detail
            // inline, instead of a single wide catalog table.
            <div className="package-pool-wrapper">
              {sections.map((section) => (
                <section key={section.kind} className="package-pool-section">
                  <h4 className="package-section-title">{section.label}</h4>
                  <div
                    className="package-list"
                    role="list"
                    aria-label={`${section.label} rows`}
                  >
                    {section.rows.map((row) => (
                      <PackageRow
                        key={row.entity_id}
                        row={row}
                        open={selectedId === row.entity_id}
                        onToggle={() =>
                          setSelectedId((current) =>
                            current === row.entity_id ? null : row.entity_id,
                          )
                        }
                      />
                    ))}
                  </div>
                </section>
              ))}
            </div>
          )}
          <Pager
            canPrev={pager.canPrev}
            nextCursor={packages.data.meta.cursor}
            onPrev={pager.prev}
            onNext={pager.next}
          />
        </>
      ) : null}
    </section>
  );
}

function PackageRow({
  row,
  open,
  onToggle,
}: {
  row: LibraryPackageRow;
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <div role="listitem" className="package-card">
      <div className={`package-row${open ? " open" : ""}`}>
        <div className="package-text">
          <strong>{row.name ?? "—"}</strong>
          <code>{row.package_kind}</code>
          <span>v{row.revision_no}</span>
          <StatusBadge tone={lifecycleTone(row.lifecycle_state)} label={row.lifecycle_state} />
          <StatusBadge tone={validationTone(row.validation_state)} label={row.validation_state} />
          <StatusBadge tone={approvalTone(row.approval_state)} label={row.approval_state} />
          <span>{row.visibility_scope}</span>
          <span title="Market scope">{scopeLabel(row.market_scope)}</span>
          <span title="Timeframe scope">{scopeLabel(row.timeframe_scope)}</span>
          <span>{row.rationale_family?.name ?? "—"}</span>
        </div>
        {/* aria-label keeps the accessible name "Detail" so the toggle stays the
            catalog's detail affordance; the glyph mirrors the mockup arrow. */}
        <button
          type="button"
          className="package-arrow"
          aria-label="Detail"
          aria-expanded={open}
          onClick={onToggle}
        >
          {open ? "▲" : "▼"}
        </button>
      </div>
      {open ? (
        <div className="package-details">
          <PackageDetail entityId={row.entity_id} onClose={onToggle} />
        </div>
      ) : null}
    </div>
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
            <dt>Market</dt>
            <dd>{scopeLabel(pkg.market_scope)}</dd>
            <dt>Timeframe</dt>
            <dd>{scopeLabel(pkg.timeframe_scope)}</dd>
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
          {/* v18 mockup .package-meta-grid — server-computed flags as bordered cells. */}
          <div className="package-meta-grid">
            {PERMISSION_FLAGS.map((flag) => (
              <div key={flag} className="package-meta-cell">
                <code>{flag}</code>: {pkg.permissions[flag] ? "yes" : "no"}
              </div>
            ))}
          </div>

          <DeriveStrategyBlock pkg={pkg} />
          <PackageRevisionActions pkg={pkg} />
          <PackageApprovalActions pkg={pkg} />
          <PackageExportBlock pkg={pkg} />
          <PackageActions pkg={pkg} onDeleted={onClose} />
          <PackageSharePanel pkg={pkg} />

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

          {/* Keep the expanded detail compact (mockup §3.1 = description +
              metadata grid + actions): the verbose raw-JSON contracts and
              snapshots stay one click away behind a disclosure instead of
              turning the row into a long technical management page. */}
          <details style={{ marginTop: 12 }}>
            <summary style={{ cursor: "pointer", fontWeight: 600 }}>
              Technical contracts &amp; snapshots
            </summary>
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
          </details>

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

// GAP-06 (epic R2a): revision-plane actions on the detail panel (doc 08 §7).
// Shown only when the SERVER marks the capability true, but the UI never
// authorizes — the command re-validates and renders 403/409/422 verbatim.
//   - Derive: any viewer copies this exact revision into a NEW private root they
//     own (name required); the source package is never modified.
//   - Create Revision: owner/Admin appends an immutable revision N+1 under the
//     BODY-form expected_head_revision_id OCC (the detail current_revision_id);
//     a concurrent head move -> 409 PACKAGE_REVISION_CONFLICT.
function PackageRevisionActions({ pkg }: { pkg: LibraryPackageDetail }) {
  const derive = useDerivePackage();
  const createRevision = useCreatePackageRevision();
  const [deriveName, setDeriveName] = useState("");
  const [deriveNote, setDeriveNote] = useState("");
  const [revisionNote, setRevisionNote] = useState("");

  if (!pkg.permissions.can_derive && !pkg.permissions.can_create_revision) return null;

  const onDerive = (event: FormEvent) => {
    event.preventDefault();
    const name = deriveName.trim();
    if (!name) return;
    derive.mutate(
      {
        entityId: pkg.entity_id,
        sourceRevisionId: pkg.current_revision_id,
        name,
        changeNote: deriveNote.trim() || undefined,
      },
      {
        onSuccess: () => {
          setDeriveName("");
          setDeriveNote("");
        },
      },
    );
  };

  const onCreateRevision = (event: FormEvent) => {
    event.preventDefault();
    createRevision.mutate(
      {
        entityId: pkg.entity_id,
        expectedHeadRevisionId: pkg.current_revision_id,
        changeNote: revisionNote.trim() || undefined,
      },
      { onSuccess: () => setRevisionNote("") },
    );
  };

  return (
    <div style={{ marginTop: 12 }}>
      <h5 style={{ marginBottom: 4 }}>Revision actions</h5>
      {pkg.permissions.can_derive ? (
        <form onSubmit={onDerive} style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          <label htmlFor="lib-derive-name">
            Derive as{" "}
            <input
              id="lib-derive-name"
              value={deriveName}
              onChange={(event) => setDeriveName(event.target.value)}
              placeholder="new package name"
            />
          </label>
          <label htmlFor="lib-derive-note">
            Change note{" "}
            <input
              id="lib-derive-note"
              value={deriveNote}
              onChange={(event) => setDeriveNote(event.target.value)}
              placeholder="optional"
            />
          </label>
          <button type="submit" className="btn" disabled={derive.isPending || !deriveName.trim()}>
            {derive.isPending ? "Deriving…" : "Derive"}
          </button>
        </form>
      ) : null}
      {pkg.permissions.can_derive ? (
        <p className="page-sub" style={{ marginTop: 4 }}>
          Copies this exact revision into your own new private package (pinned as its source).
          The source package is never modified (doc 08 §8.2).
        </p>
      ) : null}
      {derive.isError ? <ErrorState error={derive.error} /> : null}
      {derive.data ? (
        <p className="page-sub" style={{ marginTop: 4 }}>
          Derived <strong>{derive.data.name}</strong> (<code>{derive.data.entity_id}</code>).
        </p>
      ) : null}

      {pkg.permissions.can_create_revision ? (
        <form
          onSubmit={onCreateRevision}
          style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 8 }}
        >
          <label htmlFor="lib-revision-note">
            New revision note{" "}
            <input
              id="lib-revision-note"
              value={revisionNote}
              onChange={(event) => setRevisionNote(event.target.value)}
              placeholder="optional change note"
            />
          </label>
          <button type="submit" className="btn" disabled={createRevision.isPending}>
            {createRevision.isPending ? "Creating…" : "Create Revision"}
          </button>
        </form>
      ) : null}
      {pkg.permissions.can_create_revision ? (
        <p className="page-sub" style={{ marginTop: 4 }}>
          Appends an immutable revision based on the current head (v{pkg.revision_no}); the base
          revision stays unchanged. A concurrent head move is rejected (doc 08 §8.5).
        </p>
      ) : null}
      {createRevision.isError ? <ErrorState error={createRevision.error} /> : null}
      {createRevision.data ? (
        <p className="page-sub" style={{ marginTop: 4 }}>
          Created revision v{createRevision.data.revision_no}.
        </p>
      ) : null}
    </div>
  );
}

// GAP-06 (epic R2c): Export the immutable package-revision MANIFEST (doc 08 §7).
// Shown when the SERVER marks can_export (any viewer). It is read-only provenance —
// the button produces a content-addressed manifest + hash for the current head; the
// source package is never modified. The UI never authorizes (server re-validates).
function PackageExportBlock({ pkg }: { pkg: LibraryPackageDetail }) {
  const exportPkg = useExportPackage();
  if (!pkg.permissions.can_export) return null;
  const onExport = () =>
    exportPkg.mutate({ entityId: pkg.entity_id, revisionId: pkg.current_revision_id });
  return (
    <div style={{ marginTop: 12 }}>
      <h5 style={{ marginBottom: 4 }}>Export</h5>
      <button type="button" className="btn" onClick={onExport} disabled={exportPkg.isPending}>
        {exportPkg.isPending ? "Exporting…" : "Export manifest"}
      </button>
      <p className="page-sub" style={{ marginTop: 4 }}>
        Produces the immutable manifest for the current head (v{pkg.revision_no}) — the exact
        contracts, dependency snapshot and content hash. The source package is never modified.
      </p>
      {exportPkg.isError ? <ErrorState error={exportPkg.error} /> : null}
      {exportPkg.data ? (
        <>
          <p className="page-sub" style={{ marginTop: 4 }}>
            Manifest hash: <code>{exportPkg.data.manifest_hash}</code>
          </p>
          <pre style={contractStyle}>{JSON.stringify(exportPkg.data.manifest, null, 2)}</pre>
        </>
      ) : null}
    </div>
  );
}

// GAP-06 (epic R2b): approval sub-flow on the detail panel (doc 08 §7). Shown only
// when the SERVER marks the capability true, but the UI never authorizes — the
// command re-validates and renders 403/409/422 verbatim.
//   - Request Approval: owner/Admin moves the PASSED head DRAFT -> APPROVAL_REQUESTED.
//     This is the transition that opens the Admin Approve gate (can_approve_publish).
//   - Approve & Publish: Admin-only atomic APPROVED + PUBLISHED (two-step confirm).
// Both carry the BODY-form expected_head_revision_id OCC (the current head).
function PackageApprovalActions({ pkg }: { pkg: LibraryPackageDetail }) {
  const requestApproval = useRequestApproval();
  const approve = useApprovePackage();
  const [approveNote, setApproveNote] = useState("");
  const [confirmingApprove, setConfirmingApprove] = useState(false);

  if (!pkg.permissions.can_request_approval && !pkg.permissions.can_approve_publish) return null;

  const onRequest = () =>
    requestApproval.mutate({ entityId: pkg.entity_id, revisionId: pkg.current_revision_id });
  const onApprove = () =>
    approve.mutate(
      {
        entityId: pkg.entity_id,
        revisionId: pkg.current_revision_id,
        note: approveNote.trim() || undefined,
      },
      {
        onSuccess: () => {
          setConfirmingApprove(false);
          setApproveNote("");
        },
      },
    );

  return (
    <div style={{ marginTop: 12 }}>
      <h5 style={{ marginBottom: 4 }}>Approval actions</h5>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        {pkg.permissions.can_request_approval ? (
          <button
            type="button"
            className="btn"
            onClick={onRequest}
            disabled={requestApproval.isPending}
          >
            {requestApproval.isPending ? "Requesting…" : "Request Approval"}
          </button>
        ) : null}
        {pkg.permissions.can_approve_publish && !confirmingApprove ? (
          <button type="button" className="btn" onClick={() => setConfirmingApprove(true)}>
            Approve &amp; Publish
          </button>
        ) : null}
        {pkg.permissions.can_approve_publish && confirmingApprove ? (
          <>
            <label htmlFor="lib-approve-note">
              Note{" "}
              <input
                id="lib-approve-note"
                value={approveNote}
                onChange={(event) => setApproveNote(event.target.value)}
                placeholder="optional"
              />
            </label>
            <button type="button" className="btn" onClick={onApprove} disabled={approve.isPending}>
              {approve.isPending ? "Publishing…" : "Confirm approve & publish"}
            </button>
            <button
              type="button"
              className="btn"
              onClick={() => setConfirmingApprove(false)}
              disabled={approve.isPending}
            >
              Cancel
            </button>
          </>
        ) : null}
      </div>
      <p className="page-sub" style={{ marginTop: 4 }}>
        Request Approval submits the validated head for review; only an Admin can atomically
        Approve &amp; Publish it into the shared/published scope (doc 08 §7, CR-02).
      </p>
      {requestApproval.isError ? <ErrorState error={requestApproval.error} /> : null}
      {requestApproval.data ? (
        <p className="page-sub" style={{ marginTop: 4 }}>
          Approval requested ({requestApproval.data.approval_state}).
        </p>
      ) : null}
      {approve.isError ? <ErrorState error={approve.error} /> : null}
      {approve.data ? (
        <p className="page-sub" style={{ marginTop: 4 }}>
          Published — {approve.data.approval_state} · {approve.data.visibility_scope}.
        </p>
      ) : null}
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

// GAP-17: explicit sharing (doc §6.4). Shown only when the SERVER marks
// `can_share` (owner/Admin on an active, non-public head), but the UI never
// authorizes — the command re-validates and renders 403/409/422 verbatim. Grant
// by email; the backend flips the head PRIVATE <-> EXPLICITLY_SHARED as the
// first/last grant is added/removed. The OCC token is the current package
// row_version (freshest from the shares GET), carried as the If-Match "rv-N"
// ETag; a stale head -> 409 STALE_REVISION.
function PackageSharePanel({ pkg }: { pkg: LibraryPackageDetail }) {
  const shares = usePackageShares(pkg.entity_id, pkg.permissions.can_share);
  const share = useSharePackage();
  const revoke = useRevokeShare();
  const [email, setEmail] = useState("");
  if (!pkg.permissions.can_share) return null;

  const rowVersion = shares.data?.row_version ?? pkg.row_version;
  const grants = shares.data?.shares ?? [];

  const onShare = (event: FormEvent) => {
    event.preventDefault();
    const granteeEmail = email.trim();
    if (!granteeEmail) return;
    share.mutate(
      { entityId: pkg.entity_id, rowVersion, granteeEmail },
      { onSuccess: () => setEmail("") },
    );
  };
  const onRevoke = (grant: PackageShare) =>
    revoke.mutate({ entityId: pkg.entity_id, shareId: grant.share_id, rowVersion });

  return (
    <div style={{ marginTop: 12 }}>
      <h5 style={{ marginBottom: 4 }}>Sharing</h5>
      <form onSubmit={onShare} style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        <label htmlFor="lib-share-email">
          Share with{" "}
          <input
            id="lib-share-email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="grantee email"
          />
        </label>
        <button type="submit" className="btn" disabled={share.isPending || !email.trim()}>
          {share.isPending ? "Sharing…" : "Share"}
        </button>
      </form>
      <p className="page-sub" style={{ marginTop: 4 }}>
        Grants a specific user explicit view/use access to this private package. Sharing never
        transfers ownership; only the owner or an Admin can manage it (Master §6.4).
      </p>
      {share.isError ? <ErrorState error={share.error} /> : null}
      {revoke.isError ? <ErrorState error={revoke.error} /> : null}
      {shares.isLoading ? (
        <Loading label="Loading shares…" />
      ) : shares.isError ? (
        <ErrorState error={shares.error} onRetry={() => void shares.refetch()} />
      ) : grants.length === 0 ? (
        <p className="page-sub">Not shared with anyone yet.</p>
      ) : (
        <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
          {grants.map((grant) => (
            <li
              key={grant.share_id}
              style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}
            >
              <span>
                {grant.grantee_email ?? grant.grantee_display_name ?? grant.grantee_principal_id}
              </span>
              <button
                type="button"
                className="btn"
                onClick={() => onRevoke(grant)}
                disabled={revoke.isPending}
              >
                Revoke
              </button>
            </li>
          ))}
        </ul>
      )}
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

// S3 slice (d) — Import a foreign export manifest (doc 08 §9.1/§10/§14). The reverse
// of PackageExportBlock: paste an export manifest, submit a durable 202 import job and
// watch the report. A `succeeded` import produces a DRAFT root in the catalog above; a
// `blocked` import produces a FAILED-validation DRAFT root (never executable) whose
// diagnostics list the unresolved dependencies; a `failed` manifest produces no package.
// The manifest is parsed client-side — invalid JSON never reaches the server.
function ImportCard() {
  const [manifestText, setManifestText] = useState("");
  const [parseError, setParseError] = useState<string | null>(null);
  const [importJobId, setImportJobId] = useState<string | null>(null);
  const submit = useSubmitPackageImport();
  const report = usePackageImportReport(importJobId);
  const recent = usePackageImports();

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    setParseError(null);
    let parsed: unknown;
    try {
      parsed = JSON.parse(manifestText);
    } catch {
      setParseError("The manifest is not valid JSON.");
      return;
    }
    if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
      setParseError("The manifest must be a JSON object.");
      return;
    }
    submit.mutate(parsed as Record<string, unknown>, {
      onSuccess: (result) => setImportJobId(result.import_job_id),
    });
  };

  return (
    <section className="card" aria-labelledby="library-import-h" style={{ marginTop: 16 }}>
      <h2 id="library-import-h" className="card-title">
        Import package
      </h2>
      <p className="page-sub">
        Paste an export manifest (from “Export manifest” above). A durable job re-resolves
        its dependencies against this deployment’s registry and creates a private DRAFT — an
        unresolved dependency blocks it as non-executable, never silently runnable.
      </p>
      {/* R2-08 (GAP item 9): the manifest is a machine-generated export artifact
          — its schema is the export format, not a product form, so the paste
          surface lives under an explicitly named Advanced disclosure. */}
      <details>
        <summary>Advanced — import from manifest JSON</summary>
        <form onSubmit={onSubmit} style={{ marginTop: 8 }}>
          <textarea
            aria-label="Export manifest JSON"
            value={manifestText}
            onChange={(e) => setManifestText(e.target.value)}
            rows={8}
            placeholder='{"package_kind": "indicator", "input_contract": {…}, …}'
            style={{ width: "100%", fontFamily: "monospace", fontSize: 12 }}
          />
          <div style={{ marginTop: 8 }}>
            <button
              type="submit"
              className="btn"
              disabled={submit.isPending || manifestText.trim() === ""}
            >
              {submit.isPending ? "Submitting…" : "Import manifest"}
            </button>
          </div>
        </form>
      </details>
      {parseError !== null ? (
        <p className="page-sub" role="alert" style={{ color: "var(--down, #b00)" }}>
          {parseError}
        </p>
      ) : null}
      {submit.isError ? <ErrorState error={submit.error} /> : null}

      {importJobId !== null ? (
        <div style={{ marginTop: 12 }}>
          <h5 style={{ marginBottom: 4 }}>Import report</h5>
          {report.isLoading ? <Loading /> : null}
          {report.data ? <ImportReportView report={report.data} /> : null}
        </div>
      ) : null}

      <div style={{ marginTop: 16 }}>
        <h5 style={{ marginBottom: 4 }}>Recent imports</h5>
        {recent.isLoading ? <Loading /> : null}
        {recent.data && recent.data.items.length === 0 ? (
          <EmptyState title="No imports yet." />
        ) : null}
        {recent.data?.items.map((item) => (
          <button
            key={item.import_job_id}
            type="button"
            className="btn-ghost"
            onClick={() => setImportJobId(item.import_job_id)}
            style={{ display: "flex", gap: 8, alignItems: "center", width: "100%" }}
          >
            <StatusBadge tone={packageImportTone(item.status)} label={item.status} />
            <code>{item.import_job_id}</code>
            <span className="page-sub">{item.package_kind}</span>
          </button>
        ))}
      </div>
    </section>
  );
}

function ImportReportView({ report }: { report: PackageImportReport }) {
  const navigate = useNavigate();
  return (
    <div>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <StatusBadge tone={packageImportTone(report.status)} label={report.status} />
        <code>{report.import_job_id}</code>
      </div>
      {report.status === "succeeded" && report.result_package_root_id ? (
        <p className="page-sub" style={{ marginTop: 4 }}>
          Imported as a private DRAFT.{" "}
          <button
            type="button"
            className="link-btn"
            onClick={() => navigate(`/packages/library?package=${report.result_package_root_id}`)}
          >
            View in catalog
          </button>
        </p>
      ) : null}
      {report.status === "blocked" ? (
        <p className="page-sub" style={{ marginTop: 4 }}>
          Blocked: the DRAFT was created but is not executable — resolve its dependencies
          first.
        </p>
      ) : null}
      {report.status === "failed" ? (
        <p className="page-sub" style={{ marginTop: 4 }}>
          Failed: the manifest could not be parsed into a package. No package was created.
        </p>
      ) : null}
      {report.diagnostics ? (
        <pre style={contractStyle}>{JSON.stringify(report.diagnostics, null, 2)}</pre>
      ) : null}
    </div>
  );
}
