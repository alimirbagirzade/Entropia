// Shared payload↔form scalar helpers. Extracted because strategyForm.ts and
// strategyGraph.ts carried byte-identical copies of pruneUndefined, decOrOmit
// and enumStr, and two copies drift.
//
// NOT shared on purpose: `str`. Four modules define a function by that name and
// three of them mean DIFFERENT things — strategyForm renders booleans as
// "true"/"false", strategyGraph String()s everything non-nullish, and the
// trade-log / trading-signal forms drop non-strings. Only that last contract
// lives here, as `stringOrEmpty`. Do not "unify" the other two into it: they
// feed ~63 call sites whose rendered value would change.

// Drop undefined-valued keys so an omitted field stays omitted on the wire
// (a required-no-default field then reports "field required" and a defaulted
// field takes its default — the server decides, never the form).
export function pruneUndefined(obj: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(obj)) {
    if (value !== undefined) out[key] = value;
  }
  return out;
}

// A trimmed non-empty decimal string, else undefined (→ key omitted). Decimals
// travel as strings so Pydantic parses them exactly (no float artifact).
export function decOrOmit(value: string): string | undefined {
  const trimmed = value.trim();
  return trimmed === "" ? undefined : trimmed;
}

export function enumStr(value: unknown, fallback: string): string {
  return typeof value === "string" && value !== "" ? value : fallback;
}

// Read a payload scalar that must be a string; anything else reads as absent.
export function stringOrEmpty(value: unknown): string {
  return typeof value === "string" ? value : "";
}
