// F-07 §4.4 — the one presentation contract for "a server-labelled identifier".
//
// The finding's acceptance is "No common task requires recognizing an opaque
// identifier", and its prescribed correction is "Add display DTOs at query
// boundaries; never reconstruct names from IDs in the browser. Keep copyable IDs in
// advanced detail for support/audit."
//
// So this component does exactly two things and refuses a third:
//   * given a server-provided `label`, it renders that as the PRIMARY text and keeps
//     the raw id beneath (or beside) as a muted, copyable secondary token;
//   * given no label, it renders the id alone — honestly, as the only thing the
//     server could say about that row;
//   * it NEVER derives a name from the id. A null label stays null.
//
// Mirrors the `ItemLabel` shape Portfolio.tsx introduced in the presentation half of
// this sweep, generalized to the nullable server label the display DTOs now carry.

const ID_STYLE = { fontSize: 12, color: "var(--text-dim)" } as const;

export function LabelledId({
  label,
  id,
  inline = false,
}: {
  label: string | null | undefined;
  id: string;
  inline?: boolean;
}) {
  const hasLabel = label != null && label.trim() !== "";
  // No server label -> the id IS the identification. Rendered as the primary text
  // rather than as a muted subtitle under an invented name.
  if (!hasLabel) {
    return <code>{id}</code>;
  }
  const idCode = <code style={ID_STYLE}>{id}</code>;
  if (inline) {
    return (
      <span>
        {label} {idCode}
      </span>
    );
  }
  return (
    <div>
      <div>{label}</div>
      {idCode}
    </div>
  );
}
