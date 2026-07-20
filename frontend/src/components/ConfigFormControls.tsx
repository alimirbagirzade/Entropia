// Shared typed-config form controls (R2-04). Small presentational helpers the
// Trading Signal / Trade Log twin editors compose into their config grids —
// enum → select, free text/number → input, with the field-level error rendered
// next to the control (GAP item 9: schema/domain validation beside the field,
// not a JSON parse banner). Purely visual; payload production and validation
// live in lib/tradingSignalForm.ts + lib/tradeLogForm.ts.

import type { ReactNode } from "react";

export function FieldError({ error }: { error: string | undefined }) {
  if (!error) return null;
  return (
    <small role="alert" style={{ color: "var(--down)" }}>
      {error}
    </small>
  );
}

export function TextField({
  label,
  value,
  error,
  onChange,
  placeholder,
  disabled,
  wide,
  hint,
}: {
  label: string;
  value: string;
  error?: string;
  onChange: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  wide?: boolean;
  hint?: ReactNode;
}) {
  return (
    <label className={wide ? "cp-field cp-wide" : "cp-field"}>
      <span>{label}</span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        disabled={disabled}
      />
      {hint ? <small className="cp-note">{hint}</small> : null}
      <FieldError error={error} />
    </label>
  );
}

// Enum select — options are the backend enum tokens verbatim (option VALUES
// never change; only the visible label is humanized).
export function SelectField({
  label,
  value,
  options,
  error,
  onChange,
  disabled,
  hint,
}: {
  label: string;
  value: string;
  options: ReadonlyArray<string>;
  error?: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  hint?: ReactNode;
}) {
  return (
    <label className="cp-field">
      <span>{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {humanizeToken(option)}
          </option>
        ))}
      </select>
      {hint ? <small className="cp-note">{hint}</small> : null}
      <FieldError error={error} />
    </label>
  );
}

// "signal_events_only" → "Signal events only" (display only — the submitted
// option value stays the canonical enum token).
function humanizeToken(token: string): string {
  const spaced = token.replaceAll("_", " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

// Read-only provenance line for system-carried identifiers (GAP item 3 fix #3:
// a normal user never types or edits a source asset / revision id).
export function ProvenanceRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="cp-field">
      <span>{label}</span>
      <div>
        {value !== "" ? <code>{value}</code> : <small className="cp-note">pending import</small>}
      </div>
    </div>
  );
}
