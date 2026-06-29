import type { ReactNode } from "react";

interface EmptyStateProps {
  title: string;
  description?: ReactNode;
  glyph?: string;
  action?: ReactNode;
}

export function EmptyState({ title, description, glyph = "◦", action }: EmptyStateProps) {
  return (
    <div className="state">
      <div className="glyph" aria-hidden="true">{glyph}</div>
      <h3>{title}</h3>
      {description ? <p>{description}</p> : null}
      {action}
    </div>
  );
}
