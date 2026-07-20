import { useFamilies } from "@/lib/rationale";

import { FieldError } from "@/components/ConfigFormControls";

// R2-08 (GAP item 7) — a Rationale Family is chosen by its display name from
// the active registry (doc 10 §3), never typed as a raw family id. The
// immutable entity_id travels system-side and surfaces only as a read-only
// provenance line under the select. A stored id that is missing from the
// first registry page (or points at a deleted family) is kept selectable
// verbatim so an existing value is never silently dropped.

export function RationaleFamilyPicker({
  label,
  value,
  onChange,
  disabled = false,
  error,
}: {
  label: string;
  value: string;
  onChange: (familyId: string) => void;
  disabled?: boolean;
  error?: string;
}) {
  const families = useFamilies("active", null);
  const rows = families.data?.data ?? [];
  const known = rows.some((row) => row.entity_id === value);

  return (
    <label className="cp-field">
      <span>{label}</span>
      <select
        value={value}
        disabled={disabled || families.isLoading}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">(none)</option>
        {value !== "" && !known ? <option value={value}>{value} (not in registry)</option> : null}
        {rows.map((row) => (
          <option key={row.entity_id} value={row.entity_id}>
            {row.display_name}
          </option>
        ))}
      </select>
      {families.isLoading ? <small className="cp-note">Loading families…</small> : null}
      {families.isError ? (
        <small role="alert" style={{ color: "var(--down)" }}>
          Could not load the family registry.
        </small>
      ) : null}
      {value !== "" ? (
        <small className="cp-note">
          Family id (system-carried): <code>{value}</code>
        </small>
      ) : null}
      <FieldError error={error} />
    </label>
  );
}
