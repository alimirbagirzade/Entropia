import {
  type CapabilityOption,
  capabilityOption,
  isFutureDev,
} from "@/lib/engineCapabilityMatrix.generated";

// F-05 / #539 / #533 — the ONE rule both strategy forms use to disclose engine capabilities.
//
// The generated matrix says WHICH option values this build never executes. It does not say
// whether the engine even READS the field right now, and that second question is what the
// backend capability readers actually answer:
//
//   * `_read_filter_types`     (capabilities.py:633-635) — a filter with `enabled=false` is
//                                inert, so its category is never reported.
//   * `_read_opposite_hedge`   (capabilities.py:638-645) — `allow_hedge` with
//                                `exit_on_opposite_signal` ON closes the position before the
//                                hedge branch is reachable, so it is inert and does NOT block.
//
// Deciding from the value ALONE is exactly the #533 defect (the form claimed Ready Check
// blocks the shipped default when it does not). Deciding nothing at all is the #539 defect
// (15 of 22 future_dev rows rendered as ordinary options). So a caller supplies the
// reachability of the field, and this module owns the resulting presentation.

export type CapabilityNote =
  | { kind: "none" }
  /** The CURRENT value is future_dev and genuinely blocked — Ready Check refuses the run. */
  | { kind: "saved_blocked"; option: CapabilityOption }
  /** The current value is future_dev but INERT here: it executes nothing and blocks nothing. */
  | { kind: "saved_inert"; option: CapabilityOption; reason: string }
  /** Other options are blocked; the current value is fine. */
  | { kind: "options_blocked"; options: readonly CapabilityOption[] };

export interface CapabilityDisclosure {
  /** Values to render `disabled`. NEVER contains the current value. */
  blockedValues: ReadonlySet<string>;
  note: CapabilityNote;
}

const NOTHING: CapabilityDisclosure = { blockedValues: new Set(), note: { kind: "none" } };

export function capabilityDisclosure({
  fieldPath,
  value,
  optionValues,
  reachable = true,
  inertReason,
}: {
  /** Dotted saved-config path; empty/undefined = this select is not an enumerated field. */
  fieldPath?: string;
  /** The currently selected value. */
  value: string;
  /** Every value the select renders. */
  optionValues: readonly string[];
  /**
   * Whether the engine consults this field at all right now (`scaling.enabled`,
   * `filter.enabled`). `false` mirrors a backend reader that skips the field entirely:
   * no disable and no note, because nothing here can block or fail.
   */
  reachable?: boolean;
  /**
   * Set when the field IS consulted but its `future_dev` values are inert under a sibling
   * setting (hedge + `exit_on_opposite_signal` ON). Nothing is disabled — selecting the
   * value would not block — and a saved value is explained rather than accused.
   */
  inertReason?: string;
}): CapabilityDisclosure {
  if (fieldPath === undefined || fieldPath === "" || !reachable) return NOTHING;

  const selected = isFutureDev(fieldPath, value) ? capabilityOption(fieldPath, value) : undefined;

  if (inertReason !== undefined && inertReason !== "") {
    // Inert cuts BOTH ways: a non-current future_dev option would not block either, so
    // disabling it would be the same false claim #533 was filed for.
    return selected
      ? { blockedValues: new Set(), note: { kind: "saved_inert", option: selected, reason: inertReason } }
      : NOTHING;
  }

  const blockedValues = new Set(
    optionValues.filter((option) => option !== value && isFutureDev(fieldPath, option)),
  );

  if (selected) return { blockedValues, note: { kind: "saved_blocked", option: selected } };

  const options = [...blockedValues]
    .map((blocked) => capabilityOption(fieldPath, blocked))
    .filter((entry): entry is CapabilityOption => entry !== undefined);

  return {
    blockedValues,
    note: options.length > 0 ? { kind: "options_blocked", options } : { kind: "none" },
  };
}

/** The label suffix a blocked option carries inside the select. */
export function capabilityOptionLabel(label: string, blocked: boolean): string {
  return blocked ? `${label} — not available in this build` : label;
}
