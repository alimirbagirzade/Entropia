import { EmptyState } from "@/components/EmptyState";
import type { NavItem } from "@/app/nav";

// Stage 0 renders every domain screen as an explicit, stage-tagged placeholder.
// This is the navigation skeleton; the real page lands in its build stage.
export function Placeholder({ item }: { item: NavItem }) {
  return (
    <>
      <h1 className="page-title">{item.label}</h1>
      <p className="page-sub">Entropia V18 · Production V1</p>
      <div className="card">
        <EmptyState
          glyph="🧭"
          title={`Planned for Stage ${item.stage}`}
          description={
            <>
              This screen’s domain behavior is delivered in build <strong>Stage {item.stage}</strong>.
              The shell, routing, and layout are in place; the page contract will be implemented
              against the canonical Master Technical Reference and its page documentation.
            </>
          }
        />
      </div>
    </>
  );
}
