import { useState, type FormEvent } from "react";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { StatusBadge } from "@/components/StatusBadge";
import { ApiError } from "@/lib/apiClient";
import { formatUtc } from "@/lib/backtest";
import {
  assignmentStateTone,
  useAssignments,
  useBatchAssign,
  useCreateFamily,
  useFamilies,
  useReviseFamily,
  useSoftDeleteFamily,
  type AssignmentChangeInput,
  type RationaleAssignmentRow,
  type RationaleFamilyCard,
} from "@/lib/rationale";

// Command failures surface the backend canonical envelope verbatim — the client
// never invents rationale-domain messages (mirrors Trash / Panel / AnalysisLab).
function mutationErrorText(error: unknown): string {
  if (error instanceof ApiError) return `${error.code}: ${error.message}`;
  return error instanceof Error ? error.message : "Request failed.";
}

// Forward-only opaque keyset cursors (server contract): Prev replays the cursor
// stack, the client never re-orders or fabricates a page.
function useCursorStack() {
  const [stack, setStack] = useState<string[]>([]);
  const cursor = stack.length > 0 ? (stack[stack.length - 1] ?? null) : null;
  return {
    cursor,
    canPrev: stack.length > 0,
    next: (nextCursor: string) => setStack((prev) => [...prev, nextCursor]),
    prev: () => setStack((prev) => prev.slice(0, -1)),
    reset: () => setStack([]),
  };
}

// A textarea list edits one entry per line; the backend clean_metadata_list trims
// and de-dupes, so blank lines here are harmless but stripped for a tidy payload.
function linesToList(value: string): string[] {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
}

