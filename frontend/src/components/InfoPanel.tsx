import type { InfoPanelContent } from "@/lib/strategyForm";

// GAP-08 — the ⓘ Information Content disclosure (doc 02 §6). A native
// <details>/<summary> so it is keyboard-focusable and toggles with
// Enter/Space out of the box (no ARIA hand-rolling). The body is rendered
// pre-wrapped so the spec's paragraph/bullet structure survives verbatim. The
// panel is help-only: it never writes a form value or bypasses validation
// (doc 02 §6 CONTENT RULE).
export function InfoPanel({ panel }: { panel: InfoPanelContent }) {
  return (
    <details className="info-panel">
      <summary aria-label={`Information: ${panel.title}`} title={`Information: ${panel.title}`}>
        ⓘ
      </summary>
      <div className="info-panel-body" role="note">
        <strong>{panel.title}</strong>
        <p>{panel.body}</p>
      </div>
    </details>
  );
}