// Rationale Families (doc 10 §7 · UI-10): the shared taxonomy plane rendered as a
// two-column workspace — LEFT the pastel Family cards (create / rename+enrich /
// soft-delete via a compact Add row that expands into an inline editor), RIGHT the
// Package Rationale Assignment table (staged batch reclassify). Selecting a family
// card focuses the assignment column on that family (presentation only). Shared-
// editing: any signed-in member may edit both (Admin-only is NOT used here); a Guest
// sees the 401 envelope verbatim (UI visibility is never authorization, doc 10 §2).
export function RationaleFamilies() {
  // The selected card is presentation-only context for the assignment column; it
  // never gates a mutation (the per-row select remains the source of truth).
  const [selected, setSelected] = useState<RationaleFamilyCard | null>(null);

  return (
    <>
      <h1 className="page-title">Rationale Families</h1>
      <div className="package-pool-intro">
        Rationale Families are a shared-editing workspace used by Create Package, Package Library and
        strategy workflows. Any signed-in member — Admin, Supervisor, User or Agent — may add, edit,
        remove, save and use every Family card and every Package Rationale Assignment, including cards
        created by other actors. Renames create a new immutable revision (history is never rewritten).
      </div>
      <div className="rationale-panel">
        <FamilyListColumn
          selectedId={selected?.entity_id ?? null}
          onSelect={(family) =>
            setSelected((prev) => (prev?.entity_id === family.entity_id ? null : family))
          }
          onDeleted={(entityId) =>
            setSelected((prev) => (prev?.entity_id === entityId ? null : prev))
          }
        />
        <AssignmentColumn selected={selected} onClearSelection={() => setSelected(null)} />
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Left column — pastel Family list: compact Add row + create/revise/soft-delete
// ---------------------------------------------------------------------------

function FamilyListColumn({
  selectedId,
  onSelect,
  onDeleted,
}: {
  selectedId: string | null;
  onSelect: (family: RationaleFamilyCard) => void;
  onDeleted: (entityId: string) => void;
}) {
  const pager = useCursorStack();
  const families = useFamilies("active", pager.cursor);
  const create = useCreateFamily();
  const revise = useReviseFamily();
  const del = useSoftDeleteFamily();
  // The permanently-open large form is replaced by a compact Add row: it stays
  // collapsed until "New family" opens the inline editor (composing), and each
  // card's Edit opens the same editor seeded from that card (editing).
  const [composing, setComposing] = useState(false);
  const [editing, setEditing] = useState<RationaleFamilyCard | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  const editorOpen = composing || editing !== null;

  const closeEditor = () => {
    setComposing(false);
    setEditing(null);
  };

  const onEditorSubmit = (form: {
    display_name: string;
    subfamilies: string[];
    compatible_output_types: string[];
    change_note: string | null;
  }) => {
    if (editing) {
      // OCC token = the family's current head revision (doc 10 §5 Save). The editor
      // stays open after Save (the "Saved —" banner reads the active mutation's data);
      // Cancel collapses back to the compact Add row.
      revise.mutate({
        ...form,
        entity_id: editing.entity_id,
        expected_head_revision_id: editing.current_revision_id,
      });
    } else {
      create.mutate(form);
    }
  };

  const editorPending = editing ? revise.isPending : create.isPending;
  const editorError = editing ? revise.error : create.error;
  const savedName = editing ? revise.data?.display_name : create.data?.display_name;

  return (
    <section className="card" aria-labelledby="rf-registry-h">
      <h3 id="rf-registry-h" className="package-section-title" style={{ marginTop: 0 }}>
        RATIONALE FAMILY LIST
        {families.data ? (
          <span className="page-sub" style={{ marginLeft: 8, textTransform: "none" }}>
            ({families.data.data.length} active on this page)
          </span>
        ) : null}
      </h3>

      <div className="rationale-add-row">
        {editorOpen ? (
          <FamilyEditor
            key={editing?.entity_id ?? "new"}
            editing={editing}
            pending={editorPending}
            onSubmit={onEditorSubmit}
            onCancel={closeEditor}
          />
        ) : (
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => {
              setEditing(null);
              setComposing(true);
            }}
          >
            + New family
          </button>
        )}
      </div>
      {editorError ? (
        <p role="alert" style={{ color: "var(--down)" }}>
          {mutationErrorText(editorError)}
        </p>
      ) : null}
      {savedName ? <p aria-live="polite">Saved — {savedName}.</p> : null}

      {families.isLoading ? (
        <Loading label="Loading families…" />
      ) : families.isError ? (
        <ErrorState error={families.error} onRetry={() => void families.refetch()} />
      ) : families.data ? (
        <>
          {families.data.data.length === 0 ? (
            <EmptyState title="No active rationale families yet — add the first one above" />
          ) : (
            <div className="rationale-grid" role="list" aria-label="Rationale families">
              {families.data.data.map((family) => (
                <FamilyCard
                  key={family.entity_id}
                  family={family}
                  isEditing={editing?.entity_id === family.entity_id}
                  isSelected={selectedId === family.entity_id}
                  confirming={deleteConfirm === family.entity_id}
                  deleting={del.isPending}
                  onSelect={() => onSelect(family)}
                  onEdit={() => {
                    setComposing(false);
                    setEditing(family);
                  }}
                  onAskDelete={() => setDeleteConfirm(family.entity_id)}
                  onCancelDelete={() => setDeleteConfirm(null)}
                  onConfirmDelete={() => {
                    del.mutate(
                      { entity_id: family.entity_id, row_version: family.row_version },
                      {
                        onSuccess: () => {
                          setDeleteConfirm(null);
                          if (editing?.entity_id === family.entity_id) setEditing(null);
                          onDeleted(family.entity_id);
                        },
                      },
                    );
                  }}
                />
              ))}
            </div>
          )}
          <Pager
            canPrev={pager.canPrev}
            nextCursor={families.data.meta.cursor}
            onPrev={pager.prev}
            onNext={pager.next}
          />
        </>
      ) : null}

      {del.isError ? (
        <p role="alert" style={{ color: "var(--down)", marginBottom: 0 }}>
          {mutationErrorText(del.error)}
        </p>
      ) : null}
      {del.data ? (
        <p aria-live="polite">
          Deleted — {del.data.display_name ?? del.data.entity_id} ({del.data.deletion_state}).
        </p>
      ) : null}
    </section>
  );
}

function FamilyEditor({
  editing,
  pending,
  onSubmit,
  onCancel,
}: {
  editing: RationaleFamilyCard | null;
  pending: boolean;
  onSubmit: (form: {
    display_name: string;
    subfamilies: string[];
    compatible_output_types: string[];
    change_note: string | null;
  }) => void;
  onCancel: () => void;
}) {
  const [displayName, setDisplayName] = useState(editing?.display_name ?? "");
  const [subfamilies, setSubfamilies] = useState((editing?.subfamilies ?? []).join("\n"));
  const [compatible, setCompatible] = useState((editing?.compatible_output_types ?? []).join("\n"));
  const [changeNote, setChangeNote] = useState("");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    onSubmit({
      display_name: displayName,
      subfamilies: linesToList(subfamilies),
      compatible_output_types: linesToList(compatible),
      change_note: changeNote.trim() || null,
    });
  };

  return (
    <form onSubmit={submit} className="rationale-editor">
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
        <strong>{editing ? `Edit “${editing.display_name}”` : "New family"}</strong>
      </div>
      <div style={{ display: "grid", gap: 12 }}>
        <label htmlFor="rf-name">
          Display name
          <input
            id="rf-name"
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            placeholder="Momentum"
            required
          />
        </label>
        <label htmlFor="rf-subs">
          Subfamilies (one per line)
          <textarea
            id="rf-subs"
            rows={3}
            value={subfamilies}
            onChange={(event) => setSubfamilies(event.target.value)}
            placeholder={"trend\nbreakout"}
          />
        </label>
        <label htmlFor="rf-outputs">
          Compatible output types (one per line)
          <textarea
            id="rf-outputs"
            rows={3}
            value={compatible}
            onChange={(event) => setCompatible(event.target.value)}
            placeholder={"directional_signal"}
          />
        </label>
        <label htmlFor="rf-note">
          Change note (optional)
          <input
            id="rf-note"
            value={changeNote}
            onChange={(event) => setChangeNote(event.target.value)}
            placeholder="why this change"
          />
        </label>
      </div>
      <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
        <button type="submit" className="btn btn-primary" disabled={pending}>
          {editing ? "Save revision" : "Create family"}
        </button>
        <button type="button" className="btn btn-ghost" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}

function FamilyCard({
  family,
  isEditing,
  isSelected,
  confirming,
  deleting,
  onSelect,
  onEdit,
  onAskDelete,
  onCancelDelete,
  onConfirmDelete,
}: {
  family: RationaleFamilyCard;
  isEditing: boolean;
  isSelected: boolean;
  confirming: boolean;
  deleting: boolean;
  onSelect: () => void;
  onEdit: () => void;
  onAskDelete: () => void;
  onCancelDelete: () => void;
  onConfirmDelete: () => void;
}) {
  // The pastel family color becomes the whole-card wash (mockup V14); text is
  // pinned dark for contrast against the light tint. A missing color falls back to
  // the elevated surface so the theme still reads.
  const pastel = family.display_color;
  const cardStyle = {
    ...(pastel ? { background: pastel, color: "#111", borderColor: "rgba(55,55,55,0.26)" } : {}),
    ...(isSelected
      ? { outline: "2px solid var(--accent)", outlineOffset: 1 }
      : isEditing
        ? { borderColor: "var(--accent)" }
        : {}),
  };
  return (
    <div
      className={`rationale-card${isSelected ? " is-selected" : ""}`}
      role="listitem"
      style={cardStyle}
    >
      <button
        type="button"
        className="rationale-card-title rationale-card-select"
        aria-pressed={isSelected}
        onClick={onSelect}
      >
        {family.display_name}
      </button>
      <div className="rationale-card-row">
        <b>Subfamilies</b>
        <span>{family.subfamilies.length > 0 ? family.subfamilies.join(", ") : "—"}</span>
      </div>
      <div className="rationale-card-row">
        <b>Compatible Output Types</b>
        <span>
          {family.compatible_output_types.length > 0
            ? family.compatible_output_types.join(", ")
            : "—"}
        </span>
      </div>
      <div className="rationale-card-row">
        <b>Revision</b>
        <span>
          v{family.revision_no} (rv {family.row_version})
        </span>
      </div>
      <div className="rationale-card-row">
        <b>Created (UTC)</b>
        <span>{formatUtc(family.created_at)}</span>
      </div>
      <div className="rationale-card-actions">
        <button type="button" className="btn" onClick={onEdit}>
          Edit
        </button>
        {confirming ? (
          <>
            <button type="button" className="btn" disabled={deleting} onClick={onConfirmDelete}>
              Confirm delete
            </button>
            <button type="button" className="btn btn-ghost" onClick={onCancelDelete}>
              Cancel
            </button>
          </>
        ) : (
          <button type="button" className="btn" onClick={onAskDelete}>
            Delete
          </button>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Right column — Package Rationale Assignment: staged batch reclassify
// ---------------------------------------------------------------------------

const UNASSIGNED = "";

function AssignmentColumn({
  selected,
  onClearSelection,
}: {
  selected: RationaleFamilyCard | null;
  onClearSelection: () => void;
}) {
  const pager = useCursorStack();
  const assignments = useAssignments(pager.cursor);
  // The family selector reads the first page of active families (doc 10 §7 scope).
  const families = useFamilies("active", null);
  const batch = useBatchAssign();
  // packageRootId -> selected family id ("" = explicit unassign). Only rows the user
  // touched appear; a Save diffs each against the server's current assignment.
  const [staged, setStaged] = useState<Record<string, string>>({});

  const activeFamilies = families.data?.data ?? [];
  const familyById = new Map(activeFamilies.map((family) => [family.entity_id, family]));

  const currentValue = (row: RationaleAssignmentRow): string =>
    staged[row.package_root_id] ?? row.rationale_family_id ?? UNASSIGNED;

  const isChanged = (row: RationaleAssignmentRow): boolean => {
    const staff = staged[row.package_root_id];
    return staff !== undefined && staff !== (row.rationale_family_id ?? UNASSIGNED);
  };

  const changedRows = (assignments.data?.data ?? []).filter(isChanged);

  const onSelect = (row: RationaleAssignmentRow, value: string) => {
    setStaged((prev) => ({ ...prev, [row.package_root_id]: value }));
  };

  const onSave = () => {
    if (assignments.data === undefined || changedRows.length === 0) return;
    const changes: AssignmentChangeInput[] = changedRows.map((row) => {
      const selectedFamily = currentValue(row);
      const familyId = selectedFamily === UNASSIGNED ? null : selectedFamily;
      return {
        package_root_id: row.package_root_id,
        expected_head_revision_id: row.current_package_revision_id,
        rationale_family_id: familyId,
        expected_family_current_revision_id:
          familyId === null ? null : (familyById.get(familyId)?.current_revision_id ?? null),
      };
    });
    batch.mutate(
      { changes, expected_table_version: assignments.data.meta.table_version },
      { onSuccess: () => setStaged({}) },
    );
  };

  return (
    <section className="card" aria-labelledby="rf-assign-h">
      <h3 id="rf-assign-h" className="package-section-title" style={{ marginTop: 0 }}>
        PACKAGE RATIONALE ASSIGNMENT
        <span className="page-sub" style={{ marginLeft: 8, textTransform: "none" }}>
          (Indicator + Condition packages)
        </span>
      </h3>

      <div className="rationale-assignment-note">
        Select the appropriate shared Rationale Family for each package, then save the assignment
        changes. Every role can edit and save this shared assignment table.
      </div>

      <div className="rationale-context" aria-live="polite">
        {selected ? (
          <>
            <span>
              Context — <b>{selected.display_name}</b>
              {selected.compatible_output_types.length > 0
                ? ` · ${selected.compatible_output_types.join(", ")}`
                : ""}{" "}
              · packages assigned to this family are highlighted below
            </span>
            <button type="button" className="btn btn-ghost" onClick={onClearSelection}>
              Clear
            </button>
          </>
        ) : (
          <span>Select a family card on the left to focus its assigned packages.</span>
        )}
      </div>

      {assignments.isLoading ? (
        <Loading label="Loading assignments…" />
      ) : assignments.isError ? (
        <ErrorState error={assignments.error} onRetry={() => void assignments.refetch()} />
      ) : assignments.data ? (
        <>
          {assignments.data.data.length === 0 ? (
            <EmptyState title="No rationale-assignable packages yet" />
          ) : (
            <table className="metrics-table">
              <thead>
                <tr>
                  <th scope="col">Package</th>
                  <th scope="col">Kind</th>
                  <th scope="col">Current family</th>
                  <th scope="col">State</th>
                  <th scope="col">Reassign to</th>
                </tr>
              </thead>
              <tbody>
                {assignments.data.data.map((row) => (
                  <AssignmentRow
                    key={row.package_root_id}
                    row={row}
                    value={currentValue(row)}
                    changed={isChanged(row)}
                    inContext={selected !== null && row.rationale_family_id === selected.entity_id}
                    families={activeFamilies}
                    onSelect={(value) => onSelect(row, value)}
                  />
                ))}
              </tbody>
            </table>
          )}

          <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 12 }}>
            <button
              type="button"
              className="btn btn-primary"
              disabled={changedRows.length === 0 || batch.isPending}
              onClick={onSave}
            >
              Save Assignment Changes
            </button>
            <span className="page-sub">
              {changedRows.length > 0 ? `${changedRows.length} pending change(s)` : "no pending changes"}
            </span>
            {changedRows.length > 0 ? (
              <button type="button" className="btn btn-ghost" onClick={() => setStaged({})}>
                Reset
              </button>
            ) : null}
          </div>

          <Pager
            canPrev={pager.canPrev}
            nextCursor={assignments.data.meta.cursor}
            onPrev={pager.prev}
            onNext={pager.next}
          />
        </>
      ) : null}

      {batch.isError ? (
        <p role="alert" style={{ color: "var(--down)", marginBottom: 0 }}>
          {mutationErrorText(batch.error)}
        </p>
      ) : null}
      {batch.data ? (
        <div aria-live="polite">
          <p style={{ marginBottom: 4 }}>Saved — {batch.data.count} package revision(s) created.</p>
          {batch.data.warnings.length > 0 ? (
            <ul style={{ marginTop: 0, color: "var(--warn)" }}>
              {batch.data.warnings.map((warning) => (
                <li key={`${warning.package_root_id}:${warning.code}`}>
                  <code>{warning.code}</code> · {warning.message}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function AssignmentRow({
  row,
  value,
  changed,
  inContext,
  families,
  onSelect,
}: {
  row: RationaleAssignmentRow;
  value: string;
  changed: boolean;
  inContext: boolean;
  families: RationaleFamilyCard[];
  onSelect: (value: string) => void;
}) {
  // A row pinned to a soft-deleted family carries a family id absent from the active
  // option set; surface it as a synthetic option so the select never renders a value
  // outside its options (the user can still reassign away from it).
  const hasCurrent = value === UNASSIGNED || families.some((family) => family.entity_id === value);
  // A staged change wins over the selection-context highlight (edited rows always read
  // as pending, mirroring the pre-UI-10 behavior).
  const rowStyle = changed
    ? { background: "var(--bg-elev)" }
    : inContext
      ? { background: "var(--bg-elev-2)" }
      : undefined;
  return (
    <tr style={rowStyle} aria-current={inContext ? "true" : undefined}>
      <td>{row.package_name ?? row.package_root_id}</td>
      <td>
        <code>{row.package_kind}</code>
      </td>
      <td>
        {row.current_family_name ?? "—"}
        {row.assignment_state === "assigned_to_deleted_family" ? " (deleted)" : ""}
      </td>
      <td>
        <StatusBadge tone={assignmentStateTone(row.assignment_state)} label={row.assignment_state} />
      </td>
      <td>
        <select
          aria-label={`Reassign ${row.package_name ?? row.package_root_id}`}
          value={value}
          onChange={(event) => onSelect(event.target.value)}
        >
          <option value={UNASSIGNED}>(unassigned)</option>
          {!hasCurrent ? (
            <option value={value}>{row.current_family_name ?? value} (deleted)</option>
          ) : null}
          {families.map((family) => (
            <option key={family.entity_id} value={family.entity_id}>
              {family.display_name}
            </option>
          ))}
        </select>
      </td>
    </tr>
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
